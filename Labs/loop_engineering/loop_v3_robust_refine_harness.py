# 核心升級（Harness Engineering）：
# 解除 No-Think 窒息限制（Scratchpad 思考緩衝區）：允許 12B 模型先寫 1~2 句分析思路（利用 output tokens 進行邏輯排查），最後才用 python ...  區塊輸出完整代碼。
# 
# 多 Code Block 防禦性抽取：使用正規表達式抓取模型回覆中的最後一段有效 Python 程式碼，杜絕前綴廢話或未閉合代碼導致的語法崩潰。
# 
# 區分編譯崩潰 vs. 邏輯失敗：
# 
# 若模型代碼有 SyntaxError 或遺漏方法，儀表板會直接印出「💥 語法/結構嚴重崩潰」以及詳細的 Exception，不再假裝跑單元測試。
# 
# 若編譯成功，才印出逐項單元測試的 ✅ / ❌。
# 
# 健全的 Context 修剪與安全退出：維持滑動窗口，確保 12B 不被歷史廢 code 污染；10 輪未過時優雅輸出最佳版本，絕不拋出 RuntimeError 造成 Python crash。

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
# 1. 待修復程式：經典瑕疵版 TTLCache
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
# 2. 客觀驗證：5 個涵蓋邊界的嚴格單元測試
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
        return False, [], f"語法或執行期錯誤 (Syntax/Runtime Error): {type(e).__name__}: {str(e)}"

    if "TTLCache" not in namespace:
        return False, [], "代碼中未找到 'TTLCache' 類別定義，可能產生殘缺代碼！"

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

def extract_python_code(llm_output: str) -> str:
    """
    穩健提取代碼：
    優先抓取被 ```python ... ``` 包裹的最後一個完整代碼區塊
    避免中小型模型在前置寫分析時干擾 Python exec
    """
    matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", llm_output, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return llm_output.strip()

# ==========================================================
# 3. 升級版 Loop Engineering 控制核心
# ==========================================================
def run_code_repair_loop(max_iterations: int = 15):
    # Harness Prompt：允許 Scratchpad 分析，降低中小模型認知過載
    system_prompt = (
        "You are an expert Systems and Data Structures Engineer.\n"
        "Your task is to fix a TTLCache class (OrderedDict-based) so that ALL unit tests pass.\n\n"
        "Key Architectural Requirements:\n"
        "1. LRU Freshness: When get(key) succeeds, move the key to the end (most recent).\n"
        "2. TTL Expiration: If an item is expired, delete it immediately from cache and return None.\n"
        "3. Eviction Strategy: When cache is full in put(), first look for and purge expired items. If none are expired, purge the oldest item.\n"
        "4. Dynamic Resize: In resize(new_capacity), if current valid items exceed new_capacity, evict excess oldest items.\n"
        "5. Size Accuracy: size() must only count non-expired items (cleaning up expired ones if needed).\n\n"
        "Response Format:\n"
        "- First, write 1-2 sentences of diagnostic scratchpad notes.\n"
        "- Then, provide the COMPLETE and RUNNABLE TTLCache class inside a single ```python ``` code block.\n"
        "- Do not use placeholders or ellipsis (...)."
    )

    current_code = BUGGY_CODE
    best_code = None
    max_passed = -1

    # 執行初始 baseline
    print("🚩 [初始評估] 執行原始待修復的 TTLCache 代碼...")
    _, initial_reports, _ = evaluate_code(current_code)
    print_test_dashboard(initial_reports)

    # 提煉初始報錯
    failed_details = "\n".join([f"- {t[0]}: {t[3].strip().splitlines()[-1]}" for t in initial_reports if t[1] != "PASSED"])
    
    # 建立第一輪上下文
    current_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"The baseline TTLCache has bugs:\n\n```python\n{current_code}\n```\n\nFailed Unit Tests:\n{failed_details}\n\nPlease analyze and provide the full corrected implementation."
        }
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"{'='*28} [Loop 次數 {attempt}/{max_iterations}] {'='*28}")
        print(f"🤖 呼叫 {MODEL_NAME} 進行代碼修復...")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=current_messages,
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content.strip()
        
        # 顯示模型的 Scratchpad 思考（選取前 150 字教學觀摩）
        scratchpad_snippet = raw_output.split("```")[0].strip()
        if scratchpad_snippet:
            print(f"💡 [模型診斷思路]: {scratchpad_snippet[:150]}...")

        # 穩健抽取代碼
        candidate_code = extract_python_code(raw_output)

        # 外部客觀評測 (Evaluator)
        is_all_passed, test_reports, exec_error = evaluate_code(candidate_code)

        if exec_error:
            print(f"\n💥 [代碼執行失敗 (Syntax/Import Error)]:\n{exec_error}")
            failure_feedback = f"Your output could not be executed:\n{exec_error}\nPlease fix the Python syntax and return the full class definition."
        else:
            passed_count = sum(1 for t in test_reports if t[1] == "PASSED")
            print_test_dashboard(test_reports)

            if passed_count > max_passed:
                max_passed = passed_count
                best_code = candidate_code

            # 成功終止條件 (Terminal State)
            if is_all_passed:
                print(f"🎉 [達到成功終止條件：第 {attempt} 輪全數單元測試綠燈通關！]")
                print(f"📌【教學總結】：12B 模型在思考緩衝區與測試回饋驅動下，成功修復了複合型狀態機與 LRU 邏輯！")
                return candidate_code

            # 提煉精簡報錯，避免膨脹
            failed_lines = []
            for t in test_reports:
                if t[1] != "PASSED":
                    tail_err = t[3].strip().splitlines()[-1] if t[3] else "Assertion failed"
                    failed_lines.append(f"- {t[0]}: {tail_err}")
            failure_feedback = "Your code still failed these tests:\n" + "\n".join(failed_lines)

        # 上下文滑動窗口修剪 (Context Pruning)
        # 拋棄歷史重構垃圾，只保留最新代碼與反饋
        current_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Your last code submission was:\n\n```python\n{candidate_code}\n```\n\n"
                    f"Test Feedback:\n{failure_feedback}\n\n"
                    f"Please review the requirements, fix the remaining logic errors, and output the complete class inside ```python ```."
                )
            }
        ]

    # 安全退避（Graceful Fallback）
    print("\n⚠️ [達最大迭代上限 - 觸發安全退避 (Graceful Fallback)]")
    print(f"📌【教學總結】：模型在 {max_iterations} 輪內未全數通關。最佳紀錄：{max_passed}/5 個測試。")
    print("👉 工業級防禦原則：系統不拋出異常中斷服務，而是記錄日誌並提供 Best-Effort 版本。")
    return best_code

if __name__ == "__main__":
    final_code = run_code_repair_loop()
    if final_code:
        print("\n" + "="*20 + " 最終成果輸出（最佳版本） " + "="*20)
        print(final_code)