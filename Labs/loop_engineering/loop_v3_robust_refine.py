# 程式崩潰：這是典型的「未處理正常終止條件」——迴圈達到上限（Terminal State / Max Retries Exceeded）屬於業務邏輯的分支，不應該直接拋出未捕捉的 RuntimeError 導致程式 crash，而應該有優雅的退出機制（Graceful Degradation / Fallback）。
# 
# 12B 模型在第 15 輪 5 個測試全部紅燈：這不是 12B 模型智商不夠，而是觸發了 Loop Engineering 的致命陷阱——「Context 污染與注意力崩塌（Attention Collapse）」。
# 
# 為什麼 12B 會 15 輪全滅？（教學核心洞察）
# 在原本的寫法中，每次失敗就把「錯誤碼 + 完整 Traceback」往 messages 堆疊：
# 
# 跑到第 10 輪時，Context 裡已經塞了 10 份修壞的廢 code + 上萬字失敗日誌。
# 
# 中小型模型（12B 級別）對超長負面樣本的注意力很弱，模型看到滿滿的錯誤範例，直接被「洗腦帶偏」，最後連最初能過的 test_01 都被修壞了。
# 
# 要打造一個強健、不 Crash、能讓 12B 穩定收斂的 Loop，必須導入以下三個機制：
# 
# Context Pruning（上下文修剪與滑動窗口）：
# 嚴禁保留歷史廢 code！每一輪只保留：System Prompt + 原始需求 + 上一輪最新的代碼 + 最新失敗的測試報錯。
# 
# 引導式思考（Scaffold Feedback）：
# 單純丟 Traceback 給 31B 沒問題，但 12B 需要稍微結構化的提示（例如提示它：「注意：test_01 失敗代表你連基本讀寫都改壞了，請先確保基本行為」）。
# 
# 安全終止（Safe Exit）：
# 達到上限時回傳 None 或「修得最好的版本（Best Effort）」，印出總結分析，不噴 Traceback。
# 
# 具備上下文管理與安全退出的修復迴圈 (loop_v3_robust.py)

import io
import re
import unittest
from openai import OpenAI

OPENWEBUI_URL = "http://172.10.0.2:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4:12b"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI


client = OpenAI(
    base_url=OPENWEBUI_URL,
    api_key=OPENWEBUI_API_KEY,
)

# ==========================================================
# 1. 待修復程式碼
# ==========================================================
BUGGY_CODE = '''
import time
from collections import OrderedDict

class TTLCache:
    def __init__(self, capacity: int, default_ttl: float = 60.0):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None
        val, expire_at = self.cache[key]
        if time.time() > expire_at:
            return None
        return val

    def put(self, key, value, ttl: float = None):
        ttl_val = ttl if ttl is not None else self.default_ttl
        expire_at = time.time() + ttl_val

        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = (value, expire_at)
            return

        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)

        self.cache[key] = (value, expire_at)

    def resize(self, new_capacity: int):
        self.capacity = new_capacity

    def size(self) -> int:
        return len(self.cache)
'''

# ==========================================================
# 2. 客觀驗證：5 個單元測試
# ==========================================================
TEST_SUITE_CODE = '''
import unittest
import time

class TestTTLCache(unittest.TestCase):
    def test_01_basic_put_get(self):
        """測試基本的讀寫與未命中情況"""
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("non_existent"))

    def test_02_lru_eviction_order(self):
        """測試 LRU 存取新鮮度置換順序"""
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.get("a"), 1)
        c.put("c", 3)
        self.assertEqual(c.get("a"), 1, "鍵 'a' 剛被讀取過，不應被淘汰！")
        self.assertIsNone(c.get("b"), "鍵 'b' 最久未被存取，應該被淘汰！")
        self.assertEqual(c.get("c"), 3)

    def test_03_ttl_expiration_and_cleanup(self):
        """測試 TTL 到期自動失效與記憶體殘留清理"""
        c = TTLCache(capacity=5, default_ttl=0.1)
        c.put("temp", "expired_val")
        time.sleep(0.15)
        self.assertIsNone(c.get("temp"), "過期項目應回傳 None")
        self.assertEqual(c.size(), 0, "過期資料不應計入 size()")

    def test_04_capacity_resize_shrink(self):
        """測試動態縮容時由舊到新的精確淘汰"""
        c = TTLCache(capacity=4, default_ttl=10.0)
        c.put("k1", 10)
        c.put("k2", 20)
        c.put("k3", 30)
        c.put("k4", 40)
        c.resize(2)
        self.assertEqual(c.size(), 2, "縮容後 size 必須等於新容量")
        self.assertIsNone(c.get("k1"), "k1 應因縮容被淘汰")
        self.assertIsNone(c.get("k2"), "k2 應因縮容被淘汰")
        self.assertEqual(c.get("k3"), 30)
        self.assertEqual(c.get("k4"), 40)

    def test_05_expired_prioritized_over_lru(self):
        """測試容量滿時，應優先淘汰已過期的項目"""
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("short_lived", "data", ttl=0.1)
        c.put("long_lived", "important", ttl=10.0)
        time.sleep(0.15)
        c.put("new_key", "fresh")
        self.assertEqual(c.get("long_lived"), "important", "未過期的 long_lived 必須被保留！")
        self.assertEqual(c.get("new_key"), "fresh")
'''

class DetailedTestResult(unittest.TestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_reports = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.test_reports.append((test._testMethodName, "PASSED", test.shortDescription(), ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.test_reports.append((test._testMethodName, "FAILED", test.shortDescription(), self._exc_info_to_string(err, test)))

    def addError(self, test, err):
        super().addError(test, err)
        self.test_reports.append((test._testMethodName, "ERROR", test.shortDescription(), self._exc_info_to_string(err, test)))

def evaluate_code(candidate_code: str) -> tuple[bool, list, str]:
    namespace = {}
    try:
        exec(candidate_code, namespace)
    except Exception as e:
        return False, [], f"語法編譯錯誤 (Syntax/Import Error): {type(e).__name__}: {str(e)}"

    try:
        exec(TEST_SUITE_CODE, namespace)
    except Exception as e:
        return False, [], f"測試套件注入失敗: {str(e)}"

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(namespace["TestTTLCache"]))

    collector = DetailedTestResult()
    suite.run(collector)
    return collector.wasSuccessful(), collector.test_reports, ""

def print_test_dashboard(test_reports: list):
    print("\n📋【單元測試執行狀態儀表板】")
    for name, status, doc, _ in test_reports:
        mark = "✅ 通過" if status == "PASSED" else "❌ 失敗"
        print(f"  {mark} | {name.ljust(35)} : {doc}")
    print()

# ==========================================================
# 3. 強健的 Loop 控制器（防崩潰 + 上下文修剪）
# ==========================================================
def run_code_repair_loop(max_iterations: int = 15):
    system_prompt = (
        "You are an expert Python Engineer.\n"
        "Your task is to fix the TTLCache class to pass all unit tests.\n"
        "Steps to follow:\n"
        "1. Briefly identify why the tests failed (1-2 sentences).\n"
        "2. Provide the FULL, complete, and runnable TTLCache class enclosed in a single ```python ``` block.\n"
        "Ensure all methods (__init__, get, put, resize, size) are fully implemented without placeholders."
    )

    current_code = BUGGY_CODE
    best_code = None
    max_passed = -1

    for attempt in range(1, max_iterations + 1):
        print(f"{'='*28} [Loop 次數 {attempt}/{max_iterations}] {'='*28}")
        
        # 1. 評測當前代碼
        is_all_passed, test_reports, exec_error = evaluate_code(current_code)

        if not exec_error:
            passed_count = sum(1 for t in test_reports if t[1] == "PASSED")
            print_test_dashboard(test_reports)

            # 記錄最佳版本（Best Effort 保存）
            if passed_count > max_passed:
                max_passed = passed_count
                best_code = current_code

            # 成功終止條件
            if is_all_passed:
                print(f"🎉 [Loop 達到終止條件：第 {attempt} 輪全數綠燈通過！]")
                return current_code
            
            # 整理精簡報錯，不放全部 trace 避免塞爆 12B 上下文
            failed_summary = []
            for t in test_reports:
                if t[1] != "PASSED":
                    # 只抓最後兩行關鍵錯誤
                    key_err = "\n".join(t[3].strip().splitlines()[-2:])
                    failed_summary.append(f"- {t[0]}: {key_err}")
            failure_text = "\n".join(failed_summary)
        else:
            print(f"\n❌ [編譯或語法失敗]: {exec_error}")
            failure_text = f"Syntax/Runtime Error: {exec_error}"

        # 2. 【核心改進：Context Pruning】
        # 永遠只送 2 則訊息：System + 「乾淨的當前代碼與最新失敗診斷」
        # 徹底阻止 12B 模型被歷史垃圾代碼干擾！
        current_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Current implementation:\n\n{current_code}\n\n"
                    f"Failed Tests:\n{failure_text}\n\n"
                    f"Please fix the code above so that ALL tests pass. Output the complete Python code ONLY."
                ),
            },
        ]

        print(f"🤖 呼叫 {MODEL_NAME} 進行第 {attempt} 次重構...")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=current_messages,
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content.strip()
        current_code = re.sub(r"^```(?:python)?\s*|\s*```$", "", raw_output, flags=re.MULTILINE).strip()

    # 3. 【優雅降級：不拋出 RuntimeError】
    print("\n⚠️ [達最大迭代上限 - 進入安全退避機制 (Graceful Fallback)]")
    print(f"📌【教學摘要】：12B 模型在限額內未能全數通關。最高通過數：{max_passed}/5 個測試。")
    print("👉 這證明了：Loop Engineering 必須設置終止邊界與 Fallback，避免無效死循環與服務中斷。")
    return best_code

if __name__ == "__main__":
    repaired_code = run_code_repair_loop()
    if repaired_code:
        print("\n" + "="*20 + " 最終成果（包含最佳修復版本） " + "="*20)
        print(repaired_code)