import networkx as nx
import numpy as np

# 1. 建立一個圖 (以 AI Agent 的任務規劃為例)
# 頂點代表：Agent的狀態 (起點 -> 思考中 -> 尋找知識 -> 執行動作 -> 終點)
G = nx.DiGraph()  # 建立一個有向圖 (Directed Graph)

# 新增帶有權重（Cost/距離）的邊 (Weighted Edges)
# 格式: (起點, 終點, 權重)
edges = [
    ('Start', 'Thinking', 1),
    ('Thinking', 'Fetch_Knowledge', 2),
    ('Thinking', 'Take_Action', 5),
    ('Fetch_Knowledge', 'Take_Action', 1),
    ('Take_Action', 'End', 1)
]
G.add_weighted_edges_from(edges)

print("=== 1. 基本概念與術語 (Terminology) ===")
print(f"頂點 (Nodes/V): {list(G.nodes())}")
print(f"邊 (Edges/E): {list(G.edges(data=True))}")
print(f"頂點 'Thinking' 的出度 (Out-degree): {G.out_degree('Thinking')}")
print("-" * 50)

print("=== 2. 相鄰矩陣 (Adjacency Matrix) ===")
# 轉換為相鄰矩陣 (包含權重，沒連線預設為 0)
adj_matrix = nx.to_numpy_array(G)
print("頂點順序:", list(G.nodes()))
print(adj_matrix)
print("-" * 50)

print("=== 3. 圖拉普拉斯矩陣 (Graph Laplacian) ===")
# 注意：標準拉普拉斯矩陣通常定義在無向圖。我們在此將其轉為無向圖來展示 L = D - A
G_undirected = G.to_undirected()
laplacian_matrix = nx.laplacian_matrix(G_undirected).toarray()
print("無向圖的拉普拉斯矩陣 (L = D - A):")
print(laplacian_matrix)
print("-" * 50)

print("=== 4. AI Agent 的應用：最優路徑規劃 (Planning) ===")
# 模擬 AI Agent 尋找從 'Start' 到 'End' 累積權重最小（成本最低）的路徑
shortest_path = nx.shortest_path(G, source='Start', target='End', weight='weight')
path_length = nx.shortest_path_length(G, source='Start', target='End', weight='weight')

print(f"🤖 AI Agent 最佳決策路徑: {' -> '.join(shortest_path)}")
print(f"⏳ 總消耗成本 (Total Cost): {path_length}")
