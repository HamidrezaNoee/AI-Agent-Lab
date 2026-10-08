"""Encrypted Agent SQL connection catalog controlled only by GodAdmin.

The active connection is still mirrored to ``agent_sql`` so the data plane has
one small, fail-closed configuration surface.  Passwords in this catalog are
inside setup_console's AES-GCM encrypted state and are never returned by APIs.
"""

from __future__ import annotations

import re
import secrets

from . import setup_console as setup

BUNDLED_ID = "bundled"
CATALOG_VERSION = 1


class ConnectionCatalogError(Exception):
    pass


def _new_catalog():
    return {"version": CATALOG_VERSION, "active_id": None, "connections": {}}


def read():
    catalog = setup.get_setting("agent_sql_connections")
    if catalog is not None:
        return catalog

    # One-time compatibility with installations made before connection profiles.
    catalog = _new_catalog()
    current = setup.get_setting("agent_sql") or {}
    if current:
        catalog["active_id"] = "legacy"
        catalog["connections"]["legacy"] = {
            "name": "اتصال قبلی AVANAgent",
            "managed": False,
            "config": current,
        }
    setup.put_setting("agent_sql_connections", catalog)
    return catalog


def _save(catalog):
    setup.put_setting("agent_sql_connections", catalog)


def register_bundled(config):
    catalog = read()
    first_connection = not catalog.get("connections")
    catalog["connections"][BUNDLED_ID] = {
        "name": "SQL Server داخلی Docker",
        "managed": True,
        "config": config,
    }
    if first_connection and not catalog.get("active_id") and not (setup.get_setting("agent_sql") or {}):
        catalog["active_id"] = BUNDLED_ID
        setup.put_setting("agent_sql", config)
        setup.audit("AGENT_SQL_BUNDLED_ACTIVATED")
    _save(catalog)
    return catalog


def public_status():
    catalog = read()
    rows = []
    for connection_id, row in catalog.get("connections", {}).items():
        config = row.get("config") or {}
        rows.append({
            "id": connection_id,
            "name": row.get("name") or connection_id,
            "managed": bool(row.get("managed")),
            "active": connection_id == catalog.get("active_id"),
            "server": config.get("server", ""),
            "database": "AVANAgent",
            "username": "AVAN_AgentApp",
            "trust_server_certificate": bool(config.get("trust_server_certificate")),
            "password_configured": bool(config.get("password")),
        })
    rows.sort(key=lambda x: (not x["managed"], x["name"].casefold()))
    return {"active_id": catalog.get("active_id"), "connections": rows}


def save_external(*, name, config, connection_id=None):
    from .agent_install import check

    if not name or len(name) > 100 or any(c in name for c in "\x00\r\n"):
        raise ConnectionCatalogError("Invalid connection name")
    catalog = read()
    if connection_id:
        if not re.fullmatch(r"[a-f0-9]{24}|legacy", connection_id):
            raise ConnectionCatalogError("Invalid connection id")
        existing = catalog["connections"].get(connection_id)
        if not existing or existing.get("managed"):
            raise ConnectionCatalogError("Connection cannot be edited")
        if not config.get("password"):
            if config.get("server") != (existing.get("config") or {}).get("server"):
                raise ConnectionCatalogError("Changing SQL server requires a new application password")
            config["password"] = (existing.get("config") or {}).get("password", "")
    else:
        connection_id = secrets.token_hex(12)
    check(config)
    catalog["connections"][connection_id] = {
        "name": name,
        "managed": False,
        "config": config,
    }
    if connection_id == catalog.get("active_id"):
        # Keep the connection actually used by the Agent in sync with the
        # profile shown as active after an edit has passed the same check.
        setup.put_setting("agent_sql", config)
    _save(catalog)
    setup.audit("AGENT_SQL_CONNECTION_SAVED")
    return connection_id


def activate(connection_id):
    from .agent_install import check

    catalog = read()
    row = catalog.get("connections", {}).get(connection_id)
    if not row:
        raise ConnectionCatalogError("Connection does not exist")
    config = row.get("config") or {}
    check(config)
    setup.put_setting("agent_sql", config)
    catalog["active_id"] = connection_id
    _save(catalog)
    setup.audit("AGENT_SQL_CONNECTION_ACTIVATED")
    return row


def check_saved(connection_id):
    from .agent_install import check

    row = read().get("connections", {}).get(connection_id)
    if not row:
        raise ConnectionCatalogError("Connection does not exist")
    return check(row.get("config") or {})


def disconnect():
    catalog = read()
    catalog["active_id"] = None
    setup.put_setting("agent_sql", {})
    _save(catalog)
    setup.audit("AGENT_SQL_CONNECTION_DISCONNECTED")


def delete(connection_id):
    catalog = read()
    if connection_id == BUNDLED_ID:
        raise ConnectionCatalogError("Bundled connection cannot be deleted")
    if connection_id == catalog.get("active_id"):
        raise ConnectionCatalogError("Disconnect active connection first")
    if connection_id not in catalog.get("connections", {}):
        raise ConnectionCatalogError("Connection does not exist")
    del catalog["connections"][connection_id]
    _save(catalog)
    setup.audit("AGENT_SQL_CONNECTION_DELETED")
