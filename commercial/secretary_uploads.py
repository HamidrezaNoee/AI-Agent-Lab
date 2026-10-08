"""Bounded user-supplied document extraction for the conversational secretary.

Uploaded files are untrusted DATA. AVAN never executes macros, scripts or embedded
objects and does not persist the raw upload in Agent storage.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import PurePath

MAX_BYTES = 8 * 1024 * 1024
MAX_TEXT = 18000
_TEXT_EXTENSIONS = {".txt", ".md", ".csv"}
_JSON_EXTENSIONS = {".json"}
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _safe_name(value: str) -> str:
    raw = PurePath(str(value or "document")).name
    raw = re.sub(r"[\x00-\x1f\x7f]+", "", raw).strip()
    return (raw[:180] or "document")


def _bounded(text: str) -> str:
    text = str(text or "").replace("\x00", "").strip()
    if not text:
        raise ValueError("متن قابل استفاده‌ای در فایل پیدا نشد.")
    if len(text) > MAX_TEXT:
        raise ValueError("متن فایل بیش از ۱۸ هزار کاراکتر است؛ بخش مرتبط را در فایل کوچک‌تری ارسال کنید.")
    return text


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeError:
            pass
    raise ValueError("فایل متنی باید UTF-8 باشد.")


def _pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise ValueError("محتوای فایل PDF معتبر نیست.")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "commercial.secretary_uploads", "--pdf"],
            input=data,
            capture_output=True,
            timeout=15,
            check=True,
        )
        return result.stdout.decode("utf-8")
    except (subprocess.SubprocessError, UnicodeError) as exc:
        raise ValueError("متن PDF قابل استخراج نیست؛ PDF اسکن‌شده را به متن تبدیل کنید.") from exc


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ValueError
            info = archive.getinfo("word/document.xml")
            if info.file_size > 3 * 1024 * 1024:
                raise ValueError
            xml = archive.read(info)
            root = ET.fromstring(xml)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, ValueError) as exc:
        raise ValueError("ساختار فایل DOCX معتبر نیست.") from exc

    # WordprocessingML text only. Relationships, macros, external objects and
    # embedded binaries are deliberately ignored.
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(ns + "p"):
        parts = [node.text or "" for node in paragraph.iter(ns + "t")]
        if parts:
            paragraphs.append("".join(parts))
        if sum(len(x) for x in paragraphs) > MAX_TEXT:
            raise ValueError("متن فایل بیش از ۱۸ هزار کاراکتر است؛ بخش مرتبط را ارسال کنید.")
    return "\n".join(paragraphs)


def extract(data: bytes, filename: str, content_type: str = "") -> tuple[str, dict]:
    if not isinstance(data, (bytes, bytearray)) or not data or len(data) > MAX_BYTES:
        raise ValueError("فایل باید حداکثر ۸ مگابایت باشد.")
    data = bytes(data)
    name = _safe_name(filename)
    extension = PurePath(name).suffix.lower()
    mime = str(content_type or "").split(";", 1)[0].strip().lower()

    if extension in _TEXT_EXTENSIONS or mime in {"text/plain", "text/markdown", "text/csv"}:
        text = _decode_text(data)
        kind = extension.lstrip(".") or "text"
    elif extension in _JSON_EXTENSIONS or mime == "application/json":
        raw = _decode_text(data)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON فایل معتبر نیست.") from exc
        text = json.dumps(parsed, ensure_ascii=False, indent=2)
        kind = "json"
    elif extension == ".pdf" or mime == "application/pdf":
        text = _pdf_text(data)
        kind = "pdf"
    elif extension == ".docx" or mime == _DOCX_MIME:
        text = _docx_text(data)
        kind = "docx"
    else:
        raise ValueError("برای گفت‌وگوی دبیر، فایل‌های PDF متنی، DOCX، TXT، MD، CSV و JSON پشتیبانی می‌شوند.")

    text = _bounded(text)
    metadata = {
        "name": name,
        "type": kind,
        "content_type": mime or "application/octet-stream",
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "extracted_chars": len(text),
    }
    return text, metadata


if __name__ == "__main__":
    if sys.argv[1:] != ["--pdf"]:
        raise SystemExit(2)
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    except ImportError:
        pass
    from pypdf import PdfReader

    raw = sys.stdin.buffer.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise SystemExit(2)
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted or len(reader.pages) > 40:
        raise SystemExit(2)
    output = ""
    for page in reader.pages:
        output += (page.extract_text() or "") + "\n"
        if len(output) > MAX_TEXT:
            raise SystemExit(2)
    sys.stdout.write(output)
