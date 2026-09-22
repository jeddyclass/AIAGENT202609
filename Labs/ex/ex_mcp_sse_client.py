# ex_mcp_sse_client.py
# 執行前先執行 python mcp_sse_server.py

import json
import requests
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

OLLAMA_BASE_URL = "http://172.10.0.2:8080"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"
MODEL = "gemma4_e4b_ctx_2048:latest"
MCP_SSE_URL = "http://localhost:8000/sse"

def call_llm(messages: list, tools=None):
    payload = {"model": MODEL, "messages": messages, "temperature": 0.1}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    return resp.json()

async def main():
    print("=== MCP SSE 檔案讀取 Agent 啟動 ===")
    user_query = input("請輸入問題（例如：分析 mcp.txt）：\n")

    async with sse_client(url=MCP_SSE_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            mcp_tools = await session.list_tools()

            # 建立標準 OpenAI Tools 格式
            openai_tools = []
            for t in mcp_tools.tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema,
                    },
                })

            messages = [
                {"role": "system", "content": "你是一個具有本地檔案讀取能力的 AI 助手。請善用工具回答。Reply in zhtw."},
                {"role": "user", "content": user_query},
            ]

            # 第一輪：詢問 LLM 並提供可用工具
            response = call_llm(messages, openai_tools)
            message = response["choices"][0]["message"]

            if "tool_calls" in message and message["tool_calls"]:
                print("\n[Agent] LLM 決定呼叫遠端 MCP 工具...")
                messages.append(message)

                for tool_call in message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    raw_args = tool_call["function"].get("arguments", "{}")
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    print(f"[Agent] 模型原始參數: {args}")

                    # 擷取檔案路徑參數
                    filepath = (
                        args.get("filepath")
                        or args.get("file_path")
                        or args.get("file_name")
                        or args.get("path")
                    )

                    # 若模型漏傳參數，嘗試從使用者輸入中抓取副檔名字串
                    if not filepath:
                        for word in user_query.split():
                            if "." in word:
                                filepath = word.strip("，。！？\"'")
                                break

                    print(f"[Agent] 正在透過 SSE 請求工具: {tool_name}, 參數: {filepath}")

                    if not filepath:
                        result_text = "錯誤：未能識別到檔案路徑。"
                    else:
                        mcp_result = await session.call_tool(
                            tool_name, arguments={"filepath": str(filepath)}
                        )
                        result_text = (
                            mcp_result.content[0].text if mcp_result.content else ""
                        )

                    print(f"[Agent] 工具執行回傳長度: {len(result_text)} 字元")

                    # 將工具執行結果加入對話歷史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_123"),
                        "name": tool_name,
                        "content": result_text,
                    })

                # 第二輪：不傳 tools，促使模型進行內容總結分析
                final_response = call_llm(messages)
                final_message = final_response["choices"][0]["message"]
                content = final_message.get("content") or ""

                print("\n=== LLM 最終回應 ===")
                print(content if content else f"[提示：模型未生成文字內容，原始回應: {final_message}]")
            else:
                print("\n=== LLM 回應 ===")
                print(message.get("content", ""))

if __name__ == "__main__":
    asyncio.run(main())