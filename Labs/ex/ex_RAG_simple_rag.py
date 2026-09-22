# pip install gradio


import gradio as gr
import os
import shutil
from rag_engine import DOCS_DIR, rebuild_index, rag_search_and_answer

# frontend

def handle_upload(files):
    """處理使用者上傳的檔案"""
    if not files:
        return "未選擇任何檔案"
    
    uploaded_count = 0
    for file in files:
        # file.name 是暫存路徑，將其複製到我們的知識庫目錄
        dest_path = os.path.join(DOCS_DIR, os.path.basename(file.name))
        shutil.copy(file.name, dest_path)
        uploaded_count += 1
        
    # 上傳後自動重建索引
    msg = rebuild_index()
    return f"成功上傳 {uploaded_count} 個檔案！\n{msg}"

# 建立 Gradio 介面
with gr.Blocks(title="本地 Naive RAG 系統 (Gemma 4b)") as demo:
    gr.Markdown("# 🤖 本地 Naive RAG 知識庫系統")
    gr.Markdown("支援中英文 `.txt` 檔案，完全運行於本地端 (Ollama Port 8080)。")
    
    with gr.Row():
        # 左側控制台：上傳與索引管理
        with gr.Column(scale=1):
            gr.Markdown("### 🗂 檔案管理與索引更新")
            file_input = gr.File(label="上傳 TXT 檔案 (可多選)", file_types=[".txt"], file_count="multiple")
            upload_btn = gr.Button("🚀 上傳並更新索引", variant="primary")
            reindex_btn = gr.Button("🔄 純手動掃描並重建索引", variant="secondary")
            status_output = gr.Textbox(label="系統狀態通知", interactive=False, placeholder="等待操作...")

        # 右側控制台：檢索與問答
        with gr.Column(scale=2):
            gr.Markdown("### 🔍 智能問答區")
            query_input = gr.Textbox(label="請輸入您的問題", placeholder="例如：這篇檔案的核心大意是什麼？")
            top_n_slider = gr.Slider(minimum=1, maximum=5, value=3, step=1, label="Top-N 檢索篇數 (Max: 5)")
            
            submit_btn = gr.Button("提問", variant="primary")
            
            answer_output = gr.Textbox(label="Gemma 4b 回答結果", interactive=False, lines=8)
            sources_output = gr.Textbox(label="Top-N 參考資料來源", interactive=False, lines=8)

    # 綁定事件處理
    upload_btn.click(fn=handle_upload, inputs=[file_input], outputs=[status_output])
    reindex_btn.click(fn=rebuild_index, inputs=[], outputs=[status_output])
    submit_btn.click(fn=rag_search_and_answer, inputs=[query_input, top_n_slider], outputs=[answer_output, sources_output])

# 啟動 Gradio 服務
if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)