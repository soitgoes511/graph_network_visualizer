from collections import Counter

import networkx as nx

BETWEENNESS_EXACT_NODE_LIMIT = 380
BETWEENNESS_APPROX_NODE_LIMIT = 2400
COMMUNITY_GREEDY_NODE_LIMIT = 550
COMMUNITY_APPROX_NODE_LIMIT = 3200
PAGERANK_NODE_LIMIT = 5200


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _build_weighted_projection(multigraph):
    projected = nx.DiGraph()
    projected.add_nodes_from(multigraph.nodes(data=True))

    for source, target, data in multigraph.edges(data=True):
        weight = _safe_float(data.get("weight", 1.0), 1.0)
        if projected.has_edge(source, target):
            projected[source][target]["weight"] += weight
        else:
            projected.add_edge(source, target, weight=weight)

    return projected


def _compute_communities(undirected_graph):
    if undirected_graph.number_of_nodes() < 3 or undirected_graph.number_of_edges() == 0:
        return []

    node_count = undirected_graph.number_of_nodes()
    if node_count <= COMMUNITY_GREEDY_NODE_LIMIT:
        raw_communities = list(nx.community.greedy_modularity_communities(undirected_graph))
    elif node_count <= COMMUNITY_APPROX_NODE_LIMIT:
        raw_communities = list(nx.community.asyn_lpa_communities(undirected_graph, weight="weight", seed=42))
    else:
        return []

    communities = []
    for index, community_nodes in enumerate(sorted(raw_communities, key=lambda group: len(group), reverse=True)):
        communities.append({"id": index, "nodes": list(community_nodes), "size": len(community_nodes)})
    return communities


def build_graph_from_data(nodes, links):
    """
    Build a multi-edge graph with enriched edge metadata and analytics insights.
    """
    graph = nx.MultiDiGraph()

    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            continue
        graph.add_node(node_id, **node)

    for link in links:
        source = link.get("source")
        target = link.get("target")
        if not source or not target:
            continue

        edge_attributes = {k: v for k, v in link.items() if k not in {"source", "target"}}
        edge_attributes["weight"] = _safe_float(edge_attributes.get("weight", 1.0), 1.0)
        edge_attributes["confidence"] = _safe_float(edge_attributes.get("confidence", 0.5), 0.5)
        graph.add_edge(source, target, **edge_attributes)

    insights = {
        "top_bridge_nodes": [],
        "top_communities": [],
        "relation_distribution": [],
        "graph_stats": {
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
        },
    }

    try:
        if graph.number_of_nodes() > 0:
            projected = _build_weighted_projection(graph)
            undirected = projected.to_undirected()

            degree_centrality = nx.degree_centrality(projected) if projected.number_of_nodes() > 1 else {}

            if undirected.number_of_nodes() > 2 and undirected.number_of_edges() > 0:
                if undirected.number_of_nodes() <= BETWEENNESS_EXACT_NODE_LIMIT:
                    betweenness = nx.betweenness_centrality(undirected, normalized=True, weight="weight")
                elif undirected.number_of_nodes() <= BETWEENNESS_APPROX_NODE_LIMIT:
                    k_value = max(20, min(180, int(undirected.number_of_nodes() * 0.12)))
                    betweenness = nx.betweenness_centrality(
                        undirected,
                        k=k_value,
                        normalized=True,
                        weight="weight",
                        seed=42,
                    )
                else:
                    betweenness = {}
            else:
                betweenness = {}

            try:
                pagerank = (
                    nx.pagerank(projected, alpha=0.85, weight="weight", max_iter=60, tol=1.0e-4)
                    if projected.number_of_edges() > 0 and projected.number_of_nodes() <= PAGERANK_NODE_LIMIT
                    else {}
                )
            except Exception:
                pagerank = {}

            for node_id in graph.nodes:
                weighted_degree = projected.in_degree(node_id, weight="weight") + projected.out_degree(node_id, weight="weight")
                current_value = _safe_float(graph.nodes[node_id].get("val", 0), 0)
                graph.nodes[node_id]["val"] = round(max(current_value, 1 + weighted_degree * 0.35), 3)
                graph.nodes[node_id]["degree_centrality"] = round(degree_centrality.get(node_id, 0.0), 5)
                graph.nodes[node_id]["betweenness"] = round(betweenness.get(node_id, 0.0), 5)
                graph.nodes[node_id]["pagerank"] = round(pagerank.get(node_id, 0.0), 7)

            communities = _compute_communities(undirected)
            for community in communities:
                community_id = community["id"]
                for node_id in community["nodes"]:
                    if node_id in graph.nodes:
                        graph.nodes[node_id]["community"] = community_id

            top_communities = []
            for community in communities[:5]:
                sample_titles = [graph.nodes[node_id].get("title", node_id) for node_id in community["nodes"][:3] if node_id in graph.nodes]
                top_communities.append(
                    {
                        "id": community["id"],
                        "size": community["size"],
                        "sample_nodes": sample_titles,
                    }
                )

            bridge_metric = betweenness
            if not bridge_metric:
                bridge_metric = {
                    node_id: projected.in_degree(node_id, weight="weight") + projected.out_degree(node_id, weight="weight")
                    for node_id in projected.nodes
                }

            bridge_candidates = sorted(bridge_metric.items(), key=lambda item: item[1], reverse=True)
            top_bridge_nodes = []
            for node_id, score in bridge_candidates[:8]:
                node = graph.nodes[node_id] if node_id in graph.nodes else {}
                top_bridge_nodes.append(
                    {
                        "id": node_id,
                        "title": node.get("title", node_id),
                        "type": node.get("type", "unknown"),
                        "score": round(score, 5),
                    }
                )

            relation_counter = Counter()
            for _source, _target, edge_data in graph.edges(data=True):
                relation_counter[edge_data.get("relation_type", "RELATED_TO")] += 1

            insights["top_bridge_nodes"] = top_bridge_nodes
            insights["top_communities"] = top_communities
            insights["relation_distribution"] = [
                {"relation_type": relation_type, "count": count}
                for relation_type, count in relation_counter.most_common(10)
            ]

    except Exception as error:
        print(f"Error calculating graph analytics: {error}")

    graph_data = nx.node_link_data(graph)
    serialized_links = graph_data.get("links", graph_data.get("edges", []))

    return {
        "nodes": graph_data["nodes"],
        "links": serialized_links,
        "insights": insights,
    }
