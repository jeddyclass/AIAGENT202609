# pip install networkx numpy matplotlib

import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# 1. 建立圖結構 (模擬 AI Agent 的決策/狀態空間)
# ---------------------------------------------------------
# 使用有向圖 (Directed Graph) 來代表有方向性的狀態轉移
G = nx.DiGraph()

# 定義邊與權重 (起點, 終點, 權重)
# 權重可以想像成 AI 移動的距離、消耗的電量、或是評估的時間成本
edges = [
    ('Start', 'Thinking', 1),
    ('Thinking', 'Fetch_Data', 2),
    ('Thinking', 'Take_Action', 5),
    ('Fetch_Data', 'Take_Action', 1),
    ('Take_Action', 'End', 1)
]
G.add_weighted_edges_from(edges)

# ---------------------------------------------------------
# 2. 核心計算：矩陣與 AI 尋路
# ---------------------------------------------------------
# A. 相鄰矩陣 (Adjacency Matrix)
adj_matrix = nx.to_numpy_array(G)

# B. 圖拉普拉斯矩陣 (Graph Laplacian)
# 由於拉普拉斯標準定義於無向圖，我們先將其轉為無向圖計算 L = D - A
G_undirected = G.to_undirected()
laplacian_matrix = nx.laplacian_matrix(G_undirected).toarray()

# C. AI Agent 尋路 (Shortest Path)
shortest_path = nx.shortest_path(G, source='Start', target='End', weight='weight')
path_length = nx.shortest_path_length(G, source='Start', target='End', weight='weight')

# ---------------------------------------------------------
# 3. 控制台文字輸出 (與圖形互相對照)
# ---------------------------------------------------------
print("=" * 60)
print(" 📊 圖論與 AI Agent 核心概念對照表")
print("=" * 60)
print(f"📌 1. 頂點 (Nodes/V) - 代表 AI 狀態:\n   {list(G.nodes())}\n")
print(f"📌 2. 邊度數 (Out-Degree) - 'Thinking' 節點可以往外走幾步:\n   {G.out_degree('Thinking')} 步\n")

print("📌 3. 相鄰矩陣 (Adjacency Matrix) - 電腦如何儲存這張圖:")
print("   (注意首列/首行對應的頂點順序)")
print(adj_matrix, "\n")

print("📌 4. 圖拉普拉斯矩陣 (Graph Laplacian) - L = D - A:")
print(laplacian_matrix, "\n")

print("🤖 5. AI Agent 最佳規劃路徑 (Pathfinding):")
print(f"   ▶️ 最佳路線: {' ➔ '.join(shortest_path)}")
print(f"   ▶️ 總最低成本 (Total Cost): {path_length}")
print("=" * 60)

# ---------------------------------------------------------
# 4. 繪製精美視覺化圖形 (Matplotlib)
# ---------------------------------------------------------
plt.figure(figsize=(10, 6))
plt.title("AI Agent State Space & Pathfinding (Graph Theory)", fontsize=14, fontweight='bold', pad=20)

# 固定節點的版面配置，確保每次畫出來的位置都一樣，方便講解
pos = {
    'Start': (0, 1),
    'Thinking': (1, 1),
    'Fetch_Data': (2, 2),
    'Take_Action': (2, 0),
    'End': (3, 1)
}

# 標記那些在最佳路徑上的邊，我們等等要把牠們塗成紅色
path_edges = list(zip(shortest_path, shortest_path[1:]))

# 畫出所有節點
nx.draw_networkx_nodes(G, pos, node_size=2500, node_color='#1f77b4', edgecolors='black', linewidths=1.5)

# 畫出普通的邊 (灰色、虛線)
normal_edges = [edge for edge in G.edges() if edge not in path_edges]
nx.draw_networkx_edges(G, pos, edgelist=normal_edges, width=1.5, alpha=0.4, 
                       edge_color='gray', arrowsize=20, connectionstyle='arc3,rad=0.1')

# 🚀 亮點：將 AI Agent 選中的最優路徑用「粗紅線」標記出來
nx.draw_networkx_edges(G, pos, edgelist=path_edges, width=3.5, alpha=1.0, 
                       edge_color='#d62728', arrowsize=25, connectionstyle='arc3,rad=0.1')

# 加註節點名稱 (文字標籤)
nx.draw_networkx_labels(G, pos, font_size=11, font_family='sans-serif', font_weight='bold', font_color='white')

# 加註邊的權重 (Cost)
edge_labels = nx.get_edge_attributes(G, 'weight')
# 稍微調整位置避免字體重疊
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=12, font_color='#2ca02c', font_weight='bold')

# 美化視窗並顯示
plt.axis('off')
plt.tight_layout()
plt.show()
