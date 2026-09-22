# pip install sentence-transformers requests

import os
import requests
from sentence_transformers import SentenceTransformer


# ==========================================
# 1. 設定 Open WebUI / Ollama API
# ==========================================
OPEN_WEBUI_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # 請替換成您在 Open WebUI 後台生成的 API Key
MODEL_NAME = "gemma4_e4b_nothink:latest"

INPUT_FILE = "chunks_2606.12386v1_pdf_output.txt"

# ==========================================
# 2. 讀取先前儲存的 Chunks 檔案並還原
# ==========================================
if not os.path.exists(INPUT_FILE):
    print(f"⚠️ 找不到 {INPUT_FILE}，請確保上一步的產出檔案存在。")
    exit()

print(f"📖 正在讀取 {INPUT_FILE}...")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

# 從檔案中解析出純粹的 chunk 內容
chunks = []
current_chunk = []
is_reading_content = False

for line in lines:
    if line.startswith("--- [CHUNK_ID:"):
        is_reading_content = True
        current_chunk = []
    elif line.startswith("--------------------------------------------------"):
        is_reading_content = False
        chunk_text = "".join(current_chunk).strip()
        if chunk_text:
            chunks.append(chunk_text)
    elif is_reading_content:
        current_chunk.append(line)

print(f"✅ 成功提取出 {len(chunks)} 個原始文字區塊（Chunks）。")

# ==========================================
# 3. [Embed 階段] 載入微軟 e5 多語言模型並生成向量
# ==========================================
print("\n🚀 正在本地載入微軟 e5 多語言模型 (multilingual-e5-base)...")
# 第一次執行會自動下載模型，之後就會直接從本地快取讀取
model = SentenceTransformer("intfloat/multilingual-e5-base")

print("🧬 開始將 Chunks 轉換為 Embedding 向量...")
# 微軟 e5 模型有一個特殊規範：為了達到最佳效果，檢索文檔前要加上 "passage: " 
e5_inputs = [f"passage: {chunk}" for chunk in chunks]
vectors = model.encode(e5_inputs)

print("✨ 向量化完成！")
for idx, vec in enumerate(vectors, 1):
    # e5-base 的標準維度是 768 維
    print(f"   - [Chunk {idx}] 已成功轉換為 {len(vec)} 維的數字向量。前 5 個數字為: {vec[:5]}")

# ==========================================
# 4. 呼叫 Ollama / Open WebUI 進行語意理解確認
# ==========================================
# 拿第一個 Chunk 的向量特徵與內容，請 LLM 驗證
test_chunk = chunks[0]
test_vector_str = str(list(vectors[0][:3])) + " ... (省略其餘 765 個數字) ]"

print(f"\n🤖 正在將向量化結果提交給 {MODEL_NAME} 進行最終驗證...")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": MODEL_NAME,
    "messages": [
        {
            "role": "system",
            "content": "你是一個 RAG 系統架構師。請用「繁體中文(台灣)」客觀且白話地向工程師解釋目前的 Embedding 成果。"
        },
        {
            "role": "user",
            "content": (
                f"我剛剛將以下這段文字：\n「{test_chunk}」\n\n"
                f"成功透過微軟 e5 模型轉換成了 768 維的向量，長相大概是：\n{test_vector_str}\n\n"
                f"請用兩句話告訴我，這個 [Embed] 步驟成功為未來的「向量資料庫檢索」帶來了什麼好處？"
            )
        }
    ],
    "temperature": 0.3
}

try:
    response = requests.post(OPEN_WEBUI_URL, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    summary = result['choices'][0]['message']['content']
    print(f"\n💡 【Gemma4 的架構師回應】:\n{summary}")
except Exception as e:
    print(f"❌ 呼叫 Ollama 失敗: {e}")
    