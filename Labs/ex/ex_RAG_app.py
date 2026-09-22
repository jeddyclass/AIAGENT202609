#
# pip install streamlit chromadb sentence-transformers requests mcp
#
# run service:
# streamlit run ex_RAG_app.py

import streamlit as st
import os
import requests
import chromadb
from sentence_transformers import SentenceTransformer

# ==========================================
# 核心組態設定（依用戶端指定變更）
# ==========================================
OPEN_WEBUI_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # 請替換成您在 Open WebUI 後台生成的 API Key
MODEL_NAME = "gemma4_e4b_nothink:latest"
#OPEN_WEBUI_URL = "http://192.168.1.153:8080/api/chat/completions"
#API_KEY = "sk-cebd4fabff5f4b5d8434795173832ba9"
#MODEL_NAME = "gemma4_e4b_nothink:latest"
DB_PATH = "./my_vector_db"
COLLECTION_NAME = "my_rag_collection"

# 初始化物件（利用 Streamlit 快取避免重複載入模型）
@st.cache_resource
def get_resources():
    chroma_client = chromadb.PersistentClient(path=DB_PATH)
    collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
    embed_model = SentenceTransformer("intfloat/multilingual-e5-base")
    return collection, embed_model

collection, embed_model = get_resources()

# 先前實作的純 Python 手寫滑動視窗切片
def slide_window_chunking(text, chunk_size=300, overlap=50):
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk: chunks.append(chunk)
        start += (chunk_size - overlap)
        if text_len - start <= overlap:
            if start < text_len and (text_len - start) > 10:
                chunks.append(text[start:].strip())
            break
    return chunks

# ==========================================
# Streamlit UI 介面佈局
# ==========================================
st.set_page_config(page_title="企業級 RAG 知識庫系統", layout="wide")
st.title("🧠 RAG 知識庫系統 & 向量資料管理中心")

# 側邊欄：文件上傳與管理
with st.sidebar:
    st.header("📄 知識庫文件上傳")
    uploaded_file = st.file_uploader("請選擇要匯入的純文字檔 (.txt)", type=["txt"])
    
    if uploaded_file is not None:
        file_contents = uploaded_file.read().decode("utf-8")
        file_name = uploaded_file.name
        
        if st.button("🚀 開始解析並匯入 Vector DB"):
            with st.spinner("正在進行 [Parse] -> [Chunk] -> [Embed] -> [Store]..."):
                # 1+2. Parse & Chunk
                new_chunks = slide_window_chunking(file_contents)
                
                # 3+4. Embed & Store
                for i, chunk in enumerate(new_chunks):
                    vector = embed_model.encode(f"passage: {chunk}").tolist()
                    chunk_id = f"id_{file_name}_{i}"
                    collection.upsert(
                        embeddings=[vector],
                        documents=[chunk],
                        metadatas=[{"source": file_name}],
                        ids=[chunk_id]
                    )
            st.success(f"✅ 檔案「{file_name}」成功切為 {len(new_chunks)} 塊並存入資料庫！")
    #if uploaded_file is not None:
    #    # 核心安全做法：只 read() 一次，並存進變數
    #    file_bytes = uploaded_file.read()
    #    
    #    try:
    #        file_contents = file_bytes.decode("utf-8")
    #    except UnicodeDecodeError:
    #        # 萬一 UTF-8 讀取失敗，嘗試 Windows 常用的 ANSI/cp950 編碼
    #        file_contents = file_bytes.decode("cp950", errors="ignore")
    #        
    #    file_name = uploaded_file.name
    #    
    #    if st.button("🚀 開始解析並匯入 Vector DB"):
    #        if not file_contents.strip():
    #            st.error("❌ 錯誤：讀取到的檔案內容為空！請檢查檔案是否損壞或被重複讀取。")
    #        else:
    #            with st.spinner("正在進行 [Parse] -> [Chunk] -> [Embed] -> [Store]..."):
    #                new_chunks = slide_window_chunking(file_contents)
    #                
    #                # 偵錯看板：在 UI 上直接秀出切片成果，讓我們肉眼看有沒有斷字
    #                st.write(f"🐞 偵錯資訊：成功切出 {len(new_chunks)} 個區塊，準備寫入...")
    #                
    #                for i, chunk in enumerate(new_chunks):
    #                    vector = embed_model.encode(f"passage: {chunk}").tolist()
    #                    chunk_id = f"id_{file_name}_{i}_{idx}" # 加入額外標記避免 ID 衝突覆蓋
    #                    
    #                    collection.upsert(
    #                        embeddings=[vector],
    #                        documents=[chunk],
    #                        metadatas=[{"source": file_name}],
    #                        ids=[chunk_id]
    #                    )
    #            st.success(f"✅ 檔案「{file_name}」成功匯入！")

            
    st.markdown("---")
    st.subheader("📊 資料庫現況")
    try:
        count = collection.count()
        st.metric(label="目前已儲存的知識塊總數 (Chunks)", value=count)
    except:
        st.metric(label="目前已儲存的知識塊總數 (Chunks)", value=0)

# 主畫面：AI 智能對話聊天室
st.subheader("💬 與你的自建知識庫對話")

# 初始化對話歷史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 顯示歷史對話
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 接收使用者輸入
if user_query := st.chat_input("請問關於已匯入文件的任何問題..."):
    with st.chat_message("user"):
        st.markdown(user_query)
    st.session_state.messages.append({"role": "user", "content": user_query})

    # RAG 檢索流程
    with st.spinner("正在檢索向量資料庫..."):
        #st.write(new_chunks)
        query_vector = embed_model.encode(f"query: {user_query}").tolist()
        
        # 撈出最相關的 2 個區塊提供上下文
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=2
        )
        
        # --- DEBUG 顯示面板 ---
        with st.expander("🐞 RAG 檢索偵錯後台"):
            st.write("**輸入的查詢句：**", user_query)
            st.write("**資料庫回傳的原始 IDs：**", results['ids'])
            st.write("**距離分數 (Distances)：**", results.get('distances', '無分數'))
            st.write("**撈出來的原始文本：**", results['documents'])
        # ----------------------
        
        retrieved_texts = "\n\n".join(results['documents'][0]) if results['documents'] else "無相關參考資料。"

    # 呼叫遠端 LLM
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤖 AI 思考中...")
        
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        rag_prompt = f"請根據以下提供的「參考資料」，嚴格且客觀地回答使用者的「提問」。\n\n【參考資料】\n{retrieved_texts}\n\n【提問】\n{user_query}"
        
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": "你是一個嚴謹的企業知識庫助手。請完全根據給定的參考資料，使用「繁體中文(台灣)」精確回答問題。"},
                {"role": "user", "content": rag_prompt}
            ],
            "temperature": 0.2
        }
        
        try:
            response = requests.post(OPEN_WEBUI_URL, json=payload, headers=headers)
            response.raise_for_status()
            ai_answer = response.json()['choices'][0]['message']['content']
            message_placeholder.markdown(ai_answer)
            st.session_state.messages.append({"role": "assistant", "content": ai_answer})
        except Exception as e:
            error_msg = f"❌ 遠端模型呼叫失敗，請檢查 IP 或 API 金鑰。錯誤: {e}"
            message_placeholder.markdown(error_msg)