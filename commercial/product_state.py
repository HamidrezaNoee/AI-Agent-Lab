"""Persistent AVAN product configuration and one-time GodAdmin bootstrap.

This store is intentionally independent of EnterpriseProcess2 so the product
can be configured from its own UI before the external SQL connection exists.
Secrets are encrypted at rest with a locally generated Fernet key kept in the
Docker state volume. The initial GodAdmin password is generated once, stored
only as a scrypt hash, and written to a one-time local bootstrap file that is
deleted after password change.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, sqlite3, stat, time
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

STATE=Path(os.getenv("AVAN_STATE_DIR","/var/lib/avan")).resolve()
DB=STATE/"avan-state.db"
KEY=STATE/"settings.key"
BOOTSTRAP=STATE/"bootstrap-godadmin-password.txt"

class StateError(Exception): pass

def _ensure_state_dir():
    STATE.mkdir(parents=True,exist_ok=True)
    try: os.chmod(STATE,0o700)
    except OSError: pass

def _fernet():
    _ensure_state_dir()
    if not KEY.exists():
        fd=os.open(KEY,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as out: out.write(Fernet.generate_key())
    raw=KEY.read_bytes().strip()
    if len(raw)!=44: raise StateError("Invalid local settings encryption key")
    return Fernet(raw)

def _connect():
    _ensure_state_dir()
    con=sqlite3.connect(DB,timeout=8)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript("""
      CREATE TABLE IF NOT EXISTS settings(
        section TEXT NOT NULL,
        name TEXT NOT NULL,
        value TEXT,
        is_secret INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY(section,name)
      );
      CREATE TABLE IF NOT EXISTS bootstrap_admin(
        id INTEGER PRIMARY KEY CHECK(id=1),
        username TEXT NOT NULL,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        must_change INTEGER NOT NULL DEFAULT 1,
        disabled INTEGER NOT NULL DEFAULT 0,
        updated_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        occurred_at INTEGER NOT NULL,
        actor TEXT NOT NULL,
        event_code TEXT NOT NULL,
        succeeded INTEGER NOT NULL,
        detail TEXT NOT NULL
      );
    """)
    return con

def _hash_password(password:str,salt:bytes)->str:
    raw=hashlib.scrypt(password.encode("utf-8"),salt=salt,n=2**15,r=8,p=1,dklen=32)
    return base64.urlsafe_b64encode(raw).decode("ascii")

def ensure_bootstrap():
    with _connect() as con:
        row=con.execute("SELECT id FROM bootstrap_admin WHERE id=1").fetchone()
        if row:return
        alphabet="ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%_-"
        password="".join(secrets.choice(alphabet) for _ in range(24))
        salt=secrets.token_bytes(16)
        con.execute("""INSERT INTO bootstrap_admin
          (id,username,salt,password_hash,must_change,disabled,updated_at)
          VALUES(1,'godadmin',?,?,1,0,?)""",
          (base64.urlsafe_b64encode(salt).decode("ascii"),_hash_password(password,salt),int(time.time())))
        fd=os.open(BOOTSTRAP,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as out:
            out.write("godadmin\n"+password+"\n")
        con.commit()

def verify_bootstrap(username:str,password:str)->dict|None:
    ensure_bootstrap()
    with _connect() as con:
        row=con.execute("SELECT * FROM bootstrap_admin WHERE id=1").fetchone()
        if not row or row["disabled"]:return None
        try:salt=base64.urlsafe_b64decode(row["salt"])
        except Exception:return None
        expected=_hash_password(password,salt)
        if not hmac.compare_digest(expected,row["password_hash"]):return None
        return {"username":row["username"],"must_change":bool(row["must_change"])}

def change_bootstrap_password(current:str,new:str):
    if len(new)<14 or len(new)>128:
        raise StateError("Password must contain 14..128 characters")
    if not any(c.islower() for c in new) or not any(c.isupper() for c in new) or not any(c.isdigit() for c in new):
        raise StateError("Password must contain upper/lowercase letters and digits")
    if verify_bootstrap("godadmin",current) is None:
        raise StateError("Current password is invalid")
    salt=secrets.token_bytes(16)
    with _connect() as con:
        con.execute("""UPDATE bootstrap_admin SET salt=?,password_hash=?,
          must_change=0,updated_at=? WHERE id=1""",
          (base64.urlsafe_b64encode(salt).decode("ascii"),_hash_password(new,salt),int(time.time())))
        con.commit()
    try:BOOTSTRAP.unlink(missing_ok=True)
    except OSError:pass

def disable_bootstrap_admin():
    with _connect() as con:
        con.execute("UPDATE bootstrap_admin SET disabled=1,updated_at=? WHERE id=1",(int(time.time()),))
        con.commit()
    try:BOOTSTRAP.unlink(missing_ok=True)
    except OSError:pass

def bootstrap_status():
    ensure_bootstrap()
    with _connect() as con:
        row=con.execute("SELECT username,must_change,disabled FROM bootstrap_admin WHERE id=1").fetchone()
    return {"username":row["username"],"must_change":bool(row["must_change"]),
            "disabled":bool(row["disabled"]),"bootstrap_file_exists":BOOTSTRAP.exists()}

def set_setting(section:str,name:str,value:str|None,*,secret:bool=False):
    if not section.replace("_","").isalnum() or not name.replace("_","").isalnum():
        raise StateError("Invalid setting key")
    stored=None
    if value is not None:
        stored=_fernet().encrypt(value.encode("utf-8")).decode("ascii") if secret else value
    with _connect() as con:
        con.execute("""INSERT INTO settings(section,name,value,is_secret,updated_at)
          VALUES(?,?,?,?,?) ON CONFLICT(section,name) DO UPDATE SET
          value=excluded.value,is_secret=excluded.is_secret,updated_at=excluded.updated_at""",
          (section,name,stored,1 if secret else 0,int(time.time())))
        con.commit()

def get_setting(section:str,name:str,default:str|None=None)->str|None:
    with _connect() as con:
        row=con.execute("SELECT value,is_secret FROM settings WHERE section=? AND name=?",(section,name)).fetchone()
    if not row or row["value"] is None:return default
    if not row["is_secret"]:return str(row["value"])
    try:return _fernet().decrypt(str(row["value"]).encode("ascii")).decode("utf-8")
    except InvalidToken as exc:raise StateError("Encrypted setting cannot be decrypted") from exc

def has_setting(section:str,name:str)->bool:
    return get_setting(section,name,None) not in (None,"")

def section_public(section:str,secret_names:set[str])->dict:
    with _connect() as con:
        rows=con.execute("SELECT name,value,is_secret,updated_at FROM settings WHERE section=?",(section,)).fetchall()
    out={}
    for row in rows:
        name=str(row["name"])
        if name in secret_names or row["is_secret"]:
            out[name]={"configured":bool(row["value"]),"updated_at":row["updated_at"]}
        else:out[name]=row["value"]
    return out

def audit(actor:str,event_code:str,succeeded:bool,detail:str):
    safe=(detail or "")[:1000]
    with _connect() as con:
        con.execute("INSERT INTO audit(occurred_at,actor,event_code,succeeded,detail) VALUES(?,?,?,?,?)",
                    (int(time.time()),actor,event_code,1 if succeeded else 0,safe))
        con.commit()

def recent_audit(limit:int=100):
    limit=max(1,min(500,int(limit)))
    with _connect() as con:
        rows=con.execute("""SELECT occurred_at,actor,event_code,succeeded,detail
          FROM audit ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
    return [dict(x) for x in rows]

def setup_summary():
    return {
      "sql":all(has_setting("sql",x) for x in ("server","database","username","password")),
      "oidc":all(has_setting("oidc",x) for x in ("issuer","audience","client_id","client_secret")),
      "organization":all(has_setting("organization",x) for x in ("tenant_id","company_name")),
      "license_public_key":has_setting("license","public_key_pem"),
      "installation_id":has_setting("license","installation_id"),
    }
