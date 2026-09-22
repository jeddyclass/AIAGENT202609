import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import platform

# ⚙️ 解決中文字型問題
system_os = platform.system()
if system_os == "Windows":
    plt.rcParams['font.family'] = ['Microsoft JhengHei']  # 微軟正黑體
elif system_os == "Darwin":
    plt.rcParams['font.family'] = ['Heiti TC']  # Mac 黑體
else:
    plt.rcParams['font.family'] = ['sans-serif'] # Linux 預設

plt.rcParams['axes.unicode_minus'] = False  # 正常顯示負號

# 1. 建立帶有「環」的有向圖
G = nx.DiGraph()

edges = [
    ('Start', 'Thinking', 1),
    ('Thinking', 'Take_Action', 2),
    ('Take_Action', 'Evaluate', 1),
    ('Evaluate', 'End', 1),          
    ('Evaluate', 'Thinking', 3)       
]
G.add_weighted_edges_from(edges)

# 2. 找出圖中的所有環 (Cycles)
all_loops = list(nx.simple_cycles(G))
print("=" * 60)
print(f"🔍 偵測到 Agent 決策圖中的「環 (Loop)」: {all_loops}")
print("=" * 60)

# 3. 繪製精美視覺化圖形
plt.figure(figsize=(11, 6))
plt.title("AI Agent 架構: 圖 (Graph) 與 自我修正環 (Loop)", fontsize=14, fontweight='bold', pad=20)

pos = {
    'Start': (0, 1),
    'Thinking': (1, 1),
    'Take_Action': (2, 1),
    'Evaluate': (3, 1),
    'End': (4, 1)
}

loop_edges = [('Evaluate', 'Thinking')]
normal_edges = [edge for edge in G.edges() if edge not in loop_edges]

# 畫出所有節點
nx.draw_networkx_nodes(G, pos, node_size=2600, node_color='#1f77b4', edgecolors='black', linewidths=1.5)

# 畫出普通邊 (藍色箭頭)
nx.draw_networkx_edges(G, pos, edgelist=normal_edges, width=2, edge_color='#1f77b4', 
                       arrowsize=20, connectionstyle='arc3,rad=0.0')

# 畫出環的返回邊 (橘色虛線彎曲箭頭)
nx.draw_networkx_edges(G, pos, edgelist=loop_edges, width=3, edge_color='#ff7f0e', 
                       style='dashed', arrowsize=25, connectionstyle='arc3,rad=-0.5')

# 節點標籤
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')

# 🛠️ 修正點：移除 Emoji，改用中英通用字元，確保完全不報錯
edge_labels = {
    ('Start', 'Thinking'): '1.啟動',
    ('Thinking', 'Take_Action'): '2.執行',
    ('Take_Action', 'Evaluate'): '3.評估',
    ('Evaluate', 'End'): '[OK] 成功通往終點',
    ('Evaluate', 'Thinking'): '[重試] 失敗回饋環 (Loop!)'
}

nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10, font_color='black', label_pos=0.5)

plt.axis('off')
plt.tight_layout()
plt.show()
