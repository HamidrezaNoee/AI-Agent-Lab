# -*- coding: utf-8 -*-
"""Read-only document retrieval tool for the synthetic Meeting AI prototype.

Reads AI.Document / AI.DocumentChunk only from EnterpriseProcess2_AI_Test.
A bounded Python cosine search over packed float32 embeddings supports SMALL
test collections, with a lexical fallback for chunks without embeddings.
For large corpora use a proper indexed vector/full-text retrieval service.
"""
import json
import math
import os
import re
from array import array
from contextlib import contextmanager

import pyodbc
from agents import function_tool

TEST_DB = "EnterpriseProcess2_AI_Test"
EMBED_MODEL = "text-embedding-3-small"
MAX_ACTIVE_CHUNKS = 5000
STOPWORDS = {
    "این", "آن", "برای", "چیست", "کدام", "چه", "چرا", "چطور", "است",
    "هست", "هستند", "شده", "شود", "کرده", "باید", "چند", "های",
    "درباره", "براساس", "طبق", "مربوط", "لطفا", "کن", "بگو",
    "the", "and", "for", "what", "which", "does", "with", "from",
}


@contextmanager
def _connection():
    if os.getenv("SQL_DATABASE") != TEST_DB:
        raise RuntimeError("Safety: wrong SQL_DATABASE for document retrieval.")
    server, user, password = (
        os.getenv("SQL_SERVER"), os.getenv("SQL_USER"), os.getenv("SQL_PASSWORD")
    )
    if not all((server, user, password)):
        raise RuntimeError("Set SQL_SERVER, SQL_USER, SQL_PASSWORD first.")
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={server};DATABASE={TEST_DB};UID={user};PWD={password};"
        "TrustServerCertificate=yes;",
        timeout=8,
    )
    try:
        yield conn
    finally:
        conn.close()


def _tokens(text):
    normalized = text.translate(str.maketrans({"ي": "ی", "ك": "ک", "‌": " "}))
    return [
        token.lower() for token in
        re.findall(r"[\u0600-\u06ffA-Za-z0-9]{3,}", normalized)
        if token.lower() not in STOPWORDS
    ][:20]


def _cosine_from_bytes(vector_bytes, query_vector):
    if not vector_bytes or len(vector_bytes) != len(query_vector) * 4:
        return 0.0
    values = array("f")
    values.frombytes(bytes(vector_bytes))
    magnitude = math.sqrt(sum(value * value for value in values))
    query_magnitude = math.sqrt(sum(value * value for value in query_vector))
    if magnitude == 0.0 or query_magnitude == 0.0:
        return 0.0
    return sum(a * b for a, b in zip(values, query_vector)) / (magnitude * query_magnitude)


def retrieve_knowledge(query: str, limit: int = 5, meeting_id: int = 0):
    query = query.strip()[:400]
    if not query:
        return {"error": "Empty document question."}
    limit = min(max(int(limit), 1), 5)
    if meeting_id < 0:
        return {"error": "meeting_id cannot be negative"}
    with _connection() as conn:
        cursor = conn.cursor()
        if meeting_id:
            cursor.execute(
                "SELECT 1 FROM MTG.Meeting WHERE MeetingID=? AND MeetingNo LIKE N'SIM-MTG-A-%'",
                meeting_id,
            )
            if cursor.fetchone() is None:
                return {"error": "Synthetic meeting does not exist"}
        cursor.execute(
            """
            SELECT TOP (5001)
                d.DocumentID,d.OriginalFileName,d.Title,d.VersionNo,
                d.RelatedMeetingID,c.ChunkNo,c.StartChar,c.EndChar,
                c.ChunkText,c.Embedding,c.EmbeddingModel
            FROM AI.DocumentChunk c
            JOIN AI.Document d ON d.DocumentID=c.DocumentID
            WHERE d.IsCurrent=1 AND d.IsSynthetic=1
              AND (?=0 OR d.RelatedMeetingID IS NULL OR d.RelatedMeetingID=?)
            ORDER BY d.DocumentID,c.ChunkNo
            """,
            meeting_id, meeting_id,
        )
        rows = cursor.fetchall()
    if not rows:
        return {
            "kind": "SYNTHETIC_TEST_DOCUMENTS", "matches": [],
            "note": "No synthetic test documents have been imported yet.",
        }
    if len(rows) > MAX_ACTIVE_CHUNKS:
        return {
            "error": "Knowledge corpus exceeds the 5000-chunk MVP search limit. "
                     "No partial-corpus answer returned; deploy an indexed search backend."
        }
    query_vector = None
    if any(row[9] and row[10] == EMBED_MODEL for row in rows):
        if os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            query_vector = OpenAI().embeddings.create(
                model=EMBED_MODEL, input=query
            ).data[0].embedding
    tokens = _tokens(query)
    ranked = []
    for row in rows:
        doc_id, filename, title, version, linked_meeting_id, chunk_no, start, end, content, embedding, model = row
        searchable = (title + " " + content).translate(
            str.maketrans({"ي": "ی", "ك": "ک", "‌": " "})
        ).lower()
        hits = sum(min(searchable.count(term), 3) for term in set(tokens))
        semantic = (
            _cosine_from_bytes(embedding, query_vector)
            if query_vector is not None and model == EMBED_MODEL else 0.0
        )
        # Require evidence of relevance; score mixes semantic and lexical signals.
        if hits == 0 and semantic < 0.18:
            continue
        score = min(hits, 8) * 0.35 + max(semantic, 0.0) * 8.0
        ranked.append((score, {
            "citation": f"DOC:{doc_id}:v{version}:c{chunk_no}",
            "source_file": filename,
            "document_title": title,
            "document_id": doc_id,
            "document_version": version,
            "chunk_number": chunk_no,
            "start_character": start,
            "end_character": end,
            "related_meeting_id": linked_meeting_id,
            "passage": content,
            "retrieval": "hybrid" if query_vector is not None else "lexical",
        }))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return {
        "kind": "SYNTHETIC_TEST_DOCUMENTS",
        "active_chunks_searched": len(rows),
        "meeting_id_filter": meeting_id,
        "matches": [item[1] for item in ranked[:limit]],
        "source_policy": (
            "Cite exact DOC identifiers for document claims. "
            "Documents are fictional test inputs, not company policy."
        ),
    }


@function_tool
def search_knowledge_documents(question: str, meeting_id: int = 0) -> str:
    """Find cited passages in versioned synthetic Word/text documents.

    Use for document policies, guidelines, reasons, procedures and free-text
    facts, not for numerical meeting/action counts. Returns source file,
    version, chunk ID, character offsets and exact passage for attribution.
    """
    return json.dumps(retrieve_knowledge(question, meeting_id=meeting_id),
                      ensure_ascii=False, default=str)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python knowledge_tools.py 'your document question'")
    print(json.dumps(retrieve_knowledge(" ".join(sys.argv[1:])),
                     ensure_ascii=False, indent=2, default=str))
