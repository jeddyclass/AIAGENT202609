import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

# 1. 建立帶有「環」的有向圖
G = nx.DiGraph()

# 定義正常流向與「自我修正環」的邊
# ('Take_Action', 'Evaluate') ➔ ('Evaluate', 'Thinking') 這就是一個「環」！
edges = [
    ('Start', 'Thinking', 1),
    ('Thinking', 'Take_Action', 2),
    ('Take_Action', 'Evaluate', 1),
    ('Evaluate', 'End', 1),          # 成功就通往終點
    ('Evaluate', 'Thinking', 3)       # ❌ 失敗就繞回思考 (這條線構成了 Loop!)
]
G.add_weighted_edges_from(edges)

# 2. 找出圖中的所有環 (Cycles)
# networkx 內建演算法可以自動偵測圖裡面的「環」
all_loops = list(nx.simple_cycles(G))
print("=" * 60)
print(f"🔍 偵測到 Agent 決策圖中的「環 (Loop)」: {all_loops}")
print("=" * 60)

# 3. 繪製精美視覺化圖形
plt.figure(figsize=(11, 6))
plt.title("AI Agent Architecture: Graphs & The Self-Correction Loop", fontsize=14, fontweight='bold', pad=20)

# 頂點固定佈局 (X, Y 座標)
pos = {
    'Start': (0, 1),
    'Thinking': (1, 1),
    'Take_Action': (2, 1),
    'Evaluate': (3, 1),
    'End': (4, 1)
}

# 分離普通的邊與構成「環」的邊
loop_edges = [('Evaluate', 'Thinking')]
normal_edges = [edge for edge in G.edges() if edge not in loop_edges]

# 畫出所有節點
nx.draw_networkx_nodes(G, pos, node_size=2600, node_color='#1f77b4', edgecolors='black', linewidths=1.5)

# 畫出前進的普通邊 (藍色箭頭)
nx.draw_networkx_edges(G, pos, edgelist=normal_edges, width=2, edge_color='#1f77b4', 
                       arrowsize=20, connectionstyle='arc3,rad=0.0')

# 🚀 亮點：將構成「環」的返回邊畫成「橘色彎曲高亮箭頭」
nx.draw_networkx_edges(G, pos, edgelist=loop_edges, width=3, edge_color='#ff7f0e', 
                       style='dashed', arrowsize=25, connectionstyle='arc3,rad=-0.5')

# 標籤與權重
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')

# 加註邊的文字說明（方便聽眾理解環的意義）
edge_labels = {
    ('Start', 'Thinking'): '1.啟動',
    ('Thinking', 'Take_Action'): '2.執行',
    ('Take_Action', 'Evaluate'): '3.評估',
    ('Evaluate', 'End'): '✅ 成功',
    ('Evaluate', 'Thinking'): '❌ 失敗重試 (Loop!)'
}
# 微調邊標籤的位置
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10, font_color='black', label_pos=0.5)

plt.axis('off')
plt.tight_layout()
plt.show()
