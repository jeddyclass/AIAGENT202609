import os
import requests

# ==========================================
# 1. 設定 Open WebUI / Ollama API
# ==========================================
OPEN_WEBUI_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # 請替換成您在 Open WebUI 後台生成的 API Key
MODEL_NAME = "gemma4_e4b_nothink:latest"


INPUT_FILE = "parsed_2606.12386v1_pdf.txt"
OUTPUT_FILE = "chunks_2606.12386v1_pdf_output.txt"

# ==========================================
# 2. 檢查並讀取 Parse 後的檔案
# ==========================================
if not os.path.exists(INPUT_FILE):
    # 如果找不到檔案，我們建立一個模擬的 PDF 解析文字供測試
    print(f"⚠️ 找不到 {INPUT_FILE}，將自動生成模擬的 PDF 解析文本進行演示...")
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        f.write(
            "# 深度學習在 2026 年的最新進展\n\n"
            "## 1. 摘要\n本文探討了大型語言模型（LLM）與檢索增強生成（RAG）的融合。RAG 系統能有效解決模型幻覺問題。\n\n"
            "## 2. 核心架構\n整個建構向量資料庫的步驟包含解析、切片與向量化。其中，[Chunk] 切片步驟決定了檢索的顆粒度。"
            "如果切片太大，會引入太多雜訊；如果切片太小，則會遺失關鍵的上下文背景。因此，合理的重疊（Overlap）是必要的。\n\n"
            "## 3. 實驗結果\n經測試，使用 300 字大小搭配 50 字重疊的配置，在繁體中文知識庫的檢索準確度表現最佳，大幅提升了企業應用的實用性。"
        )

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    source_text = f.read()

print(f"📖 成功讀取 {INPUT_FILE}，總字數：{len(source_text)} 字。")

# ==========================================
# 3. [Chunk 階段] 純 Python 滑動視窗切片函式
# ==========================================
def slide_window_chunking(text, chunk_size=300, overlap=50):
    """
    純 Python 實現的固定長度滑動視窗切片
    """
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()
        
        if chunk:
            chunks.append(chunk)
            
        # 往後滑動：新起點 = 目前終點 - 重疊字數
        start += (chunk_size - overlap)
        
        # 剩餘字數不足以支撐下一個有意義的 chunk 時就跳出
        if text_len - start <= overlap:
            # 如果最後還剩下一點點尾巴，就全部打包進去
            if start < text_len and (text_len - start) > 10:
                chunks.append(text[start:].strip())
            break
            
    return chunks

# 執行切片
all_chunks = slide_window_chunking(source_text, chunk_size=300, overlap=50)

# ==========================================
# 4. 將 Chunk 結果寫入新檔案
# ==========================================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(f"=== 檔案 {INPUT_FILE} 的 Chunk 切片結果 ===\n")
    f.write(f"參數設定: Chunk Size = 300, Overlap = 50\n")
    f.write(f"總共切出: {len(all_chunks)} 個區塊\n")
    f.write("=" * 50 + "\n\n")
    
    for idx, chunk in enumerate(all_chunks, 1):
        f.write(f"--- [CHUNK_ID: {idx}] | 字數: {len(chunk)} ---\n")
        f.write(chunk + "\n")
        f.write("-" * 50 + "\n\n")

print(f"💾 Chunk 處理完畢！切片後的檔案已儲存至: {OUTPUT_FILE}")

# ==========================================
# 5. 抽取第一個 Chunk 丟給 Ollama 進行總結驗證
# ==========================================
if all_chunks:
    test_chunk = all_chunks[0]
    print(f"\n🚀 隨機挑選 [Chunk 1] 丟給 {MODEL_NAME} 進行測試...")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "你是一個 RAG 資料庫管理員。請用「繁體中文(台灣)」針對以下這段剛切片出來的知識塊（Chunk），進行一句話的重點摘要。"
            },
            {
                "role": "user",
                "content": f"請摘要這段 Chunk：\n\n{test_chunk}"
            }
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(OPEN_WEBUI_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()
        summary = result['choices'][0]['message']['content']
        print(f"\n🤖 Gemma4 針對 [Chunk 1] 的摘要回報：\n{summary}")
    except Exception as e:
        print(f"❌ 呼叫 Ollama/Open WebUI 失敗: {e}")