import networkx as nx
import json

def build_graph_from_data(nodes, links):
    """
    Constructs a NetworkX graph from a list of nodes and links.
    Calculates basic centrality metrics used for visualization sizing.
    """
    G = nx.DiGraph()
    
    # Add nodes first to ensure attributes are set
    # Using 'id' as the unique identifier
    for node in nodes:
        # attributes: title, type, etc.
        G.add_node(node["id"], **node)
        
    # Add edges
    for link in links:
        # Check if source/target exist? NetworkX adds them if not, but better to be safe
        G.add_edge(link["source"], link["target"])

    # Calculate metrics for visualization sizing
    try:
        if len(G.nodes) > 0:
            # Degree centrality -> val (node size)
            degree_centrality = nx.degree_centrality(G)
            # Scale it up for visibility? 
            # react-force-graph uses 'val' for radius/volume
            for n, val in degree_centrality.items():
                G.nodes[n]['val'] = val * 10 + 1 # offset to avoid 0 size
                
    except Exception as e:
        print(f"Error calculating metrics: {e}")

    # Convert to JSON format compatible with react-force-graph
    graph_data = nx.node_link_data(G)
    
    return {
        "nodes": graph_data["nodes"],
        "links": graph_data["links"]
    }
