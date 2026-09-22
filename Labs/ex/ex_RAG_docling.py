# https://github.com/docling-project/docling
# pip install docling requests

import os
import requests
from docling.document_converter import DocumentConverter

# ==========================================
# 1. 設定 Open WebUI / Ollama 的 API 資訊
# ==========================================
# 請根據您的 Open WebUI 實際設定修改網址與 API Key
OPEN_WEBUI_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # 請替換成您在 Open WebUI 後台生成的 API Key
MODEL_NAME = "gemma4_e4b_nothink:latest"

def summarize_with_llm(text_content):
    """呼叫 Open WebUI API 進行文字總結"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是一個專業的文章總結助手，請使用「繁體中文(台灣)」為接下來輸入的文本做精簡、結構化的重點摘要。"
            },
            {
                "role": "user",
                "content": f"請幫我總結以下這段文件內容：\n\n{text_content}"
            }
        ],
        "temperature": 0.3
    }
    
    try:
        print(f"🤖 正在呼叫 LLM ({MODEL_NAME}) 進行總結...")
        response = requests.post(OPEN_WEBUI_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"❌ LLM 總結失敗，錯誤原因: {e}"

# ==========================================
# 2. [Parse 階段] 讀取並解析文件
# ==========================================
converter = DocumentConverter()
files_to_parse = ["2606_12386v1_txt.txt", "2606.12386v1_pdf.pdf"]

for file_name in files_to_parse:
    if not os.path.exists(file_name):
        print(f"⚠️ 找不到檔案 {file_name}，跳過處理。")
        continue
        
    print(f"\n--- 📄 開始解析檔案: {file_name} ---")
    
    # Docling 自動辨識格式並進行 Layout-Aware Parsing
    result = converter.convert(file_name)
    
    # 轉成大模型最愛的 Markdown 格式純文字
    parsed_markdown = result.document.export_to_markdown()
    
    # 將 Parse 結果存成文字檔
    output_filename = f"parsed_{os.path.splitext(file_name)[0]}.txt"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(parsed_markdown)
    print(f"💾 Parse 完成！乾淨的文本已儲存至: {output_filename}")
    
    # ==========================================
    # 3. [LLM 總結階段]
    # ==========================================
    summary = summarize_with_llm(parsed_markdown)
    
    print("\n💡 【LLM 總結結果】:")
    print(summary)
    print("=" * 40)
    
    