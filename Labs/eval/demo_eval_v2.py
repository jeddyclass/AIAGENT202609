import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

def generate_agent_graph(alignment_success=False):
    """
    Simulates an AI Agent's graph layout based on alignment/validation results.
    """
    G = nx.DiGraph()
    # Explicit node order for the adjacency matrix
    nodes_order = ['Start', 'Thinking', 'Evaluate', 'End']
    G.add_nodes_from(nodes_order)
    
    # Core reasoning chain (Graph Structure)
    G.add_edge('Start', 'Thinking', weight=1.0)
    G.add_edge('Thinking', 'Evaluate', weight=1.0)
    
    # Dynamic Alignment / Guardrail Mechanism
    if alignment_success:
        # Scenario A: Validation passed -> Open edge to End
        G.add_edge('Evaluate', 'End', weight=1.0)
        scenario_title = "Scenario A: Alignment Passed (Path to End Opened)"
    else:
        # Scenario B: Validation failed -> Close path to End, route back to Thinking (Loop)
        G.add_edge('Evaluate', 'Thinking', weight=3.0)
        scenario_title = "Scenario B: Alignment Failed (Forced Correction Loop)"
        
    return G, nodes_order, scenario_title

# -----------------------------------------------------------------
# Execution & Analysis (Let's simulate a FAILED validation first)
# -----------------------------------------------------------------
G, nodes_order, title = generate_agent_graph(alignment_success=False)
adj_matrix = nx.to_numpy_array(G, nodelist=nodes_order)

print("=" * 70)
print(title)
print("=" * 70)
print("📌 AI Agent's Adjacency Matrix (Brain State):")
print("            [Start, Thinking, Evaluate, End]")
for i, row in enumerate(adj_matrix):
    row_str = " ".join([f"{val:6.1f}" for val in row])
    print(f"{nodes_order[i]:11} [{row_str}]")

print("\n💡 Mathematical Insight for Students:")
print("- Notice the row for 'Evaluate' (Index 2).")
print("- Column 'End' (Index 3) is 0.0 -> The guardrail has blocked this path.")
print("- Column 'Thinking' (Index 1) is 3.0 -> A sub-diagonal entry signifying a Loop!")
print("=" * 70)

# -----------------------------------------------------------------
# Visualizing the Alignment Guardrail using Matplotlib
# -----------------------------------------------------------------
plt.figure(figsize=(10, 5))
plt.title(f"AI Agent Alignment & Guardrail Mechanism\n{title}", fontsize=12, fontweight='bold', pad=15)

# Horizontal timeline layout
pos = {'Start': (0, 1), 'Thinking': (1, 1), 'Evaluate': (2, 1), 'End': (3, 1)}

# Draw Nodes
nx.draw_networkx_nodes(G, pos, node_size=2800, node_color='#1f77b4', edgecolors='black', linewidths=1.5)
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')

# Dynamic Edge Rendering based on Scenario
if ('Evaluate', 'Thinking') in G.edges():
    # Render failed alignment (Red dashed loop line)
    nx.draw_networkx_edges(G, pos, edgelist=[('Start', 'Thinking'), ('Thinking', 'Evaluate')], width=2, edge_color='gray', arrowsize=20)
    nx.draw_networkx_edges(G, pos, edgelist=[('Evaluate', 'Thinking')], width=3, edge_color='#d62728', style='dashed', arrowsize=25, connectionstyle='arc3,rad=-0.5')
    edge_labels = {
        ('Start', 'Thinking'): 'Init', 
        ('Thinking', 'Evaluate'): 'Generate Response', 
        ('Evaluate', 'Thinking'): 'Alignment Failed (Retry)'
    }
else:
    # Render successful alignment (Green lines)
    nx.draw_networkx_edges(G, pos, edgelist=G.edges(), width=2, edge_color='#2ca02c', arrowsize=20)
    edge_labels = {
        ('Start', 'Thinking'): 'Init', 
        ('Thinking', 'Evaluate'): 'Generate Response', 
        ('Evaluate', 'End'): 'Aligned (Exit)'
    }

nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=9, font_weight='bold')

plt.axis('off')
plt.tight_layout()
plt.show()
