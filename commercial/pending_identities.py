"""Signed OIDC login requests awaiting explicit GodAdmin approval.

No access tokens, passwords, unsigned headers or BPMS identifiers are stored.
Only claims from an already verified OIDC identity are staged.  BPMS binding is
a separate admin action after the AVAN account is approved.
"""
from datetime import datetime,timezone
import json
from .setup_console import _db,audit

def _ensure():
    with _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS pending_identity(
            tenant_id TEXT NOT NULL, subject TEXT NOT NULL,
            username TEXT,
            name TEXT NOT NULL,email TEXT,email_verified INTEGER NOT NULL,
            roles_json TEXT NOT NULL,seen_at_utc TEXT NOT NULL,
            PRIMARY KEY(tenant_id,subject)
        )""")
        columns={str(r[1]) for r in con.execute("PRAGMA table_info(pending_identity)").fetchall()}
        if "username" not in columns:
            con.execute("ALTER TABLE pending_identity ADD COLUMN username TEXT")

def stage(principal,*,username:str|None,name:str,email:str|None,email_verified:bool):
    _ensure()
    clean_username=(username or "").strip()[:180] or None
    with _db() as con:
        con.execute("""INSERT INTO pending_identity(
           tenant_id,subject,username,name,email,email_verified,roles_json,seen_at_utc)
           VALUES(?,?,?,?,?,?,?,?)
           ON CONFLICT(tenant_id,subject) DO UPDATE SET
             username=excluded.username,name=excluded.name,email=excluded.email,
             email_verified=excluded.email_verified,
             roles_json=excluded.roles_json,
             seen_at_utc=excluded.seen_at_utc""",
            (str(principal.tenant_id),principal.subject,clean_username,str(name)[:250],
             email[:250] if email else None,1 if email_verified else 0,
             json.dumps(sorted(principal.roles),ensure_ascii=False),
             datetime.now(timezone.utc).isoformat()))
    audit("OIDC_SUBJECT_PENDING_GODADMIN_APPROVAL")

def list_pending()->list[dict]:
    _ensure()
    with _db() as con:
        rows=con.execute("""SELECT tenant_id,subject,username,name,email,email_verified,
                       roles_json,seen_at_utc FROM pending_identity
                       ORDER BY seen_at_utc DESC LIMIT 100""").fetchall()
    return [{"tenant_id":str(r[0]),"subject":str(r[1]),
            "username":str(r[2]) if r[2] else None,"name":str(r[3]),
            "email":str(r[4]) if r[4] else None,"email_verified":bool(r[5]),
            "roles":json.loads(r[6]),"seen_at_utc":str(r[7])} for r in rows]

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
