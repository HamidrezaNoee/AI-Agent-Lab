"""Isolated, loopback-only, synthetic-data product preview. NEVER use as API auth.

Run ONLY: python -m uvicorn commercial.demo_preview:app --host 127.0.0.1 --port 8090
It exposes static fictional JSON and visual-only module switches. No SQL, OIDC,
OpenAI, license mutations, or ProcessMaker data. DO NOT deploy this preview.
"""
from functools import lru_cache
from pathlib import Path
import json
from ipaddress import ip_address

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web" / "preview"
DATASET = ROOT / "datasets" / "100_automotive_meeting_scenarios_FA.json"

app = FastAPI(title="Fictional Meeting Agent Preview (localhost only)",
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware,
                   allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def loopback_only(request: Request, call_next):
    # Never use request.headers['X-Forwarded-For'] for an access decision.
    # In tests, Starlette TestClient uses a synthetic hostname, not a socket.
    remote = request.client.host if request.client else ""
    try:
        local = ip_address(remote).is_loopback
    except ValueError:
        local = remote == "testclient"
    if not local:
        return JSONResponse({"detail": "Local fictional preview only"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response


@lru_cache(maxsize=1)
def _fictional_data() -> dict:
    source = json.loads(DATASET.read_text(encoding="utf-8"))
    if source.get("synthetic") is not True or len(source.get("scenarios", [])) != 100:
        raise RuntimeError("The checked-in dataset must be exactly 100 fictional cases")
    return source


@app.get("/", include_in_schema=False)
def page():
    return FileResponse(WEB / "index.html", media_type="text/html; charset=utf-8")


@app.get("/preview.css", include_in_schema=False)
def styles():
    return FileResponse(WEB / "preview.css", media_type="text/css; charset=utf-8")


@app.get("/preview.js", include_in_schema=False)
def script():
    return FileResponse(WEB / "preview.js", media_type="text/javascript; charset=utf-8")


@app.get("/assets/{font_name}", include_in_schema=False)
def font_asset(font_name: str):
    allowed = {
        "byekanplus-regular.ttf": WEB / "assets" / "byekanplus-regular.ttf",
        "byekanplus-bold.ttf": WEB / "assets" / "byekanplus-bold.ttf",
    }
    path = allowed.get(font_name)
    if path is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path, media_type="font/ttf")


@app.get("/demo-data", include_in_schema=False)
def demo_data():
    source = _fictional_data()
    # Return only synthetic source file content. This route is intentionally
    # NOT backed by the production API or original ProcessMaker SQL tables.
    return {
        "synthetic": True,
        "notice": "داده‌های کاملاً ساختگی؛ هیچ تراکنش یا مجوز واقعی صادر نمی‌شود.",
        "count": source["count"],
        "scenarios": source["scenarios"],
    }


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "up", "mode": "fictional-loopback-ui-preview",
            "real_login": False, "production_data": False, "real_license": False}



# Optional locally installed user-owned fonts. Binary fonts are NOT embedded
# in the repository or returned as downloadable artifacts from this chat.
# Copy your original B Yekan Plus files into commercial/web/fonts yourself.
@lru_cache(maxsize=2)
def _installed_font(name: str) -> Path:
    if name not in ("regular", "bold"):
        raise HTTPException(status_code=404,detail="Font not found")
    filename = "byekanplus-" + name + ".ttf"
    path = ROOT / "web" / "fonts" / filename
    if not path.is_file():
        raise HTTPException(status_code=404,detail="Optional local font not installed")
    return path


@app.get("/preview-font-regular",include_in_schema=False)
def local_regular_font():
    return FileResponse(_installed_font("regular"), media_type="font/ttf")


@app.get("/preview-font-bold",include_in_schema=False)
def local_bold_font():
    return FileResponse(_installed_font("bold"),media_type="font/ttf")
