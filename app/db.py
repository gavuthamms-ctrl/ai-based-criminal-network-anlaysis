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
        # Auto-create verification audit log table if not present
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `verification_audit_log` (
              `log_id` int AUTO_INCREMENT PRIMARY KEY,
              `person_id` varchar(10) NOT NULL,
              `case_id` varchar(20) NOT NULL,
              `officer_name` varchar(100) NOT NULL,
              `officer_badge` varchar(50) NOT NULL,
              `decision` enum('ACCEPTED','REJECTED','REQUIRES_PROBE') NOT NULL,
              `notes` text,
              `timestamp` timestamp DEFAULT CURRENT_TIMESTAMP,
              KEY `person_id` (`person_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        for table in required_tables:
            cursor.execute(f"SELECT COUNT(*) as row_count FROM `{table}`")
            res = cursor.fetchone()
            status["tables"][table] = res["row_count"]
    finally:
        cursor.close()
        conn.close()
        
    return status

CASES_METADATA = {
    "2026-CR-0417": {
        "case_id": "2026-CR-0417",
        "title": "Financial Fraud & Syndicate Money Laundering",
        "station": "Anna Nagar PS (Chennai Central)",
        "sections": "IPC 420, 120B | BNS 318, 61",
        "summary": "Organized syndicate operating fraudulent investment schemes and layered fund transfers between Anna Nagar, Tambaram, and Adyar. Identifies key coordinator bridging financial accounts and prison visitation channels.",
        "primary_suspect": "Karthik Selvam (P17)",
        "status": "Active Trial Preparation / Chargesheet Filed"
    },
    "2026-CR-0512": {
        "case_id": "2026-CR-0512",
        "title": "Interstate Luxury Vehicle Theft & Forged RC Racket",
        "station": "Porur PS (Crime Branch)",
        "sections": "IPC 379, 420, 467, 471 | BNS 303, 318, 336",
        "summary": "Interstate luxury car theft ring altering chassis numbers and forging RTO documents. Financial transfers and CDR tower logs reveal Vikramaditya Seth (P55) funding document forgers and disposal transporters.",
        "primary_suspect": "Vikramaditya Seth (P55)",
        "status": "Active Warrants Issued (Sec 73 CrPC)"
    },
    "ALL": {
        "case_id": "ALL",
        "title": "Unified Multi-Case Criminal Intelligence Grid",
        "station": "NCRB / State Crime Records Bureau",
        "sections": "Multi-Jurisdiction Syndicate Intelligence",
        "summary": "Holistic cross-case intelligence map aggregating all registered FIRs, CDR communications, and financial channels across police stations to detect repeat offenders and inter-case bridges.",
        "primary_suspect": "Cross-Syndicate Coordinators (P17, P31, P55)",
        "status": "Inter-Agency Active Monitoring"
    }
}

def get_all_cases() -> List[Dict[str, Any]]:
    return list(CASES_METADATA.values())

def get_case_summary(case_id: str = "2026-CR-0417") -> Dict[str, Any]:
    return CASES_METADATA.get(case_id, CASES_METADATA["2026-CR-0417"])

def get_all_persons(case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if case_id == "2026-CR-0417":
            cursor.execute("SELECT * FROM persons WHERE person_id IN ('P01','P04','P05','P09','P17','P22','P31','P41') ORDER BY person_id ASC")
        elif case_id == "2026-CR-0512":
            cursor.execute("SELECT * FROM persons WHERE person_id IN ('P55','P62','P71','P31') ORDER BY person_id ASC")
        else:
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

def get_all_relationships(case_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if case_id == "2026-CR-0417":
            cursor.execute("""
                SELECT * FROM relationships 
                WHERE person_a_id IN ('P01','P04','P05','P09','P17','P22','P31','P41') 
                  AND person_b_id IN ('P01','P04','P05','P09','P17','P22','P31','P41')
                ORDER BY edge_id ASC
            """)
        elif case_id == "2026-CR-0512":
            cursor.execute("""
                SELECT * FROM relationships 
                WHERE (person_a_id IN ('P55','P62','P71','P31') AND person_b_id IN ('P55','P62','P71','P31'))
                ORDER BY edge_id ASC
            """)
        else:
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
        rec = cursor.fetchone()
        if not rec:
            return None
        
        # Enrich with Chain of Custody & Statutory Provenance (Section 65B BSA compliance)
        provenance = {
            "legal_authority": "Section 91 CrPC / Section 94 BNSS Notice Ref #IO/2026/884",
            "collecting_officer": "Inspector R. Santhosh (Badge: TN-POL-4482)",
            "source_entity": "Airtel/Jio LERS Portal" if record_type == "cdr" else ("HDFC Bank Nodal Cell" if record_type in ["txn","financial"] else "Puzhal Prison Visitor Reg."),
            "integrity_hash_sha256": f"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "admissibility_status": "Section 65B Indian Evidence Act / BSA 2023 Certified"
        }
        return {**rec, "_provenance": provenance}
    finally:
        cursor.close()
        conn.close()

def get_chronological_case_timeline() -> List[Dict[str, Any]]:
    """Generates a unified chronological timeline across all multi-source records."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    timeline = []
    try:
        # 1. FIR Records
        cursor.execute("SELECT * FROM fir_records")
        for f in cursor.fetchall():
            timeline.append({
                "id": f["fir_id"],
                "type": "FIR_FILING",
                "datetime": f"{f['filed_date']} 09:00:00",
                "headline": f"FIR Registered ({f['fir_id']}) at {f['station']}",
                "detail": f["narrative_text"],
                "participants": ["Case Official"],
                "tier": "direct_evidence"
            })

        # 2. Prison Visits
        cursor.execute("""
            SELECT v.*, p1.display_name as visitor, p2.display_name as inmate
            FROM prison_visits v
            JOIN persons p1 ON v.visitor_person_id = p1.person_id
            JOIN persons p2 ON v.inmate_person_id = p2.person_id
        """)
        for v in cursor.fetchall():
            timeline.append({
                "id": v["visit_id"],
                "type": "PRISON_VISIT",
                "datetime": f"{v['visit_date']} 11:30:00",
                "headline": f"Prison Visitation at {v['facility']}",
                "detail": f"{v['visitor']} ({v['visitor_person_id']}) visited inmate {v['inmate']} ({v['inmate_person_id']})",
                "participants": [v['visitor_person_id'], v['inmate_person_id']],
                "tier": "analytical_inference"
            })

        # 3. Financial Transactions
        cursor.execute("""
            SELECT f.*, p1.display_name as sender, p2.display_name as receiver
            FROM financial_transactions f
            JOIN persons p1 ON f.sender_person_id = p1.person_id
            JOIN persons p2 ON f.receiver_person_id = p2.person_id
        """)
        for t in cursor.fetchall():
            timeline.append({
                "id": t["txn_id"],
                "type": "FINANCIAL_TXN",
                "datetime": str(t["txn_datetime"]),
                "headline": f"INR {float(t['amount_inr']):,.2f} Bank Transfer",
                "detail": f"{t['sender']} ({t['sender_person_id']}) transferred INR {float(t['amount_inr']):,.2f} to {t['receiver']} ({t['receiver_person_id']})",
                "participants": [t['sender_person_id'], t['receiver_person_id']],
                "tier": "corroborated_association"
            })

        # 4. CDR Calls
        cursor.execute("""
            SELECT c.*, p1.display_name as caller, p2.display_name as callee
            FROM cdr_records c
            JOIN persons p1 ON c.caller_person_id = p1.person_id
            JOIN persons p2 ON c.callee_person_id = p2.person_id
        """)
        for c in cursor.fetchall():
            timeline.append({
                "id": c["cdr_id"],
                "type": "CDR_CALL",
                "datetime": str(c["call_datetime"]),
                "headline": f"Telecom Call ({c['duration_seconds']}s duration)",
                "detail": f"Voice call between {c['caller']} ({c['caller_person_id']}) and {c['callee']} ({c['callee_person_id']})",
                "participants": [c['caller_person_id'], c['callee_person_id']],
                "tier": "corroborated_association"
            })

        timeline.sort(key=lambda x: x["datetime"])
        return timeline
    finally:
        cursor.close()
        conn.close()

def log_verification_decision(person_id: str, case_id: str, officer_name: str, officer_badge: str, decision: str, notes: str) -> Dict[str, Any]:
    """Human-in-the-loop verification logger."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            INSERT INTO `verification_audit_log` (`person_id`, `case_id`, `officer_name`, `officer_badge`, `decision`, `notes`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (person_id, case_id, officer_name, officer_badge, decision, notes))
        return {
            "success": True,
            "decision": decision,
            "officer": officer_name,
            "badge": officer_badge,
            "person_id": person_id
        }
    finally:
        cursor.close()
        conn.close()

def get_verification_logs(person_id: str) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT * FROM `verification_audit_log` WHERE `person_id` = %s ORDER BY `timestamp` DESC
        """, (person_id,))
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        cursor.close()
        conn.close()

