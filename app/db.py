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

        # FIR records where person or their alias/name is mentioned
        cursor.execute("SELECT * FROM persons WHERE person_id = %s", (person_id,))
        p = cursor.fetchone()
        
        firs = []
        if p:
            name_fragments = [p["display_name"]]
            if p["known_aliases"]:
                name_fragments.extend([a.strip() for a in p["known_aliases"].split(",")])
            
            query_conds = " OR ".join(["narrative_text LIKE %s" for _ in name_fragments])
            params = [f"%{frag}%" for frag in name_fragments]
            if query_conds:
                cursor.execute(f"SELECT * FROM fir_records WHERE {query_conds} ORDER BY filed_date DESC", tuple(params))
                firs = cursor.fetchall()

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
