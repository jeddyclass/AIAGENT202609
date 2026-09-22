import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import platform

# ⚙️ 解決中文字型問題
system_os = platform.system()
if system_os == "Windows":
    plt.rcParams['font.family'] = ['Microsoft JhengHei']
elif system_os == "Darwin":
    plt.rcParams['font.family'] = ['Heiti TC']
plt.rcParams['axes.unicode_minus'] = False

# 1. 建立帶有「環」的有向加權圖
G = nx.DiGraph()

# 為了方便對照矩陣，我們刻意依照這個順序加入節點
nodes_order = ['Start', 'Thinking', 'Take_Action', 'Evaluate', 'End']
G.add_nodes_from(nodes_order)

# 定義邊與權重（成本）
edges = [
    ('Start', 'Thinking', 1),
    ('Thinking', 'Take_Action', 2),
    ('Take_Action', 'Evaluate', 1),
    ('Evaluate', 'End', 1),          # 成功路徑
    ('Evaluate', 'Thinking', 3)       # ❌ 失敗重試的回饋環 (Loop!)
]
G.add_weighted_edges_from(edges)

# 2. 獲取相鄰矩陣 (依照我們指定的頂點順序)
adj_matrix = nx.to_numpy_array(G, nodelist=nodes_order)

# 3. 控制台文字輸出：矩陣對照講解
print("=" * 60)
print(" 🔢 「環 (Loop)」在相鄰矩陣中的數學秘密")
print("=" * 60)
print(f"頂點對應順序：\n索引 0: Start\n索引 1: Thinking\n索引 2: Take_Action\n索引 3: Evaluate\n索引 4: End\n")

print("📌 有向加權相鄰矩陣 (Row=起點, Column=終點):")
print("        [Sta, Thi, Act, Eva, End]")
for i, row in enumerate(adj_matrix):
    # 格式化輸出，讓數字對齊
    row_str = " ".join([f"{val:4.1f}" for val in row])
    print(f"{nodes_order[i]:11} [{row_str}]")
print("-" * 60)

print("💡 課堂引導（你可以對著學生這樣講）：")
print("1. 正常前進 (上三角區間)：")
print("   - [0, 1] = 1.0 代表 Start ➔ Thinking")
print("   - [1, 2] = 2.0 代表 Thinking ➔ Take_Action")
print("   - [2, 3] = 1.0 代表 Take_Action ➔ Evaluate")
print("   - [3, 4] = 1.0 代表 Evaluate ➔ End")
print("\n🚀 2. 關鍵亮點：打破常規的『環』(下三角區間)！")
print("   - 看看 [3, 1] 的位置，是不是出現了 3.0？")
print("   - 這代表 Evaluate (索引3) 逆流指回了 Thinking (索引1)！")
print("   - 當有向圖的矩陣在『下三角』出現非0數字時，就暗示了『環』的存在。")
print("=" * 60)

# 4. 繪製精美視覺化圖形
plt.figure(figsize=(11, 6))
plt.title("AI Agent: 圖 (Graph) 與 相鄰矩陣中的回饋環 (Loop)", fontsize=14, fontweight='bold', pad=20)

pos = {'Start': (0, 1), 'Thinking': (1, 1), 'Take_Action': (2, 1), 'Evaluate': (3, 1), 'End': (4, 1)}
loop_edges = [('Evaluate', 'Thinking')]
normal_edges = [edge for edge in G.edges() if edge not in loop_edges]

nx.draw_networkx_nodes(G, pos, node_size=2600, node_color='#1f77b4', edgecolors='black', linewidths=1.5)
nx.draw_networkx_edges(G, pos, edgelist=normal_edges, width=2, edge_color='#1f77b4', arrowsize=20)
nx.draw_networkx_edges(G, pos, edgelist=loop_edges, width=3, edge_color='#ff7f0e', style='dashed', arrowsize=25, connectionstyle='arc3,rad=-0.5')
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')

edge_labels = {
    ('Start', 'Thinking'): '[0➔1]=1.0',
    ('Thinking', 'Take_Action'): '[1➔2]=2.0',
    ('Take_Action', 'Evaluate'): '[2➔3]=1.0',
    ('Evaluate', 'End'): '[3➔4]=1.0',
    ('Evaluate', 'Thinking'): '[3➔1]=3.0 (Loop!)'
}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=9, font_color='black')

plt.axis('off')
plt.tight_layout()
plt.show()
