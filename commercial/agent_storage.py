"""The Agent's own SQL Server database. Never connects to meeting mirror tables."""

from contextlib import contextmanager
import hashlib, json, secrets
from . import setup_console as setup

DATABASE = "AVANAgent"
LOGIN = "AVAN_AgentApp"


class AgentStorageUnavailable(Exception):
    pass


def quoted(value):
    if not value or any(x in value for x in ("\x00", "\r", "\n")):
        raise AgentStorageUnavailable("Invalid SQL setting")
    return "{" + value.replace("}", "}}") + "}"


def connect(config=None, *, autocommit=False):
    c = config or setup.get_setting("agent_sql") or {}
    if c.get("database") != DATABASE or c.get("username") != LOGIN:
        raise AgentStorageUnavailable("Dedicated AVANAgent database/account required")
    server = str(c.get("server", ""))
    if not server or any(x in server for x in (";", "{", "}", "\x00", "\r", "\n")):
        raise AgentStorageUnavailable("Invalid SQL endpoint")
    if "," not in server and "\\" not in server:
        server += ",1433"
    try:
        import pyodbc

        con = pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};SERVER="
            + quoted(server)
            + ";DATABASE=AVANAgent;UID=AVAN_AgentApp;PWD="
            + quoted(c.get("password", ""))
            + ";Encrypt=yes;TrustServerCertificate="
            + ("yes" if c.get("trust_server_certificate") else "no")
            + ";Connection Timeout=8;",
            timeout=8,
            autocommit=autocommit,
        )
        con.timeout = 15
        return con
    except Exception as exc:
        raise AgentStorageUnavailable("Agent SQL Server unavailable") from exc


def state_key(name):
    return hashlib.sha256(name.encode()).hexdigest()


class Transaction:
    def __init__(self, con):
        self.con = con

    def get(self, name, default=None, *, lock=False):
        hint = " WITH (UPDLOCK,HOLDLOCK)" if lock else ""
        row = (
            self.con.cursor()
            .execute(
                "SELECT Payload FROM dbo.AgentState" + hint + " WHERE StateKey=?",
                state_key(name),
            )
            .fetchone()
        )
        return setup._unseal("agent:" + name, bytes(row[0])) if row else default

    def put(self, name, value):
        key = state_key(name)
        blob = setup._seal("agent:" + name, value)
        cur = self.con.cursor()
        cur.execute(
            "SELECT StateKey FROM dbo.AgentState WITH (UPDLOCK,HOLDLOCK) WHERE StateKey=?",
            key,
        )
        if cur.fetchone():
            cur.execute(
                "UPDATE dbo.AgentState SET Payload=?,UpdatedAt=SYSUTCDATETIME() WHERE StateKey=?",
                blob,
                key,
            )
        else:
            cur.execute(
                "INSERT dbo.AgentState(StateKey,Payload,UpdatedAt) VALUES(?,?,SYSUTCDATETIME())",
                key,
                blob,
            )

    def audit(self, tenant, actor, event, detail):
        self.con.cursor().execute(
            "INSERT dbo.AgentAudit(EventID,TenantID,ActorID,EventCode,HappenedAt,Detail) VALUES(?,?,?,?,SYSUTCDATETIME(),?)",
            secrets.token_hex(16),
            str(tenant),
            str(actor),
            event,
            json.dumps(detail, ensure_ascii=False),
        )


@contextmanager
def transaction():
    con = connect()
    try:
        yield Transaction(con)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
