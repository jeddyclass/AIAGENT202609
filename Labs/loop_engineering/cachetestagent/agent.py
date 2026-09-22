import io
import os
import unittest
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# ==========================================
# 1. 設置 Open WebUI / Ollama 連線環境變數
# ==========================================
os.environ["OPENAI_API_BASE"] = "http://172.10.0.2:8080/api/v1"
os.environ["OPENAI_BASE_URL"] = "http://172.10.0.2:8080/api/v1"
os.environ["OPENAI_API_KEY"] = "sk-f60ffbf03ede457987a23650b8b11763"

# ==========================================
# 2. 測試套件 (規格鎖定)
# ==========================================
TEST_SUITE_CODE = """
import unittest
import time

class TestTTLCache(unittest.TestCase):
    def test_01_basic_put_get(self):
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("a", 1)
        self.assertEqual(c.get("a"), 1)
        self.assertIsNone(c.get("non_existent"))

    def test_02_lru_hit_ordering(self):
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("a", 1)
        c.put("b", 2)
        c.get("a")
        c.put("c", 3)
        self.assertEqual(c.get("a"), 1, "鍵 'a' 剛被讀過，不應被淘汰！")
        self.assertIsNone(c.get("b"), "鍵 'b' 最久未被存取，應該被淘汰！")

    def test_03_size_without_get(self):
        c = TTLCache(capacity=3, default_ttl=0.1)
        c.put("exp1", 10)
        c.put("exp2", 20)
        time.sleep(0.15)
        self.assertEqual(c.size(), 0, "size() 必須能辨識並過濾過期項目，不能只回傳 len(cache)")

    def test_04_expired_priority_strict(self):
        c = TTLCache(capacity=2, default_ttl=10.0)
        c.put("k1_long", "data1", ttl=10.0)
        c.put("k2_short", "data2", ttl=0.05)
        time.sleep(0.1)
        c.put("k3_new", "data3")
        self.assertEqual(c.get("k1_long"), "data1", "k1 還未過期且不該被淘汰！應優先剔除過期的 k2")
        self.assertIsNone(c.get("k2_short"), "k2 已過期，應被優先清理掉")

    def test_05_resize_eviction(self):
        c = TTLCache(capacity=4, default_ttl=10.0)
        c.put("a", 1); c.put("b", 2); c.put("c", 3); c.put("d", 4)
        c.resize(2)
        self.assertEqual(c.size(), 2, "縮容至 2 後，有效元素量必須為 2")
        self.assertIsNone(c.get("a"), "最舊的 a 應在縮容時被剔除")
        self.assertIsNone(c.get("b"), "次舊的 b 應在縮容時被剔除")
"""

# ==========================================
# 3. ADK Tool: 單元測試執行器
# ==========================================
def run_unit_tests(candidate_code: str) -> str:
    """執行候選 TTLCache 代碼的單元測試並回傳評測結果。

    Args:
        candidate_code: 包含 TTLCache 完整定義的 Python 程式碼。
    Returns:
        包含測試成功與否與詳細失敗原因的報告文字。
    """
    namespace = {}
    try:
        exec(candidate_code, namespace)
    except Exception as e:
        return f"語法編譯失敗: {type(e).__name__}: {str(e)}"

    if "TTLCache" not in namespace:
        return "錯誤：代碼中找不到 TTLCache 類別！"

    try:
        exec(TEST_SUITE_CODE, namespace)
    except Exception as e:
        return f"測試注入失敗: {str(e)}"

    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(namespace["TestTTLCache"]))

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        return "SUCCESS: 全部 5 個單元測試均已通過！程式碼完全符合規格。"

    output = ["FAILED: 單元測試未全數通過。詳細狀況："]
    for failure in result.failures:
        output.append(f"- [失敗] {failure[0]._testMethodName}: {failure[1].strip().splitlines()[-1]}")
    for error in result.errors:
        output.append(f"- [錯誤] {error[0]._testMethodName}: {error[1].strip().splitlines()[-1]}")

    return "\n".join(output)

# ==========================================
# 4. Agent 定義 (使用 LiteLlm 介面)
# ==========================================
system_instruction = """
You are an expert Systems Engineer. Your job is to fix the given TTLCache implementation.

CRITICAL INSTRUCTIONS:
1. DO NOT explain your thoughts. DO NOT output internal monologues or reasoning text.
2. DO NOT write docstrings or long comments (save tokens!).
3. STRICT SPECIFICATION LOCK: Do NOT alter method names or signatures (get, put, resize, size).
4. MANDATORY ACTION: In your FIRST response, you MUST generate the complete refactored TTLCache Python code and call the `run_unit_tests` tool immediately.
5. If the tests fail, observe the errors, rewrite the class, and call `run_unit_tests` again.
6. Only output final conversational text after `run_unit_tests` returns "SUCCESS".
"""

root_agent = Agent(
    name="cachetestagent",
    model=LiteLlm(
        model="openai/gemma4:12b",
        api_base="http://172.10.0.2:8080/api/v1",
        api_key="sk-f60ffbf03ede457987a23650b8b11763",
        max_tokens=4096,  # 提高上限，避免寫 code 到一半被截斷
        temperature=0.0,  # 設為 0，讓小模型專注於精確代碼生成，不要天馬行空
    ),
    instruction="""
You are an Automated Code Repair Agent.
YOUR GOAL: Fix TTLCache so that all 5 unit tests pass.

STRICT OPERATIONAL RULES:
1. NEVER output your thoughts, analysis, or explanation. Zero chit-chat.
2. In each turn, your reply MUST ONLY be the invocation of `run_unit_tests(candidate_code=...)`.
3. Do not include docstrings or comments in your code to save tokens.
4. KEY SPECIFICATION HINTS for TTLCache:
   - `get(k)`: if expired, delete and return None; if valid, call `move_to_end(k)`.
   - `size()`: count ONLY unexpired keys (lazily prune or dynamically filter).
   - `put(k, v, ttl)`: when full, FIRST iterate over all keys to remove any expired item; ONLY if no expired items exist, pop the oldest item via `popitem(last=False)`.
   - `resize(n)`: immediately pop the oldest items until size <= n.
""",
    tools=[run_unit_tests],
)