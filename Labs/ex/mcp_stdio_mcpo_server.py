# mcp_stdio_server.py
import os
from mcp.server.fastmcp import FastMCP

# pip install mcpo fastmcp requests

# 請在終端機輸入以下指令來啟動 mcpo。它會把上面的 stdio 腳本包裝成 http://localhost:8000 的 OpenAPI 網頁
# mcpo --port 8000 -- python mcp_stdio_mcpo_server.py

mcp = FastMCP("File-Reader")

@mcp.tool()
def read_file(filepath: str) -> str:
    """讀取本地檔案內容。
    
    Args:
        filepath: 檔案的完整路徑或名稱。
    """
    try:
        if not os.path.exists(filepath):
            return f"錯誤：檔案不存在 {filepath}"
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()[:8000]
    except Exception as e:
        return f"錯誤：{str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
