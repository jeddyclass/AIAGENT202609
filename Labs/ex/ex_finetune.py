# =====================================================================
# 核心教學：大型語言模型微調（LoRA）至落地部署全流程pseudo code
# =====================================================================

# 【步驟 1：準備教材】
Training_Dataset = [
    {"prompt": "請問公司的年假特休怎麼算？", "response": "根據公司規章第4條，入職滿半年享有3天特休..."},
    {"prompt": "客戶要求退貨時的SOP是什麼？", "response": "請先核對發票，並於系統中提交RMA申請流程..."},
]

# 保留 10% 的考卷不給模型看，留作畢業考試用
Validation_Dataset = [
    {"prompt": "新進員工待滿半年有幾天假？", "response": "根據公司規章第4條，入職滿半年享有3天特休..."},
]

# 【步驟 2：載入基礎模型與 Tokenizer】
Base_Model = Load_Pretrained_LLM("Llama-3-8B-Base") 
Tokenizer  = Load_Text_Converter("Llama-3-8B-Base") 

# 【步驟 3：加裝 LoRA 外掛晶片】
LoRA_Adapter_Config = {"target_layers": ["Attention_Layers"], "rank_size": 16, "alpha": 32}
FineTune_Model = Apply_PEFT_LoRA(Base_Model, LoRA_Adapter_Config)

# 【步驟 4：設定特訓規則】
Training_Settings = {"learning_rate": 0.0002, "epochs": 3, "batch_size": 4, "optimizer": "AdamW"}

# 【步驟 5：執行特訓（Training Loop）】
print("🚀 特訓開始...")
# ... (特訓迴圈，在此省略，詳見前段) ...

# 【步驟 6：畢業與打包外掛】
print("🎉 特訓完成！")
Save_LoRA_Weights(FineTune_Model, "my_company_lora_adapter")


# =====================================================================
# 🔥 新增【步驟 6.5：評判微調得好不好？（模型評估 Evaluation）】
# =====================================================================
print("\n--- 進入畢業考試階段（Evaluation）---")

# 評判心法：不能只看訓練時的 Loss，要拿模型沒看過的考卷（Validation）來考它
Evaluation_Results = []
For exam_question in Validation_Dataset:
    # 1. 讓微調後的模型回答
    Model_Output = FineTune_Model.Predict(exam_question["prompt"])
    
    # 2. 自動化評估：使用主流指標（如 ROUGE Score 或 BLEU Score）計算文字相似度
    Text_Score = Calculate_ROUGE_Score(Model_Output, exam_question["response"])
    
    # 3. 2026主流評估：LLM-as-a-Judge（請最強的 GPT-4o 或 Claude 3.5 當閱卷老師）
    AI_Judge_Score = Ask_GPT4_To_Grade(
        question=exam_question["prompt"], 
        ideal_answer=exam_question["response"], 
        model_answer=Model_Output
    ) # 閱卷老師會針對「正確性」、「語氣」、「格式」給予 1~5 分
    
    Evaluation_Results.append({"text_score": Text_Score, "judge_score": AI_Judge_Score})

# 評判標準邏輯
If Average(Evaluation_Results["judge_score"]) >= 4.5:
    print("✅ 評估通過！模型表現優異，準備合體上線。")
Else:
    print("❌ 評估失敗！模型產生幻覺或格式錯誤。請重新檢查步驟1的教材品質。")
    Exit_Program()


# =====================================================================
# 【步驟 7：參數永久熔合（Merge & Save）】
# =====================================================================
print("\n--- 進入參數熔合階段 ---")
Merged_Model = FineTune_Model.Merge_And_Unload() 

# 為了後續能塞進 Ollama 或 vLLM，我們將融合後的完整模型存成標準的 HuggingFace 格式
Save_Full_Model(Merged_Model, "./my_merged_llm_hf_folder")
print("💾 熔合完成！已產出標準格式模型資料夾。")


# =====================================================================
# 🔥 新增【步驟 8：套用到部署推論引擎（Ollama & vLLM）】
# =====================================================================
print("\n--- 進入生產環境部署（Deployment）---")

# -----------------------------------------------------------------
# 場景一：怎麼套用到 Ollama？（適合個人測試、地端 Mac/PC、輕量辦公室應用）
# -----------------------------------------------------------------
def Deploy_To_Ollama(hf_model_path):
    print("📦 正在準備 Ollama 部署...")
    # 1. Ollama 看不懂原本的檔案，必須先把 HuggingFace 模型格式轉換並壓縮成「GGUF」格式
    GGUF_File = Convert_HF_To_GGUF(hf_model_path, quantization="Q4_K_M") # 壓縮成4位元，速度更快
    
    # 2. 撰寫一個給 Ollama 看的設定檔（Modelfile）
    Modelfile_Content = f"""
    FROM {GGUF_File}
    TEMPLATE "[INST] <<SYS>> 你是公司專屬的 AI 特助。 <</SYS>> {{prompt}} [/INST]"
    PARAMETER temperature 0.2
    """
    Save_Text_File(Modelfile_Content, "Modelfile")
    
    # 3. 在背後執行的終端機指令 (Terminal Command)
    Execute_Terminal_Command("ollama create my_company_model -f ./Modelfile")
    Execute_Terminal_Command("ollama run my_company_model")
    print("🟢 Ollama 部署成功！現在可以在終端機或透過 API 與專屬模型對話了。")


# -----------------------------------------------------------------
# 場景二：怎麼套用到 vLLM？（適合企業級生產環境、百人以上高併發使用、K8s 佈署）
# -----------------------------------------------------------------
def Deploy_To_vLLM(hf_model_path):
    print("⚡ 正在準備 vLLM 高併發伺服器部署...")
    # vLLM 強大在於它不需要壓縮成 GGUF，它能直接讀取 HuggingFace 原始格式
    # 並且利用 PagedAttention 技術，讓多個用戶同時提問時完全不卡頓
    
    # 模擬在伺服器背景啟動 vLLM 的 OpenAI 相容 API 服務
    vLLM_Command = f"""
    python -m vllm.entrypoints.openai.api_server \
        --model {hf_model_path} \
        --port 8000 \
        --gpu-memory-utilization 0.9 \
        --max-model-len 4096
    """
    # 執行上述指令後，伺服器就會在 8000 埠口開出一個極速的 API 服務
    print("🟢 vLLM 伺服器已架設完成！已提供與 OpenAI 完全相同格式的 API 接口。")

# 執行部署教學
Deploy_To_Ollama("./my_merged_llm_hf_folder")
Deploy_To_vLLM("./my_merged_llm_hf_folder")