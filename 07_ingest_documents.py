# -*- coding: utf-8 -*-
"""Versioned synthetic-document importer for SQL Server 2022 test database.

Usage:
  python 07_ingest_documents.py --file sample_docs/synthetic_import_procedure.md --synthetic
  python 07_ingest_documents.py --file sample_docs/synthetic_import_procedure.md --synthetic --embed

Writer uses Windows Authentication (TEST DBA); NEVER use the read-only agent account.
Embedding API sends selected document content to OpenAI. Use ONLY approved fictional
test material here; no production/confidential documents in the isolated test DB.
"""
import argparse
import hashlib
import os
import re
import struct
from pathlib import Path

import pyodbc

TEST_DB = "EnterpriseProcess2_AI_Test"
EMBED_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 140
MAX_FILE_BYTES = 2_000_000
MAX_TEXT_CHARS = 400_000


def read_text(path: Path) -> str:
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".docx":
        try:
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph
            from docx.oxml.table import CT_Tbl
            from docx.oxml.text.paragraph import CT_P
        except ImportError as exc:
            raise RuntimeError("Install python-docx for Word files: pip install python-docx") from exc
        doc = Document(str(path))
        parts = []
        for child in doc.element.body.iterchildren():
            if isinstance(child, CT_P):
                p = Paragraph(child, doc)
                if p.text.strip():
                    parts.append(p.text.strip())
            elif isinstance(child, CT_Tbl):
                table = Table(child, doc)
                for row in table.rows:
                    cells = [re.sub(r"\s+", " ", cell.text).strip() for cell in row.cells]
                    if any(cells):
                        parts.append(" | ".join(cells))
        return "\n".join(parts)
    raise ValueError("Only .txt, .md, and .docx files are supported in this phase.")


def chunks_from_text(text: str):
    """Yield bounded (start_char, end_char, text) preserving exact offsets."""
    size = len(text)
    start = 0
    while start < size:
        end = min(start + CHUNK_SIZE, size)
        if end < size:
            # Prefer a paragraph/sentence boundary without creating tiny chunks.
            possible = [text.rfind(sep, start + CHUNK_SIZE // 2, end) for sep in ("\n", ". ", "؟", "؛")]
            boundary = max(possible)
            if boundary > start + CHUNK_SIZE // 2:
                end = boundary + 1
        chunk = text[start:end]
        if chunk.strip():
            yield start, end, chunk
        if end >= size:
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def embed_texts(chunks: list[str]) -> list[bytes]:
    from openai import OpenAI
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY required with --embed.")
    client = OpenAI()
    result = []
    for i in range(0, len(chunks), 32):
        batch = chunks[i:i + 32]
        response = client.embeddings.create(model=EMBED_MODEL, input=batch)
        vectors = sorted(response.data, key=lambda item: item.index)
        if len(vectors) != len(batch):
            raise RuntimeError("Embedding count differs from chunk count.")
        for item in vectors:
            values = item.embedding
            result.append(struct.pack("<" + "f" * len(values), *values))
    return result


def open_admin_connection():
    if os.getenv("SQL_DATABASE") != TEST_DB:
        raise RuntimeError("Safety: SQL_DATABASE must be EnterpriseProcess2_AI_Test.")
    server = os.getenv("SQL_SERVER")
    if not server:
        raise RuntimeError("SQL_SERVER missing.")
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={server};DATABASE={TEST_DB};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;",
        timeout=10,
        autocommit=False,
    )


def ingest(file_path: Path, embed: bool, meeting_id: int = 0) -> None:
    file_path = file_path.resolve(strict=True)
    if file_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File exceeds 2MB MVP safety limit.")
    text = read_text(file_path).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text or len(text) > MAX_TEXT_CHARS:
        raise ValueError("Document empty or exceeds 400,000 extracted characters.")
    parts = list(chunks_from_text(text))
    if not parts:
        raise ValueError("Document has no readable text.")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source_name = file_path.name
    vector_bytes = embed_texts([part[2] for part in parts]) if embed else [None] * len(parts)

    conn = open_admin_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DB_NAME()")
        if cur.fetchone()[0] != TEST_DB:
            raise RuntimeError("Wrong target database.")
        if meeting_id < 0:
            raise ValueError("meeting_id cannot be negative.")
        if meeting_id:
            cur.execute(
                "SELECT 1 FROM MTG.Meeting WHERE MeetingID=? AND MeetingNo LIKE N'SIM-MTG-A-%'",
                meeting_id,
            )
            if cur.fetchone() is None:
                raise ValueError("Related MeetingID is not a synthetic meeting in the test DB.")
        cur.execute(
            "SELECT TOP(1) Sha256,VersionNo FROM AI.Document WITH (UPDLOCK,HOLDLOCK) "
            "WHERE OriginalFileName=? AND IsCurrent=1 ORDER BY VersionNo DESC",
            source_name,
        )
        current = cur.fetchone()
        if current and current[0] == sha and (not embed):
            print(f"UNCHANGED: {source_name}, active version {current[1]}")
            conn.rollback()
            return
        cur.execute(
            "SELECT COALESCE(MAX(VersionNo),0) FROM AI.Document WITH (UPDLOCK,HOLDLOCK) "
            "WHERE OriginalFileName=?",
            source_name,
        )
        version = int(cur.fetchone()[0]) + 1
        cur.execute(
            "UPDATE AI.Document SET IsCurrent=0 WHERE OriginalFileName=? AND IsCurrent=1",
            source_name,
        )
        cur.execute(
            """
            INSERT AI.Document(OriginalFileName,Title,FileType,Sha256,VersionNo,
                                    IsCurrent,IsSynthetic,RelatedMeetingID,CharCount)
            OUTPUT inserted.DocumentID
            VALUES (?,?,?,?,?,1,1,?,?)
            """,
            source_name, file_path.stem[:300], file_path.suffix.lower().lstrip("."),
            sha, version, meeting_id or None, len(text),
        )
        doc_id = int(cur.fetchone()[0])
        for index, ((start, end, body), vector) in enumerate(zip(parts, vector_bytes), 1):
            if vector is None:
                cur.execute(
                    """
                    INSERT AI.DocumentChunk(DocumentID,ChunkNo,StartChar,EndChar,ChunkText)
                    VALUES (?,?,?,?,?)
                    """,
                    doc_id, index, start, end, body,
                )
            else:
                cur.execute(
                    """
                    INSERT AI.DocumentChunk(DocumentID,ChunkNo,StartChar,EndChar,ChunkText,
                                                 Embedding,EmbeddingModel,EmbeddingDimensions)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    doc_id, index, start, end, body,
                    pyodbc.Binary(vector), EMBED_MODEL, len(vector) // 4,
                )
        conn.commit()
        print(f"IMPORTED: {source_name} | version={version} | document_id={doc_id} "
              f"| chunks={len(parts)} | embeddings={'on' if embed else 'off'}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import SYNTHETIC test documents only.")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--synthetic", action="store_true",
                        help="Confirm the file contains fictional data approved for testing.")
    parser.add_argument("--meeting-id", type=int, default=0,
                        help="Optional verified SIM-MTG-A MeetingID to link this fictional document.")
    parser.add_argument("--embed", action="store_true",
                        help="Send chunks to OpenAI embeddings API for semantic search.")
    args = parser.parse_args()
    if not args.synthetic:
        parser.error("Add --synthetic ONLY for approved fictional test documents.")
    ingest(args.file, args.embed, args.meeting_id)
