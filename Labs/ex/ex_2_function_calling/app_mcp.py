#
# python app_mcp.py [西元生日年月日] [地點]
# python app_mcp.py 19880501 台北
#
import sys
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from llm_client import create_client

async def main():
    if len(sys.argv) < 3:
        print("Usage:\npython app_mcp.py 19761026 高雄")
        return

    birthday = sys.argv[1]
    current_loc = sys.argv[2]
    
    llm_client = create_client()
    user_prompt = f"我現在在 {current_loc}，我的生日是 {birthday}，請幫我計算今天的天氣和我的命重。"

    # 1. 定義如何啟動剛剛寫的 MCP Server (使用 python 執行 my_server.py)
    server_params = StdioServerParameters(
        command="python",
        args=["my_server.py"]
    )

    # 2. 建立連線並啟動 MCP 會話
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as mcp_session:
            # 初始化 MCP 連線
            await mcp_session.initialize()

            # 3. 【動態撈取工具】直接從 Server 取得定義好的工具清單，不用再自己手寫 JSON！
            mcp_tools = await mcp_session.list_tools()
            
            # 將 MCP 的工具格式轉換為 OpenAI/Gemma 相容的 tools 參數格式
            # (FastMCP 產出的規格會完美對齊標準)
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                }
                for tool in mcp_tools.tools
            ]

            # 4. 第一次呼叫大模型
            response = llm_client.chat.completions.create(
                model="gemma4_e4b_ctx_2048:latest",
                messages=[{"role": "user", "content": user_prompt}],
                tools=openai_tools,
                tool_choice="auto"
            )

            msg = response.choices[0].message
            if not msg.tool_calls:
                print(msg.content)
                return

            # 準備第二輪對話歷史
            followup_messages = [
                {"role": "user", "content": user_prompt},
                msg
            ]

            # 5. 用迴圈處理模型要求的所有工具（平行呼叫）
            for tool_call in msg.tool_calls:
                tool_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f">>> [MCP] 正在請求 Server 執行工具: {tool_name}, 參數: {args}")

                # 【核心改變】不用再自己寫 if-else 分流呼叫本地函式了！
                # 直接交給 mcp_session 發送請求給 Server，Server 會自己找對應的函式執行
                mcp_result = await mcp_session.call_tool(tool_name, arguments=args)
                
                # 取得 Server 回傳的文字內容
                tool_content = mcp_result.content[0].text if mcp_result.content else "{}"

                followup_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_content
                })

            # 6. 第二次呼叫大模型，統整結果
            followup = llm_client.chat.completions.create(
                model="gemma4_e4b_ctx_2048:latest",
                messages=followup_messages
            )

            print("\n====================")
            print(followup.choices[0].message.content)
            print("====================")

if __name__ == "__main__":
    # 因為 MCP 許多底層通訊是異步的（Async），所以使用 asyncio 執行
    asyncio.run(main())
