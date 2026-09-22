import requests
import json
import re
import time

# ==========================================
# 1. 設定 Open WebUI / Ollama 的 API 資訊
# ==========================================
OPEN_WEBUI_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"
MODEL_NAME = "gemma4_e4b_nothink:latest"

#OPEN_WEBUI_URL = "http://192.168.1.153:8080/api/chat/completions"
#API_KEY = "sk-cebd4fabff5f4b5d8434795173832ba9"
#MODEL_NAME = "gemma4_e4b_nothink:latest"


def call_llm(prompt: str, system_prompt: str = "你是一個有用的 AI 助手。", stop: list = None) -> str:
    """呼叫 Open WebUI / Ollama API 的統一函式，支援自訂 stop 標記"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1  # 調低 temperature，保證 ReAct 格式與調度輸出精確
    }
    if stop:
        payload["stop"] = stop

    try:
        response = requests.post(OPEN_WEBUI_URL, headers=headers, json=payload, timeout=240)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        else:
            return f"Error: API 回傳錯誤碼 {response.status_code} - {response.text}"
    except Exception as e:
        return f"Error: 無法連線到 Open WebUI: {str(e)}"


# ==========================================
# 2. MCP (Model Context Protocol) 模擬端
# ==========================================
class MockMCPServer:
    """模擬一個獨立的 MCP 伺服器，提供 Tools 與 Resources"""
    def __init__(self):
        self.company_db = {
            "專案x": "專案X（Project X）官方代號為『Nebula』，預計於 2026 年第三季啟動 AI 核心模組線。",
            "mcp協定": "MCP 是 Model Context Protocol 的縮寫，是一套開放標準，允許開發者建立安全的雙向連線，讓 LLM 與外部資料與工具互動。"
        }

    def list_tools(self):
        return [{
            "name": "query_company_knowledge",
            "description": "檢索公司內部機密或最新專案知識庫",
            "input_schema": {"type": "object", "properties": {"keyword": {"type": "string"}}}
        }]

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        if tool_name == "query_company_knowledge":
            raw_keyword = arguments.get("keyword", "")
            # 清理關鍵字中的特殊標點符號與大小寫
            clean_keyword = re.sub(r"[^\w\u4e00-\u9fff]", "", raw_keyword).lower()
            print(f"🔌 [MCP Server] 執行工具 '{tool_name}'，參數: '{raw_keyword}' (搜尋比對: '{clean_keyword}')")
            
            for k, v in self.company_db.items():
                target_key = re.sub(r"[^\w\u4e00-\u9fff]", "", k).lower()
                # 雙向子字串包含比對，提高容錯度
                if target_key in clean_keyword or clean_keyword in target_key:
                    return f"【MCP Resource 尋獲】: {v}"
            return f"【MCP Resource】未找到與「{raw_keyword}」相關的機密文檔。"
        return "錯誤：無此工具"


# ==========================================
# 3. Memory 模組 (維持對話上下文)
# ==========================================
class AgentMemory:
    def __init__(self):
        self.history = []

    def add(self, role: str, msg: str):
        self.history.append({"role": role, "content": msg})

    def get_context(self) -> str:
        return "\n".join([f"{h['role']}: {h['content']}" for h in self.history[-6:]])


# ==========================================
# 4. Multi-Agent & A2A & ReAct 核心實作
# ==========================================
class RagAgent:
    """RAG Agent：專門透過 MCP 協定檢索知識庫的 Agent"""
    def __init__(self, mcp_server: MockMCPServer):
        self.mcp = mcp_server
        self.system_prompt = """你是一個 RAG 專門檢索代理。
你擁有調用 MCP 工具的能力。請嚴格遵守 ReAct 格式推理：
- 思考步驟請輸出： Thought: <你的思考>
- 若需要查資料，請輸出： Action: query_company_knowledge[關鍵字]
【注意】：輸出 Action 後請立刻停止，嚴禁自己編造「Observation:」內容！
- 當拿到足夠的 Observation 後，請輸出最終答案： Final Answer: <完整解答>"""

    def receive_message(self, request_text: str) -> str:
        print(f"🤖 [RagAgent] 收到 A2A 請求: '{request_text}'")
        
        # 建立專屬該請求的 ReAct 對話鏈
        scratchpad = f"請幫我處理這個請求，必要時使用工具查詢：{request_text}\n"
        max_turns = 3  # 最多支援 3 輪工具查詢（解決同時問多個關鍵字的問題）

        for turn in range(max_turns):
            # 設定 stop=["Observation:"] 防止模型自行偽造觀測結果
            llm_output = call_llm(scratchpad, self.system_prompt, stop=["Observation:", "Observation "])
            print(f"🧠 [RagAgent 第 {turn + 1} 輪思考]:\n{llm_output}")
            scratchpad += f"\n{llm_output}\n"

            # 使用 Regex 解析 Action: tool_name[param]（容許 Markdown 語法）
            action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\[(.*?)\]", llm_output)
            
            if action_match:
                tool_name = action_match.group(1).strip()
                tool_arg = action_match.group(2).strip()

                # 調用真正的 MCP 工具
                observation = self.mcp.call_tool(tool_name, {"keyword": tool_arg})
                print(f"📥 [RagAgent 收到真實 MCP 回傳]: {observation}")

                # 將真實的 Observation 餵回給模型
                scratchpad += f"Observation: {observation}\n"
            else:
                # 沒有 Action，檢查是否有 Final Answer
                final_match = re.search(r"Final Answer:\s*(.*)", llm_output, re.DOTALL)
                if final_match:
                    return final_match.group(1).strip()
                return llm_output

        # 超過最大輪數，強制要求結案
        scratchpad += "請根據以上所有的 Observation 輸出 Final Answer。\n"
        final_output = call_llm(scratchpad, self.system_prompt)
        final_match = re.search(r"Final Answer:\s*(.*)", final_output, re.DOTALL)
        return final_match.group(1).strip() if final_match else final_output


class CoordinatorAgent:
    """主協調 Agent (Router)：面對用戶，透過 A2A 調度專業 Agent"""
    def __init__(self, rag_agent: RagAgent):
        self.rag_agent = rag_agent
        self.memory = AgentMemory()
        self.system_prompt = """你是一個團隊協調代理 (Coordinator)。
你負責分析用戶的問題，並決定是直接回答，還是需要透過 A2A (Agent-to-Agent) 委託給專門的 RagAgent。

你的思考規則 (ReAct)：
1. 若問題涉及公司內部機密、專案X、最新技術細節、MCP等，請輸出：
   Action: Call_Agent[RagAgent, 具體提問內容]
【注意】：輸出 Action 後請立刻停止，嚴禁自己編造「Observation:」內容！
2. 一般閒聊或對話歷史已有的資訊，直接回答：
   Final Answer: 給用戶的最終回答"""

    def handle_user_input(self, user_input: str):
        print(f"\n👥 ====== 收到用戶請求: {user_input} ======")
        context = self.memory.get_context()
        
        prompt = f"【對話歷史】:\n{context}\n\n【當前用戶提問】: {user_input}\n請進行 ReAct 推理。"
        
        # 設定 stop=["Observation:"] 防止模型自己偽造 Agent 回傳
        llm_output = call_llm(prompt, self.system_prompt, stop=["Observation from RagAgent:", "Observation:"])
        print(f"👑 [Coordinator 思考]:\n{llm_output}")

        # 使用 Regex 擷取 A2A 委派指令
        a2a_match = re.search(r"Action:\s*Call_Agent\[RagAgent,\s*(.*?)\]", llm_output, re.DOTALL)
        
        if a2a_match:
            sub_request = a2a_match.group(1).strip()
            print(f"🤝 [A2A 啟動] 轉發子任務至 RagAgent: '{sub_request}'")
            
            # ==== 呼叫 RagAgent ====
            rag_response = self.rag_agent.receive_message(sub_request)
            print(f"🤝 [A2A 完成] RagAgent 已產出查核結論。")

            # 由 Coordinator 進行最終統整輸出給用戶
            next_prompt = f"{prompt}\n{llm_output}\nObservation from RagAgent: {rag_response}\n請根據 RagAgent 的回覆整合輸出最終 Final Answer。"
            final_response = call_llm(next_prompt, self.system_prompt)
            
            final_match = re.search(r"Final Answer:\s*(.*)", final_response, re.DOTALL)
            reply = final_match.group(1).strip() if final_match else final_response
        else:
            final_match = re.search(r"Final Answer:\s*(.*)", llm_output, re.DOTALL)
            reply = final_match.group(1).strip() if final_match else llm_output

        # 寫入歷史記憶庫
        self.memory.add("User", user_input)
        self.memory.add("Coordinator", reply)
        print(f"\n✨ [最終對外回應]:\n{reply}")


# ==========================================
# 5. 啟動模擬測試
# ==========================================
if __name__ == "__main__":
    mcp_server = MockMCPServer()
    rag_agent = RagAgent(mcp_server)
    coordinator = CoordinatorAgent(rag_agent)

    # 任務一：觸發多步驟 A2A 與真實 MCP 查詢的任務
    coordinator.handle_user_input("幫我查一下專案X的代號是什麼？順便解釋一下什麼是MCP協定")

    print("\n" + "="*60 + "\n")

    # 任務二：無需工具呼叫的上下文感謝
    coordinator.handle_user_input("太棒了，謝謝你的詳細解答！")