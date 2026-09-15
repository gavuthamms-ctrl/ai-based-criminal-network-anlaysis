import networkx as nx
import community as community_louvain
from typing import Dict, Any, List, Tuple
from app.db import get_all_persons, get_all_relationships

# Production upgrade note:
# NOTE: GraphSAGE (GNN) is the specified production upgrade path for scalable inductive link prediction.
# For this prototype, Common Neighbors similarity heuristic provides a verified, mathematically transparent baseline.

EVIDENCE_TIER_STYLES = {
    "direct_evidence": {
        "color": "#1e293b",
        "highlight": "#0f172a",
        "dashes": False,
        "width": 3.5,
        "title": "Direct Evidence (Documented in FIR/Case Record)",
        "badge_class": "badge-direct"
    },
    "corroborated_association": {
        "color": "#d97706",
        "highlight": "#b45309",
        "dashes": False,
        "width": 2.8,
        "title": "Corroborated Association (Multi-source CDR/Banking data)",
        "badge_class": "badge-corroborated"
    },
    "analytical_inference": {
        "color": "#ea580c",
        "highlight": "#c2410c",
        "dashes": [6, 6],
        "width": 2.2,
        "title": "Analytical Inference (Network Structure / Shared Patterns)",
        "badge_class": "badge-inference"
    },
    "ai_predicted_link": {
        "color": "#ef4444",
        "highlight": "#b91c1c",
        "dashes": [4, 4],
        "width": 2.0,
        "title": "AI-Predicted Link (Baseline Common-Neighbors / GraphSAGE Candidate)",
        "badge_class": "badge-predicted"
    }
}

class NetworkGraphManager:
    def __init__(self):
        self.G = nx.Graph()
        self.persons_cache = {}
        self.relationships_cache = []
        self.metrics = {}
        self.communities = {}

    def build_graph(self) -> nx.Graph:
        """Constructs NetworkX graph from MySQL database records."""
        self.G = nx.Graph()
        persons = get_all_persons()
        relationships = get_all_relationships()

        self.persons_cache = {p["person_id"]: p for p in persons}
        self.relationships_cache = relationships

        # Add nodes
        for p in persons:
            self.G.add_node(
                p["person_id"],
                display_name=p["display_name"],
                phone=p["phone_number"],
                aliases=p["known_aliases"],
                address=p["address"],
                confidence=float(p["resolution_confidence"] or 1.0)
            )

        # Add edges
        for r in relationships:
            u, v = r["person_a_id"], r["person_b_id"]
            if u in self.persons_cache and v in self.persons_cache:
                self.G.add_edge(
                    u, v,
                    edge_id=r["edge_id"],
                    channel=r["channel"],
                    evidence_tier=r["evidence_tier"],
                    confidence_score=float(r["confidence_score"]) if r["confidence_score"] is not None else None,
                    source_record_id=r["source_record_id"],
                    frequency=r.get("frequency", 1)
                )

        self._compute_metrics()
        return self.G

    def _compute_metrics(self):
        if len(self.G.nodes) == 0:
            return

        # Centrality metrics
        deg_centrality = nx.degree_centrality(self.G)
        bet_centrality = nx.betweenness_centrality(self.G)
        
        # Louvain community detection
        try:
            partition = community_louvain.best_partition(self.G)
        except Exception:
            partition = {n: 0 for n in self.G.nodes}

        self.communities = partition

        # Percentiles for priority assignment
        bet_values = sorted(bet_centrality.values())
        n = len(bet_values)

        self.metrics = {}
        for node in self.G.nodes:
            bc = bet_centrality.get(node, 0.0)
            dc = deg_centrality.get(node, 0.0)
            comm = partition.get(node, 0)
            
            # Rank percentile
            rank = sum(1 for v in bet_values if v <= bc)
            pct = int((rank / n) * 100) if n > 0 else 50
            
            # Determine priority
            if pct >= 80 or bc > 0.35:
                priority = "HIGH"
                role = "Bridge / Coordinator candidate"
            elif pct >= 50 or bc > 0.15:
                priority = "MEDIUM"
                role = "Active Cluster Associate"
            else:
                priority = "LOW"
                role = "Peripheral Member"

            self.metrics[node] = {
                "degree_centrality": round(dc, 4),
                "betweenness_centrality": round(bc, 4),
                "betweenness_percentile": pct,
                "community_id": comm,
                "priority": priority,
                "network_role": role
            }

    def predict_links_common_neighbors(self, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Common-Neighbors Link Prediction baseline heuristic.
        Calculates |N(u) ∩ N(v)| for unconnected pairs.
        """
        predictions = []
        nodes = list(self.G.nodes)
        
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                u, v = nodes[i], nodes[j]
                if not self.G.has_edge(u, v):
                    cn = list(nx.common_neighbors(self.G, u, v))
                    if len(cn) > 0:
                        # Jaccard / Adamic-Adar normalized confidence score
                        deg_u = self.G.degree(u)
                        deg_v = self.G.degree(v)
                        union_size = deg_u + deg_v - len(cn)
                        score = len(cn) / union_size if union_size > 0 else 0.5
                        confidence = round(min(0.95, max(0.50, 0.55 + score * 0.4)), 3)
                        
                        predictions.append({
                            "person_a_id": u,
                            "person_b_id": v,
                            "person_a_name": self.persons_cache.get(u, {}).get("display_name", u),
                            "person_b_name": self.persons_cache.get(v, {}).get("display_name", v),
                            "common_neighbors": cn,
                            "common_neighbors_names": [self.persons_cache.get(c, {}).get("display_name", c) for c in cn],
                            "channel": "ai_predicted",
                            "evidence_tier": "ai_predicted_link",
                            "confidence_score": confidence,
                            "note": f"Shared {len(cn)} common associates: {', '.join(cn)}. Production roadmap: GraphSAGE inductive validation."
                        })

        predictions.sort(key=lambda x: x["confidence_score"], reverse=True)
        return predictions[:top_k]

    def get_vis_graph(self) -> Dict[str, Any]:
        """Formats nodes and edges for Vis.js Network visualization with tier styles."""
        self.build_graph()
        
        # Color palette for communities
        COMMUNITY_COLORS = {
            0: {"bg": "#3b82f6", "border": "#1d4ed8"}, # Blue
            1: {"bg": "#10b981", "border": "#047857"}, # Green
            2: {"bg": "#8b5cf6", "border": "#6d28d9"}, # Purple
            3: {"bg": "#f59e0b", "border": "#b45309"}, # Amber
        }

        vis_nodes = []
        for node_id, data in self.G.nodes(data=True):
            metric = self.metrics.get(node_id, {})
            comm = metric.get("community_id", 0)
            priority = metric.get("priority", "LOW")
            
            # Special highlighting for high priority/key bridge person (e.g. P17)
            if priority == "HIGH":
                node_color = {"background": "#dc2626", "border": "#991b1b", "highlight": {"background": "#ef4444", "border": "#7f1d1d"}}
                font_color = "#ffffff"
                size = 32
                shape = "dot"
            else:
                c = COMMUNITY_COLORS.get(comm % 4, COMMUNITY_COLORS[0])
                node_color = {"background": c["bg"], "border": c["border"], "highlight": {"background": "#60a5fa", "border": "#1e40af"}}
                font_color = "#ffffff"
                size = 22
                shape = "dot"

            p_info = self.persons_cache.get(node_id, {})
            vis_nodes.append({
                "id": node_id,
                "label": f"{node_id}\n{p_info.get('display_name', '')}",
                "title": f"<b>{p_info.get('display_name')}</b> ({node_id})<br>Role: {metric.get('network_role')}<br>Priority: {priority}<br>Betweenness Centrality: {metric.get('betweenness_centrality')}<br>Community: Cluster {comm + 1}",
                "color": node_color,
                "size": size,
                "shape": shape,
                "font": {"color": font_color, "size": 13, "face": "Inter, system-ui, sans-serif"},
                "borderWidth": 2,
                "shadow": True,
                "data": {
                    "person_id": node_id,
                    "display_name": p_info.get("display_name"),
                    "aliases": p_info.get("known_aliases"),
                    "phone": p_info.get("phone_number"),
                    "vehicle": p_info.get("vehicle_number"),
                    "account": p_info.get("account_number"),
                    "address": p_info.get("address"),
                    "metrics": metric
                }
            })

        vis_edges = []
        for u, v, data in self.G.edges(data=True):
            tier = data.get("evidence_tier", "direct_evidence")
            style = EVIDENCE_TIER_STYLES.get(tier, EVIDENCE_TIER_STYLES["direct_evidence"])
            
            label = data.get("channel", "")
            if data.get("confidence_score") is not None:
                label += f" ({int(data['confidence_score'] * 100)}%)"

            vis_edges.append({
                "id": f"e_{u}_{v}",
                "from": u,
                "to": v,
                "label": label,
                "color": {"color": style["color"], "highlight": style["highlight"], "hover": style["highlight"]},
                "dashes": style["dashes"],
                "width": style["width"],
                "font": {"size": 11, "align": "middle", "color": "#475569", "background": "rgba(255,255,255,0.85)"},
                "title": f"<b>Tier: {tier.replace('_', ' ').title()}</b><br>Channel: {data.get('channel')}<br>Source: {data.get('source_record_id')}<br>Frequency: {data.get('frequency', 1)}",
                "arrows": {"to": {"enabled": False}},
                "data": {
                    "edge_id": data.get("edge_id"),
                    "tier": tier,
                    "channel": data.get("channel"),
                    "source": data.get("source_record_id"),
                    "confidence": data.get("confidence_score"),
                    "frequency": data.get("frequency")
                }
            })

        predicted_links = self.predict_links_common_neighbors()

        return {
            "nodes": vis_nodes,
            "edges": vis_edges,
            "predicted_links": predicted_links,
            "summary": {
                "node_count": len(vis_nodes),
                "edge_count": len(vis_edges),
                "high_priority_count": sum(1 for n in vis_nodes if n["data"]["metrics"].get("priority") == "HIGH"),
                "communities_count": len(set(self.communities.values())) if self.communities else 0
            }
        }

graph_manager = NetworkGraphManager()
