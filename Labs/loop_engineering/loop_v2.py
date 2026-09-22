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
from pydantic import BaseModel, Field, field_validator, model_validator

OPENWEBUI_URL = "http://172.10.0.2:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4:12b"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI

client = OpenAI(
    base_url=OPENWEBUI_URL,
    api_key=OPENWEBUI_API_KEY,
)

# 匯率標準（外部客觀依據）
RATES = {"TWD": 1.0, "USD": 32.5, "JPY": 0.21}

class ExpenseItem(BaseModel):
    date: str  # YYYY-MM-DD
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
            raise ValueError(f"日期 {v} 是週末（週六/週日），公司政策嚴禁報銷週末消費！")
        return v

class ExpenseReport(BaseModel):
    employee: str
    items: list[ExpenseItem]
    total_twd: float = Field(..., description="所有 items 換算後 TWD 的加總")
    audit_expression: str = Field(..., description="用於 Python eval 的純算式，例如 '3200 + 420 + 1500'")

    @model_validator(mode="after")
    def validate_financial_consistency(self):
        # 1. 驗證匯率計算精確度
        for item in self.items:
            curr = item.original_currency.upper()
            if curr not in RATES:
                raise ValueError(f"不支援的幣別: {curr}，僅允許 {list(RATES.keys())}")
            expected_twd = round(item.original_amount * RATES[curr], 1)
            if abs(item.converted_twd - expected_twd) > 1.0:
                raise ValueError(
                    f"項目 '{item.category}' 匯率換算錯誤！"
                    f"{item.original_amount} {curr} 依匯率 {RATES[curr]} 應為 {expected_twd} TWD，但填寫為 {item.converted_twd} TWD"
                )

        # 2. 驗證明細總和
        calculated_sum = round(sum(item.converted_twd for item in self.items), 1)
        if abs(self.total_twd - calculated_sum) > 1.0:
            raise ValueError(f"總金額不一致！明細加總為 {calculated_sum} TWD，但 total_twd 寫了 {self.total_twd} TWD")

        # 3. 執行 audit_expression 外部執行校驗
        try:
            # 限制 eval 命名空間確保安全
            eval_result = float(eval(self.audit_expression, {"__builtins__": {}}, {}))
            if abs(eval_result - self.total_twd) > 1.0:
                raise ValueError(
                    f"算式執行結果 ({eval_result}) 與 total_twd ({self.total_twd}) 不符！"
                    f"算式內容: '{self.audit_expression}'"
                )
        except Exception as e:
            raise ValueError(f"audit_expression 無法被 Python 執行或語法錯誤: {e}")

        return self

def run_hard_loop(raw_text: str, max_iterations: int = 15):
    system_instruction = (
        "You are an automated financial auditor. Extract expense records and output raw JSON ONLY.\n"
        f"Exchange rates to TWD: {json.dumps(RATES)}.\n"
        "Strict Requirements:\n"
        "1. Do NOT include items incurred on weekends (Saturday/Sunday).\n"
        "2. All currency must be accurately converted to TWD based on the provided rates.\n"
        "3. Ensure the sum of items strictly equals total_twd.\n"
        "4. Output ONLY valid JSON matching the schema, with no markdown code blocks or explanations."
    )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Extract and audit expenses from this communication:\n\n{raw_text}"}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"\n==================== [Loop Step {attempt}/{max_iterations}] ====================")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.1,
        )
        output_content = response.choices[0].message.content.strip()

        # 清理可能夾帶的 code fence
        clean_json_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", output_content, flags=re.MULTILINE).strip()

        try:
            data = json.loads(clean_json_str)
            validated_report = ExpenseReport(**data)
            print(f"🎉 [成功終止] 第 {attempt} 次迭代完全通過嚴格審計檢驗！")
            return validated_report

        except (json.JSONDecodeError, ValueError) as err:
            print(f"❌ [檢驗失敗 - 觸發自我修復反饋]\n報錯原因: {err}")
            
            # 將錯誤精確反饋給模型
            feedback_message = (
                f"Your previous output failed validation with the following error:\n"
                f"{str(err)}\n\n"
                f"Please correct the errors in calculations, weekend filtering, or schema structure. Return RAW JSON only."
            )
            messages.append({"role": "assistant", "content": output_content})
            messages.append({"role": "user", "content": feedback_message})

    raise RuntimeError(f"Loop 終止：在 {max_iterations} 次迭代內仍無法通過驗證。")

if __name__ == "__main__":
    # 測試樣本：包含多幣別、週末陷阱、口語反悔
    tricky_input = """
    老闆你好，我是 Ken。這次出差日本與美國的報銷清單如下：
    1. 2026-03-12 (週四)：買了活動展示架，花了 120 USD。
    2. 2026-03-13 (週五)：客戶請午餐我先墊付，日本料理 15000 JPY。原本說還要買書 3000 JPY 但後來發票掉了就別報了。
    3. 2026-03-14 (週六)：去東京巨蛋看展兼假日聚餐，花了 8000 JPY。
    4. 2026-03-16 (週一)：在機場買高鐵接駁票 650 TWD。
    匯率你就幫我按 USD 32.5、JPY 0.21 換算算總額給我，謝謝！
    """
    result = run_hard_loop(tricky_input)
    print("\n最終審定通過報銷單：\n", result.model_dump_json(indent=2))