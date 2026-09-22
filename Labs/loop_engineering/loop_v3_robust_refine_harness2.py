# Loop Engineering 中的「規格鎖定」
# 在軟體工程 Agent 中，有一個黃金法則：
# 
# 「永遠不要讓中小型模型去決定函數的簽章（Signature）。」
# 
# 模型負責填寫演算法邏輯，而類別骨架與函數介面必須由 Harness 固定住。同時，禁止它在代碼裡浪費 token 去寫又臭又長的 Docstring，避免觸發 Token 截斷。

import io
import re
import unittest
from openai import OpenAI

OPENWEBUI_URL = "http://172.10.0.2:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4:12b"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI

client = OpenAI(base_url=OPENWEBUI_URL, api_key=OPENWEBUI_API_KEY)

# 1. 保留完整簽章，但塞入真實邏輯陷阱的待修復代碼
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

# 2. 嚴密的測試套件（堵住所有矇混過關的順序巧合）
TEST_SUITE_CODE = '''
import unittest
import time

class TestTTLCache(unittest.TestCase):
    def test_01_basic_put_get(self):
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("non_existent"))

    def test_02_lru_hit_ordering(self):
        """讀取命中必須刷新 LRU 權重"""
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
        # 關鍵：此時完全不呼叫 get()，直接問 size()
        self.assertEqual(c.size(), 0, "size() 必須能辨識並過濾過期項目，不能只回傳 len(cache)")

    def test_04_expired_priority_strict(self):
        """
        防矇混測試：故意讓【後放入】的項目先過期！
        放入順序：k1 (久), k2 (快過期)
        如果單純 popitem(last=False)，會錯殺 k1！
        """
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("k1_long", "data1", ttl=10.0) # 先放入，存活很久
        c.put("k2_short", "data2", ttl=0.05) # 後放入，極快過期
        
        time.sleep(0.1) # 此時 k2 已過期，但 k1 還很健康
        c.put("k3_new", "data3") # 滿載寫入

        self.assertEqual(c.get("k1_long"), "data1", "k1 還未過期且不該被淘汰！應優先剔除過期的 k2")
        self.assertIsNone(c.get("k2_short"), "k2 已過期，應被優先清理掉")

    def test_05_resize_eviction(self):
        """縮容必須即時剔除超額舊資料"""
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

    # 先跑原始代碼展示失敗
    print("🚩 [初始評估] 執行帶有 Bug 的原始代碼...")
    _, initial_reports, _ = evaluate_code(current_code)
    print("\n📋【初始測試狀態】")
    for name, status, _, _ in initial_reports:
        print(f"  {'✅ 通過' if status == 'PASSED' else '❌ 失敗'} | {name}")

    failed_info = "\n".join([f"- {r[0]}: {r[3].strip().splitlines()[-1]}" for r in initial_reports if r[1] != "PASSED"])

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"The following code is buggy:\n\n```python\n{current_code}\n```\n\nFailed Tests:\n{failed_info}\n\nPlease fix the implementation."}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"\n{'='*25} [Loop 次數 {attempt}/{max_iterations}] {'='*25}")
        print(f"🤖 呼叫 {MODEL_NAME} 進行修復...")

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
            print(f"💥 語法/結構問題: {err}")
            feedback = f"Execution error:\n{err}\nPlease return the full class with valid syntax."
        else:
            print("\n📋【單元測試執行看板】")
            for name, status, _, _ in reports:
                print(f"  {'✅ 通過' if status == 'PASSED' else '❌ 失敗'} | {name}")

            if is_passed:
                print(f"\n🎉 [Loop 終止] 12B 模型在第 {attempt} 輪真正解決了所有深層狀態機 Bug！")
                return candidate

            failed_info = "\n".join([f"- {r[0]}: {r[3].strip().splitlines()[-1]}" for r in reports if r[1] != "PASSED"])
            feedback = f"Still failing:\n{failed_info}\n\nPlease analyze the edge cases and fix them."

        # 滑動窗口回饋
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Previous submission:\n```python\n{candidate}\n```\n\nFeedback:\n{feedback}\n\nProvide the complete fixed class in ```python ```."}
        ]

    print("\n⚠️ 未能在迭代內完全解決。")
    return None

if __name__ == "__main__":
    final = run_real_loop()