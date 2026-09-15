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
    case_id: Optional[str] = "2026-CR-0417"

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

from app.db import get_all_cases, get_case_summary

@router.get("/api/cases")
async def list_cases():
    """Returns list of registered cases for case switcher."""
    return get_all_cases()

@router.get("/api/cases/{case_id}")
async def get_case_detail(case_id: str):
    """Returns details and summary of a specific case."""
    return get_case_summary(case_id)

@router.get("/api/graph")
async def get_network_graph(case_id: Optional[str] = None):
    """
    Features 1-4: Returns complete multi-source evidentiary graph with community clusters,
    betweenness metrics, and multi-tier evidence channels.
    """
    data = graph_manager.get_vis_graph(case_id=case_id)
    return data

@router.get("/api/person/{person_id}")
@router.get("/api/person/{person_id}/explain")
async def get_person_details(person_id: str):
    """
    Feature 5: Person profile & explainable score decomposition.
    """
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if not graph_manager.metrics:
        graph_manager.build_graph()

    metrics = graph_manager.metrics.get(person_id, {
        "degree_centrality": 0,
        "betweenness_centrality": 0,
        "betweenness_percentile": 50,
        "priority": "MEDIUM",
        "network_role": "Associate"
    })

    evidence = get_person_evidence_records(person_id)
    cached_exp = get_cached_explanation(person_id)

    source_ids = {
        "fir_ids": [f["fir_id"] for f in evidence.get("fir_records", [])],
        "cdr_ids": [c["cdr_id"] for c in evidence.get("cdrs", [])],
        "txn_ids": [t["txn_id"] for t in evidence.get("financial_transactions", [])],
        "visit_ids": [v["visit_id"] for v in evidence.get("prison_visits", [])]
    }

    if cached_exp:
        return {
            "person_id": person_id,
            "network_role": cached_exp["network_role"],
            "priority": cached_exp["priority"],
            "confidence_pct": cached_exp["confidence_pct"],
            "explanation_text": cached_exp["explanation_text"],
            "person": person,
            "metrics": metrics,
            "source_records": source_ids,
            "source": "database_cached"
        }

    # Generate live explanation
    explanation_res = explain_person(person_id, person, metrics, evidence)
    return {
        **explanation_res,
        "person": person,
        "metrics": metrics,
        "source_records": source_ids,
        "source": "live_generated"
    }

@router.get("/api/explain/{person_id}")
async def generate_live_explanation(person_id: str):
    """
    Feature 5 & Job 2: Forces generation of fresh Gemini/rule-based explanation.
    """
    person = get_person_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if not graph_manager.metrics:
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
        "metrics": metrics,
        "source_records": source_ids,
        "source": "live_generated"
    }

@router.post("/api/query")
async def copilot_query(req: QueryRequest):
    """
    Feature 6: Investigator Copilot.
    Answers natural language queries using graph reasoning and cites node/edge IDs to highlight.
    """
    case_id = req.case_id or "2026-CR-0417"
    graph_data = graph_manager.get_vis_graph(case_id=case_id)
    result = answer_graph_query(req.question, graph_data, case_id=case_id)
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

from app.evaluation import evaluate_link_prediction_leave_one_out

@router.get("/api/evaluate/link-prediction")
async def evaluate_link_prediction():
    """Evaluate link prediction baseline using Leave-One-Out validation."""
    return evaluate_link_prediction_leave_one_out()

@router.get("/api/evidence/{record_type}/{record_id}")
async def get_evidence_detail(record_type: str, record_id: str):
    """Inspect raw evidentiary records (FIR, CDR, TXN, Prison Visit)."""
    record = get_evidence_record_by_id(record_type.lower(), record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return {"record_type": record_type, "record_id": record_id, "data": record}

from app.db import get_chronological_case_timeline, log_verification_decision, get_verification_logs

class VerificationRequest(BaseModel):
    officer_name: str = "Inspector R. Santhosh"
    officer_badge: str = "TN-POL-4482"
    decision: str  # 'ACCEPTED', 'REJECTED', 'REQUIRES_PROBE'
    notes: str = ""

@router.get("/api/timeline")
async def get_case_timeline():
    """Investigation Feature 2: Unified chronological event timeline."""
    return get_chronological_case_timeline()

@router.get("/api/person/{person_id}/verification-history")
async def get_person_verification_history(person_id: str):
    """Investigation Feature 6: Human verification audit trail."""
    logs = get_verification_logs(person_id)
    return {"person_id": person_id, "history": logs}

@router.post("/api/person/{person_id}/verify")
async def verify_person_lead(person_id: str, req: VerificationRequest):
    """Investigation Feature 6: Record human-in-the-loop sign-off."""
    res = log_verification_decision(
        person_id=person_id,
        case_id="2026-CR-0417",
        officer_name=req.officer_name,
        officer_badge=req.officer_badge,
        decision=req.decision,
        notes=req.notes
    )
    return res
