# mcp_sse_server.py
import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("File-Reader-SSE")

@mcp.tool()
def read_file(filepath: str, max_chars: int = 1800) -> str:
    """讀取本地檔案內容的前段文字。"""
    try:
        if not os.path.exists(filepath):
            return f"錯誤：檔案不存在 {filepath}"
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            total_len = len(content)
            # 限制長度，避免灌爆 2048 context
            trimmed = content[:max_chars]
            if total_len > max_chars:
                trimmed += f"\n\n...[因模型上下文限制，已截斷。全文共 {total_len} 字，目前顯示前 {max_chars} 字]..."
            return trimmed
    except Exception as e:
        return f"錯誤：{str(e)}"

if __name__ == "__main__":
    print("正在啟動 MCP SSE 伺服器，監聽 http://localhost:8000 ...")
    mcp.run(transport="sse")