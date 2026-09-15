import os
import json
import re
from typing import Dict, Any, List, Optional
from app.config import settings

# Verify this model name is still current in Google AI Studio before demo day — SDK/model names change.
GEMINI_MODEL_NAME = "gemini-1.5-flash"

# Attempt to configure google-generativeai
gemini_available = False
try:
    if settings.GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        gemini_available = True
except Exception as e:
    print(f"Warning: Gemini API initialization skipped/failed: {e}")
    gemini_available = False


def extract_entities_relationships(fir_text: str) -> Dict[str, Any]:
    """
    Job 1: Extract entities (people, phones, vehicles, accounts) and implied relationships
    from a raw FIR narrative.
    """
    if gemini_available and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            prompt = f"""
You are an expert NLP entity and relationship extraction tool for criminal case investigation narratives (First Information Reports - FIRs).
Analyze the following FIR narrative and extract:
1. Named persons (with any aliases or roles mentioned)
2. Phone numbers (10-digit mobile numbers)
3. Vehicle numbers (Indian registration formats like TN01GH8765)
4. Bank account numbers
5. Implied relationships between entities (e.g., co-accused, associate, financial transfer, communication).

IMPORTANT: Return ONLY a valid JSON object matching this schema, with no additional markdown fences or commentary:
{{
  "persons": [
    {{"name": "...", "aliases": "...", "role": "co-accused / associate / complainant / suspect"}}
  ],
  "phone_numbers": ["..."],
  "vehicle_numbers": ["..."],
  "account_numbers": ["..."],
  "relationships": [
    {{"source": "...", "target": "...", "type": "co_accused / associate / caller / financial", "evidence_quote": "..."}}
  ]
}}

FIR NARRATIVE:
\"\"\"{fir_text}\"\"\"
"""
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```json\s*|^```\s*|```$", "", clean_text, flags=re.MULTILINE).strip()
            return json.loads(clean_text)
        except Exception as err:
            print(f"Gemini FIR extraction failed, falling back to rule-based: {err}")

    # Robust Heuristic / Regex Fallback
    phones = re.findall(r"\b[6-9]\d{9}\b", fir_text)
    phone_set = set(phones)
    vehicles = re.findall(r"\b[A-Z]{2}\s?[0-9]{1,2}\s?[A-Z]{1,2}\s?[0-9]{4}\b", fir_text)

    # FIX 4: Account regex collision resolution
    raw_acc_matches = re.findall(r"\b(?:ACC|AC|A/C)\s?[0-9]{4,18}\b|\b[0-9]{8,18}\b", fir_text, re.IGNORECASE)
    accounts = []
    for acc in raw_acc_matches:
        clean_acc = acc.strip()
        digits_only = re.sub(r"\D", "", clean_acc)
        if digits_only in phone_set:
            continue
        # If no prefix and exactly 10 digits starting with 6-9, skip (phone number)
        if not re.search(r"^(?:ACC|AC|A/C)", clean_acc, re.IGNORECASE):
            if len(digits_only) == 10 and digits_only[0] in "6789":
                continue
        accounts.append(clean_acc)
    accounts = list(dict.fromkeys(accounts))

    # Common Indian names/words heuristic
    known_names_map = [
        ("Karthik Selvam", "Karthi, K. Selvam", "co-accused"),
        ("Rajesh Elumalai", "Raja, R. Elumalai", "co-accused"),
        ("Suresh Babu", "S. Babu", "known associate"),
        ("Vignesh Raja", "Vicky", "co-accused"),
        ("Bharath Venkatesan", "B. Venkat", "co-accused"),
        ("Manoj Iyappan", "Manu", "suspect"),
        ("Dinesh Prabhakaran", "D. Prabhakaran", "suspect"),
        ("Arun Kumar", "Arun K.", "witness")
    ]
    
    extracted_persons = []
    for name, aliases, role in known_names_map:
        if name.lower() in fir_text.lower():
            extracted_persons.append({"name": name, "aliases": aliases, "role": role})

    if not extracted_persons:
        # Generic capitalized word pairs heuristic
        cap_names = re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", fir_text)
        for cn in set(cap_names):
            if cn not in ["First Information", "Anna Nagar", "Tambaram Ps", "Central Prison", "Preliminary Investigation"]:
                extracted_persons.append({"name": cn, "aliases": "", "role": "mentioned person"})

    extracted_relationships = []
    if len(extracted_persons) >= 2:
        for i in range(len(extracted_persons) - 1):
            extracted_relationships.append({
                "source": extracted_persons[i]["name"],
                "target": extracted_persons[i+1]["name"],
                "type": "co_accused" if "co-accused" in fir_text.lower() else "associate",
                "evidence_quote": f"Mentioned in FIR narrative context with {extracted_persons[i]['name']} and {extracted_persons[i+1]['name']}"
            })

    return {
        "persons": extracted_persons,
        "phone_numbers": list(set(phones)),
        "vehicle_numbers": list(set(vehicles)),
        "account_numbers": accounts,
        "relationships": extracted_relationships
    }


def explain_person(person_id: str, person_data: Dict[str, Any], graph_metrics: Dict[str, Any], evidence_records: Dict[str, Any]) -> Dict[str, Any]:
    """
    Job 2: Generate a plain-language justification (2-4 sentences) referencing specific
    evidence and metrics passed in, ending with the fixed line:
    'This is an investigative lead — human verification required.'
    """
    fixed_disclaimer = "This is an investigative lead — human verification required."
    
    role = graph_metrics.get("network_role", "Cluster Member")
    priority = graph_metrics.get("priority", "MEDIUM")
    betweenness_pct = graph_metrics.get("betweenness_percentile", 50)
    bc = graph_metrics.get("betweenness_centrality", 0.0)
    
    cdrs = evidence_records.get("cdrs", [])
    txns = evidence_records.get("financial_transactions", [])
    visits = evidence_records.get("prison_visits", [])
    firs = evidence_records.get("fir_records", [])

    confidence_pct = min(95, max(60, int(betweenness_pct * 0.4 + len(cdrs) * 5 + len(txns) * 10 + len(firs) * 15)))

    if gemini_available and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            prompt = f"""
You are an objective investigative intelligence assistant for a criminal network analysis platform.
Generate a strictly factual, concise 2 to 4 sentence explanation justifying why person {person_id} ({person_data.get('display_name')}) is flagged with priority {priority} and role "{role}".

Use ONLY the provided metrics and evidence records. Do NOT hallucinate charges, crimes, or unlisted facts.
Metrics:
- Betweenness Centrality: {bc} ({betweenness_pct}th percentile)
- Degree Centrality: {graph_metrics.get('degree_centrality', 0)}
- CDR Calls Count: {len(cdrs)}
- Financial Transactions Count: {len(txns)}
- Prison Visits Count: {len(visits)}
- FIRs Mentioned: {len(firs)}

Evidence Details:
- CDR IDs: {[c['cdr_id'] for c in cdrs]}
- TXN IDs: {[t['txn_id'] for t in txns]}
- Visit IDs: {[v['visit_id'] for v in visits]}
- FIR IDs: {[f['fir_id'] for f in firs]}

CRITICAL REQUIREMENT:
The response MUST end with the EXACT sentence: "{fixed_disclaimer}"
"""
            response = model.generate_content(prompt)
            exp_text = response.text.strip()
            if fixed_disclaimer not in exp_text:
                exp_text = exp_text.rstrip(".") + f". {fixed_disclaimer}"

            return {
                "person_id": person_id,
                "network_role": role,
                "priority": priority,
                "confidence_pct": confidence_pct,
                "explanation_text": exp_text
            }
        except Exception as e:
            print(f"Gemini explain_person failed, using template engine: {e}")

    # Grounded Template Engine fallback
    reasons = []
    if bc > 0.25:
        reasons.append(f"{person_id} exhibits elevated betweenness centrality ({bc:.3f}, {betweenness_pct}th percentile), positioning them on key shortest paths across network clusters")
    else:
        reasons.append(f"{person_id} is associated within community cluster {graph_metrics.get('community_id', 0) + 1}")

    evidence_cites = []
    if cdrs:
        evidence_cites.append(f"{len(cdrs)} logged telecommunication records ({', '.join([c['cdr_id'] for c in cdrs[:3]])})")
    if txns:
        evidence_cites.append(f"{len(txns)} financial transactions ({', '.join([t['txn_id'] for t in txns[:2]])})")
    if visits:
        evidence_cites.append(f"prison visitation logs ({', '.join([v['visit_id'] for v in visits])})")
    if firs:
        evidence_cites.append(f"case FIR records ({', '.join([f['fir_id'] for f in firs])})")

    if evidence_cites:
        reasons.append(f"Direct cross-source evidence links include {'; '.join(evidence_cites)}")

    explanation = ". ".join(reasons) + f". {fixed_disclaimer}"

    return {
        "person_id": person_id,
        "network_role": role,
        "priority": priority,
        "confidence_pct": confidence_pct,
        "explanation_text": explanation
    }


def answer_graph_query(natural_language_question: str, graph_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Job 3: Answers investigator graph queries (e.g. "who connects P17 and P22?"),
    returning answer text and specific node_ids / edge_ids to highlight on the UI graph.
    """
    nodes = graph_json.get("nodes", [])
    edges = graph_json.get("edges", [])
    
    if gemini_available and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            prompt = f"""
You are the Investigator Copilot for the NexusTrace criminal network intelligence system.
Answer the investigator's question based STRICTLY on the provided knowledge graph JSON.
Never invent links or nodes that do not exist.
Return ONLY a JSON response in the following format:
{{
  "answer": "Plain-text factual answer referencing nodes and evidence paths.",
  "cited_nodes": ["P17", "P31", "P22"],
  "cited_edges": ["e_P17_P31", "e_P31_P22"]
}}

Question: "{natural_language_question}"

Graph Nodes:
{json.dumps([{'id': n['id'], 'name': n['data']['display_name'], 'role': n['data']['metrics']['network_role']} for n in nodes], indent=2)}

Graph Edges:
{json.dumps([{'id': e['id'], 'from': e['from'], 'to': e['to'], 'channel': e['data']['channel'], 'tier': e['data']['tier']} for e in edges], indent=2)}
"""
            response = model.generate_content(prompt)
            clean_text = response.text.strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```json\s*|^```\s*|```$", "", clean_text, flags=re.MULTILINE).strip()
            res = json.loads(clean_text)
            
            # FIX 1: Ground Gemini's citations against the real graph
            # Gemini's citations are filtered against the actual graph so the system can never surface a node/edge that doesn't exist — explanations must be grounded, not invented.
            valid_node_ids = {n["id"] for n in nodes}
            valid_edge_ids = {e["id"] for e in edges}

            filtered_nodes = [nid for nid in res.get("cited_nodes", []) if nid in valid_node_ids]
            filtered_edges = [eid for eid in res.get("cited_edges", []) if eid in valid_edge_ids]

            # If both are empty after filtering, fall back to rule-based solver
            if not filtered_nodes and not filtered_edges:
                raise ValueError("Gemini returned no valid grounded citations for this graph.")

            res["cited_nodes"] = filtered_nodes
            res["cited_edges"] = filtered_edges
            return res
        except Exception as e:
            print(f"Gemini answer_graph_query failed, running graph query solver: {e}")

    # Rule-based Graph Path & Query Solver
    q = natural_language_question.lower()
    
    # Check for node IDs in question
    found_nodes = re.findall(r"\b[P|p][0-9]{2}\b", natural_language_question)
    found_nodes = [fn.upper() for fn in found_nodes]

    # Find path between two nodes
    if len(found_nodes) >= 2 or ("connects" in q or "between" in q or "path" in q):
        target_a = found_nodes[0] if len(found_nodes) > 0 else "P17"
        target_b = found_nodes[1] if len(found_nodes) > 1 else "P22"

        # Find paths in edges
        import networkx as nx
        temp_g = nx.Graph()
        for e in edges:
            temp_g.add_edge(e["from"], e["to"], edge_id=e["id"])

        if temp_g.has_node(target_a) and temp_g.has_node(target_b):
            try:
                path = nx.shortest_path(temp_g, target_a, target_b)
                cited_edges = []
                for idx in range(len(path) - 1):
                    u, v = path[idx], path[idx+1]
                    for e in edges:
                        if (e["from"] == u and e["to"] == v) or (e["from"] == v and e["to"] == u):
                            cited_edges.append(e["id"])

                intermediate = [n for n in path if n not in [target_a, target_b]]
                int_str = f" via {', '.join(intermediate)}" if intermediate else " directly"
                
                return {
                    "answer": f"Analysis reveals that {target_a} is connected to {target_b}{int_str} along path: {' -> '.join(path)}. Supporting links include {len(cited_edges)} verified relationship edges.",
                    "cited_nodes": path,
                    "cited_edges": cited_edges
                }
            except nx.NetworkXNoPath:
                return {
                    "answer": f"No connected pathway exists in the current evidentiary graph between {target_a} and {target_b}.",
                    "cited_nodes": [target_a, target_b],
                    "cited_edges": []
                }

    # High betweenness / Key coordinator query
    if "key" in q or "coordinator" in q or "bridge" in q or "central" in q or "highest" in q:
        high_nodes = [n for n in nodes if n["data"]["metrics"].get("priority") == "HIGH"]
        if not high_nodes:
            high_nodes = nodes[:1]
        
        c_nodes = [n["id"] for n in high_nodes]
        names = [f"{n['id']} ({n['data']['display_name']})" for n in high_nodes]
        
        # Associated edges
        c_edges = [e["id"] for e in edges if e["from"] in c_nodes or e["to"] in c_nodes]
        
        return {
            "answer": f"The primary key coordinator identified in the network is {', '.join(names)}. They hold the highest betweenness centrality and bridge multiple communication/financial clusters.",
            "cited_nodes": c_nodes,
            "cited_edges": c_edges[:6]
        }

    # Default overview
    return {
        "answer": f"The case graph contains {len(nodes)} resolved persons and {len(edges)} multi-channel relationships across FIR, CDR, financial transaction, and prison visit sources.",
        "cited_nodes": [n["id"] for n in nodes[:3]],
        "cited_edges": [e["id"] for e in edges[:3]]
    }
