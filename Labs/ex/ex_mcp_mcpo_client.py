# lab_2_3_openapi_client.py
import json
import requests

# 若後端為 Ollama 且需要相容 OpenAI 格式，建議確認端點是 /v1/chat/completions 還是目前自訂端點
OLLAMA_BASE_URL = "http://172.10.0.2:8080"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"
MODEL = "gemma4_e4b_ctx_2048:latest"

# mcpo 代理伺服器的網址
MCPO_BASE_URL = "http://localhost:8000"

def call_llm(messages: list, tools=None):
    payload = {"model": MODEL, "messages": messages, "temperature": 0.1}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    
    url = f"{OLLAMA_BASE_URL}/api/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    
    if resp.status_code != 200:
        print(f"[HTTP 錯誤 {resp.status_code}] LLM 回應失敗: {resp.text}")
        return None
        
    data = resp.json()
    if "choices" not in data:
        print(f"[API 回傳錯誤結構] 無法解析 choices，完整回應內容：\n{json.dumps(data, indent=2, ensure_ascii=False)}")
        return None
        
    return data

def get_tools_from_mcpo():
    """從 mcpo 的 openapi.json 動態解析並轉換為 OpenAI Tools 格式"""
    try:
        resp = requests.get(f"{MCPO_BASE_URL}/openapi.json")
        openapi_spec = resp.json()
        
        openai_tools = []
        paths = openapi_spec.get("paths", {})
        
        for path, methods in paths.items():
            if "post" in methods:
                tool_name = path.lstrip("/")
                post_detail = methods["post"]
                description = post_detail.get("description", post_detail.get("summary", ""))
                
                ref_schema = {}
                try:
                    content_schema = post_detail["requestBody"]["content"]["application/json"]["schema"]
                    if "$ref" in content_schema:
                        ref_name = content_schema["$ref"].split("/")[-1]
                        ref_schema = openapi_spec["components"]["schemas"][ref_name]
                    else:
                        ref_schema = content_schema
                except KeyError:
                    ref_schema = {"type": "object", "properties": {}}

                # 修正：符合標準 OpenAI Tools 規格 (type: function)
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": description,
                        "parameters": {
                            "type": "object",
                            "properties": ref_schema.get("properties", {}),
                            "required": ref_schema.get("required", [])
                        }
                    }
                })
        return openai_tools
    except Exception as e:
        print(f"[警告] 無法從 mcpo 取得工具清單: {e}")
        return []

def main():
    print("=== Open WebUI mcpo (OpenAPI) 檔案讀取 Agent 啟動 ===")
    user_query = input("請輸入問題（例如：分析 mcp.txt）：\n")

    # 1. 透過 HTTP GET 向 mcpo 自動取得工具
    openai_tools = get_tools_from_mcpo()
    if not openai_tools:
        print("未偵測到任何可用工具，結束。")
        return

    messages = [
        {"role": "system", "content": "你是一個具有本地檔案讀取能力的 AI 助手。請善用工具回答。"},
        {"role": "user", "content": user_query}
    ]

    # 2. 第一次呼叫 LLM
    response = call_llm(messages, openai_tools)
    if not response:
        return

    # 修正：加上 choices[0] 索引
    message = response["choices"][0]["message"]

    if message.get("tool_calls"):
        print("\n[Agent] LLM 決定呼叫 mcpo 工具...")
        messages.append(message)

        for tool_call in message["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])
            
            filepath = args.get("filepath") or args.get("file_path") or args.get("file_name")
            print(f"[Agent] 正在向 mcpo 發送標準 HTTP POST 請求: /{tool_name}, 參數: {filepath}")
            
            # 3. 呼叫 mcpo 端點
            tool_resp = requests.post(
                f"{MCPO_BASE_URL}/{tool_name}",
                json={"filepath": filepath}
            )
            
            result_json = tool_resp.json()
            print(f"[Agent] mcpo 回傳結果: {json.dumps(result_json, ensure_ascii=False)}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", "call_123"),
                "name": tool_name,
                "content": json.dumps(result_json, ensure_ascii=False)
            })

        # 4. 第二次呼叫 LLM 彙整結果
        final_response = call_llm(messages, openai_tools)
        if final_response:
            print("\n=== LLM 最終回應 ===")
            print(final_response["choices"][0]["message"]["content"])
    else:
        print("\n=== LLM 回應 ===")
        print(message.get("content"))

if __name__ == "__main__":
    main()