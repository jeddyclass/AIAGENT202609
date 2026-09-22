# curl http://localhost:11434/api/tags
# curl http://172.10.0.22:11434/api/tags

import json
import requests

# 1. 設定 Ollama 的原生 API 連線資訊
# 根據你的設定：改用 Ollama 預設 Port 11434 的 /api/chat 接口
OLLAMA_URL = "http://172.10.0.2:11434/api/chat"
#OLLAMA_URL = "http://localhost:11434/api/chat"
#MODEL_NAME = "gemma4_e4b_ctx_2048:latest"
MODEL_NAME = "gemma4:12b"


def generate_joke():
    """Task 1: 讓 LLM 產生一個中文笑話"""
    print("--- 🎭 正在執行 Task 1：產生中文笑話 ---")

    # 建構符合 Ollama /api/chat 的 Payload
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一個幽默的助手，請寫一個好笑的中文笑話。"},
            {"role": "user", "content": "請講一個好笑的中文笑話，直接講笑話內容就好。"},
        ],
        "options": {"temperature": 0.7},  # Ollama 的參數要放在 options 裡
        "stream": False,  # 關閉串流，讓結果一次回傳
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()  # 檢查 HTTP 狀態碼是否正常

        # 解析 Ollama 的回傳格式
        result_json = response.json()
        answer = result_json["message"]["content"]
        print(answer)

    except Exception as e:
        print(f"Task 1 執行出錯: {e}")


def translate_text():
    """Task 2: 翻譯指定句子成中、英、日、韓四國語言，並輸出標準 Markdown 表格"""
    print("\n--- 🌐 正在執行 Task 2：多國語言翻譯 ---")

    source_text = "ReAct: Synergizing Reasoning and Acting in Language Models"

    prompt = f"""請將以下英文句子翻譯成 中文（繁體）、英文（保持原文）、日文、韓文。
    
    要翻譯的句子："{source_text}"
    
    請嚴格使用以下 Markdown 表格格式回傳，不要有任何額外的解釋文字：
    | 語言 | 翻譯結果 |
    | --- | --- |
    | 中文 (繁體) | [中文翻譯] |
    | 英文 (Original) | [英文原文] |
    | 日文 | [日文翻譯] |
    | 韓文 | [韓文翻譯] |
    """

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是一個精準的翻譯專家，只輸出的 Markdown 格式表格。",
            },
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.2},  # 降低隨機性
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()

        result_json = response.json()
        answer = result_json["message"]["content"]
        print(answer)

    except Exception as e:
        print(f"Task 2 執行出錯: {e}")


# --- 執行主程式 ---
if __name__ == "__main__":
    # 執行前請確保環境已安裝 requests 套件 (pip install requests)
    generate_joke()
    translate_text()