import numpy as np
from scipy.sparse.csgraph import dijkstra

stations = ["台北車站", "中山站", "西門站"]
INF = float('inf')

# 建立票價矩陣 (沒直達寫 INF，自己到自己寫 0)
fare_matrix = np.array([
    [0, 20, 20],   # 台北車站 到 北車(0)、中山(20)、西門(20)
    [20, 0, INF],  # 中山站   到 北車(20)、中山(0)、西門(無限大/沒直達)
    [20, INF, 0]   # 西門站   到 北車(20)、中山(無限大/沒直達)、西門(0)
])

# 應用：使用著名的 Dijkstra 演算法計算「所有車站之間的最省錢票價」
dist_matrix = dijkstra(csgraph=fare_matrix, directed=False)

print("--- 電腦計算出的【最省錢票價矩陣】 ---")
for i, start in enumerate(stations):
    for j, end in enumerate(stations):
        print(f"從 [{start}] 到 [{end}] 最少需要: {int(dist_matrix[i][j])} 元")
