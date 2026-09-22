# ex_a2a_calling.py
import json
import os
import re
import threading
import time
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# ==================== 配置 ====================
OLLAMA_URL = "http://172.10.0.2:8080/api/chat/completions"
API_KEY = "sk-f60ffbf03ede457987a23650b8b11763"
MODEL = "gemma4_e4b_ctx_2048:latest"

# ==================== Agent Card (A2A 核心) ====================
AGENT_CARD = {
    "name": "local_file_agent",
    "description": "一個專門處理本地檔案讀取與分析的 Agent",
    "skills": ["read_file", "analyze_text"],
    "version": "1.0",
    "endpoint": "http://localhost:5000/a2a",
}


# ==================== 簡單工具 ====================
def read_file(filepath: str):
    """讀取本地文字檔案，針對 2048 ctx 模型限制讀取長度"""
    if not os.path.exists(filepath):
        return f"[錯誤] 檔案不存在: {filepath}"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            # 限制長度避免塞爆 2048 tokens
            return f.read()[:1000]
    except Exception as e:
        return f"[讀取異常]: {str(e)}"


# ==================== A2A Server Endpoint ====================
@app.route("/a2a", methods=["POST"])
def a2a_handler():
    data = request.get_json(silent=True) or {}
    task = data.get("task", {})
    user_input = task.get("input", "")

    print(f"\n[Server] 收到 A2A 任務: {user_input}")

    # 1. 檔名識別
    file_match = re.search(r"([a-zA-Z0-9_\-\./\\]+\.(txt|md|log|json|csv|py))", user_input)
    file_content = ""
    used_artifacts = []

    if file_match:
        target_path = file_match.group(1)
        print(f"[Tool] 觸發 read_file: {target_path}")
        file_content = read_file(target_path)
        used_artifacts.append(target_path)

    # 2. 構建簡潔的 Prompt
    if file_content:
        prompt_content = f"檔案內容如下：\n{file_content}\n\n任務：請用繁體中文以條列方式總結以上內容。"
    else:
        prompt_content = user_input

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt_content},
        ],
        "temperature": 0.3,
        "max_tokens": 512,  # 明確指定生成上限
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, headers=headers, timeout=60)

        if resp.status_code != 200:
            return jsonify({
                "status": "failed",
                "output": f"LLM 伺服器拒絕 (HTTP {resp.status_code}): {resp.text}",
                "artifacts": used_artifacts,
            })

        result = resp.json()
        choice = result["choices"][0]
        output_text = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "unknown")
        
        print(f"[Server] 生成結束原因 (finish_reason): {finish_reason}")

        return jsonify({
            "status": "completed",
            "output": output_text,
            "artifacts": used_artifacts,
        })

    except requests.RequestException as e:
        return jsonify({"status": "failed", "output": f"連線異常: {str(e)}", "artifacts": used_artifacts})
    except (KeyError, IndexError) as e:
        return jsonify({"status": "failed", "output": f"回應解析異常: {str(e)}", "artifacts": used_artifacts})


@app.route("/agent-card", methods=["GET"])
def get_agent_card():
    return jsonify(AGENT_CARD)


# ==================== A2A Client 示範 ====================
def call_remote_agent(agent_url: str, task: str):
    payload = {"task": {"id": "task-001", "input": task}}
    try:
        resp = requests.post(f"{agent_url}/a2a", json=payload, timeout=65)
        return resp.json()
    except requests.RequestException as e:
        return {"status": "client_error", "output": f"連線至代理失敗: {str(e)}"}


# ==================== 啟動 ====================
if __name__ == "__main__":
    if not os.path.exists("mcp.txt"):
        with open("mcp.txt", "w", encoding="utf-8") as f:
            f.write(
                "Model Context Protocol (MCP) 是由 Anthropic 提出的開放標準協定。\n"
                "它旨在讓 AI 模型能夠安全、標準化地連接本機與遠端資料來源與自訂工具，"
                "類似於 AI 世界的 USB-C 連接埠。"
            )

    print("=== A2A Agent 示範 ===")
    print("Agent Card:", json.dumps(AGENT_CARD, indent=2, ensure_ascii=False))

    server_thread = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    time.sleep(1)

    print("\nA2A Server 已啟動在 http://localhost:5000")
    print("Agent Card: http://localhost:5000/agent-card")

    input("\n按 Enter 模擬另一個 Agent 委派任務...")
    result = call_remote_agent("http://localhost:5000", "請讀取 mcp.txt 並總結內容")
    print("\n=== 收到遠端 Agent 回應 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))