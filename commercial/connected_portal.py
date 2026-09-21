"""Opt-in, same-origin connected lab portal shell for a REAL external OAuth IdP.

This is NOT an identity provider: no local JWT minting, test bypass or credentials.
The public SPA uses Authorization Code + PKCE (S256) with an admin-approved HTTPS
provider that supports browser token endpoint CORS and issues RS256 access tokens
containing trusted tenant_id. The existing API authenticates every Bearer call.
No claim of end-to-end external IdP testing before actual configuration.
"""
from ipaddress import ip_address
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from .security import VerifiedTokenAuthenticator, ConfigurationFailed, _https_url
from .local_font_css import installed_font_css

ROOT = Path(__file__).resolve().parent / "web"
router = APIRouter(include_in_schema=False)


def _enabled():
    if (os.getenv("COMMERCIAL_WEB_PORTAL_ENABLED") != "1"
            or os.getenv("COMMERCIAL_MODE") != "lab"
            or os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"):
        raise HTTPException(status_code=404, detail="Connected lab portal disabled")


def _localhost(request: Request):
    _enabled()
    remote = request.client.host if request.client else ""
    try:
        loopback = ip_address(remote).is_loopback
    except ValueError:
        loopback = remote == "testclient"  # Starlette's in-process TestClient ONLY
    # Docker Desktop rewrites localhost-published connections as a private
    # bridge-gateway client. Explicitly opt into that route ONLY for the
    # isolated test DB and a localhost Host header. Compose must bind the
    # host port on 127.0.0.1; never deploy this lab portal publicly.
    docker_local = False
    if (not loopback and os.getenv("COMMERCIAL_PORTAL_DOCKER") == "1"
            and request.url.hostname in ("127.0.0.1", "localhost")):
        try:
            docker_local = ip_address(remote).is_private
        except ValueError:
            docker_local = False
    if not (loopback or docker_local) or request.url.hostname not in (
        "127.0.0.1", "localhost", "testserver"
    ):
        raise HTTPException(status_code=403, detail="Connected lab portal is loopback only")


def _config():
    # Reuse the EXACT issuer/audience/JWKS configuration used by API token checks.
    verifier = VerifiedTokenAuthenticator.from_environment()
    authorization = _https_url(os.getenv("COMMERCIAL_OIDC_AUTHORIZATION_URL", ""),
                                "authorization endpoint")
    token = _https_url(os.getenv("COMMERCIAL_OIDC_TOKEN_URL", ""),
                       "token endpoint")
    client_id = os.getenv("COMMERCIAL_OIDC_CLIENT_ID", "")
    if not 1 <= len(client_id) <= 256 or re.search(r"[\s\x00-\x1f]", client_id):
        raise ConfigurationFailed("Invalid public OIDC client ID")
    scopes = os.getenv("COMMERCIAL_OIDC_SCOPES", "openid profile")
    if not scopes or len(scopes) > 500 or re.search(r"[\x00-\x1f]", scopes):
        raise ConfigurationFailed("Invalid OAuth scope setting")
    # Optional provider-specific authorization audience, set by operator only.
    auth_audience = os.getenv("COMMERCIAL_OIDC_AUTH_AUDIENCE", "")
    if len(auth_audience) > 256 or re.search(r"[\s\x00-\x1f]", auth_audience):
        raise ConfigurationFailed("Invalid OAuth authorization audience")
    endpoint = urlsplit(token)
    if not re.fullmatch(r"[A-Za-z0-9.-]+", endpoint.hostname or ""):
        raise ConfigurationFailed("Invalid token endpoint hostname")
    try:
        port = endpoint.port
    except ValueError as exc:
        raise ConfigurationFailed("Invalid token endpoint port") from exc
    if (port is not None and not 1 <= port <= 65535
            or not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?", endpoint.netloc)):
        raise ConfigurationFailed("Invalid HTTPS token endpoint origin")
    origin = "https://" + endpoint.netloc
    return {
        "issuer": verifier.issuer, "authorization_url": authorization,
        "token_url": token, "client_id": client_id, "scopes": scopes,
        "audience": verifier.audience, "auth_audience": auth_audience,
        "token_origin": origin,
    }


def _headers(response, token_origin=None):
    connect = "'self'" + ((" " + token_origin) if token_origin else "")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "font-src 'self'; img-src 'self' data:; connect-src " + connect + "; "
        "form-action 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@router.get("/portal/")
def portal_home(request: Request):
    _localhost(request)
    try:
        token_origin = _config()["token_origin"]
    except ConfigurationFailed:
        token_origin = None  # Only a no-login diagnostic shell may render.
    return _headers(FileResponse(ROOT / "portal" / "index.html",
                                 media_type="text/html; charset=utf-8"), token_origin)


@router.get("/portal/portal.js")
def portal_js(request: Request):
    _localhost(request)
    return _headers(FileResponse(ROOT / "portal" / "portal.js",
                                 media_type="text/javascript; charset=utf-8"))


@router.get("/portal/portal.css")
def portal_css(request: Request):
    _localhost(request)
    css = (installed_font_css("/portal/font/")
           + (ROOT / "preview" / "preview.css").read_text(encoding="utf-8"))
    return _headers(Response(css, media_type="text/css; charset=utf-8"))


@router.get("/portal/config")
def portal_config(request: Request):
    _localhost(request)
    try:
        config = _config()
    except ConfigurationFailed:
        return _headers(JSONResponse({"ready": False,
                                      "reason": "Real HTTPS identity provider is not configured"},
                                     status_code=503))
    config.pop("token_origin")
    # Public UI signal only; the server, not the browser, enforces the gate.
    config["hierarchy_only"] = os.getenv("COMMERCIAL_V2_ONLY", "0") == "1"
    return _headers(JSONResponse({"ready": True, **config}))



@router.get("/portal/font/{weight}")
def portal_font(weight: str, request: Request):
    _localhost(request)
    if weight not in ("regular", "bold"):
        raise HTTPException(status_code=404,detail="Font not found")
    # Serve only two fixed, user-installed paths; never accept arbitrary paths
    # from the request. No font binaries are embedded in this repository.
    source = ROOT / "fonts" / ("byekanplus-" + weight + ".ttf")
    if not source.is_file():
        raise HTTPException(status_code=404,detail="Optional local font not installed")
    return _headers(FileResponse(source,media_type="font/ttf"))
