# 要讓 31B 這種大模型「無法一次偷看答案秒殺，必須在測試案例的撞牆中逐步自我修正」，必須具備三個要素：
# 
# 隱蔽的交互狀態機（State Machine / Subtle Edge Cases）：沒有直白註解提示，Bug 是多個方法的交互副作用。
# 
# 多個測試案例的即時記分板（Per-Test Status Dashboard）：每一輪清晰印出每個 Test 是 PASSED 還是 FAILED，教學時一眼就能看出模型「修了 A 卻踩到 B」的拉扯過程。
# 
# 隱晦規格與回歸陷阱（Regression Trap）：修復某個問題很容易破壞另一個測試。
# 
# 全新實務題：高彈性 LRU 快取（含 TTL 過期與動態縮容）
# 這是一個真實軟體工程中極容易寫出暗坑的組件：具備 TTL（過期時間）、淘汰機制與動態容量調整的 LRU Cache。
# 
# 隱藏的 4 個深水區 Bug：
# TTL 惰性檢查順序錯誤：取得已過期的 Key 時，沒有清乾淨記憶體與計數。
# 
# LRU 存取新鮮度斷鏈：get() 成功讀取後，忘記將節點提升到最新（Most Recently Used），導致下一次淘汰了剛被讀取的資料。
# 
# 動態縮容時的級聯淘汰錯誤：當執行 resize(new_capacity) 縮容時，如果現有元素多於新容量，必須精準由冷到熱淘汰，且必須略過已過期元素。
# 
# 型別與回傳合約：找不到或過期時必須回傳 None，但模型容易拋出 KeyError。

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
# 1. 待修復程式：看似簡潔但邏輯多處破綻的 TTLCache
# ==========================================================
BUGGY_CODE = '''
import time
from collections import OrderedDict

class TTLCache:
    def __init__(self, capacity: int, default_ttl: float = 60.0):
        self.capacity = capacity
        self.default_ttl = default_ttl
        # 儲存結構: key -> (value, expire_at)
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None
        
        val, expire_at = self.cache[key]
        
        # 檢查是否過期
        if time.time() > expire_at:
            # 這裡有 Bug: 標記過期但沒有把 key 從 OrderedDict 中刪除乾淨
            return None

        # 這裡有 Bug: 讀取命中後，未更新 LRU 順序（未移到末尾）
        return val

    def put(self, key, value, ttl: float = None):
        ttl_val = ttl if ttl is not None else self.default_ttl
        expire_at = time.time() + ttl_val

        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = (value, expire_at)
            return

        # 容量已滿時的淘汰邏輯 (有 Bug: 未先清理過期資料，直接 popitem(last=False))
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)

        self.cache[key] = (value, expire_at)

    def resize(self, new_capacity: int):
        # 動態調整容量大小
        # 這裡有重大 Bug: 完全沒做任何縮容淘汰處理
        self.capacity = new_capacity

    def size(self) -> int:
        # 回傳目前快取內「有效（未過期）」的資料量
        # 這裡有 Bug: 直接回傳 dict 長度，把過期的也算進去了
        return len(self.cache)
'''

# ==========================================================
# 2. 客觀驗證：5 個涵蓋邊界與時間狀態的嚴苛單元測試
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
        # 存取 'a'，使其成為最常使用的項目
        self.assertEqual(c.get("a"), 1)
        
        # 寫入 'c'，此時容量已滿，應淘汰最少使用的 'b'，保留 'a'
        c.put("c", 3)
        self.assertEqual(c.get("a"), 1, "鍵 'a' 剛被讀取過，不應被淘汰！")
        self.assertIsNone(c.get("b"), "鍵 'b' 最久未被存取，應該被淘汰！")
        self.assertEqual(c.get("c"), 3)

    def test_03_ttl_expiration_and_cleanup(self):
        """測試 TTL 到期自動失效與記憶體殘留清理"""
        c = TTLCache(capacity=5, default_ttl=0.1) # 100ms
        c.put("temp", "expired_val")
        time.sleep(0.15)
        
        # 過期後 get 應回傳 None
        self.assertIsNone(c.get("temp"), "過期項目應回傳 None")
        # size() 應該只回報有效數量，且內部記憶體不能保留過期資料
        self.assertEqual(c.size(), 0, "過期資料不應計入 size()")

    def test_04_capacity_resize_shrink(self):
        """測試動態縮容時由舊到新的精確淘汰"""
        c = TTLCache(capacity=4, default_ttl=10.0)
        c.put("k1", 10)
        c.put("k2", 20)
        c.put("k3", 30)
        c.put("k4", 40)
        
        # 將容量由 4 縮減至 2，應由舊至新淘汰 k1, k2，保留 k3, k4
        c.resize(2)
        self.assertEqual(c.size(), 2, "縮容後 size 必須等於新容量")
        self.assertIsNone(c.get("k1"), "k1 應因縮容被淘汰")
        self.assertIsNone(c.get("k2"), "k2 應因縮容被淘汰")
        self.assertEqual(c.get("k3"), 30)
        self.assertEqual(c.get("k4"), 40)

    def test_05_expired_prioritized_over_lru(self):
        """測試容量滿時，應優先淘汰已過期的項目，而非直接擠掉有效的 LRU 項目"""
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("short_lived", "data", ttl=0.1)
        c.put("long_lived", "important", ttl=10.0)
        
        time.sleep(0.15) # 讓 short_lived 過期
        # 此時放入新元素，即使容量是 2，也不應該淘汰未過期的 long_lived
        c.put("new_key", "fresh")
        
        self.assertEqual(c.get("long_lived"), "important", "未過期的 long_lived 必須被保留！")
        self.assertEqual(c.get("new_key"), "fresh")
'''

# ==========================================================
# 3. 測試細節收集器（為每個 Test 產生個別狀態）
# ==========================================================
class DetailedTestResult(unittest.TestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_reports = []  # (test_name, status, doc, err_msg)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.test_reports.append((test._testMethodName, "PASSED", test.shortDescription(), ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        msg = self._exc_info_to_string(err, test)
        self.test_reports.append((test._testMethodName, "FAILED", test.shortDescription(), msg))

    def addError(self, test, err):
        super().addError(test, err)
        msg = self._exc_info_to_string(err, test)
        self.test_reports.append((test._testMethodName, "ERROR", test.shortDescription(), msg))

def evaluate_code(candidate_code: str) -> tuple[bool, list, str]:
    """執行測試並回傳：(是否全過, 每個測試的詳細狀態清單, 原始日誌)"""
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

    result_collector = DetailedTestResult()
    suite.run(result_collector)

    is_all_passed = result_collector.wasSuccessful()
    return is_all_passed, result_collector.test_reports, ""

# ==========================================================
# 4. 繁體中文教學解析器
# ==========================================================
def print_test_dashboard(test_reports: list):
    """印出每個測試案例的執行看板"""
    print("\n📋【單元測試執行狀態儀表板】")
    for name, status, doc, _ in test_reports:
        mark = "✅ 通過" if status == "PASSED" else "❌ 失敗"
        print(f"  {mark} | {name.ljust(35)} : {doc}")
    print()

def generate_teaching_analysis(test_reports: list) -> str:
    """分析測試失敗原因，轉換為課堂教學口白"""
    failed_tests = [t for t in test_reports if t[1] in ("FAILED", "ERROR")]
    if not failed_tests:
        return "所有測試案例全數通過。"

    lines = ["【本輪問題診斷】"]
    for name, status, _, err in failed_tests:
        if "test_02_lru" in name:
            lines.append("  • LRU 淘汰錯置：`get()` 成功讀取時，未呼叫 `move_to_end()` 更新活躍度，導致剛被讀取的鍵慘遭淘汰。")
        elif "test_03_ttl" in name:
            lines.append("  • 記憶體未釋放：偵測到過期時僅回傳了 None，字典內仍堆積著殭屍鍵，造成 `size()` 計算失準。")
        elif "test_04_capacity_resize" in name:
            lines.append("  • 縮容未觸發淘汰：`resize()` 改變容量後，未主動將超出上限的多餘舊元素清除。")
        elif "test_05_expired_prioritized" in name:
            lines.append("  • 優先級邏輯缺陷：容量滿時直接粗暴剔除 LRU 首項，未先巡檢並清除已過期的無效項目。")
        else:
            lines.append(f"  • {name} 斷言未達預期。")
    return "\n".join(lines)

# ==========================================================
# 5. 核心修復迴圈
# ==========================================================
def run_code_repair_loop(max_iterations: int = 15):
    system_prompt = (
        "You are an expert Systems and Data Structures Engineer.\n"
        "Your task is to fix all logical and memory bugs in a TTLCache class (OrderedDict-based).\n"
        "Requirements:\n"
        "1. Strictly maintain standard TTLCache signatures: __init__, get, put, resize, size.\n"
        "2. Ensure O(1) or O(N) bounded performance, correct TTL lazy/active eviction, and strict LRU order.\n"
        "3. Output ONLY the raw Python code. No markdown code blocks, no backticks, no explanations."
    )

    current_code = BUGGY_CODE

    print("🚩 [初始評估] 執行原始有瑕疵的 TTLCache 代碼...")
    _, initial_reports, err = evaluate_code(current_code)
    if initial_reports:
        print_test_dashboard(initial_reports)
    else:
        print(f"初始執行嚴重報錯: {err}")

    # 組裝第一輪 prompt
    feedback_failures = "\n\n".join([f"[{t[0]}] Failed:\n{t[3]}" for t in initial_reports if t[1] != "PASSED"])
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"The following TTLCache implementation has multiple bugs:\n\n{current_code}\n\nIt failed these tests:\n{feedback_failures}\n\nPlease fix the implementation and output the complete corrected Python code."}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"{'='*30} [Loop 次數 {attempt}/{max_iterations}] {'='*30}")
        print(f"🤖 呼叫 {MODEL_NAME} 進行程式碼重構修復...")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content.strip()
        cleaned_code = re.sub(r"^```(?:python)?\s*|\s*```$", "", raw_output, flags=re.MULTILINE).strip()

        # 執行評測
        is_all_passed, test_reports, exec_error = evaluate_code(cleaned_code)

        if exec_error:
            print(f"\n❌ [編譯或語法失敗]: {exec_error}")
            feedback = f"Your code caused an execution error:\n{exec_error}\nPlease return strictly executable Python code."
        else:
            # 印出當前每一個 test case 的綠燈/紅燈狀態
            print_test_dashboard(test_reports)

            if is_all_passed:
                print("🎉 [Loop 達到成功終止條件：全部測試通關！]")
                print(f"📌【教學總結】：歷經 {attempt} 輪迭代反饋，所有邊界、LRU 順序、過期優先權與縮容邏輯全部修復達成！")
                return cleaned_code

            # 未全過：印出教學講解白話文
            print("-" * 65)
            print(generate_teaching_analysis(test_reports))
            print("-" * 65)

            # 組裝下一輪反饋
            failed_details = "\n\n".join([f"Test '{t[0]}' failed with details:\n{t[3]}" for t in test_reports if t[1] != "PASSED"])
            feedback = (
                f"Your code still failed some unit tests.\n\n"
                f"{failed_details}\n\n"
                f"Analyze the failures carefully. Ensure `resize()`, `get()`, `put()`, and `size()` all correctly handle TTL cleanup and LRU ordering. Return ONLY the complete Python code."
            )

        messages.append({"role": "assistant", "content": raw_output})
        messages.append({"role": "user", "content": feedback})

    raise RuntimeError(f"Loop 終止：在 {max_iterations} 輪迭代內未能解決所有 Bug。")

if __name__ == "__main__":
    final_code = run_code_repair_loop()
    print("\n" + "="*20 + " 最終通過所有測試之代碼 " + "="*20)
    print(final_code)
	