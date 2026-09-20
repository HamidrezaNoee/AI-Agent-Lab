"""Tenant-purchased optional modules. Module 1 is core; 2/3/4 require SQL license
AND tenant admin enabled flag, checked on EACH request after membership/subscription.
The customer can pause/resume an already licensed module, never self-purchase one.
"""
from datetime import datetime, timezone
from .security import Principal
from .sql_store import AccessDenied

OPTIONAL_MODULES = {
    2: ("secretary", "دبیر هوشمند جلسه"),
    3: ("analytics", "تحلیل و گزارش مدیریتی"),
    4: ("monitoring", "هشدار و پیگیری اقدامات"),
}


def modules_snapshot(con, principal: Principal) -> list[dict]:
    cursor = con.cursor()
    cursor.execute("""
        SELECT ModuleCode, IsLicensed, IsEnabled, LicenseUntilUtc
        FROM AgentProduct.TenantModule
        WHERE TenantID=? AND ModuleCode IN (2,3,4)
    """, str(principal.tenant_id))
    rows = {int(r[0]): r for r in cursor.fetchall()}
    now = datetime.now(timezone.utc)
    result = [{"module_code": 1, "key": "assistant",
               "title": "دستیار مدیریتی", "licensed": True,
               "enabled": True, "active": True,
               "license_until_utc": None}]
    for code, (key, title) in OPTIONAL_MODULES.items():
        row = rows.get(code)
        end = row[3] if row else None
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        licensed = bool(row and row[1] and (end is None or end > now))
        enabled = bool(row and row[2])
        result.append({
            "module_code": code, "key": key, "title": title,
            "licensed": licensed, "enabled": enabled,
            "active": licensed and enabled,
            "license_until_utc": end.isoformat() if end else None,
        })
    return result


def require_module(con, principal: Principal, code: int) -> None:
    """Never use UI visibility as the authorization boundary."""
    if code not in OPTIONAL_MODULES:
        raise AccessDenied("Unknown optional module")
    matching = next(m for m in modules_snapshot(con, principal)
                    if m["module_code"] == code)
    if not matching["active"]:
        raise AccessDenied("Module is not purchased, expired or disabled")


def set_module_enabled(con, principal: Principal, code: int, enabled: bool) -> dict:
    if code not in OPTIONAL_MODULES or type(enabled) is not bool:
        raise AccessDenied("Invalid module setting")
    cursor = con.cursor()
    # Stored procedure repeats verified DB Owner/Admin and license/tenant checks,
    # audits each change and refuses activation without a purchased license.
    try:
        cursor.execute(
            "EXEC AgentProduct.SetTenantModuleEnabled "
            "@TenantID=?,@SubjectID=?,@ModuleCode=?,@Enabled=?",
            str(principal.tenant_id), principal.subject, code, int(enabled),
        )
        row = cursor.fetchone()
    except Exception as exc:
        # A raced expiry/revocation or unavailable SQL procedure must fail closed.
        # Never echo SQL exception details or silently activate an unlicensed module.
        raise AccessDenied("Module activation denied by database") from exc
    return {"module_code": code, "licensed": bool(row[1]),
            "enabled": bool(row[2]), "license_until_utc": str(row[3])}
