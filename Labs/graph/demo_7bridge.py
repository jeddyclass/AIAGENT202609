import numpy as np

# 1. 建立七橋問題的鄰接矩陣 (Multigraph Adjacency Matrix)
# 順序為: [A:北岸, B:南岸, C:小島, D:大島]
konigsberg_matrix = np.array([
    [0, 0, 2, 1],  # A 連結了 2座到C, 1座到D
    [0, 0, 2, 1],  # B 連結了 2座到C, 1座到D
    [2, 2, 0, 1],  # C 連結了 2座到A, 2座到B, 1座到D
    [1, 1, 1, 0]   # D 連結了 1座到A, 1座到B, 1座到C
])

regions = ["北岸(A)", "南岸(B)", "小島(C)", "大島(D)"]

print("--- 普魯士哥尼斯堡七橋矩陣 ---")
print(konigsberg_matrix)

# 2. 電腦應用：計算每個區域連接了幾座橋 (計算節點的度數 Degree)
# 橫排直接加總就是該區域連出去的橋樑總數
bridge_counts = konigsberg_matrix.sum(axis=1)

print("\n--- 各陸地連接的橋樑總數 ---")
odd_nodes_count = 0

for i, region in enumerate(regions):
    count = bridge_counts[i]
    is_odd = "奇數" if count % 2 != 0 else "偶數"
    print(f"[{region}] 連接了 {count} 座橋 ({is_odd})")
    
    if count % 2 != 0:
        odd_nodes_count += 1

# 3. 尤拉定理判斷
print(f"\n--- 尤拉演算法分析結果 ---")
print(f"全圖中共有 {odd_nodes_count} 個區域連接了『奇數』座橋。")

# 尤拉路徑定理：奇數節點數量必須為 0 或 2 才能走完
if odd_nodes_count == 0 or odd_nodes_count == 2:
    print("【成功】這張地圖可以不重複地走完所有橋樑！")
else:
    print("【無解】尤拉定理證明：不可能不重複地走完這七座橋！")
