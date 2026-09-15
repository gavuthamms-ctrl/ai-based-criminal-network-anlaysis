from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from app.db import (
    verify_database_startup,
    get_all_persons,
    get_person_by_id,
    get_person_evidence_records,
    get_cached_explanation,
    save_explanation,
    get_evidence_record_by_id
)
from app.graph_engine import graph_manager
from app.llm_service import (
    extract_entities_relationships,
    explain_person,
    answer_graph_query
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

class QueryRequest(BaseModel):
    question: str

class FIRExtractRequest(BaseModel):
    fir_text: str

# HTML Page Endpoints
@router.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    db_status = verify_database_startup()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"db_status": db_status}
    )

@router.get("/fir-ingest", response_class=HTMLResponse)
async def fir_ingestion_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="fir_ingestion.html",
        context={}
    )

# API Endpoints
@router.get("/api/status")
async def get_system_status():
    """Startup check verifying MySQL connection and seed data."""
    try:
        status = verify_database_startup()
        return {"status": "ok", "db_status": status}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/graph")
async def get_graph_data():
    """Exposes NetworkX nodes and edges with evidence tiers, centrality scores, and predicted links."""
    return graph_manager.get_vis_graph()

@router.get("/api/person/{person_id}")
async def get_person_details(person_id: str):
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    evidence = get_person_evidence_records(person_id)
    return {
        "person": person,
        "evidence": evidence
    }

@router.get("/api/person/{person_id}/explain")
async def get_person_explanation(person_id: str, force_regenerate: bool = False):
    """
    Feature 4: 'Why this person?' panel
    Pulls centrality scores + connected evidence, checks cache or calls Gemini explain_person(),
    returns network role, priority, confidence %, explanation, and source record IDs.
    """
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check cache first if not forced
    if not force_regenerate:
        cached = get_cached_explanation(person_id)
        if cached:
            evidence = get_person_evidence_records(person_id)
            source_ids = {
                "fir_ids": [f["fir_id"] for f in evidence.get("fir_records", [])],
                "cdr_ids": [c["cdr_id"] for c in evidence.get("cdrs", [])],
                "txn_ids": [t["txn_id"] for t in evidence.get("financial_transactions", [])],
                "visit_ids": [v["visit_id"] for v in evidence.get("prison_visits", [])]
            }
            return {
                **cached,
                "person": person,
                "source_records": source_ids,
                "source": "database_cache"
            }

    # Ensure graph metrics are calculated
    if person_id not in graph_manager.metrics:
        graph_manager.build_graph()

    metrics = graph_manager.metrics.get(person_id, {
        "degree_centrality": 0,
        "betweenness_centrality": 0,
        "betweenness_percentile": 50,
        "priority": "MEDIUM",
        "network_role": "Associate"
    })

    evidence = get_person_evidence_records(person_id)
    explanation_res = explain_person(person_id, person, metrics, evidence)

    # Save to explanations table
    save_explanation(
        person_id=person_id,
        network_role=explanation_res["network_role"],
        priority=explanation_res["priority"],
        confidence_pct=explanation_res["confidence_pct"],
        explanation_text=explanation_res["explanation_text"]
    )

    source_ids = {
        "fir_ids": [f["fir_id"] for f in evidence.get("fir_records", [])],
        "cdr_ids": [c["cdr_id"] for c in evidence.get("cdrs", [])],
        "txn_ids": [t["txn_id"] for t in evidence.get("financial_transactions", [])],
        "visit_ids": [v["visit_id"] for v in evidence.get("prison_visits", [])]
    }

    return {
        **explanation_res,
        "person": person,
        "source_records": source_ids,
        "source": "live_generated"
    }

@router.post("/api/query")
async def copilot_query(req: QueryRequest):
    """
    Feature 6: Investigator Copilot.
    Answers natural language queries using graph reasoning and cites node/edge IDs to highlight.
    """
    graph_data = graph_manager.get_vis_graph()
    result = answer_graph_query(req.question, graph_data)
    return result

@router.post("/api/extract-fir")
async def extract_fir(req: FIRExtractRequest):
    """
    Feature 7: FIR Ingestion & NLP Entity Extraction.
    Extracts entities, phones, vehicles, accounts, and implied relationships.
    """
    if not req.fir_text.strip():
        raise HTTPException(status_code=400, detail="FIR narrative cannot be empty")
    
    extracted = extract_entities_relationships(req.fir_text)
    return extracted

@router.get("/api/evidence/{record_type}/{record_id}")
async def get_evidence_detail(record_type: str, record_id: str):
    """Inspect raw evidentiary records (FIR, CDR, TXN, Prison Visit)."""
    record = get_evidence_record_by_id(record_type.lower(), record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return {"record_type": record_type, "record_id": record_id, "data": record}
