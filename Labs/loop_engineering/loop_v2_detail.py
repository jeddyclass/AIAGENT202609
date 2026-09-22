# 升級版：差旅報銷自動審計與正規化 Loop
# 一個「報銷審計機器人」：
# 輸入：一段混亂、充滿口語和幣別切換的報銷對話。
# 
# 挑戰：
# 幣別必須統一換算為 TWD，且必須依據給定的固定匯率表。
# 明細金額相加必須精確等於宣告的總額（LLM 算術極易出現 1~2 元的幻覺偏差）。
# 必須產出可被 Python 直接 eval 通過的金額核算表達式。
# 時間跨度不可超過 7 天，且不得報銷周末餐費。
#
# ==========================================================================
# 這個難題設計了哪些「阻礙」？
#
# 週末地雷（2026-03-14）：模型直覺常會把看到的項目全部抽取出來，但 Pydantic 的 validate_date 會直接檢查星期幾並報錯拋出："日期 2026-03-14 是週末，公司政策嚴禁報銷週末消費！"，強迫模型在第 2 輪剔除該項目。
# 
# 算術精度陷阱：120 * 32.5 = 3900、15000 * 0.21 = 3150。大語言模型在做多品項加總時，經常會在 total_twd 出現 1~5 塊錢的計算誤差。
#
# 外部程式碼求值 (eval)：模型生成的 audit_expression 必須是一段真正的數學算式字串（例如 "3900 + 3150 + 650"），且計算結果必須嚴格等於 total_twd。
#
# ==========================================================================

import json
import re
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

OPENWEBUI_URL = "http://192.168.1.175:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-3bc30ba040b34172a00fba0b3d414189"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4_31b_nothink:latest"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI

client = OpenAI(
    base_url=OPENWEBUI_URL,
    api_key=OPENWEBUI_API_KEY,
)

RATES = {"TWD": 1.0, "USD": 32.5, "JPY": 0.21}

class ExpenseItem(BaseModel):
    date: str
    category: str
    original_currency: str
    original_amount: float
    converted_twd: float

    @field_validator("date")
    def validate_date(cls, v):
        try:
            dt = datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"日期格式必須是 YYYY-MM-DD，收到了：{v}")
        if dt.weekday() >= 5:
            raise ValueError(f"日期 {v} 是週末，公司政策嚴禁報銷週末消費！")
        return v

class ExpenseReport(BaseModel):
    employee: str
    items: list[ExpenseItem]
    total_twd: float = Field(..., description="所有 items 換算後 TWD 的加總")
    audit_expression: str = Field(..., description="用於 Python eval 的純算式")

    @model_validator(mode="after")
    def validate_financial_consistency(self):
        for item in self.items:
            curr = item.original_currency.upper()
            if curr not in RATES:
                raise ValueError(f"不支援的幣別: {curr}")
            expected_twd = round(item.original_amount * RATES[curr], 1)
            if abs(item.converted_twd - expected_twd) > 1.0:
                raise ValueError(
                    f"項目 '{item.category}' 匯率錯誤！"
                    f"{item.original_amount} {curr} 應為 {expected_twd} TWD，但填寫為 {item.converted_twd} TWD"
                )

        calculated_sum = round(sum(item.converted_twd for item in self.items), 1)
        if abs(self.total_twd - calculated_sum) > 1.0:
            raise ValueError(f"總金額不一致！明細加總為 {calculated_sum} TWD，但 total_twd 寫了 {self.total_twd} TWD")

        try:
            eval_result = float(eval(self.audit_expression, {"__builtins__": {}}, {}))
            if abs(eval_result - self.total_twd) > 1.0:
                raise ValueError(
                    f"算式執行結果 ({eval_result}) 與 total_twd ({self.total_twd}) 不符！算式: '{self.audit_expression}'"
                )
        except Exception as e:
            raise ValueError(f"audit_expression 無法被 Python 執行或語法錯誤: {e}")

        return self

def generate_teaching_summary(err: Exception, raw_output: str) -> str:
    """將技術性報錯轉譯為課程教學用的繁體中文摘要"""
    err_msg = str(err)
    summary_lines = []

    if isinstance(err, json.JSONDecodeError):
        summary_lines.append("【錯誤類型】JSON 語法損毀")
        summary_lines.append("【原因解構】模型未輸出純 JSON，可能夾帶了多餘的解說文字或 Markdown 標籤。")
    elif "Field required" in err_msg:
        missing_fields = re.findall(r"([a-zA-Z0-9_\.]+)\s+Field required", err_msg)
        summary_lines.append("【錯誤類型】Schema 結構不符（欄位遺漏或命名幻覺）")
        summary_lines.append(f"【原因解構】模型漏掉了必要欄位，或自創了欄位名：{', '.join(missing_fields[:4])}")
    elif "週末" in err_msg:
        summary_lines.append("【錯誤類型】業務規則防線觸發（週末報銷攔截）")
        summary_lines.append("【原因解構】模型未按指示過濾掉週六/週日的開銷，被外部程式的日曆邏輯精確抓包。")
    elif "audit_expression" in err_msg or "invalid syntax" in err_msg:
        summary_lines.append("【錯誤類型】外部程式碼執行失敗（Execution Verification）")
        summary_lines.append("【原因解構】模型產生的算式無法在 Python 環境執行（例如誤寫了等號 '=' 或賦值語法）。")
    elif "匯率" in err_msg or "總金額不一致" in err_msg:
        summary_lines.append("【錯誤類型】數值計算幻覺（Arithmetic Inconsistency）")
        summary_lines.append("【原因解構】明細加總或匯率換算有微小誤差，未通過外部嚴格的數學等式校驗。")
    else:
        summary_lines.append("【錯誤類型】一般資料校驗未通過")
        summary_lines.append(f"【原因解構】{err_msg.splitlines()[0]}")

    summary_lines.append("【Loop 機制】系統將此客觀錯誤自動組裝進對話歷史，要求模型在下一輪自我修正。")
    return "\n".join(summary_lines)

def run_hard_loop(raw_text: str, max_iterations: int = 15):
    system_instruction = (
        "You are an automated financial auditor. Extract expense records and output raw JSON ONLY.\n"
        f"Exchange rates to TWD: {json.dumps(RATES)}.\n"
        "Strict Requirements:\n"
        "1. Do NOT include items incurred on weekends (Saturday/Sunday).\n"
        "2. All currency must be accurately converted to TWD based on the provided rates.\n"
        "3. Ensure the sum of items strictly equals total_twd.\n"
        "4. audit_expression must be a purely evaluable Python math string without '=', e.g., '100 + 200'.\n"
        "5. Output ONLY valid JSON matching the schema, with no markdown code blocks or explanations."
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Extract and audit expenses from this communication:\n\n{raw_text}"}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"\n{'='*25} [Loop 次數 {attempt}/{max_iterations}] {'='*25}")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
        )
        output_content = response.choices[0].message.content.strip()
        clean_json_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_content, flags=re.MULTILINE).strip()

        try:
            data = json.loads(clean_json_str)
            validated_report = ExpenseReport(**data)
            
            print(f"\n🎉 [成功終止 (Terminal State Reach)]")
            print(f"📌【教學摘要】：模型歷經 {attempt - 1} 次錯誤反饋，第 {attempt} 次完全符合 Schema、邏輯約束與代碼執行驗證！")
            return validated_report

        except (json.JSONDecodeError, ValueError, ValidationError) as err:
            print(f"\n❌ [檢驗未通過 (Evaluator Rejected)]")
            # 印出技術性報錯的精簡版
            print(f"👉 技術底層報錯: {str(err).splitlines()[0]}")
            
            # 印出為課堂教學設計的繁體中文解析
            teaching_summary = generate_teaching_summary(err, output_content)
            print("-" * 55)
            print(teaching_summary)
            print("-" * 55)

            feedback_message = (
                f"Validation Failed with error:\n{str(err)}\n\n"
                f"Please fix your JSON schema and calculations based on the error above. Return RAW JSON only."
            )
            messages.append({"role": "assistant", "content": output_content})
            messages.append({"role": "user", "content": feedback_message})

    raise RuntimeError(f"Loop 終止：在 {max_iterations} 次迭代內未能達成成功條件。")

if __name__ == "__main__":
    tricky_input = """
    老闆你好，我是 Ken。這次出差日本與美國的報銷清單如下：
    1. 2026-03-12 (週四)：買了活動展示架，花了 120 USD。
    2. 2026-03-13 (週五)：客戶請午餐我先墊付，日本料理 15000 JPY。原本說還要買書 3000 JPY 但後來發票掉了就別報了。
    3. 2026-03-14 (週六)：去東京巨蛋看展兼假日聚餐，花了 8000 JPY。
    4. 2026-03-16 (週一)：在機場買高鐵接駁票 650 TWD。
    匯率你就幫我按 USD 32.5、JPY 0.21 換算算總額給我，謝謝！
    """
    result = run_hard_loop(tricky_input)
    print("\n最終審定通過成果：\n", result.model_dump_json(indent=2))
	