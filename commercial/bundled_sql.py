"""One-shot provisioning for the Docker-managed AVANAgent SQL Server."""

from __future__ import annotations

from pathlib import Path
import os
import time

from . import setup_console as setup
from .agent_connections import BUNDLED_ID, read, register_bundled
from .agent_install import provision


def bootstrap():
    setup.initialize()
    secret_path = Path(os.getenv(
        "AVAN_BUNDLED_SQL_SA_PASSWORD_PATH",
        "/run/secrets/avan_sql_sa_password",
    ))
    password = secret_path.read_text(encoding="utf-8").strip()
    if len(password) < 16 or len(password) > 128 or any(c in password for c in "\x00\r\n"):
        raise RuntimeError("Bundled SQL administrator secret is invalid")

    existing = (read().get("connections", {}).get(BUNDLED_ID) or {}).get("config") or {}
    last = None
    for attempt in range(12):
        try:
            config = provision(
                server="agent-sql,1433",
                username="sa",
                password=password,
                trust_server_certificate=True,
                app_password=existing.get("password"),
                reset_existing_login=not bool(existing.get("password")),
            )
            register_bundled(config)
            print("Bundled AVANAgent database is ready.")
            return
        except Exception as exc:
            last = exc
            if attempt < 11:
                time.sleep(5)
    raise RuntimeError("Bundled AVANAgent database provisioning failed") from last


if __name__ == "__main__":
    bootstrap()
