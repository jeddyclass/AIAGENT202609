# pip install chromadb
# pip install sentence-transformers
# 新版的 transformers 限制必須使用 PyTorch 2.4 以上 的版本

import hmac, hashlib, base64, json, requests, os
from flask import Flask, request, abort
from pathlib import Path
import chromadb  # 引入 ChromaDB
from sentence_transformers import SentenceTransformer

CONFIG_FILE = Path.home() / '.config/rc-bot/config.env'

app = Flask(__name__)

# 初始化 ChromaDB 客戶端 (指向你的資料庫路徑)
# 注意：chromadb 讀取時通常指定目錄而非單一檔案，它會去讀裡面的 chroma.sqlite3
CHROMA_DB_DIR = "./my_vector_db"
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

embedding_model = SentenceTransformer("intfloat/multilingual-e5-base")

def load_config():
    cfg = {}
    for line in CONFIG_FILE.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return cfg

def verify_signature(body, signature, secret):
    h = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(h).decode(), signature)

def reply_line(reply_token, text, token):
    if len(text) > 4900:
        text = text[:4900] + '...'
    requests.post(
        'https://api.line.me/v2/bot/message/reply',
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Bearer {token}'},
        json={'replyToken': reply_token,
              'messages': [{'type': 'text', 'text': text}]}
    )

def query_vector_db_bak(user_query, threshold=1.2):
    """
    查詢 ChromaDB 向量資料庫
    threshold: 距離閾值 (L2 距離越小越接近，請根據你當初建庫的對齊方式微調，預設 1.2 供參考)
    """
    try:
        # 取得你的 collection，這裡假設名字叫 "documents"，請改成你實際的 collection 名稱
        # 如果不知道名字，可以用 chroma_client.list_collections() 查
        collection = chroma_client.get_collection(name="documents")
        
        # 查詢最接近的前 2 筆資料
        results = collection.query(
            query_texts=[user_query],
            n_results=2
        )
        
        # 檢查是否有內容，且距離（相似度）在合理範圍內
        if results and results['documents'] and len(results['documents'][0]) > 0:
            # 檢查第一筆最像的資料其距離是否小於閾值
            distance = results['distances'][0][0] if 'distances' in results and results['distances'] else 0
            
            # 如果距離太大，視為找不到相關資訊
            if distance > threshold:
                return None
                
            # 將找到的相關文本拼接起來
            context = "\n".join(results['documents'][0])
            return context
    except Exception as e:
        print(f"ChromaDB 查詢出錯: {str(e)}")
        return None
    return None

def query_vector_db(user_query, threshold=0.5):
    """
    查詢 ChromaDB 向量資料庫
    threshold: 距離閾值。因為 e5-base 預設可能是 Cosine 相似度或 L2。
               如果是 Cosine 距離（1 - similarity），通常 0.2 ~ 0.4 算很近，超過 0.5 算遠。
               這裡預設給 0.5，你可以根據實際測試調整。
    """
    try:
        # 使用你當初建立的正確 Collection 名稱
        collection = chroma_client.get_collection(name="my_rag_collection")
        
        # 依據 E5 模型規範：查詢時加上 "query: " 前綴能提高檢索精準度
        formatted_query = f"query: {user_query}"
        
        # 在地端直接將文字轉成向量 (轉成 list 型態)
        query_vector = embedding_model.encode(formatted_query).tolist()
        
        # 使用 query_embeddings 傳入向量，而不是傳入 query_texts
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=2
        )
        
        if results and results['documents'] and len(results['documents'][0]) > 0:
            distance = results['distances'][0][0] if 'distances' in results and results['distances'] else 0
            
            # 如果分數（距離）大於設定的閾值，判定為「找不到相關資訊」
            if distance > threshold:
                return None
                
            context = "\n".join(results['documents'][0])
            return context
    except Exception as e:
        print(f"ChromaDB 查詢出錯: {str(e)}")
        return None
    return None
    
def ask_local_llm(user_message, cfg, system_prompt=None):
    if system_prompt is None:
        system_prompt = "你是一個部署在 Homelab 地端 的 AI 助手。請用繁體中文親切、簡短地回答問題。"

    headers = {
        'Authorization': f"Bearer {cfg['OPENWEBUI_API_KEY']}",
        'Content-Type': 'application/json'
    }
    payload = {
        'model': cfg['LLM_MODEL'],
        'messages': [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        'temperature': 0.7
    }
    try:
        response = requests.post(cfg['OPENWEBUI_API_URL'], headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            res_json = response.json()
            return res_json['choices'][0]['message']['content'].strip()
        else:
            return f"❌ 地端 LLM 回傳錯誤 (Status: {response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ 無法連線至地端 LLM: {str(e)}"

@app.route('/webhook', methods=['POST'])
def webhook():
    cfg  = load_config()
    body = request.get_data()
    sig  = request.headers.get('X-Line-Signature', '')

    if not verify_signature(body, sig, cfg['LINE_CHANNEL_SECRET']):
        abort(400)

    for event in json.loads(body).get('events', []):
        if event.get('type') != 'message':
            continue
        if event['message'].get('type') != 'text':
            continue

        sender_uid = event.get('source', {}).get('userId', '')
        reply_token = event.get('replyToken')
        user_text   = event['message']['text'].strip()
        token       = cfg['LINE_CHANNEL_ACCESS_TOKEN']

        # ── 臨時功能：讓管理者查自己的 LINE UID ──
        if user_text == '#uid':
            reply_line(reply_token, f'你的 LINE UID：{sender_uid}', token)
            continue

        # ── 白名單檢查 ──
        if cfg.get('ALLOWED_UID', '') == '' or cfg.get('ALLOWED_UID') == '先留空_等Step5取得後再填入':
            reply_line(reply_token, f'⚠️ 系統尚未設定安全白名單。請傳送 #uid 取得您的 UID 並寫入設定檔。', token)
            continue

        if sender_uid != cfg.get('ALLOWED_UID', ''):
            continue

        # ── RAG 向量資料庫檢索 ──
        db_context = query_vector_db(user_text)

        if db_context is None:
            # 【情境 1】：ChromaDB 內找不到相關資訊
            # 1. 先行準備告知找不到的文字
            reply_prefix = "在現有資料庫內沒有相關資訊\n\n但我的理解可能是<<以下為AI主動回覆,請謹慎使用>>:\n"
            
            # 2. 轉向 LLM 基本能力取得回覆
            llm_response = ask_local_llm(user_text, cfg)
            final_reply = reply_prefix + llm_response
        else:
            # 【情境 2】：ChromaDB 有找到資訊
            # 1. 重新設計 System Prompt，把資料庫內容餵給 LLM 順一順
            rag_system_prompt = (
                "你是一個部署在 Homelab 地端的 AI 助手。\n"
                "請根據以下提供的【參考資料】，用繁體中文親切、精簡地回答使用者的問題。\n"
                "如果參考資料與問題無關，請忽略它。\n\n"
                f"【參考資料】:\n{db_context}"
            )
            llm_response = ask_local_llm(user_text, cfg, system_prompt=rag_system_prompt)
            final_reply = f"現有資料庫有相關資訊, 請參考:\n\n{llm_response}"

        # ── 統一回覆給 LINE ──
        reply_line(reply_token, final_reply, token)

    return 'OK'

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050)