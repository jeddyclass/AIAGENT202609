import os
import time
import json
import requests

# 依照你的要求設定環境變數與參數
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763" 
ENDPOINT = "http://172.10.0.2:8080/api/chat/completions"
MODEL_NAME = "gemma4_e4b_ctx_2048:latest"

# 模擬資料庫：過去散落的團隊對話紀錄（記憶庫）
CHAT_HISTORY_DATABASE = [
    {"date": "2026-05-20", "content": "小明：X專案的後端架構已經開出了，目前API進度大約完成60%。"},
    {"date": "2026-05-25", "content": "小華：前端畫面切好了，但設計師說Logo可能還要改。"},
    {"date": "2026-06-02", "content": "小明：後端API全數完工！測試環境也架好了。"},
    {"date": "2026-06-08", "content": "客戶：這次X專案的時程有提早，我們非常滿意。"}
]

class ProactiveAgent:
    def __init__(self):
        self.is_user_busy = True  # 模擬用戶目前的狀態（專心工作中）
        self.prepared_data = None

    def listen_stream(self, new_message: str):
        """
        1. 輕量級監聽機制 (模擬 2605.30152)
        用極低的成本（本地規則）過濾訊息，避免頻繁呼叫大模型。
        """
        print(f"\n[系統監聽中...] 收到新訊息: '{new_message}'")
        
        trigger_keywords = ["報告", "開會", "進度", "專案"]
        # 觸發條件：包含關鍵字且提到「下週」
        if any(kw in new_message for kw in trigger_keywords) and "下週" in new_message:
            print("⚡ [守門員觸發]: 偵測到高價值主動事件！啟動後台 LLM 記憶處理...")
            self._proactive_memory_processing(new_message)
        else:
            print("💤 [守門員守衛]: 普通日常對話，不觸發主動機制。")

    def _proactive_memory_processing(self, incoming_task: str):
        """
        2. 後台主動記憶提取與重構 (模擬 2601.04463)
        使用原生 requests 呼叫自定義模型，讓 AI 自動去翻歷史紀錄並整理。
        """
        # 將過去的混亂對話拼接成脈絡文本
        context = "\n".join([f"[{m['date']}] {m['content']}" for m in CHAT_HISTORY_DATABASE])
        
        # 建立純文字 Prompt，並強迫模型輸出乾淨的 JSON
        prompt = (
            f"你是一個幕後的主動式AI助手。\n"
            f"用戶剛收到這個指令：'{incoming_task}'\n"
            f"請主動翻閱以下過去三週的對話歷史，幫用戶把這個專案最新的『真實核心進度』整理出來，並自動擬定一份報告草稿。\n\n"
            f"歷史紀錄:\n{context}\n\n"
            f"請嚴格一律以 JSON 格式回覆，不要帶有任何 markdown 標籤（如 ```json ），格式如下：\n"
            f"{{\n"
            f"  \"project_name\": \"專案名稱\",\n"
            f"  \"latest_status\": \"一兩句話總結最新進度\",\n"
            f"  \"draft_points\": [\"簡報要點1\", \"簡報要點2\"]\n"
            f"}}"
        )

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json; charset=utf-8" # 確保標準編碼
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            # 強制模型返回 JSON 物件 (如果你的地端推理引擎支援的話)
            "response_format": {"type": "json_object"} 
        }

        try:
            # 發送請求給你的地端 API
            response = requests.post(ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            
            # 解析模型回傳的純文字為 Python Dict
            raw_content = response.json()['choices'][0]['message']['content']
            self.prepared_data = json.loads(raw_content)
            
            print("🧠 [後台記憶處理完成]: 報告草稿已在後台生成完畢，等待最佳時機介入...")
            self._wait_for_user_idle()
            
        except Exception as e:
            print(f"❌ 後台處理失敗: {e}")

    def _wait_for_user_idle(self):
        """ 3. 模擬環境感知：監測用戶狀態，直到用戶有空才打擾 """
        print("⏳ [狀態監測]: 用戶目前鍵盤輸入頻繁，處於忙碌狀態，暫不打擾...")
        time.sleep(3) 
        self.is_user_busy = False # 模擬用戶停下工作（例如偵測到滑鼠閒置）
        self._trigger_proactive_intervention()

    def _trigger_proactive_intervention(self):
        """
        4. 主動介入與偏好對齊 (模擬 2511.02208)
        """
        if not self.prepared_data:
            return
            
        print("\n" + "="*40)
        print("✨✨✨ [AI 主動助理跳出提示] ✨✨✨")
        print(f"嗨！我注意到主管剛剛要求你準備【{self.prepared_data.get('project_name', 'X專案')}】的報告。")
        print(f"我幫你翻了一下過去的群組對話，最新進度是：\n👉 \"{self.prepared_data.get('latest_status')}\"")
        print("\n我已經自動為你寫好一份下週一可用的報告要點草稿：")
        
        for i, point in enumerate(self.prepared_data.get('draft_points', []), 1):
            print(f"  {i}. {point}")
        
        print("\n[請選擇下一步行動 (輸入數字)]:")
        print("  [1] 聽起來很棒，直接幫我匯出成 PPT 簡報檔。")
        print("  [2] 先不用，下午五點再提醒我這件事。")
        print("  [3] 進度有誤，我要手動修改。")
        print("="*40)

# --- 測試執行 ---
if __name__ == "__main__":
    agent = ProactiveAgent()
    
    # 測試情境：主管在 Slack 上發了一句話，被系統的 Stream 捕捉到
    incoming_slack_message = "主管：下週一開會時，順便報告一下 X 專案的進度。"
    agent.listen_stream(incoming_slack_message)