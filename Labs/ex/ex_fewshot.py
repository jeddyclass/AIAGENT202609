import requests
import json

# 1. 基礎設定
OLLAMA_API_URL = "http://172.10.0.2:8080/api/chat/completions"
OPENWEBUI_API_KEY = "sk-f60ffbf03ede457987a23650b8b11763" 
MODEL = "gemma4_e4b_nothink:latest"

def get_api_headers():
    return {
        "Authorization": f"Bearer {OPENWEBUI_API_KEY}",
        "Content-Type": "application/json"
    }

# 2. 您指定的 LLM 呼叫函數
def call_llm(messages, model_name):
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=get_api_headers(), json=payload, timeout=240)
        response.raise_for_status()
        result = response.json()
        # 解析並回傳模型文字
        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        print(f"API 請求失敗: {e}")
        return None

# 3. 系統角色（System Prompt）與 Few-shot 範例
SYSTEM_PROMPT = """你是一個產品名稱與分類轉換工具。請嚴格模仿以下格式，將使用者輸入的產品名稱轉換為「[分類] 英文對應詞或常見名稱」：

輸入：蘋果手機 -> 輸出：[電子產品] iPhone
輸入：保溫杯 -> 輸出：[生活用品] Thermos
輸入：球鞋 -> 輸出：[服飾配件] Sneakers
輸入：咖啡機 -> 輸出：[廚房家電] Coffee Maker
輸入：除濕機 -> 輸出：[生活家電] Dehumidifier
輸入：辦公椅 -> 輸出：[家具寢具] Office Chair
輸入：維他命C -> 輸出：[保健食品] Vitamin C
輸入：藍牙耳機 -> 輸出：[電子產品] Bluetooth Earphones
輸入：防曬乳 -> 輸出：[美妝保養] Sunscreen
輸入：智慧手錶 -> 輸出：[電子產品] Smartwatch
輸入：精油 -> 輸出：[香氛護理] Essential Oil
輸入：瑜珈墊 -> 輸出：[運動用品] Yoga Mat"""

# 4. 封裝轉換邏輯的函數
def transform_product_name(product_name, model_name=MODEL):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"輸入：{product_name} -> 輸出："}
    ]
    return call_llm(messages, model_name)

# --- 測試執行 ---
if __name__ == "__main__":
    # 單筆測試
    test_item = "電腦顯示器"
    output = transform_product_name(test_item)
    print(f"單筆測試結果：\n{output}\n")
    
    # 多筆批次測試
    test_list = ["微波爐", "機械鍵盤", "夾腳拖", "益生菌"]
    print("批次測試結果：")
    for item in test_list:
        res = transform_product_name(item)
        print(f"{item} -> {res}")
