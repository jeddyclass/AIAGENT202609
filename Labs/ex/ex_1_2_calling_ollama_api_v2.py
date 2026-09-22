import requests

# 本機 Ollama 的標準 OpenAI 相容路徑
URL = "http://127.0.0.1:11434/v1/chat/completions"

# 填寫你在 Ollama 中已下載的模型名稱（例如 gemma4:e4b, llama3 等）
#MODEL_NAME = "gemma4_e4b_ctx_2048:latest"
MODEL_NAME = "gemma4_nothink:latest"
#MODEL_NAME = "gemma4:e2b"

headers = {
    "Content-Type": "application/json"
}

payload = {
    "model": MODEL_NAME,
    "messages": [
        {"role": "system", "content": "你是一個專業的程式助手。"},
        {"role": "user", "content": "請用一句話解釋什麼是 API？"}
    ],
    "temperature": 0.7,
    "stream": False  # 關閉串流，一次性回傳
}

try:
    response = requests.post(URL, json=payload, headers=headers)
    response.raise_for_status()
    
    # 這是標準的 OpenAI 回傳格式解析方式
    result = response.json()
    answer = result["choices"][0]["message"]["content"]
    
    print("🤖 LLM 回覆：")
    print(answer)

except Exception as e:
    print(f"連線失敗，請檢查 Ollama 是否有正常開啟: {e}")