"""Operator preflight for the isolated meeting product; never prints secrets.

Usage: python -m commercial.preflight
       python -m commercial.preflight --database
       python -m commercial.preflight --database --processmaker
A PASS here is a configuration/scheme check, NOT a real external OIDC login,
a penetration test, or permission to import production ProcessMaker content.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import uuid

from .security import ConfigurationFailed, VerifiedTokenAuthenticator

REQUIRED_DB = "EnterpriseProcess2_AI_Test"
SCHEMA_OBJECTS = (
    "AgentProduct.DirectoryUser",
    "AgentProduct.MeetingActor",
    "AgentProduct.LetterIndex",
    "AgentProduct.LetterGrant",
    "AgentProduct.SyncProcessMakerUsers",
    "AgentProduct.SetOrgManager",
    "AgentProduct.SetOrgRole",
    "AgentProduct.TenantBranding",
    "AgentProduct.TenantLicense",
    "AgentProduct.PlatformOperator",
)


def assess_settings(environ=None, *, font_root=None):
    values = environ if environ is not None else os.environ
    checks = {}
    checks["isolated_database"] = (
        values.get("COMMERCIAL_MODE") == "lab"
        and values.get("COMMERCIAL_SQL_DATABASE") == REQUIRED_DB
    )
    checks["hierarchy_content_gate"] = values.get("COMMERCIAL_V2_ONLY") == "1"
    checks["external_chat_disabled"] = values.get("COMMERCIAL_CHAT_ENABLED", "0") == "0"
    checks["protected_portal_opt_in"] = values.get("COMMERCIAL_WEB_PORTAL_ENABLED") == "1"
    checks["restricted_reader_configured"] = bool(
        values.get("COMMERCIAL_SQL_SERVER")
        and values.get("COMMERCIAL_SQL_USER") == "AI_CommercialReader"
        and values.get("COMMERCIAL_SQL_PASSWORD")
    )
    checks["separate_directory_admin_configured"] = bool(
        values.get("COMMERCIAL_DIRECTORY_SQL_USER") == "AI_CommercialDirectoryAdmin"
        and values.get("COMMERCIAL_DIRECTORY_SQL_PASSWORD")
    )
    checks["separate_platform_admin_configured"] = bool(
        values.get("COMMERCIAL_PLATFORM_SQL_USER") == "AI_CommercialPlatformAdmin"
        and values.get("COMMERCIAL_PLATFORM_SQL_PASSWORD")
    )
    try:
        VerifiedTokenAuthenticator(
            values.get("COMMERCIAL_OIDC_ISSUER", ""),
            values.get("COMMERCIAL_OIDC_AUDIENCE", ""),
            values.get("COMMERCIAL_OIDC_JWKS_URL", ""),
        )
        checks["oidc_https_metadata_configured"] = True
    except ConfigurationFailed:
        checks["oidc_https_metadata_configured"] = False
    checks["processmaker_sync_opt_in"] = values.get("COMMERCIAL_PM_SYNC_ENABLED") == "1"
    checks["processmaker_source_configured"] = bool(
        values.get("COMMERCIAL_PM_BASE_URL")
        and values.get("COMMERCIAL_PM_WORKSPACE")
        and values.get("COMMERCIAL_PM_BEARER_TOKEN")
    )
    font_dir = Path(font_root) if font_root is not None else (
        Path(__file__).resolve().parent / "web" / "fonts"
    )
    checks["byekanplus_fonts_local"] = all(
        (font_dir / ("byekanplus-" + weight + ".ttf")).is_file()
        for weight in ("regular", "bold")
    )
    return checks


def database_checks():
    from .security import Principal
    from .sql_store import authorization_snapshot, scoped_connection
    tenant = os.getenv("COMMERCIAL_TEST_TENANT_ID", "")
    subject = os.getenv("COMMERCIAL_TEST_SUBJECT", "")
    try:
        principal = Principal(uuid.UUID(tenant), subject)
    except (ValueError, TypeError):
        return {"verified_test_identity_configured": False}
    if not principal.subject.strip():
        return {"verified_test_identity_configured": False}
    try:
        with scoped_connection(principal) as con:
            authorization_snapshot(con, principal)
            cur = con.cursor()
            objects = {}
            for name in SCHEMA_OBJECTS:
                cur.execute("SELECT OBJECT_ID(?)", name)
                objects[name] = cur.fetchone()[0] is not None
            cur.execute("""
                SELECT COUNT_BIG(*) FROM AgentProduct.DirectoryUser
                WHERE TenantID=? AND SubjectID=? AND IsEnabled=1
                  AND PMStatus='ACTIVE'
            """, str(principal.tenant_id), principal.subject)
            linked = int(cur.fetchone()[0]) == 1
            return {"sql_reader_active_membership": True,
                    "sql_directory_subject_linked": linked,
                    "sql_schema_objects_available": all(objects.values()),
                    "missing_schema_objects": [
                        name for name, found in objects.items() if not found
                    ]}
    except Exception:
        return {"sql_reader_active_membership": False,
                "sql_directory_subject_linked": False,
                "sql_schema_objects_available": False,
                "missing_schema_objects": ["Database connection or authorized schema unavailable"]}


def processmaker_checks():
    # Only the opt-in read-only users endpoint. Never source passwords or content.
    try:
        from .processmaker_directory import fetch_users
        users = fetch_users()
        return {"processmaker_user_source_reachable": len(users) > 0,
                "processmaker_user_count": len(users)}
    except Exception:
        return {"processmaker_user_source_reachable": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Isolated meeting product readiness, no secrets")
    parser.add_argument("--database", action="store_true", help="Read-only isolated SQL check")
    parser.add_argument("--processmaker", action="store_true",
                        help="Opt-in read-only ProcessMaker users API check")
    args = parser.parse_args(argv)
    result = assess_settings()
    if args.database:
        result.update(database_checks())
    if args.processmaker:
        result.update(processmaker_checks())
    # Never claim readiness until a real browser login, per-role tenant ACL and
    # signed license have been tested by the operator on this installation.
    result["real_idp_login_end_to_end_verified"] = False
    result["processmaker_meeting_actor_import_verified"] = False
    result["customer_deployment_approved"] = False
    report = {"status": "REVIEW_PREVIEW_ONLY", "checks": result,
              "note": "Configuration checks only. No production readiness assertion."}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(value is True for key, value in result.items()
                    if key not in (
                        "real_idp_login_end_to_end_verified",
                        "processmaker_meeting_actor_import_verified",
                        "customer_deployment_approved",
                        "byekanplus_fonts_local",
                        "processmaker_sync_opt_in",
                        "processmaker_source_configured",
                        "separate_directory_admin_configured",
                        "separate_platform_admin_configured",
                        "protected_portal_opt_in",
                        "oidc_https_metadata_configured",
                    ) and isinstance(value, bool)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
