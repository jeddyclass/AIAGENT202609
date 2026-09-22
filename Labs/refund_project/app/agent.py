import os
from google.adk.agents import Agent
from google.adk.models import LiteLlm  # 或 OpenAIClient，取決於 ADK 2.0 的通用適配器
from .tools import query_order_db, execute_refund

# 讀取模式設定，預設為 cloud
RUN_MODE = os.getenv("ADK_MODE", "cloud").lower()

if RUN_MODE == "local":
    # 模式 2：Local (OpenWebUI API -> Ollama gemma4:12b)
    # OpenWebUI 提供 OpenAI-compatible 端點
    active_model = LiteLlm(
        model="openai/gemma4:12b",
        api_base=os.getenv("LOCAL_OPENWEBUI_URL", "http://172.10.0.22:8080/api"),
        api_key=os.getenv("LOCAL_OPENWEBUI_KEY", "your-openwebui-api-key")
    )
else:
    # 模式 1：Cloud (Google Gemini)
    active_model = "gemini-2.5-flash"

# 1. 唯讀查詢 Worker（加強指令，強制調用工具）
order_query_worker = Agent(
    name="order_query_worker",
    model=active_model,
    instruction="""你專責查詢訂單資訊。
    【重要規則】：
    1. 無論顧客是詢問狀態還是要求退款，只要提及訂單編號，你「必須先調用」query_order_db 工具查詢訂單。
    2. 查詢完成後，如果顧客的需求是退款，請調用 transfer_to_agent 將任務移交給 refund_worker。
    3. 嚴禁自己進行退款操作。
    【輸出規範】：直接以繁體中文回覆顧客最終結論。嚴禁輸出思考過程。""",
    tools=[query_order_db]
)

# 2. 退款操作 Worker
refund_worker = Agent(
    name="refund_worker",
    model=active_model,
    instruction="""你負責準備退款申請。
    在調用 execute_refund 工具前，必須確認訂單存在且金額小於等於 500 元。
    若金額超過 500 元，不可調用 execute_refund，直接告知顧客金額超限。
    【輸出規範】：直接以繁體中文回覆顧客最終結論。嚴禁輸出思考過程。""",
    tools=[execute_refund]
)

# 3. 頂層接待與路由 (Root Agent)
root_agent = Agent(
    name="customer_service_root",
    model=active_model,
    instruction="""你是客服經理。
    顧客提出任何訂單或退款需求時，一律先委派給 order_query_worker 進行查核。
    【輸出規範】：直接以繁體中文回覆顧客最終結論。嚴禁輸出思考過程。""",
    sub_agents=[order_query_worker, refund_worker]
)
