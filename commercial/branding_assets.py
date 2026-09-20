"""Restricted, private, tenant-scoped PNG brand assets (LAB ONLY).

No SVG, HTML, remote URL, data URL, untrusted filename or arbitrary path.
The filesystem directory is explicitly configured outside the Git repository.
All logo reads require the same active tenant SQL membership. Asset names are
opaque random 32hex tokens, stored only after a vetted tenant SysAdmin DB write.
"""
from pathlib import Path
import os
import re
import struct
import uuid

from fastapi import HTTPException
from fastapi.responses import FileResponse

MAX_PNG_BYTES=256*1024


def logo_root() -> Path:
    path=os.getenv("COMMERCIAL_LOGO_STORAGE_DIR","").strip()
    if not path or not Path(path).is_absolute():
        raise HTTPException(status_code=503,detail="Private logo storage not configured")
    root=Path(path).resolve()
    checkout=Path(__file__).resolve().parent.parent
    if root==checkout or checkout in root.parents:
        raise HTTPException(status_code=503,detail="Logo storage cannot be inside source repository")
    if not root.is_dir():
        raise HTTPException(status_code=503,detail="Private logo storage folder missing")
    return root


def validate_png(payload: bytes) -> None:
    if not isinstance(payload,bytes) or not 33 <= len(payload) <= MAX_PNG_BYTES:
        raise HTTPException(status_code=422,detail="PNG file is missing or too large (max 256 KB)")
    if (payload[:8]!=b"\x89PNG\r\n\x1a\n" or payload[12:16]!=b"IHDR"
        or struct.unpack(">I",payload[8:12])[0]!=13):
        raise HTTPException(status_code=422,detail="Only valid PNG headers are accepted")
    width,height=struct.unpack(">II",payload[16:24])
    if not (1<=width<=2048 and 1<=height<=2048):
        raise HTTPException(status_code=422,detail="Logo dimensions must be 1..2048px")


def store_png(payload: bytes) -> tuple[str,Path]:
    validate_png(payload)
    root=logo_root()
    name=uuid.uuid4().hex+".png"
    file=root/name
    try:
        with file.open("xb") as output:
            output.write(payload)
    except OSError:
        raise HTTPException(status_code=503,detail="Private logo storage unavailable")
    return name,file


def logo_response(name: str) -> FileResponse:
    if not isinstance(name,str) or not re.fullmatch(r"[0-9a-f]{32}\.png",name):
        raise HTTPException(status_code=404,detail="Logo not available")
    file=logo_root()/name
    if not file.is_file() or file.stat().st_size>MAX_PNG_BYTES:
        raise HTTPException(status_code=404,detail="Logo not available")
    response=FileResponse(file,media_type="image/png",filename=None)
    response.headers["Cache-Control"]="private, no-store"
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    return response
