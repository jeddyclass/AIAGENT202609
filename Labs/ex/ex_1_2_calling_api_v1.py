# pip install openai
import os
from openai import OpenAI

# 1. 初始化 Client
# 根據你的設定：Endpoint 為 Open WebUI 的 API 路徑，並帶入指定的 API Key
client = OpenAI(
    api_key="sk-f60ffbf03ede457987a23650b8b11763",
    base_url="http://172.10.0.2:8080/api"  # 請依你的 Open WebUI 實際網址修改（通常 /api/chat/completions 的 base 是到 /api）
)

#MODEL_NAME = "gemma4_e4b_ctx_2048:latest"
MODEL_NAME = "gemma4:12b"


def generate_joke():
    """Task 1: 讓 LLM 產生一個中文笑話"""
    print("--- 🎭 正在執行 Task 1：產生中文笑話 ---")
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一個幽默的助手，請寫一個好笑的中文笑話。"},
                {"role": "user", "content": "請講一個好笑的中文笑話，直接講笑話內容就好。"}
            ],
            temperature=0.7
        )
        
        # 取得 Markdown 格式的回答
        answer = response.choices[0].message.content
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

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是一個精準的翻譯專家，只輸出的 Markdown 格式表格。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2 # 翻譯任務調低 temperature 讓結果更穩定
        )
        
        answer = response.choices[0].message.content
        print(answer)
        
    except Exception as e:
        print(f"Task 2 執行出錯: {e}")

# --- 執行主程式 ---
if __name__ == "__main__":
    generate_joke()
    translate_text()
    