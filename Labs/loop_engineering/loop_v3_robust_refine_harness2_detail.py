# Loop Engineering 中的「規格鎖定」
# 在軟體工程 Agent 中，有一個黃金法則：
# 
# 「永遠不要讓中小型模型去決定函數的簽章（Signature）。」
# 
# 模型負責填寫演算法邏輯，而類別骨架與函數介面必須由 Harness 固定住。同時，禁止它在代碼裡浪費 token 去寫又臭又長的 Docstring，避免觸發 Token 截斷。
#
# ---
# 講述 Loop Engineering（迴圈工程） 的經典教材。
# 
# 測試案例的目的說明（讓台下知道每個 test 在抓什麼）。
# 
# 語法/結構問題的底層原因解構（解釋為什麼會噴「找不到 TTLCache」或「截斷」）。
# 
# 單元測試失敗時的直白繁中診斷（說明這輪 AI 哪裡想錯了、踩到什麼狀態陷阱）。
# 
# 當前回饋狀態說明（說明系統如何把客觀事實封裝成下一輪的 prompt）。
#

import io
import re
import unittest
from openai import OpenAI

OPENWEBUI_URL = "http://172.10.0.2:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4:12b"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI

client = OpenAI(base_url=OPENWEBUI_URL, api_key=OPENWEBUI_API_KEY)

# ==========================================
# 1. 待修復程式碼（保持原樣，不做任何修改）
# ==========================================
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
            # 缺陷 1: 標記過期但忘記從 cache 中刪除
            return None
        # 缺陷 2: 忘記更新 LRU 活躍狀態 (move_to_end)
        return val

    def put(self, key, value, ttl: float = None):
        ttl_val = ttl if ttl is not None else self.default_ttl
        expire_at = time.time() + ttl_val

        if key in self.cache:
            self.cache[key] = (value, expire_at)
            self.cache.move_to_end(key)
            return

        # 缺陷 3: 滿載時直接彈出最舊的，沒有優先巡檢查殺已過期的項目
        if len(self.cache) >= self.capacity:
            self.cache.popitem(last=False)

        self.cache[key] = (value, expire_at)

    def resize(self, new_capacity: int):
        # 缺陷 4: 縮容時完全沒有剔除多餘資料
        self.capacity = new_capacity

    def size(self) -> int:
        # 缺陷 5: 直接算 len，把已經過期但還沒被 get 碰過的項目也算進去
        return len(self.cache)
'''

# ==========================================
# 2. 單元測試（保持原樣，不做任何更動）
# ==========================================
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

    def test_02_lru_hit_ordering(self):
        """讀取命中必須刷新 LRU 權重 (move_to_end)"""
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")  # a 被存取，變成最新；b 變成最舊
        c.put("c", 3) # 滿載淘汰最舊的 b
        self.assertEqual(c.get("a"), 1, "鍵 'a' 剛被讀過，不應被淘汰！")
        self.assertIsNone(c.get("b"), "鍵 'b' 最久未被存取，應該被淘汰！")

    def test_03_size_without_get(self):
        """不透過 get()，直接檢查 size() 是否能主動剔除過期項目"""
        c = TTLCache(capacity=3, default_ttl=0.1)
        c.put("exp1", 10)
        c.put("exp2", 20)
        time.sleep(0.15)
        self.assertEqual(c.size(), 0, "size() 必須能辨識並過濾過期項目，不能只回傳 len(cache)")

    def test_04_expired_priority_strict(self):
        """容量滿時，必須優先淘汰已過期項目，而非最舊的未過期項目"""
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("k1_long", "data1", ttl=10.0)
        c.put("k2_short", "data2", ttl=0.05)
        time.sleep(0.1)
        c.put("k3_new", "data3")
        self.assertEqual(c.get("k1_long"), "data1", "k1 還未過期且不該被淘汰！應優先剔除過期的 k2")
        self.assertIsNone(c.get("k2_short"), "k2 已過期，應被優先清理掉")

    def test_05_resize_eviction(self):
        """動態縮容必須即時剔除超額舊資料"""
        c = TTLCache(capacity=4, default_ttl=10.0)
        c.put("a", 1); c.put("b", 2); c.put("c", 3); c.put("d", 4)
        c.resize(2)
        self.assertEqual(c.size(), 2, "縮容至 2 後，有效元素量必須為 2")
        self.assertIsNone(c.get("a"), "最舊的 a 應在縮容時被剔除")
        self.assertIsNone(c.get("b"), "次舊的 b 應在縮容時被剔除")
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

def evaluate_code(candidate_code: str):
    namespace = {}
    try:
        exec(candidate_code, namespace)
    except Exception as e:
        return False, [], f"語法編譯失敗: {type(e).__name__}: {str(e)}"

    if "TTLCache" not in namespace:
        return False, [], "代碼中找不到 TTLCache 類別！"

    try:
        exec(TEST_SUITE_CODE, namespace)
    except Exception as e:
        return False, [], f"測試注入失敗: {str(e)}"

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(namespace["TestTTLCache"]))

    collector = DetailedTestResult()
    suite.run(collector)
    return collector.wasSuccessful(), collector.test_reports, ""

def extract_code(raw: str) -> str:
    matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", raw, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return raw.strip()

# ==========================================
# 3. 教學專用詳細解析器（僅增加解說文字）
# ==========================================
TEST_DESCRIPTIONS = {
    "test_01_basic_put_get": "測試基礎 Key-Value 寫入與讀取能力",
    "test_02_lru_hit_ordering": "驗證讀取命中時，是否透過 move_to_end 刷新活躍度",
    "test_03_size_without_get": "驗證 size() 是否具備過期項目的主動過濾與清理能力",
    "test_04_expired_priority_strict": "驗證容量滿時，是否優先清理已過期項目（而非錯殺有效項目）",
    "test_05_resize_eviction": "驗證縮容時，是否主動剔除超出上限的陳舊資料"
}

def print_detailed_dashboard(reports: list, title: str = "單元測試執行看板"):
    print(f"\n📋【{title}】")
    for name, status, doc, _ in reports:
        desc = TEST_DESCRIPTIONS.get(name, doc or "")
        mark = "✅ 通過" if status == "PASSED" else "❌ 失敗"
        print(f"  {mark} | {name.ljust(33)} : {desc}")

def print_pedagogical_analysis(reports: list):
    """為失敗的測試生成教學分析說明"""
    failed_names = [r[0] for r in reports if r[1] != "PASSED"]
    if not failed_names:
        return

    print("\n🔍【教學診斷分析】")
    if len(failed_names) == 5:
        print("  💡 [全局連鎖失效] 5 個測試全部紅燈！這通常代表模型更動了函數簽章（如改了參數名稱），導致測試套件在呼叫端即觸發異常。")
    else:
        for name in failed_names:
            if name == "test_01_basic_put_get":
                print("  • 基本讀寫失效：模型在重構時破壞了最基礎的 dict 存取結構。")
            elif name == "test_02_lru_hit_ordering":
                print("  • LRU 順序缺陷：`get()` 命中時未正確調用 `move_to_end()`，導致最新存取的項目被誤當作最舊的淘汰。")
            elif name == "test_03_size_without_get":
                print("  • 惰性計算漏洞：`size()` 依然直接回傳 `len(cache)`，未過濾已過期但尚未被讀取的殭屍資料。")
            elif name == "test_04_expired_priority_strict":
                print("  • 淘汰優先級錯誤：滿載時直接彈出首項，未先巡檢並清除已過期的項目，導致健康資料被誤殺。")
            elif name == "test_05_resize_eviction":
                print("  • 縮容處置未落實：`resize()` 僅修改了上限值，未立即觸發迴圈縮減內部字典長度。")
    print("  🔄 [Loop 機制驅動]：評測器已擷取上述客觀失敗原因，正注入上下文迫使模型進行目標修正...")

# ==========================================
# 4. 主迴圈工程（修補邏輯不變，解說加深）
# ==========================================
def run_real_loop(max_iterations: int = 15):
    system_prompt = (
        "You are an expert Systems Engineer. Fix all bugs in the given TTLCache implementation.\n"
        "Rules:\n"
        "1. Strictly preserve all existing method names and argument signatures.\n"
        "2. Do NOT write comments, docstrings, or extra explanations (keep token output small).\n"
        "3. Ensure:\n"
        "   - get(key) moves key to most recent.\n"
        "   - size() counts only valid, non-expired keys.\n"
        "   - put() evicts expired keys first before evicting the oldest key.\n"
        "   - resize() drops excess elements immediately.\n"
        "4. Wrap the complete class in a single ```python ``` code block."
    )

    current_code = BUGGY_CODE

    # 執行初始基線檢查
    print("🚩 [初始狀態評估] 執行帶有 Bug 的原始 TTLCache 代碼...")
    _, initial_reports, _ = evaluate_code(current_code)
    print_detailed_dashboard(initial_reports, title="初始測試狀態")
    print_pedagogical_analysis(initial_reports)

    failed_info = "\n".join([f"- {r[0]}: {r[3].strip().splitlines()[-1]}" for r in initial_reports if r[1] != "PASSED"])

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"The following code is buggy:\n\n```python\n{current_code}\n```\n\nFailed Tests:\n{failed_info}\n\nPlease fix the implementation."}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"\n{'='*30} [Loop 次數 {attempt}/{max_iterations}] {'='*30}")
        print(f"🤖 呼叫 {MODEL_NAME} 進行程式碼修補與重構...")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
            max_tokens=2048,
        )
        raw_output = response.choices[0].message.content.strip()
        candidate = extract_code(raw_output)

        is_passed, reports, err = evaluate_code(candidate)

        if err:
            print(f"\n💥 [代碼執行失敗 (Syntax / Contract Violation)]")
            print(f"  👉 錯誤訊息: {err}")
            print("  💡【教學解析】模型未輸出完整的 class 結構（例如中途被 Token 上限截斷、未正確閉合括號，或輸出了非代碼的純文字對話）。")
            print("  🔄 [Loop 機制驅動]：系統將語法/結構錯誤反饋給模型，要求其必須輸出完整且合法的 Python 類別定義。")
            feedback = f"Execution error:\n{err}\nPlease return the full TTLCache class with valid syntax inside ```python ```."
        else:
            print_detailed_dashboard(reports, title=f"第 {attempt} 輪單元測試看板")

            if is_passed:
                print(f"\n🎉 [達成成功終止條件 (Terminal Success)]")
                print(f"📌【教學成果】：歷經 {attempt} 輪迭代反饋，12B 模型在未修改簽章的前提下，成功修復了複合型狀態機與所有深層 Bug！")
                return candidate

            print_pedagogical_analysis(reports)

            failed_info = "\n".join([f"- {r[0]}: {r[3].strip().splitlines()[-1]}" for r in reports if r[1] != "PASSED"])
            feedback = f"Still failing:\n{failed_info}\n\nPlease analyze the edge cases and fix them."

        # 上下文修剪滑動窗口 (Context Pruning)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Previous submission:\n```python\n{candidate}\n```\n\nFeedback:\n{feedback}\n\nProvide the complete fixed class in ```python ```."}
        ]

    print("\n⚠️ [達最大迭代上限 - 安全退出機制]")
    return None

if __name__ == "__main__":
    final = run_real_loop()