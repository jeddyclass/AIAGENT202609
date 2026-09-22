import json
import requests

# 1. 環境變數與設定要求
#API_KEY = "sk-cebd4fabff5f4b5d8434795173832ba9"
#ENDPOINT = "http://192.168.1.153:8080/api/chat/completions"
#MODEL_NAME = "gemma4_e4b_nothink:latest"
ENDPOINT = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"  # 請替換成您在 Open WebUI 後台生成的 API Key
MODEL_NAME = "gemma4_e4b_nothink:latest"

#def call_local_llm(prompt: str, max_tokens: int = 200) -> str:
#    """呼叫本地 gemma4_e4b_nothink:latest 模型的輔助函式"""
#    headers = {
#        "Authorization": f"Bearer {API_KEY}",
#        "Content-Type": "application/json"
#    }
#    
#    # 由於題目指定的是 /v1/completions (Text Completion API) 而非 /v1/chat/completions
#    # 我們使用單一 Prompt 文本進行請求
#    payload = {
#        "model": MODEL_NAME,
#        "prompt": prompt,
#        "max_tokens": max_tokens,
#        "temperature": 0.3
#    }
#    
#    try:
#        response = requests.post(ENDPOINT, headers=headers, json=payload)
#        response.raise_for_status()
#        result = response.json()
#        return result["choices"][0]["text"].strip()
#    except Exception as e:
#        return f"【LLM 呼叫失敗】: {str(e)}。請確認 Ollama 是否在 8080 port 服務且已下載 {MODEL_NAME}"
#def call_local_llm(prompt: str, max_tokens: int = 200) -> str:
#    """呼叫本地 gemma4_e4b_nothink:latest 模型的輔助函式"""
#    headers = {
#        "Authorization": f"Bearer {API_KEY}",
#        "Content-Type": "application/json"
#    }
#    
#    payload = {
#        "model": MODEL_NAME,
#        "prompt": prompt,
#        "max_tokens": max_tokens,
#        "temperature": 0.3
#    }
#    
#    try:
#        response = requests.post(ENDPOINT, headers=headers, json=payload)
#        response.raise_for_status()
#        result = response.json()
#        
#        # 修正點：優先讀取 Chat 格式的 content，如果沒有才讀取傳統 Text 格式的 text
#        choice = result["choices"][0]
#        if "message" in choice and "content" in choice["message"]:
#            return choice["message"]["content"].strip()
#        elif "text" in choice:
#            return choice["text"].strip()
#        else:
#            return f"【格式解析失敗】: 無法從回傳資料中找到文字欄位。回傳內容: {json.dumps(result)}"
#            
#    except Exception as e:
#        return f"【LLM 呼叫失敗】: {str(e)}。請確認 Ollama 是否在 8080 port 服務且已下載 {MODEL_NAME}"
def call_local_llm(prompt: str, max_tokens: int = 200) -> str:
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 修正點：Chat API 必須包成 messages 格式
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # 修正點：從標準的 OpenAI 格式中取出文字
        return result["choices"][0]["message"]["content"].strip()
        
    except Exception as e:
        return f"【LLM 呼叫失敗】: {str(e)}。請確認 API 伺服器狀態。"
        
# ==========================================
# 2. 說明各級記憶的的意義 (程式碼定義)
# ==========================================
print("==========================================")
print(" 1. 說明各級記憶的意義 (架構初始化)")
print("==========================================")

class AgentMemorySystem:
    def __init__(self):
        # 短期記憶：儲存最近幾輪的精確對話（維持當前話題細節）
        self.short_term_memory = [] 
        self.short_term_limit = 3  # 最多存 3 輪對話，超過就必須壓縮
        
        # 長期記憶摘要：經過壓縮後的歷史事實，會永久累加
        self.long_term_summary = "使用者初次加入對話。" 
        
        # 長期語義記憶庫：模擬 RAG 向量資料庫，用來做特徵比對（此處用簡易關鍵字模擬）
        self.long_term_rag_store = {
            "程式語言": "使用者表示他最常使用的後端語言是 Python。",
            "硬體環境": "使用者正在 M3 Max 晶片的 Mac 上運行本地 AI 實驗。"
        }

    # ==========================================
    # 3. 使用LLM 做應用時 (記，以及取用) 的例子
    # ==========================================
    def recall_context(self, user_input: str) -> str:
        """【取用記憶】將長期、短期與 RAG 記憶拼裝成 Prompt"""
        print("\n⚡ [記憶檢索中...] 正在為 LLM 組裝大腦背景...")
        
        # A. 提取 RAG 長期記憶 (根據使用者關鍵字匹配)
        rag_knowledge = ""
        for key, value in self.long_term_rag_store.items():
            if key in user_input:
                rag_knowledge += f"- 歷史偏好紀錄: {value}\n"
        
        # B. 建立給 LLM 的上下文 Prompt
        context_prompt = "你是個高效率的 AI 助理。請根據以下記憶背景回答使用者。\n"
        context_prompt += f"【長期歷史摘要】: {self.long_term_summary}\n"
        if rag_knowledge:
            context_prompt += f"【RAG 檢索到的長期偏好】:\n{rag_knowledge}"
            
        context_prompt += "【近期短期對話】:\n"
        for chat in self.short_term_memory:
            context_prompt += f"User: {chat['user']}\nAI: {chat['ai']}\n"
            
        context_prompt += f"\nUser最新提問: {user_input}\nAI回答:"
        return context_prompt

    def remember(self, user_input: str, ai_response: str):
        """【記住記憶】儲存至短期記憶，並在必要時執行『壓縮』"""
        # 寫入短期記憶
        self.short_term_memory.append({"user": user_input, "ai": ai_response})
        print(f"📥 [記入短期記憶] 當前短期記憶輪數: {len(self.short_term_memory)}/{self.short_term_limit}")
        
        # 判斷是否需要【壓縮】
        if len(self.short_term_memory) >= self.short_term_limit:
            self.compress_memory()

    def compress_memory(self):
        """【壓縮機制】使用 LLM 將短期記憶提煉並融入長期記憶摘要，隨後清空短期記憶"""
        print("\n🚨 [觸發記憶壓縮] 短期記憶已滿！正在召喚 gemma4_e4b_nothink:latest 進行記憶提煉...")
        
        # 建立壓縮專用的 Prompt
        compress_prompt = (
            "請將以下的【目前長期摘要】與【新對話紀錄】融合成一段全新、精簡的長期歷史摘要。\n"
            "只保留使用者的核心人設、提到過的事實與重要偏好，字數請控制在 50 字內。\n\n"
            f"【目前長期摘要】: {self.long_term_summary}\n"
            "【新對話紀錄】:\n"
        )
        for chat in self.short_term_memory:
            compress_prompt += f"User: {chat['user']} -> AI: {chat['ai']}\n"
            
        compress_prompt += "\n請輸出全新融合後的歷史摘要:"
        
        # 呼叫 LLM 進行壓縮
        new_summary = call_local_llm(compress_prompt, max_tokens=100)
        
        print(f"📝 [壓縮成功] 舊摘要: {self.long_term_summary}")
        print(f"✨ [壓縮成功] 新摘要: {new_summary}")
        
        # 更新長期記憶摘要，並清空短期記憶清單
        self.long_term_summary = new_summary
        self.short_term_memory.clear()
        print("🧹 [清理完畢] 短期記憶已清空，成功釋放 Context Window 空間！\n")


# ==========================================
# 4. 實際模擬對話工作流
# ==========================================
if __name__ == "__main__":
    # 初始化記憶系統
    agent_brain = AgentMemorySystem()

    # 模擬對話 1：觸發 RAG 長期記憶
    print("\n--- 🟢 第一輪對話（測試 RAG 讀取） ---")
    user_q1 = "嗨，我今天想寫點程式語言，你有什麼建議的框架嗎？"
    full_prompt = agent_brain.recall_context(user_q1)
    ai_res1 = call_local_llm(full_prompt)
    print(f"User: {user_q1}")
    print(f"AI: {ai_res1}")
    agent_brain.remember(user_q1, ai_res1)

    # 模擬對話 2：連續對話（記入短期記憶）
    print("\n--- 🟢 第二輪對話（記入短期記憶） ---")
    user_q2 = "那你可以幫我用這個語言寫一個 Hello World 嗎？" # 這裡的「這個語言」依賴短期或 RAG 記憶
    full_prompt = agent_brain.recall_context(user_q2)
    ai_res2 = call_local_llm(full_prompt)
    print(f"User: {user_q2}")
    print(f"AI: {ai_res2}")
    agent_brain.remember(user_q2, ai_res2)

    # 模擬對話 3：達到短期記憶上限，觸發 LLM 記憶壓縮
    print("\n--- 🟢 第三輪對話（觸發記憶壓縮機制） ---")
    user_q3 = "太棒了，明天我預計會在我的新硬體環境上測試這個服務。"
    full_prompt = agent_brain.recall_context(user_q3)
    ai_res3 = call_local_llm(full_prompt)
    print(f"User: {user_q3}")
    print(f"AI: {ai_res3}")
    # 這一輪記完後，因為達到 3 輪限制，會自動在 function 內部呼叫 LLM 做 compress_memory()
    agent_brain.remember(user_q3, ai_res3)
    
    # 模擬對話 4：驗證壓縮後的長期記憶是否生效
    print("\n--- 🟢 第四輪對話（驗證壓縮後的長期記憶） ---")
    user_q4 = "對了，你知道我剛剛說明天要在哪裡測試程式嗎？"
    full_prompt = agent_brain.recall_context(user_q4)
    ai_res4 = call_local_llm(full_prompt)
    print(f"User: {user_q4}")
    print(f"AI: {ai_res4}")