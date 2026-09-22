import json
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

# 1. 透過 Open WebUI 暴露的 OpenAI 相容端點連接
OPENWEBUI_URL = "http://172.10.0.2:8080/api/v1"  # 依你的 Open WebUI 地址調整
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # Open WebUI 的 API Key
MODEL_NAME = "gemma4:12b"  # 確保 Ollama 已 pull 該模型並同步到 Open WebUI

client = OpenAI(
    base_url=OPENWEBUI_URL,
    api_key=OPENWEBUI_API_KEY,
)

# 2. 定義明確的「客觀終止標準」(Schema)
class UserProfile(BaseModel):
    name: str
    age: int = Field(gt=0, lt=120)
    skills: list[str]
    is_employed: bool

def run_loop_engineering(raw_text: str, max_iterations: int = 4):
    """
    Loop Engineering 實踐：
    - 不依賴一次性 Prompt 完美達成
    - 由外部環境 (Pydantic) 驗證真實性
    - 動態餵回錯誤，直到通過驗證或達上限
    """
    system_instruction = (
        "You are an expert data extraction agent. Output ONLY valid, raw JSON matching the required schema. "
        "Do not include Markdown code blocks (e.g., ```json), explanations, or preamble."
    )
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Extract the profile from this text:\n'{raw_text}'\nTarget schema keys: name, age, skills, is_employed."}
    ]

    for attempt in range(1, max_iterations + 1):
        print(f"\n[Loop Step {attempt}/{max_iterations}] 呼叫 {MODEL_NAME} 產生結果...")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.2,  # 結構化任務建議低溫
        )
        output_content = response.choices[0].message.content.strip()

        # --- 外部驗證環境 (Evaluator) ---
        try:
            # 清理常見的 markdown 符號（容錯處理）
            clean_json_str = output_content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(clean_json_str)
            
            # Pydantic 嚴格型別與數值邊界校驗
            validated_obj = UserProfile(**data)
            
            print(f"[Loop 成功終止] 第 {attempt} 次迭代順利通過客觀檢驗！")
            return validated_obj

        except (json.JSONDecodeError, ValidationError) as err:
            error_feedback = f"Validation Failed: {str(err)}\nYour previous output was:\n{output_content}\nPlease fix the schema errors and return raw JSON only."
            print(f"[檢驗未通過 - 反饋回傳模型]: {err}")
            
            # --- 回饋注入 (Feedback Injection) ---
            # 將模型的錯誤輸出與環境反饋寫入 context，驅動下一次自我修正
            messages.append({"role": "assistant", "content": output_content})
            messages.append({"role": "user", "content": error_feedback})

    raise RuntimeError(f"Loop 終止：在 {max_iterations} 次迭代內未能達成成功條件。")

# 3. 測試非結構化文字提取
if __name__ == "__main__":
    sample_text = "嗨！我是 Alice，剛過完 28 歲生日。目前在一間軟體公司擔任前端工程師，擅長 Python、Vue 和 TypeScript。"
    result = run_loop_engineering(sample_text)
    print("\n最終提取成果：", result.model_dump_json(indent=2))
    