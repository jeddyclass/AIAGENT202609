import numpy as np

# 1. 建立「多蓋一座橋」後的全新鄰接矩陣
# 順序依然為: [A:北岸, B:南岸, C:小島, D:大島]
# 注意：第一列與第二列的 A-B 連線從 0 變成了 1
new_bridge_matrix = np.array([
    [0, 1, 2, 1],  # A 連結了 1座到B, 2座到C, 1座到D
    [1, 0, 2, 1],  # B 連結了 1座到A, 2座到C, 1座到D
    [2, 2, 0, 1],  # C 連結了 2座到A, 2座到B, 1座到D
    [1, 1, 1, 0]   # D 連結了 1座到A, 1座到B, 1座到C
])

regions = ["北岸(A)", "南岸(B)", "小島(C)", "大島(D)"]

print("--- 現代化改建後的新七橋矩陣（共8座橋） ---")
print(new_bridge_matrix)

# 2. 計算每個區域連接的橋樑總數
bridge_counts = new_bridge_matrix.sum(axis=1)

print("\n--- 各陸地連接的全新橋樑總數 ---")
odd_nodes_count = 0
odd_regions = []

for i, region in enumerate(regions):
    count = bridge_counts[i]
    is_odd = "奇數" if count % 2 != 0 else "偶數"
    print(f"[{region}] 連接了 {count} 座橋 ({is_odd})")
    
    if count % 2 != 0:
        odd_nodes_count += 1
        odd_regions.append(region)

# 3. 尤拉定理全新判斷
print(f"\n--- 尤拉演算法分析結果 ---")
print(f"全圖中共有 {odd_nodes_count} 個區域連接了『奇數』座橋。")

if odd_nodes_count == 0 or odd_nodes_count == 2:
    print("【成功】這張新地圖可以不重複地走完所有橋樑了！")
    if odd_nodes_count == 2:
        print(f"💡 電腦導航建議：你必須從【{odd_regions[0]}】出發，並在【{odd_regions[1]}】結束，才能成功！")
else:
    print("【無解】奇數區域數量不對，依然走不完。")
