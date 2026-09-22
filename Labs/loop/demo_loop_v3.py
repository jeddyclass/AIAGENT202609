import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

# 1. Create a directed graph with a loop
G = nx.DiGraph()

edges = [
    ('Start', 'Thinking', 1),
    ('Thinking', 'Take_Action', 2),
    ('Take_Action', 'Evaluate', 1),
    ('Evaluate', 'End', 1),          
    ('Evaluate', 'Thinking', 3)       
]
G.add_weighted_edges_from(edges)

# 2. Draw the visualization (Pure English - No Warnings)
plt.figure(figsize=(11, 6))
plt.title("AI Agent Architecture: Graphs & Loops", fontsize=14, fontweight='bold', pad=20)

pos = {'Start': (0, 1), 'Thinking': (1, 1), 'Take_Action': (2, 1), 'Evaluate': (3, 1), 'End': (4, 1)}
loop_edges = [('Evaluate', 'Thinking')]
normal_edges = [edge for edge in G.edges() if edge not in loop_edges]

nx.draw_networkx_nodes(G, pos, node_size=2600, node_color='#1f77b4', edgecolors='black', linewidths=1.5)
nx.draw_networkx_edges(G, pos, edgelist=normal_edges, width=2, edge_color='#1f77b4', arrowsize=20)
nx.draw_networkx_edges(G, pos, edgelist=loop_edges, width=3, edge_color='#ff7f0e', style='dashed', arrowsize=25, connectionstyle='arc3,rad=-0.5')
nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')

# English labels (Clean & Professional)
edge_labels = {
    ('Start', 'Thinking'): '1. Init',
    ('Thinking', 'Take_Action'): '2. Act',
    ('Take_Action', 'Evaluate'): '3. Eval',
    ('Evaluate', 'End'): 'Success -> Exit',
    ('Evaluate', 'Thinking'): 'Failed -> Retry Loop'
}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10, font_color='black')

plt.axis('off')
plt.tight_layout()
plt.show()
