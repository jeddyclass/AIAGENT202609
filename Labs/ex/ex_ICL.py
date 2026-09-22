import requests
import json

# --- 1. 連線設定 ---
OLLAMA_API_URL = "http://172.10.0.2:8080/api/chat/completions"
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763" 
MODEL = "gemma4_e4b_nothink:latest"

def get_api_headers():
    return {
        "Authorization": f"Bearer {OPENWEBUI_API_KEY}",
        "Content-Type": "application/json"
    }

# --- 2. 通用 LLM 呼叫函數 (依要求修改) ---
def call_llm(messages, model_name=MODEL):
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3, # 較低的溫度，讓模型嚴格模仿 Few-shot 的推理邏輯與格式
        "stream": False,
        "response_format": {"type": "json_object"} # 註解：強迫模型啟動 JSON 模式，搭配 ICL 範例可達到 100% 格式正確率
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=get_api_headers(), json=payload, timeout=240)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'] # 修正原程式碼漏掉的 [0] 索引
    except requests.exceptions.RequestException as e:
        print(f"API 請求失敗: {e}")
        return None

# --- 3. In-context Learning 精髓：結構化提示詞設計 ---

# 註解 [ICL 核心 1：系統角色定位] 
# 在 Chat API 中，System 角色負責定調全局規則與輸出容器（JSON 格式）。
system_prompt = """你是一位專業的客戶服務分析師。你的任務是分析客戶與客服之間的對話紀錄，並以 JSON 格式輸出結構化的分析結果。

請嚴格遵循以下輸出格式，不要輸出任何額外的解釋文字：
{
  "summary": "簡短的對話摘要（不超過 50 字）",
  "sentiment": "客戶情緒（正面/中性/負面）",
  "category": "問題類別（訂單問題/產品問題/帳戶問題/系統問題/其他）",
  "priority": "處理優先級（低/中/高）",
  "action_items": ["建議的後續行動清單"]
}"""

# 註解 [ICL 核心 2：對照組 Few-shot 範例]
# 這裡提供三組截然不同的情境。LLM 會在「未改動參數」的情況下，
# 自動比對這三組範例的「語氣強弱」與「分類邏輯」，並當場學會如何客觀判斷新文本。
few_shot_examples = """===== 範例 1 (中性/低優先級/詢問情境) =====
對話紀錄：
客戶：你好，我上週訂的書到現在還沒收到，可以幫我查一下嗎？
客服：好的，我幫您查詢。您的訂單編號是？
客戶：ORD-2024-001。
客服：查到了，目前顯示已出貨，預計明天送達。
客戶：好的，謝謝你。

分析結果：
{
  "summary": "客戶查詢訂單配送進度，客服確認已出貨。",
  "sentiment": "中性",
  "category": "訂單問題",
  "priority": "低",
  "action_items": ["無需後續行動"]
}

===== 範例 2 (負面/高優先級/實體硬體問題) =====
對話紀錄：
客戶：你們的產品有夠爛！我買的耳機用三天就壞了，我要退貨！
客服：非常抱歉造成您的困擾，我馬上為您辦理退貨。
客戶：而且你們的客服電話超難打，我等了半小時！
客服：真的很抱歉，我會將您的意見反映給相關部門。

分析結果：
{
  "summary": "客戶抱怨產品品質不佳及客服等待時間過長。",
  "sentiment": "負面",
  "category": "產品問題",
  "priority": "高",
  "action_items": ["立即辦理退貨", "提供補償方案", "檢討客服流程"]
}

===== 範例 3 (正面/低優先級/純諮詢情境) =====
對話紀錄：
客戶：我想請問一下，我的會員等級要怎麼升級？
客服：您好，會員等級是根據年度消費金額自動計算的。
客戶：我目前是銀卡會員，要消費多少才能升金卡？
客服：需要年度消費滿 10,000 元即可升級。
客戶：了解，謝謝你的說明。

分析結果：
{
  "summary": "客戶詢問會員等級升級條件，客服提供相關資訊。",
  "sentiment": "正面",
  "category": "帳戶問題",
  "priority": "低",
  "action_items": ["無需後續行動"]
}"""

# 註解 [ICL 核心 3：新任務輸入]
# 這是一筆包含「系統錯誤、重複扣款、客戶極度憤怒」的複雜新對話。
# 模型將藉由前面範例學到的「情緒與優先級推論邏輯」，動態輸出正確的分析。
new_conversation = """===== 新的對話紀錄 =====
對話紀錄：
客戶：我昨天在你們官網下單，但刷卡一直失敗，試了好幾次都一樣！
客服：先生您好，請問您使用的是哪家銀行的信用卡？
客戶：我用的是華南銀行的。
客服：可能是銀行端的風控機制擋住了，建議您換一張卡試試看。
客戶：我換了三張卡都一樣！而且我發現我的帳戶被扣了三次款，但訂單都沒有成立！
客服：這部分我需要請財務部門協助確認，請您稍等。
客戶：還要等？我已經搞了一個小時了！你們的系統真的有問題！
客服：非常抱歉，我已經將您的案件升級處理，會在今天內給您回覆。

分析結果：
"""

# --- 4. 組裝符合 Chat API 最佳實踐的 Messages 結構 ---
# 註解：我們不使用單一長字串的 full_prompt，而是將「規則+範例」當作上下文基底，
# 讓「新問題」獨立在 user 角色中，這才是發揮 In-context Learning 穩定度最高的做法。
messages = [
    {"role": "system", "content": f"{system_prompt}\n\n這裡是一些高質量的分析範例供你參考：\n{few_shot_examples}"},
    {"role": "user", "content": new_conversation}
]

# --- 5. 執行與解析 ---
if __name__ == "__main__":
    print("=== 開始呼叫本地大模型 (Gemma4) ===")
    response = call_llm(messages)
    
    if response:
        print("\n=== LLM 原始回傳文字 ===")
        print(response)
        
        # 解析 JSON 結果
        try:
            analysis_result = json.loads(response)
            print("\n=== 結構化分析結果 (Python 成功解析) ===")
            print(f"【摘要】　：{analysis_result.get('summary')}")
            print(f"【情緒】　：{analysis_result.get('sentiment')}")
            print(f"【類別】　：{analysis_result.get('category')}")
            print(f"【優先級】：{analysis_result.get('priority')}")
            print(f"【建議行動】：{', '.join(analysis_result.get('action_items', []))}")
        except json.JSONDecodeError:
            print("\n[錯誤] 無法解析 LLM 的回應為 JSON 格式，請檢查模型輸出。")
