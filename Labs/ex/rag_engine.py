import os
import requests  # 或使用 ollama 套件

# 1. 知識庫檔案存放目錄
DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")
os.makedirs(DOCS_DIR, exist_ok=True)

def rebuild_index() -> str:
    """
    掃描 DOCS_DIR 下的所有 .txt 檔案，將文字切塊 (chunking) 
    並計算 Embedding 建立向量索引 (FAISS / Chroma / 記憶體內陣列)。
    """
    # 執行索引重建邏輯...
    return "索引重建完成！共載入 N 筆資料。"

def rag_search_and_answer(query: str, top_n: int) -> tuple[str, str]:
    """
    1. 計算 query 的 embedding 並檢索 top_n 最相似的片段。
    2. 將檢索到的 context 組成 Prompt 送至本地 Ollama (如 port 8080 的 gemma:latest)。
    3. 回傳 (答案字串, 參考來源字串)。
    """
    # 範例回傳格式：
    answer = "這是模型生成的回答..."
    sources = "[來源 1] doc1.txt: ...\n[來源 2] doc2.txt: ..."
    return answer, sources