# pip install chromadb sentence-transformers requests

import os
import requests
import chromadb
from sentence_transformers import SentenceTransformer

# ==========================================
# 1. 設定 Open WebUI / Ollama API
# ==========================================
OPEN_WEBUI_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # 請替換成您在 Open WebUI 後台生成的 API Key
MODEL_NAME = "gemma4_e4b_nothink:latest"

INPUT_FILE = "chunks_2606.12386v1_pdf_output.txt"

# ==========================================
# 2. 初始化本地向量資料庫 (Chroma) 與 Embedding 模型
# ==========================================
print("📁 正在初始化本地 Chroma DB (資料將儲存在 ./my_vector_db 資料夾)...")
# PersistentClient 會自動在本地建立資料夾存檔，重啟程式資料不會不見
chroma_client = chromadb.PersistentClient(path="./my_vector_db")

# 建立一個叫做 "my_rag_collection" 的資料庫表格 (Collection)
# 如果已經存在就直接讀取
collection = chroma_client.get_or_create_collection(name="my_rag_collection")

print("🚀 正在載入微軟 e5 多語言模型...")
embed_model = SentenceTransformer("intfloat/multilingual-e5-base")

# ==========================================
# 3. 讀取並解析先前儲存的 Chunks
# ==========================================
if not os.path.exists(INPUT_FILE):
    print(f"⚠️ 找不到 {INPUT_FILE}，請確保該檔案存在。")
    exit()

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

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

# ==========================================
# 4. [Store to Vector DB 階段] 生成向量並寫入資料庫
# ==========================================
print(f"🧬 正在將 {len(chunks)} 個 Chunks 轉換為向量並寫入 Vector DB...")

for idx, chunk in enumerate(chunks, 1):
    # 微軟 e5 規範：文檔前要加 "passage: "
    vector = embed_model.encode(f"passage: {chunk}").tolist()
    
    # 存入資料庫：需要提供 向量、原始文字、以及唯一的 ID
    collection.upsert(
        embeddings=[vector],
        documents=[chunk],
        ids=[f"id_{idx}"]
    )

print("💾 儲存成功！所有知識塊已進入向量資料庫中。")
print("=" * 50)

# ==========================================
# 5. 【RAG 測試：模擬使用者提問與檢索】
# ==========================================
user_query = "手機本地執行 AI 有什麼好處？"
print(f"❓ 使用者提問：{user_query}")

# 微軟 e5 規範：查詢句前要加 "query: "
query_vector = embed_model.encode(f"query: {user_query}").tolist()

# 讓 Vector DB 進行「語意相似度檢索」，撈出最相關的 1 個 Chunk
results = collection.query(
    query_embeddings=[query_vector],
    n_results=1
)

retrieved_context = results['documents'][0][0]
print(f"🔍 Vector DB 瞬間撈出的最相關知識塊：\n{retrieved_context}\n")
print("=" * 50)

# ==========================================
# 6. 【RAG 終點站：把撈出來的資料餵給 Ollama LLM】
# ==========================================
print(f"🤖 正在將問題與參考資料提交給 {MODEL_NAME} 生成回答...<<第一題>>")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 經典的 RAG Prompt 模板
rag_prompt = f"""請根據以下提供的「參考資料」，嚴格且客觀地回答使用者的「提問」。如果參考資料中沒有提到，請回答「不知道」。

【參考資料】
{retrieved_context}

【提問】
{user_query}
"""

payload = {
    "model": MODEL_NAME,
    "messages": [
        {
            "role": "system",
            "content": "你是一個嚴謹的企業知識庫助手。請完全根據給定的參考資料，使用「繁體中文(台灣)」精確回答問題，不要胡扯或瞎編。"
        },
        {
            "role": "user",
            "content": rag_prompt
        }
    ],
    "temperature": 0.2
}

try:
    response = requests.post(OPEN_WEBUI_URL, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    answer = result['choices'][0]['message']['content']
    print(f"\n💡 【Gemma4 的最終 RAG 回答】:\n{answer}")
except Exception as e:
    print(f"❌ 呼叫 Ollama 失敗: {e}")

####

# ==========================================
# 7. 【RAG 測試：模擬使用者提問與檢索】 round 2
# ==========================================
user_query = "你知道ATLAS嗎?"
print(f"❓ 使用者提問：{user_query}")

# 微軟 e5 規範：查詢句前要加 "query: "
query_vector = embed_model.encode(f"query: {user_query}").tolist()

# 讓 Vector DB 進行「語意相似度檢索」，撈出最相關的 1 個 Chunk
results = collection.query(
    query_embeddings=[query_vector],
    n_results=1
)

retrieved_context = results['documents'][0][0]
print(f"🔍 Vector DB 瞬間撈出的最相關知識塊：\n{retrieved_context}\n")
print("=" * 50)

# ==========================================
# 8. 【RAG 終點站：把撈出來的資料餵給 Ollama LLM】 v2
# ==========================================
print(f"🤖 正在將問題與參考資料提交給 {MODEL_NAME} 生成回答...<<第二題>>")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 經典的 RAG Prompt 模板
rag_prompt = f"""請根據以下提供的「參考資料」，嚴格且客觀地回答使用者的「提問」。如果參考資料中沒有提到，請回答「不知道」。

【參考資料】
{retrieved_context}

【提問】
{user_query}
"""

payload = {
    "model": MODEL_NAME,
    "messages": [
        {
            "role": "system",
            "content": "你是一個嚴謹的企業知識庫助手。請完全根據給定的參考資料，使用「繁體中文(台灣)」精確回答問題，不要胡扯或瞎編。"
        },
        {
            "role": "user",
            "content": rag_prompt
        }
    ],
    "temperature": 0.2
}

try:
    response = requests.post(OPEN_WEBUI_URL, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    answer = result['choices'][0]['message']['content']
    print(f"\n💡 【Gemma4 的最終 RAG 回答】:\n{answer}")
except Exception as e:
    print(f"❌ 呼叫 Ollama 失敗: {e}")
