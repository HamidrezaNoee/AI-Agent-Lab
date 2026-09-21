"""Signed OIDC login requests awaiting explicit GodAdmin-to-ProcessMaker mapping.

No access tokens, passwords, unsigned headers or self-asserted PM identifiers
are stored. Only claims from already RS256-verified, issuer/audience-bound JWTs
may be passed by the operational login callback.
"""
from datetime import datetime,timezone
import json
from .setup_console import _db,audit

def _ensure():
    with _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS pending_identity(
            tenant_id TEXT NOT NULL, subject TEXT NOT NULL,
            name TEXT NOT NULL,email TEXT,email_verified INTEGER NOT NULL,
            roles_json TEXT NOT NULL,seen_at_utc TEXT NOT NULL,
            PRIMARY KEY(tenant_id,subject)
        )""")

def stage(principal,*,name:str,email:str|None,email_verified:bool):
    _ensure()
    with _db() as con:
        con.execute("""INSERT INTO pending_identity(
           tenant_id,subject,name,email,email_verified,roles_json,seen_at_utc)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(tenant_id,subject) DO UPDATE SET
             name=excluded.name,email=excluded.email,
             email_verified=excluded.email_verified,
             roles_json=excluded.roles_json,
             seen_at_utc=excluded.seen_at_utc""",
            (str(principal.tenant_id),principal.subject,str(name)[:250],
             email[:250] if email else None,1 if email_verified else 0,
             json.dumps(sorted(principal.roles),ensure_ascii=False),
             datetime.now(timezone.utc).isoformat()))
    audit("OIDC_SUBJECT_PENDING_GODADMIN_APPROVAL")

def list_pending()->list[dict]:
    _ensure()
    with _db() as con:
        rows=con.execute("""SELECT tenant_id,subject,name,email,email_verified,
                       roles_json,seen_at_utc FROM pending_identity
                       ORDER BY seen_at_utc DESC LIMIT 100""").fetchall()
    return [{"tenant_id":str(r[0]),"subject":str(r[1]),"name":str(r[2]),
            "email":str(r[3]) if r[3] else None,"email_verified":bool(r[4]),
            "roles":json.loads(r[5]),"seen_at_utc":str(r[6])} for r in rows]

def find(tenant_id:str,subject:str)->dict|None:
    return next((item for item in list_pending()
                 if item["tenant_id"]==tenant_id and item["subject"]==subject),
                None)

def approve(tenant_id:str,subject:str):
    _ensure()
    with _db() as con:
        con.execute("DELETE FROM pending_identity WHERE tenant_id=? AND subject=?",
                    (tenant_id,subject))
    audit("OIDC_SUBJECT_APPROVED")
