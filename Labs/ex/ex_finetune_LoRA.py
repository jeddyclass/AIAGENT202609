# =====================================================================
# 核心教學：低秩適應（LoRA）底層數學與動態流向偽程式碼
# =====================================================================

class LoRALayer():
    def __init__(self, original_dim, rank_size=8, alpha=32):
        self.r = rank_size      # 秩 (Rank)：控制瘦長矩陣的寬度，通常是 8 或 16
        self.alpha = alpha      # 縮放係數 (Scaling)：控制外掛對原模型的影響權重
        self.scaling = alpha / rank_size
        
        # 【右路：LoRA 旁路外掛】
        # 矩陣 A：負責將高維度資料「降維」壓縮。通常用高斯分佈隨機初始化
        self.Matrix_A = Create_Random_Matrix(row=original_dim, col=self.r)
        
        # 矩陣 B：負責將低維度資料「昇維」還原。初始值全部設為 0
        # 💡 教學亮點：B 初始為 0 意味著在訓練的第一秒，B*A = 0，此時模型行為與原廠完全一致！
        self.Matrix_B = Create_Zero_Matrix(row=self.r, col=original_dim)

    def forward_pass(self, input_x, Frozen_Base_Weight):
        # 輸入 input_x 進入節點，開始兵分兩路：
        
        # 1. 左路（主幹道）：通過被凍結的原廠大權重 (W0)
        # 這一路在特訓時「不計算梯度」，所以極度省顯存
        left_output = Matrix_Multiply(input_x, Frozen_Base_Weight)
        
        # 2. 右路（旁支外掛）：通過 LoRA 的降維與昇維 (ΔW = B × A)
        # 這一路才是真正要訓練、會變動的部分
        low_rank_features = Matrix_Multiply(input_x, self.Matrix_A)
        right_output      = Matrix_Multiply(low_rank_features, self.Matrix_B)
        
        # 3. 兩路合流：將原廠答案加上外掛微調的精華（並乘上縮放係使）
        final_output = left_output + (right_output * self.scaling)
        
        return final_output


# =====================================================================
# 🎬 模擬 LoRA 完整的生命週期：從訓練到熔合部署
# =====================================================================

# 1. 載入一個原廠權重矩陣（假設維度為 4096 x 4096）
W_0 = Load_Frozen_Weights("Llama-3-Attention-Layer")
Freeze_Parameters(W_0) # 🔒 鎖定原廠參數，不准更改

# 2. 為該層配置一個輕量化的 LoRA 外掛
lora_layer = LoRALayer(original_dim=4096, rank_size=8, alpha=32)

print("🚀 啟動 LoRA 特訓迴圈...")
for epoch in range(10):
    for input_x, target_y in Training_Data:
        # 前向傳播：同時走左路 W0 與右路 A->B
        prediction = lora_layer.forward_pass(input_x, Frozen_Base_Weight=W_0)
        
        # 計算答錯的差距
        loss = Calculate_Loss(prediction, target_y)
        
        # 誤差反向傳播：【關鍵】只計算並更新 Matrix_A 與 Matrix_B 的梯度
        # W_0 的防護罩開啟，完全不參與更新！
        lora_layer.Matrix_A.Update_Gradient(loss)
        lora_layer.Matrix_B.Update_Gradient(loss)

print("🎉 訓練結束！LoRA 外掛晶片已記錄了新知識。")


# =====================================================================
# ⚡ 落地商業重點：零推論延遲的「數學熔合 (Merge)」
# =====================================================================
print("\n--- 正在進行永久熔合 (Weight Merging) ---")

# 在數學上：ΔW = B × A
Delta_W = Matrix_Multiply(lora_layer.Matrix_B, lora_layer.Matrix_A) * lora_layer.scaling

# 熔合公式：新權重 = 原廠權重 + 訓練好的外掛增量
# 相當於把便利貼的內容直接原子級地寫入原書中
W_New = W_0 + Delta_W

# 儲存合體後的新大模型
Save_Weights_To_Disk(W_New, "Merged_Production_Model")
print("🟢 熔合完成！上線推論時只需讀取 W_New，速度與原廠一模一樣，沒有任何外掛開銷。")