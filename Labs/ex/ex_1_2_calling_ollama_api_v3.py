# pip install openai

from openai import OpenAI

# 初始化 Client，將 base_url 指向本機 Ollama 的 v1 接口
# 因為是本地端，api_key 隨便填一個字串即可（不可為空）
client = OpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="ollama-local" 
)

#   MODEL_NAME = "gemma4_e4b_ctx_2048:latest"
MODEL_NAME = "gemma4:12b"

try:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "user", "content": "為什麼 Python 適合寫 AI 程式？"}
        ],
        temperature=0.5
    )

    # 標準 SDK 解析方式
    answer = response.choices[0].message.content
    print("🤖 LLM 回覆：")
    print(answer)

except Exception as e:
    print(f"呼叫失敗: {e}")