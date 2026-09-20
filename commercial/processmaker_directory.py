"""ProcessMaker 3.3.x read-only directory adapter (TEST/OPERATOR CONTROLLED).

Source API: GET /api/1.0/{workspace}/users?status=all&start=N&limit=50.
NEVER ingest usr_password or any other arbitrary source property. Read-only OAuth
bearer is server-side only. No account is linked to a trusted OIDC subject by name.
No automatic admin role assignment or ProcessMaker user creation.
"""
from dataclasses import asdict, dataclass
import json
import os
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPHandler, ProxyHandler, HTTPRedirectHandler


class PMSyncUnavailable(Exception):
    pass


@dataclass(frozen=True)
class PMUser:
    pm_uid: str
    username: str
    display_name: str
    email: str | None
    status: str


def clean_users(payload: object) -> list[PMUser]:
    """Strict allowlist: source may contain legacy password hashes: DROP them."""
    if not isinstance(payload, list):
        raise PMSyncUnavailable("Unexpected ProcessMaker user-list response")
    result = []
    seen = set()
    for row in payload:
        if not isinstance(row, dict):
            raise PMSyncUnavailable("Malformed ProcessMaker user record")
        uid, username = row.get("usr_uid"), row.get("usr_username")
        status = str(row.get("usr_status", "")).upper()
        if not isinstance(uid, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", uid):
            raise PMSyncUnavailable("Invalid ProcessMaker user UID")
        if not isinstance(username, str) or not 1 <= len(username.strip()) <= 120:
            raise PMSyncUnavailable("Invalid ProcessMaker username")
        if status not in {"ACTIVE", "INACTIVE", "VACATION"}:
            raise PMSyncUnavailable("Unsupported ProcessMaker user status")
        firstname, lastname = row.get("usr_firstname"), row.get("usr_lastname")
        display_name = " ".join(str(x).strip() for x in (firstname, lastname)
                                if isinstance(x, str) and x.strip())
        email = row.get("usr_email")
        if email is not None and not isinstance(email, str):
            raise PMSyncUnavailable("Malformed ProcessMaker email")
        if isinstance(email, str):
            email = email.strip()[:240] or None
        uid = uid.lower()
        if uid in seen:
            raise PMSyncUnavailable("Duplicate ProcessMaker UID in snapshot")
        seen.add(uid)
        # NEVER store, log, return or hash source usr_password.
        result.append(PMUser(uid, username.strip(), display_name[:240] or username.strip(),
                             email, status))
    return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PMSyncUnavailable("ProcessMaker API redirect denied")


def fetch_users(*, base_url: str | None = None,
                workspace: str | None = None,
                bearer: str | None = None,
                per_page: int = 50, max_users: int = 5000) -> list[PMUser]:
    """Return ONLY a complete validated snapshot or fail without applying any DB changes.

    Configuration is trusted server-side operator input, never a request body.
    Production HTTPS must use system-trusted TLS; localhost HTTP is opt-in
    only for a physically local, isolated ProcessMaker installation.
    """
    if os.getenv("COMMERCIAL_PM_SYNC_ENABLED") != "1":
        raise PMSyncUnavailable("ProcessMaker sync is disabled")
    if (os.getenv("COMMERCIAL_MODE") != "lab" or
        os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"):
        raise PMSyncUnavailable("ProcessMaker sync is restricted to test database")
    base = (base_url if base_url is not None
            else os.getenv("COMMERCIAL_PM_BASE_URL", "")).rstrip("/")
    space = workspace if workspace is not None else os.getenv("COMMERCIAL_PM_WORKSPACE", "")
    token = bearer if bearer is not None else os.getenv("COMMERCIAL_PM_BEARER_TOKEN", "")
    parts = urlsplit(base)
    if parts.username or parts.password or parts.query or parts.fragment or not parts.hostname:
        raise PMSyncUnavailable("Invalid ProcessMaker server URL")
    local_plain_http = (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost")
                        and os.getenv("COMMERCIAL_PM_ALLOW_LOCAL_HTTP") == "1")
    if parts.scheme != "https" and not local_plain_http:
        raise PMSyncUnavailable("ProcessMaker API requires HTTPS (or explicitly enabled local HTTP)")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", space or ""):
        raise PMSyncUnavailable("Invalid ProcessMaker workspace")
    if not isinstance(token, str) or not 8 <= len(token) <= 8192 or "\r" in token or "\n" in token:
        raise PMSyncUnavailable("Read-only ProcessMaker OAuth bearer missing")
    if not 1 <= per_page <= 100 or not 1 <= max_users <= 5000:
        raise PMSyncUnavailable("Invalid synchronization limits")

    # Disabled system proxy avoids redirect/proxy surprises for internal sources.
    opener = build_opener(ProxyHandler({}), _NoRedirect(),
                          HTTPSHandler(context=ssl.create_default_context()), HTTPHandler())
    seen = set()
    gathered = []
    start = 0
    for _page_no in range(max_users // per_page + 2):
        params = urlencode({"status": "all", "start": start, "limit": per_page})
        url = base + "/api/1.0/" + quote(space, safe="") + "/users?" + params
        req = Request(url, headers={"Authorization": "Bearer " + token,
                                    "Accept": "application/json"}, method="GET")
        try:
            with opener.open(req, timeout=12) as response:
                if response.status != 200:
                    raise PMSyncUnavailable("ProcessMaker API did not return HTTP 200")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise PMSyncUnavailable("ProcessMaker API page too large")
                # json decoder raises on malformed payload; no partial DB apply.
                batch = clean_users(json.loads(raw.decode("utf-8")))
        except (HTTPError, URLError, TimeoutError, ValueError, UnicodeError) as exc:
            # NEVER include remote body, URL credentials or bearer in errors.
            raise PMSyncUnavailable("ProcessMaker users API unavailable or malformed") from exc
        if len(batch) > per_page:
            raise PMSyncUnavailable("ProcessMaker API ignored page limit")
        for user in batch:
            if user.pm_uid in seen:
                raise PMSyncUnavailable("Duplicate UID across ProcessMaker API pages")
            seen.add(user.pm_uid)
            gathered.append(user)
        if len(gathered) > max_users:
            raise PMSyncUnavailable("ProcessMaker user count exceeds safety limit")
        if len(batch) < per_page:
            # A complete snapshot is a precondition for applying changes.
            return gathered
        start += per_page
    raise PMSyncUnavailable("ProcessMaker API pagination did not terminate")


def safe_preview(users: list[PMUser]) -> dict:
    """No passwords, bearer, endpoints or connection strings exposed."""
    return {"count": len(users),
            "active": sum(u.status == "ACTIVE" for u in users),
            "inactive": sum(u.status == "INACTIVE" for u in users),
            "vacation": sum(u.status == "VACATION" for u in users),
            "sample": [asdict(u) for u in users[:20]],
            "note": "Read-only snapshot. No OIDC identities or privileged roles assigned."}
