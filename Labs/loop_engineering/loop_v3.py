# LLM 的角色是「軟體工程師」，外部環境的 Python unittest 執行器則是嚴格的「CI/CD 評測員」。
# 
# 實務挑戰設計：高併發/分散式限流器（Token Bucket Rate Limiter）
# 我們提供一段有隱藏 Bug 的 Rate Limiter 程式碼，並準備了 4 個嚴苛的單元測試：
# 
# Test 1（基本功能）：一般請求正常通過與阻擋。
# 
# Test 2（動態補水機制）：隨時間流逝，Bucket 應精確補充 Token（模型常寫錯時間差浮點數換算）。
# 
# Test 3（邊界條件與突發流量）：短時間突發大量併發消耗。
# 
# Test 4（執行緒安全 Thread-Safety）：多個 Thread 併發搶佔時不得超額放行（高難度！ 模型必須正確引入 threading.Lock，且不能造成死鎖）。

import io
import re
import sys
import unittest
from openai import OpenAI

OPENWEBUI_URL = "http://172.10.0.2:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4:12b"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI

client = OpenAI(
    base_url=OPENWEBUI_URL,
    api_key=OPENWEBUI_API_KEY,
)

# ==========================================
# 1. 任務：待修復的原始程式碼（充滿 Bug 與 Thread 漏洞）
# ==========================================
BUGGY_CODE = '''
import time

class TokenBucket:
    def __init__(self, capacity: int, fill_rate: float):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        # BUG 1: 忘記處理 tokens 超過 capacity 的邊界
        # BUG 2: 補水邏輯沒有考慮 min(capacity, ...)
        # BUG 3: 完全沒有 Thread Lock，多執行緒下會 Race Condition
        now = time.time()
        elapsed = now - self.last_update
        self.tokens += elapsed * self.fill_rate
        self.last_update = now

        if self.tokens >= tokens:
            # 刻意製造一個極小 sleep 放大 Race Condition
            time.sleep(0.0001)
            self.tokens -= tokens
            return True
        return False
'''

# ==========================================
# 2. 客觀真理：標準單元測試（絕對不給模型修改）
# ==========================================
TEST_SUITE_CODE = '''
import unittest
import time
from threading import Thread

class TestTokenBucket(unittest.TestCase):
    def test_01_basic_consumption(self):
        """測試基礎消耗與餘額耗盡阻擋"""
        bucket = TokenBucket(capacity=5, fill_rate=1.0)
        for _ in range(5):
            self.assertTrue(bucket.consume(1))
        self.assertFalse(bucket.consume(1), "容量耗盡後應立即被拒絕")

    def test_02_refill_mechanism(self):
        """測試隨時間補充 Token 的精度與上限控制"""
        bucket = TokenBucket(capacity=10, fill_rate=20.0) # 每秒 20 個
        self.assertTrue(bucket.consume(10))
        self.assertFalse(bucket.consume(1))
        time.sleep(0.2) # 應補充約 4 個
        self.assertTrue(bucket.consume(3), "補水後應足以消耗 3 個 token")
        
        # 測試不能超過容量上限
        time.sleep(1.0)
        self.assertFalse(bucket.consume(15), "即使補水再久，單次也不能超過 capacity")

    def test_03_invalid_requests(self):
        """測試要求超過上限或負數的不合理請求"""
        bucket = TokenBucket(capacity=5, fill_rate=1.0)
        self.assertFalse(bucket.consume(10), "請求量直接大於 capacity 應回傳 False")

    def test_04_thread_safety(self):
        """測試高併發多執行緒搶佔（Thread-Safety）"""
        bucket = TokenBucket(capacity=100, fill_rate=0.0) # 不補水，純測併發扣除
        success_count = 0

        def worker():
            nonlocal success_count
            if bucket.consume(1):
                success_count += 1

        threads = [Thread(target=worker) for _ in range(150)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(success_count, 100, f"併發競爭失敗！預期放行 100 個，實際放行了 {success_count} 個")
'''

# ==========================================
# 3. 外部評測器：沙盒執行 unittest
# ==========================================
def evaluate_code(candidate_code: str) -> tuple[bool, str]:
    """
    在乾淨命名空間中編譯候選代碼 + 執行測試套件
    回傳 (是否全部通過, 詳細測試報錯)
    """
    namespace = {}
    try:
        # 靜態語法檢查與載入
        exec(candidate_code, namespace)
    except Exception as e:
        return False, f"語法或編譯錯誤 (Syntax/Runtime Error): {type(e).__name__}: {str(e)}"

    # 注入測試案例
    try:
        exec(TEST_SUITE_CODE, namespace)
    except Exception as e:
        return False, f"測試案例裝載異常: {str(e)}"

    # 執行 Unittest 並捕獲輸出
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(namespace["TestTokenBucket"]))
    
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    test_result = runner.run(suite)
    
    output = stream.getvalue()
    is_success = test_result.wasSuccessful()
    return is_success, output

# ==========================================
# 4. 教學摘要解析器（轉為課程用白話文）
# ==========================================
def parse_test_failure_to_chinese(test_output: str) -> str:
    lines = []
    if "SyntaxError" in test_output:
        lines.append("【錯誤層級】Python 語法層損毀")
        lines.append("【現況解析】模型產生的修復代碼存在未閉合括號或縮排錯誤，無法執行。")
    elif "test_04_thread_safety" in test_output:
        lines.append("【錯誤層級】高併發競爭危害 (Race Condition)")
        lines.append("【現況解析】多執行緒同時讀寫 `self.tokens` 發生競態條件，模型尚未引入 `threading.Lock` 或加鎖範圍不足。")
    elif "test_02_refill_mechanism" in test_output:
        lines.append("【錯誤層級】演算法邊界與時間精度邏輯缺失")
        lines.append("【現況解析】Token 補水計算超過了 `capacity` 上限，或浮點數時間差計算未被妥善夾取 (clamped)。")
    elif "test_03_invalid_requests" in test_output:
        lines.append("【錯誤層級】邊界輸入防禦不足")
        lines.append("【現況解析】當請求量大於總容量時，模型未做先驗防禦直接進行減算。")
    else:
        lines.append("【錯誤層級】單元測試斷言失敗 (Assertion Failed)")
        lines.append("【現況解析】基本邏輯行為與規格不符。")

    lines.append("【Loop 演進機制】外部環境將具體的 Traceback 自動注入對話，迫使模型在下一輪從工程細節進行重構。")
    return "\n".join(lines)

# ==========================================
# 5. Loop Engineering 核心修復迴圈
# ==========================================
def run_code_repair_loop(max_iterations: int = 15):
    system_prompt = (
        "You are an elite Python Systems Engineer. Your job is to fix a buggy implementation of a Token Bucket Rate Limiter.\n"
        "Requirements:\n"
        "1. Strictly conform to the TokenBucket class signature.\n"
        "2. It must be completely thread-safe under concurrent access.\n"
        "3. Output ONLY the raw, complete Python code for TokenBucket. No markdown code blocks, no backticks, no explanations."
    )

    current_code = BUGGY_CODE
    
    # 第一次先測原本的 code，建立基線
    passed, test_report = evaluate_code(current_code)
    print("🚩 [初始狀態檢查] 執行未修復的原始程式碼...")
    print(f"原始代碼測試結果: {'通過' if passed else '失敗'}")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"The following code is failing our CI/CD unit tests:\n\n{current_code}\n\nHere is the test execution output:\n{test_report}\n\nPlease fix the implementation and return the full corrected code."}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"\n{'='*28} [Loop 次數 {attempt}/{max_iterations}] {'='*28}")
        print(f"🤖 呼叫 {MODEL_NAME} 進行代碼重構與 Bug 修復...")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
        )
        raw_output = response.choices[0].message.content.strip()
        
        # 清理可能夾帶的 ```python ... ```
        cleaned_code = re.sub(r"^```(?:python)?\s*|\s*```$", "", raw_output, flags=re.MULTILINE).strip()

        # --- 外部嚴格評測環境 (Evaluator) ---
        is_passed, report = evaluate_code(cleaned_code)

        if is_passed:
            print("\n🎉 [達到終止條件：CI/CD 綠燈通過！]")
            print(f"📌【教學摘要】：模型在第 {attempt} 輪迭代中，成功修正了包含多執行緒鎖 (Lock)、容量限制與時間計算的所有缺陷！")
            return cleaned_code
        else:
            print("\n❌ [CI/CD 測試紅燈 (Tests Failed)]")
            
            # 印出繁體中文解析供教學講解
            chinese_summary = parse_test_failure_to_chinese(report)
            print("-" * 60)
            print(chinese_summary)
            print("-" * 60)

            # 抓取最後 5 行報錯作為精簡日誌
            tail_err = "\n".join(report.strip().splitlines()[-6:])
            print(f"👉 終端測試關鍵 Traceback:\n{tail_err}\n")

            # --- Feedback Injection (將 CI/CD 失敗輸出餵回模型) ---
            feedback = (
                f"Your proposed fix still failed the test suite.\n"
                f"Here is the exact unittest failure output:\n\n{report}\n\n"
                f"Analyze the failures, ensure thread-safety with locks, handle all edge cases, and output the complete Python code ONLY."
            )
            messages.append({"role": "assistant", "content": raw_output})
            messages.append({"role": "user", "content": feedback})

    raise RuntimeError(f"修復失敗：在 {max_iterations} 次迭代內仍無法通過所有測試。")

if __name__ == "__main__":
    final_repaired_code = run_code_repair_loop()
    print("\n" + "="*20 + " 最終修復通過的程式碼 " + "="*20)
    print(final_repaired_code)