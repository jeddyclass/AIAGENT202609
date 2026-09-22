import numpy as np
import requests
import json

# ==========================================
# 環境設定 (符合您的 local LLM 需求)
# ==========================================
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"
PORT = "8080"
ENDPOINT = "/api/chat/completions"
# 根據您的設定，通常 Ollama/OpenWebUI 的完整路徑如下：
URL = f"http://172.10.0.2:{PORT}{ENDPOINT}" 
MODEL_NAME = "gemma4_e4b_nothink:latest"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ==========================================
# 第一部份：說明 Cosine Similarity 的意義
# ==========================================
def explain_cosine_similarity():
    print("=== 1. Cosine Similarity (餘弦相似度) 的意義 ===")
    explanation = """
    根據 Tom Hazledine 的文章指出：
    1. 幾何意義：將文字轉換成向量（Vector）後，它們可以被視為多維空間中的「點」或「方向」。
       Cosine Similarity 測量的是兩個向量之間的『夾角（θ）』的餘弦值，而非點與點之間的直線距離。
    
    2. 公式： d(A, B) = cos(θ) = (A · B) / (||A|| × ||B||)
       也就是兩個向量的「點積 (Dot Product)」除以它們「模長 (Magnitude) 的乘積」。
    
    3. 特點與 LLM 應用：
       - 值介於 -1 到 1 之間（在 LLM 文本嵌入中通常為 0 到 1）。1 表示方向完全相同（語意極度相似），0 表示正交（毫無關聯）。
       - 在 LLM Embeddings（文本嵌入）中，向量代表的是文字的「語意（Meaning）」。
       - 關鍵點：諸如 OpenAI 或許多現代 Embedding 模型，輸出的向量都已經過「歸一化 (Normalized，模長為 1)」。
         此時，||A|| 和 ||B|| 都等於 1，公式可以簡化為：Normalized cos(θ) = A · B (純點積)。
         這使得計算變得極快，也是為什麼它成為 RAG（檢索增強生成）中最推崇的相似度計算方式。
    """
    print(explanation)

# 手動實作一個簡單的 Cosine Similarity 計算函式
def calculate_cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    # 點積
    dot_product = np.dot(vec1, vec2)
    # 模長
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
    return float(dot_product / (norm_vec1 * norm_vec2))


# ==========================================
# 第二部份：以 LLM 做應用時的例子 (RAG 語意檢索模擬)
# ==========================================
def run_llm_application_example():
    print("\n=== 2. 以 LLM 做應用時的例子 (語意相似度模擬) ===")
    
    # 這裡我們模擬 LLM Embedding 模型將 3 個句子轉換為向量的結果 (假設為3維空間簡化版)
    # 實務上 LLM 的 Embedding 通常是 1536 或 4096 維度
    database = {
        "蘋果是一種很好吃的水果。": [0.9, 0.1, 0.2],
        "微軟推出了最新的作業系統。": [0.1, 0.8, 0.9],
        "香蕉富含鉀離子，對健康有益。": [0.85, 0.15, 0.1]
    }
    
    # 使用者輸入的搜尋問題 (Query)
    user_query = "我想吃點甜甜的水果"
    query_vector = [0.88, 0.12, 0.15] # 模擬這個問題被 Embedding 轉換後的向量
    
    print(f"使用者搜尋: '{user_query}'\n")
    print("計算知識庫中各句子的 Cosine Similarity 比對中...")
    
    best_match_text = ""
    highest_similarity = -1
    
    for text, vector in database.items():
        similarity = calculate_cosine_similarity(query_vector, vector)
        print(f" -> 與「{text}」的相似度: {similarity:.4f}")
        
        if similarity > highest_similarity:
            highest_similarity = similarity
            best_match_text = text
            
    print(f"\n[檢索結果] 最相關的背景知識是: '{best_match_text}' (相似度: {highest_similarity:.4f})")
    
    # --- 將檢索到的資料送到 Local LLM 進行 RAG 問答 ---
    print(f"\n正在將最相關的資料傳送至 Local LLM ({MODEL_NAME}) 進行生成...")
    
    # 建立 RAG 的 Prompt
    prompt = f"""根據以下提供的背景知識，回答使用者的問題。
背景知識：{best_match_text}
使用者問題：{user_query}
請簡短回答："""

    # 封裝傳送給 Ollama / OpenWebUI 的資料 (採用 /v1/completions 格式)
    payload = {
        "model": MODEL_NAME,  # 加上 ollama/
        "messages": [
            {
                "role": "user",
                "content": f"根據以下提供的背景知識，回答使用者的問題。\n背景知識：{best_match_text}\n使用者問題：{user_query}\n請簡短回答："
            }
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(URL, headers=headers, data=json.dumps(payload), timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            # 2. 解析 Chat 格式的回傳結果
            llm_response = result['choices'][0]['message']['content'].strip()
            print("\n=== LLM 回覆結果 ===")
            print(llm_response)
        else:
            print(f"\n呼叫 LLM 失敗，錯誤碼: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"\n無法連線到 Local LLM 端點 ({URL})。請確認 Ollama 與 OpenWebUI 是否已啟動。")
        print(f"錯誤訊息: {e}")

# ==========================================
# 主程式執行
# ==========================================
if __name__ == "__main__":
    # 1. 說明意義
    explain_cosine_similarity()
    
    # 2. 應用範例
    run_llm_application_example()