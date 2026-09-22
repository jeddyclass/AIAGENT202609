# mcp_stdio_server.py
import os
from typing import Optional
from mcp.server.fastmcp import FastMCP

# 建立一個名為 "File-Reader" 的 MCP 服務
mcp = FastMCP("File-Reader")

#@mcp.tool()
#def read_file(filepath: str) -> str:
#    """讀取本地檔案內容。
#    
#    Args:
#        filepath: 檔案的完整路徑或名稱。
#    """
#    try:
#        if not os.path.exists(filepath):
#            return f"錯誤：檔案不存在 {filepath}"
#        with open(filepath, "r", encoding="utf-8") as f:
#            return f.read()[:8000]
#    except Exception as e:
#        return f"錯誤：{str(e)}"

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
        
#@mcp.tool()
#def read_file(filepath: Optional[str] = None) -> str:
#    """讀取本地檔案內容。
#    
#    Args:
#        filepath: 檔案的完整路徑或名稱。
#    """
#    try:
#        if not filepath:
#            return "錯誤：未提供有效的檔案路徑 (filepath 為空)"
#            
#        if not os.path.exists(filepath):
#            return f"錯誤：檔案不存在 {filepath}"
#            
#        with open(filepath, "r", encoding="utf-8") as f:
#            return f.read()[:8000]
#    except Exception as e:
#        return f"錯誤：{str(e)}"
        
if __name__ == "__main__":
    # 啟動 stdio 伺服器
    mcp.run(transport="stdio")
