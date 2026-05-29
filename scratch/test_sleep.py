import sys
import os
import networkx as nx

# Create a sample DiGraph
g = nx.DiGraph()
g.add_node("A")
g.add_node("B")
g.add_edge("A", "B", relation="is_a", confidence=0.8)

# Simulating the bug in run_cognitive_sleep_cycle:
print("Keys of graph[A][B]:", list(g["A"]["B"]))
try:
    for edge_rel in list(g["A"]["B"]):
        curr_conf = g["A"]["B"][edge_rel].get("confidence", 1.0)
        print("Successful get:", curr_conf)
except Exception as e:
    print("CRASHED WITH:", type(e), str(e))
