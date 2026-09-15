# NexusTrace — AI-Powered Criminal Network Analysis System
**Smart India Hackathon 2026 | Problem Statement: SIH26189**  
*Explainable, Evidence-Traceable Decision-Support Intelligence for Investigators*

---

## 🌟 Executive Overview

NexusTrace is an AI-powered criminal network intelligence prototype built for law-enforcement and investigative decision support. It ingests multi-source case data (First Information Reports, Call Detail Records, Financial Transactions, and Prison Visitor Logs), resolves entity aliases, builds a temporal relationship graph, computes network centrality and community structures, predicts undocumented links, and provides **plain-language explainability grounded strictly in evidentiary records**.

### 🛡️ Core Ethos & Differentiator
- **Never accuses anyone:** The system is strictly a decision-support tool producing labeled investigative leads with confidence scores.
- **Mandatory Guardrail Banner:** Every AI-generated flag or prediction is stamped with `"Investigative lead — requires human verification."`
- **Strict Evidence Tiering:** Edges and nodes are visually categorized into 4 tiers so inferences never masquerade as documented facts.

---

## 📊 Evidence Confidence Tiers

| Evidence Tier | Definition / Data Source | Visual Representation in Graph |
| :--- | :--- | :--- |
| **Direct Evidence** | Explicitly documented in case FIRs / chargesheets. | **Solid Dark Edge** (`#1e293b`), width 3.5 |
| **Corroborated Association** | Corroborated across multiple independent sources (CDR + Financial). | **Solid Amber Edge** (`#d97706`), width 2.8 |
| **Analytical Inference** | Derived from graph topology (centrality, prison visitation). | **Dashed Orange Edge** (`#ea580c`), dashed `[6, 6]` |
| **AI-Predicted Link** | Suggested by link prediction baseline with confidence %. | **Dashed Red Edge** (`#ef4444`), dashed `[4, 4]` |

---

## 🚀 Key Features Implemented

1. **Multi-Source Knowledge Graph Engine (`NetworkX` + `python-louvain`):**
   - Degree Centrality & Betweenness Centrality (identifies key coordinators bridging clusters like `P17`).
   - Louvain Community Detection (partitions the syndicate into operational cells).
   - Baseline Common-Neighbors link prediction *(Production Roadmap: GraphSAGE GNN inductive learning)*.

2. **"Why This Person?" Explainability Panel:**
   - Plain-language justification referencing structural metrics and concrete records (`[FIR]`, `[CDR]`, `[TXN]`, `[VIS]`).
   - Priority classification (`HIGH`, `MEDIUM`, `LOW`) and confidence %.
   - Interactive evidence inspection modal displaying underlying raw database records.

3. **Investigator Copilot:**
   - Natural language query layer ("Who connects P17 and P22?", "Identify key coordinators").
   - Analyzes graph paths and highlights the cited nodes and edges directly on the interactive Vis.js graph.

4. **FIR Ingestion & NLP Entity Extraction Demo:**
   - Extracts structured people, aliases, phone numbers, vehicle registrations, bank accounts, and relationship triples from raw case narratives.

---

## 🛠️ Technical Stack

- **Backend:** Python 3.11 / 3.13, FastAPI, Uvicorn
- **Database:** MySQL (`mysql-connector-python`), database `crime_network_prototype`
- **Graph Engine:** NetworkX 3.x, python-louvain
- **AI / LLM:** Google Gemini (`google-generativeai`) with rule-based fallback engines
- **Frontend:** Single-page dashboard using Vis.js Network via CDN, HTML5/CSS3, Jinja2 templates

---

## ⚡ Quickstart Setup Guide (Under 5 Minutes)

### 1. Clone / Open Project
```bash
cd your-project-folder
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Setup
Ensure your local MySQL server (XAMPP / MySQL Service) is running.
The database schema and seed data are available in `schema_and_seed_data.sql`.
If you need to re-import it:
```bash
mysql -u root -p < schema_and_seed_data.sql
```

### 4. Configure Environment (.env)
Check `.env`:
```ini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=crime_network_prototype

# Optional: Add your Google Gemini API Key from https://aistudio.google.com/
GEMINI_API_KEY=
```
*(Note: NexusTrace contains built-in graph solvers and rule-based template engines, so the app will function even without an API key).*

### 5. Run the Server
```bash
python -m uvicorn main:app --reload --port 8000
```

Open your browser and navigate to:
- **Main Investigator Dashboard:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **FIR Ingestion Demo:** [http://127.0.0.1:8000/fir-ingest](http://127.0.0.1:8000/fir-ingest)
- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🎤 SIH Presentation & Pitching Notes

- **Q: Why common-neighbors instead of full GraphSAGE training right now?**
  *A:* On small-scale synthetic hackathon seed data, GNNs risk overfitting. The common-neighbors heuristic sets a transparent baseline, and GraphSAGE is designed as the inductive production upgrade path.
- **Q: How does this prevent false accusation?**
  *A:* Through structural evidence confidence tiering: frequent phone calls alone produce an *Analytical Inference* or *Corroborated Association*, never a *Direct Evidence* chargesheet record. Every screen displays `"Investigative lead — human verification required."`
