import networkx as nx
from typing import Dict, Any, List
from app.graph_engine import graph_manager

# NOTE: This is a leave-one-out validation sanity check designed specifically for the 6-edge synthetic seed dataset,
# establishing a verifiable baseline floor before migrating to the 15-20% holdout methodology on larger production datasets.

def evaluate_link_prediction_leave_one_out() -> Dict[str, Any]:
    """
    Leave-One-Out link prediction evaluation on the baseline Common-Neighbors heuristic.
    Iteratively removes each true edge, re-scores all missing pairs, and measures recovery rank.
    """
    graph_manager.build_graph()
    original_g = graph_manager.G
    edges_list = list(original_g.edges(data=True))
    nodes = list(original_g.nodes())

    if len(edges_list) == 0:
        return {
            "status": "error",
            "message": "Evidentiary graph is empty"
        }

    per_edge_results = []
    ranks = []
    top3_recovered = 0

    for u, v, data in edges_list:
        # Create an isolated copy without this edge
        g_temp = original_g.copy()
        g_temp.remove_edge(u, v)

        # Score all non-edges in g_temp using Common Neighbors
        candidate_scores = []
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                n1, n2 = nodes[i], nodes[j]
                if not g_temp.has_edge(n1, n2):
                    cn = list(nx.common_neighbors(g_temp, n1, n2))
                    deg1 = g_temp.degree(n1)
                    deg2 = g_temp.degree(n2)
                    union_size = deg1 + deg2 - len(cn)
                    score = (len(cn) / union_size) if union_size > 0 else 0.0
                    candidate_scores.append((n1, n2, score, len(cn)))

        # Sort candidate non-edges descending by score
        candidate_scores.sort(key=lambda x: x[2], reverse=True)

        # Find the rank of the removed true edge (u, v)
        true_rank = None
        true_score = 0.0
        shared_neighbors_count = 0
        for rank_idx, (c1, c2, sc, cn_count) in enumerate(candidate_scores, start=1):
            if (c1 == u and c2 == v) or (c1 == v and c2 == u):
                true_rank = rank_idx
                true_score = sc
                shared_neighbors_count = cn_count
                break

        is_top3 = (true_rank is not None and true_rank <= 3 and shared_neighbors_count > 0)
        if is_top3:
            top3_recovered += 1

        if true_rank is not None:
            ranks.append(true_rank)

        per_edge_results.append({
            "edge": f"{u} ↔ {v}",
            "edge_id": data.get("edge_id"),
            "channel": data.get("channel"),
            "evidence_tier": data.get("evidence_tier"),
            "rank": true_rank,
            "score": round(true_score, 4),
            "common_neighbors_count": shared_neighbors_count,
            "recovered_in_top3": is_top3
        })

    mean_rank = round(sum(ranks) / len(ranks), 2) if ranks else 0.0
    recovery_rate = round((top3_recovered / len(edges_list)) * 100, 1)

    return {
        "status": "success",
        "methodology": "Leave-One-Out Cross Validation (Baseline Common Neighbors)",
        "dataset_edges_evaluated": len(edges_list),
        "top3_recovered_count": top3_recovered,
        "top3_recovery_rate_pct": recovery_rate,
        "mean_recovery_rank": mean_rank,
        "details": per_edge_results,
        "production_upgrade_note": "Evaluated against common-neighbors baseline. Production roadmap specifies inductive GraphSAGE GNN validation."
    }
