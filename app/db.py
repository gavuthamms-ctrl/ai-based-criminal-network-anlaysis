import re
import mysql.connector
from mysql.connector import pooling
from typing import Dict, Any, List, Optional
from app.config import settings

# Setup connection pool
pool = None

def get_connection():
    global pool
    if pool is None:
        pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="nexustrace_pool",
            pool_size=10,
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DATABASE,
            charset="utf8mb4",
            collation="utf8mb4_general_ci",
            autocommit=True
        )
    return pool.get_connection()

def verify_database_startup() -> Dict[str, Any]:
    """Startup check to verify connection and required seed data tables."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    required_tables = [
        "persons", "fir_records", "cdr_records", 
        "financial_transactions", "prison_visits", 
        "relationships", "explanations"
    ]
    status = {"connected": True, "database": settings.MYSQL_DATABASE, "tables": {}}
    
    try:
        for table in required_tables:
            cursor.execute(f"SELECT COUNT(*) as row_count FROM `{table}`")
            res = cursor.fetchone()
            status["tables"][table] = res["row_count"]
    finally:
        cursor.close()
        conn.close()
        
    return status

def get_all_persons() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM persons ORDER BY person_id ASC")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_person_by_id(person_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM persons WHERE person_id = %s", (person_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def get_all_relationships() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM relationships ORDER BY edge_id ASC")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_person_evidence_records(person_id: str) -> Dict[str, Any]:
    """Retrieve all direct and indirect evidence records mentioning this person."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # CDR records
        cursor.execute(
            """
            SELECT c.*, p1.display_name as caller_name, p2.display_name as callee_name 
            FROM cdr_records c
            JOIN persons p1 ON c.caller_person_id = p1.person_id
            JOIN persons p2 ON c.callee_person_id = p2.person_id
            WHERE c.caller_person_id = %s OR c.callee_person_id = %s
            ORDER BY c.call_datetime DESC
            """, (person_id, person_id)
        )
        cdrs = cursor.fetchall()

        # Financial Transactions
        cursor.execute(
            """
            SELECT f.*, p1.display_name as sender_name, p2.display_name as receiver_name 
            FROM financial_transactions f
            JOIN persons p1 ON f.sender_person_id = p1.person_id
            JOIN persons p2 ON f.receiver_person_id = p2.person_id
            WHERE f.sender_person_id = %s OR f.receiver_person_id = %s
            ORDER BY f.txn_datetime DESC
            """, (person_id, person_id)
        )
        txns = cursor.fetchall()

        # Prison Visits
        cursor.execute(
            """
            SELECT v.*, p1.display_name as visitor_name, p2.display_name as inmate_name 
            FROM prison_visits v
            JOIN persons p1 ON v.visitor_person_id = p1.person_id
            JOIN persons p2 ON v.inmate_person_id = p2.person_id
            WHERE v.visitor_person_id = %s OR v.inmate_person_id = %s
            ORDER BY v.visit_date DESC
            """, (person_id, person_id)
        )
        visits = cursor.fetchall()

        # FIX 2: Non-overlapping longest-match FIR entity attribution
        cursor.execute("SELECT * FROM persons")
        all_persons = cursor.fetchall()

        all_frags = []
        for p in all_persons:
            pid = p["person_id"]
            if p["display_name"] and len(p["display_name"].strip()) >= 3:
                all_frags.append((pid, p["display_name"].strip()))
            if p["known_aliases"]:
                for a in p["known_aliases"].split(","):
                    cleaned = a.strip()
                    if len(cleaned) >= 3:
                        all_frags.append((pid, cleaned))

        # Sort by length descending so longer phrases match first and claim spans
        all_frags.sort(key=lambda x: len(x[1]), reverse=True)

        cursor.execute("SELECT * FROM fir_records ORDER BY filed_date DESC")
        all_firs = cursor.fetchall()
        
        firs = []
        for fir in all_firs:
            narrative = fir.get("narrative_text", "")
            matched_spans = []
            matched_pids = set()

            for pid, frag in all_frags:
                for m in re.finditer(rf"\b{re.escape(frag)}\b", narrative, re.IGNORECASE):
                    s, e = m.span()
                    # Check overlap with already claimed longer spans
                    overlap = any(not (e <= cs or s >= ce) for (cs, ce, _) in matched_spans)
                    if not overlap:
                        matched_spans.append((s, e, pid))
                        matched_pids.add(pid)

            if person_id in matched_pids:
                firs.append(fir)

        return {
            "cdrs": cdrs,
            "financial_transactions": txns,
            "prison_visits": visits,
            "fir_records": firs
        }
    finally:
        cursor.close()
        conn.close()

def get_cached_explanation(person_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM explanations WHERE person_id = %s", (person_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

def save_explanation(person_id: str, network_role: str, priority: str, confidence_pct: int, explanation_text: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO explanations (person_id, network_role, priority, confidence_pct, explanation_text)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                network_role = VALUES(network_role),
                priority = VALUES(priority),
                confidence_pct = VALUES(confidence_pct),
                explanation_text = VALUES(explanation_text),
                generated_at = CURRENT_TIMESTAMP
            """,
            (person_id, network_role, priority, confidence_pct, explanation_text)
        )
    finally:
        cursor.close()
        conn.close()

def get_evidence_record_by_id(record_type: str, record_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if record_type == "fir":
            cursor.execute("SELECT * FROM fir_records WHERE fir_id = %s", (record_id,))
        elif record_type == "cdr":
            cursor.execute("SELECT * FROM cdr_records WHERE cdr_id = %s", (record_id,))
        elif record_type == "txn" or record_type == "financial":
            cursor.execute("SELECT * FROM financial_transactions WHERE txn_id = %s", (record_id,))
        elif record_type == "visit" or record_type == "prison":
            cursor.execute("SELECT * FROM prison_visits WHERE visit_id = %s", (record_id,))
        else:
            return None
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
