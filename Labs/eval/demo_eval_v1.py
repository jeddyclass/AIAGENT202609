import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
import platform

# ⚙️ 解決中文字型問題
if platform.system() == "Windows": plt.rcParams['font.family'] = ['Microsoft JhengHei']
elif platform.system() == "Darwin": plt.rcParams['font.family'] = ['Heiti TC']
plt.rcParams['axes.unicode_minus'] = False

def run_agent_demo(validation_passed=False):
    G = nx.DiGraph()
    nodes_order = ['Start', 'Thinking', 'Evaluate', 'End']
    G.add_nodes_from(nodes_order)
    
    # 基本思考與評估
    G.add_edge('Start', 'Thinking', weight=1)
    G.add_edge('Thinking', 'Evaluate', weight=1)
    
    # 🎯 動態對齊與驗證機制
    if validation_passed:
        # 驗證通過：開啟通往終點的路，關閉失敗環
        G.add_edge('Evaluate', 'End', weight=1)
        status_text = "【案例 A：驗證通過 ➔ 開啟終點通道】"
    else:
        # 驗證失敗：通往終點的成本變無限大（此處不連線），並強迫進入『回饋環』
        G.add_edge('Evaluate', 'Thinking', weight=3)
        status_text = "【案例 B：驗證失敗 ➔ 強制導流回 Retry Loop】"
        
    return G, nodes_order, status_text

# 我們以「驗證失敗」為例進行繪圖與矩陣展示
G, nodes_order, status = run_agent_demo(validation_passed=False)
adj_matrix = nx.to_numpy_array(G, nodelist=nodes_order)

print("=" * 60)
print(status)
print("=" * 60)
print("📌 當驗證失敗時，Agent 大腦的相鄰矩陣狀態：")
print("          [Start, Thinking, Evaluate, End]")
for i, row in enumerate(adj_matrix):
    row_str = " ".join([f"{val:5.1f}" for val in row])
    print(f"{nodes_order[i]:10} [{row_str}]")
print("\n💡 數學解讀：")
print("Evaluate (索引2) 到 End (索引3) 的數值是 0.0（此路不通）！")
print("取而代之的是 Evaluate ➔ Thinking 出現 3.0，這就是『驗證失敗硬性導流』。")
print("=" * 60)

# 繪製圖形
plt.figure(figsize=(10, 5))
plt.title(f"AI Agent 驗證與對齊機制\n{status}", fontsize=13, fontweight='bold')
pos = {'Start': (0, 1), 'Thinking': (1, 1), 'Evaluate': (2, 1), 'End': (3, 1)}

# 畫出節點與邊
nx.draw_networkx_nodes(G, pos, node_size=2500, node_color='#1f77b4', edgecolors='black')
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')

# 根據狀態著色
if ('Evaluate', 'Thinking') in G.edges():
    nx.draw_networkx_edges(G, pos, edgelist=[('Start', 'Thinking'), ('Thinking', 'Evaluate')], width=2, edge_color='gray')
    nx.draw_networkx_edges(G, pos, edgelist=[('Evaluate', 'Thinking')], width=3, edge_color='#d62728', style='dashed', connectionstyle='arc3,rad=-0.5')
    edge_labels = {('Start', 'Thinking'): '啟動', ('Thinking', 'Evaluate'): '生成解答', ('Evaluate', 'Thinking'): '❌ 驗證未對齊 (重試)'}
else:
    nx.draw_networkx_edges(G, pos, edgelist=G.edges(), width=2, edge_color='#2ca02c')
    edge_labels = {('Start', 'Thinking'): '啟動', ('Thinking', 'Evaluate'): '生成', ('Evaluate', 'End'): '✅ 驗證成功 (放行)'}

nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10)
plt.axis('off')
plt.tight_layout()
plt.show()
