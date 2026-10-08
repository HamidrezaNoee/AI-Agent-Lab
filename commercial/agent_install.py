"""Install only the dedicated AVANAgent database, using fixed reviewed DDL."""

from pathlib import Path
import re, secrets
from .agent_storage import DATABASE, LOGIN, quoted, connect, AgentStorageUnavailable
from . import setup_console as setup


class InstallationDenied(Exception):
    pass


def provision(*, server, username, password, trust_server_certificate=False,
              app_password=None, reset_existing_login=False):
    if not server or any(c in server for c in ";{}\x00\r\n"):
        raise InstallationDenied("Invalid SQL endpoint")
    if username.casefold() == LOGIN.casefold():
        raise InstallationDenied("Installer account required")
    endpoint = server if "," in server or "\\" in server else server + ",1433"
    import pyodbc

    con = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER="
        + quoted(endpoint)
        + ";DATABASE=master;UID="
        + quoted(username)
        + ";PWD="
        + quoted(password)
        + ";Encrypt=yes;TrustServerCertificate="
        + ("yes" if trust_server_certificate else "no")
        + ";Connection Timeout=8;",
        timeout=8,
        autocommit=True,
    )
    con.timeout = 30
    try:
        cur = con.cursor()
        if not cur.execute("SELECT IS_SRVROLEMEMBER('sysadmin')").fetchone()[0]:
            raise InstallationDenied(
                "Initial provisioning requires a SQL administrator"
            )
        exists = cur.execute("SELECT SUSER_ID(?)", LOGIN).fetchone()[0] is not None
        if exists and not app_password and not reset_existing_login:
            raise InstallationDenied(
                "Login already exists; use connection settings with its existing password"
            )
        app_password = app_password or "Aa1!" + secrets.token_urlsafe(40)
        if len(app_password) > 128 or any(c in app_password for c in "'\x00\r\n"):
            raise InstallationDenied("Invalid application credential")
        config = {
            "server": server,
            "database": DATABASE,
            "username": LOGIN,
            "password": app_password,
            "trust_server_certificate": trust_server_certificate,
        }
        cur.execute("IF DB_ID(N'AVANAgent') IS NULL CREATE DATABASE [AVANAgent]")
        for batch in re.split(
            r"(?im)^\s*GO\s*$",
            (Path(__file__).parent / "sql" / "AVANAgent_01_schema.sql").read_text(),
        ):
            if batch.strip():
                cur.execute(batch)
        if exists and reset_existing_login:
            cur.execute(
                "ALTER LOGIN [AVAN_AgentApp] WITH PASSWORD='" + app_password + "'"
            )
        elif not exists:
            # Generated ASCII only, never request text interpolated into DDL.
            cur.execute(
                "USE [master]; CREATE LOGIN [AVAN_AgentApp] WITH PASSWORD='"
                + app_password
                + "',CHECK_POLICY=ON"
            )
        cur.execute(
            "USE [AVANAgent]; IF USER_ID(N'AVAN_AgentApp') IS NULL CREATE USER [AVAN_AgentApp] FOR LOGIN [AVAN_AgentApp]"
        )
        cur.execute("GRANT SELECT,INSERT,UPDATE ON dbo.AgentState TO [AVAN_AgentApp]")
        cur.execute("GRANT SELECT,INSERT ON dbo.AgentAudit TO [AVAN_AgentApp]")
        config = {
            "server": server,
            "database": DATABASE,
            "username": LOGIN,
            "password": app_password,
            "trust_server_certificate": trust_server_certificate,
        }
        check(config)
        return config
    finally:
        con.close()


def prepare(
    *, server, username, password, trust_server_certificate=False, confirmation=""
):
    if confirmation != DATABASE:
        raise InstallationDenied("Confirm AVANAgent database creation")
    current = (
        setup.get_setting("agent_sql")
        or setup.get_setting("agent_sql_pending")
        or {}
    )
    same_endpoint = current.get("server") == server and current.get("password")
    config = provision(
        server=server,
        username=username,
        password=password,
        trust_server_certificate=trust_server_certificate,
        app_password=current.get("password") if same_endpoint else None,
    )
    from .agent_connections import save_external, activate
    connection_id = save_external(
        name="SQL Server خارجی " + server,
        config=config,
    )
    activate(connection_id)
    return {"installed": True, "database": DATABASE, "meeting_data_copied": False}


def check(config):
    con = connect(config)
    try:
        cur = con.cursor()
        cur.execute("SELECT TOP (0) StateKey,Payload FROM dbo.AgentState")
        cur.execute("SELECT TOP (0) EventID FROM dbo.AgentAudit")
        row = cur.execute(
            "SELECT HAS_PERMS_BY_NAME('dbo.AgentState','OBJECT','SELECT'),"
            "HAS_PERMS_BY_NAME('dbo.AgentState','OBJECT','INSERT'),"
            "HAS_PERMS_BY_NAME('dbo.AgentState','OBJECT','UPDATE'),"
            "HAS_PERMS_BY_NAME('dbo.AgentAudit','OBJECT','SELECT'),"
            "HAS_PERMS_BY_NAME('dbo.AgentAudit','OBJECT','INSERT'),"
            "IS_SRVROLEMEMBER('sysadmin'),IS_MEMBER('db_owner')"
        ).fetchone()
        if not row or any(row[i] != 1 for i in range(5)) or row[5] != 0 or row[6] != 0:
            raise AgentStorageUnavailable(
                "Restricted Agent account permissions required"
            )
        return {"connected": True, "database": DATABASE}
    finally:
        con.close()
