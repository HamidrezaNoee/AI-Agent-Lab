"""REAL SQL / real API query integration test — synthetic fixture only.

No HTTP server, NO model API, NO real identity provider, and NO production DB.
Authentication dependency is overridden ONLY INSIDE THIS LOCAL TEST HARNESS.
DO NOT copy the override into commercial/api.py or run this as a web service.
"""
from contextlib import contextmanager
import os
import sys
from uuid import UUID

from fastapi.testclient import TestClient

from commercial.api import app, _authenticated_principal
from commercial.security import Principal
from commercial.sql_store import scoped_connection

A = UUID("11111111-1111-4111-8111-111111111111")
B = UUID("22222222-2222-4222-8222-222222222222")
A_DOC = "33333333-3333-4333-8333-333333333331"
B_DOC = "44444444-4444-4444-8444-444444444441"


def check(condition: bool, label: str):
    if not condition:
        raise AssertionError(f"FAIL: {label}")
    print(f"PASS: {label}")


@contextmanager
def as_principal(principal: Principal):
    # The API application is never served or modified; override is confined
    # to this in-process TestClient context for synthetic integration checks.
    app.dependency_overrides[_authenticated_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def main():
    if os.getenv("RUN_COMMERCIAL_SQL_INTEGRATION") != "LAB_ONLY_NO_SERVER":
        raise SystemExit("Set RUN_COMMERCIAL_SQL_INTEGRATION=LAB_ONLY_NO_SERVER explicitly.")
    if os.getenv("COMMERCIAL_MODE") != "lab" or (
        os.getenv("COMMERCIAL_SQL_DATABASE") != "EnterpriseProcess2_AI_Test"
    ):
        raise SystemExit("Only the isolated synthetic lab DB is allowed.")
    if os.getenv("COMMERCIAL_SQL_USER", "").lower() != "ai_commercialreader":
        raise SystemExit("Use the separate AI_CommercialReader SQL login, not the DBA.")
    if os.getenv("COMMERCIAL_CHAT_ENABLED") == "1":
        raise SystemExit("Set COMMERCIAL_CHAT_ENABLED=0. This test MUST NOT call a model.")

    alice = Principal(A, "lab-alice")
    bob = Principal(A, "lab-bob")
    carol = Principal(B, "lab-carol")

    with scoped_connection(alice) as con:
        cursor = con.cursor()
        cursor.execute(
            """
            SELECT ORIGINAL_LOGIN(), DB_NAME(), ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0),
                   ISNULL(IS_MEMBER(N'db_owner'),0),
                   HAS_PERMS_BY_NAME(N'AgentProduct.Tenant',N'OBJECT',N'INSERT'),
                   HAS_PERMS_BY_NAME(N'MTG.Meeting',N'OBJECT',N'SELECT')
            """
        )
        login, db, sysadmin, owner, write_tenant, read_legacy = cursor.fetchone()
        check(str(login).lower() == "ai_commercialreader",
              "DB connection uses separate commercial SQL login")
        check(db == "EnterpriseProcess2_AI_Test" and sysadmin == 0 and owner == 0,
              "DB is isolated and SQL account has no admin role")
        check(write_tenant == 0 and read_legacy == 0,
              "SQL account cannot insert tenants or read unscoped MTG records")

    with as_principal(alice) as client:
        me = client.get("/v1/me")
        check(me.status_code == 200 and me.json()["role"] == "Viewer",
              "Alice has active synthetic membership and subscription")
        meetings = client.get("/v1/meetings")
        # Once optional fixture 16 is installed, Alice also has 100 additional
        # EXPLICIT meeting grants. The endpoint returns the 20 newest only.
        alice_meeting_ids = [m["meeting_id"] for m in meetings.json()["meetings"]]
        check(meetings.status_code == 200 and alice_meeting_ids
              and all(mid == 900001 or 910001 <= mid <= 910100
                      for mid in alice_meeting_ids)
              and (900001 in alice_meeting_ids or 910100 in alice_meeting_ids),
              "Alice sees only her explicitly granted A-001 / optional 100-case meetings")
        docs = client.get("/v1/knowledge/search", params={"q": "گمرک"})
        check(docs.status_code == 200, "Alice document search succeeds")
        ids = {d["document_id"] for d in docs.json()["matches"]}
        check(A_DOC in ids and B_DOC not in ids
              and "33333333-3333-4333-8333-333333333332" not in ids,
              "Alice gets her document but never Bob/Carol documents")
        preview = client.post("/v1/chat/preview", json={
            "question": "گمرک و شماره شاسی", "meeting_id": 900001})
        items = preview.json().get("evidence", [])
        check(preview.status_code == 200
              and preview.json()["requested_meeting_accessible"] is True
              and any(item["kind"] == "meeting" for item in items)
              and all(item.get("document_id") != B_DOC for item in items),
              "Alice preview contains granted, meeting-scoped evidence")
        denied = client.post("/v1/chat/preview", json={
            "question": "بودجه و گمرک", "meeting_id": 900002})
        check(denied.status_code == 200
              and denied.json()["requested_meeting_accessible"] is False
              and not any(item["kind"] == "meeting" for item in denied.json()["evidence"]),
              "Alice cannot see Bob's meeting via preview")
        disabled = client.post("/v1/chat/answer", json={
            "question": "گمرک و شماره شاسی", "meeting_id": 900001})
        check(disabled.status_code == 503,
              "External-model chat is disabled for real-SQL integration test")

    with as_principal(bob) as client:
        meetings = client.get("/v1/meetings")
        check(meetings.status_code == 200
              and [m["meeting_id"] for m in meetings.json()["meetings"]] == [900002],
              "Bob sees only his granted A-002 meeting")
        docs = client.get("/v1/knowledge/search", params={"q": "گمرک"})
        ids = {d["document_id"] for d in docs.json()["matches"]}
        check(docs.status_code == 200 and A_DOC not in ids and B_DOC not in ids,
              "Bob cannot retrieve Alice/Carol documents even on keyword match")

    with as_principal(carol) as client:
        meetings = client.get("/v1/meetings")
        check(meetings.status_code == 200
              and [m["meeting_id"] for m in meetings.json()["meetings"]] == [900003],
              "Carol sees only tenant B meeting")
        docs = client.get("/v1/knowledge/search", params={"q": "گمرک"})
        ids = {d["document_id"] for d in docs.json()["matches"]}
        check(docs.status_code == 200 and B_DOC in ids and A_DOC not in ids,
              "Carol sees only tenant B's permitted document")

    for principal in (Principal(A, "lab-carol"), Principal(B, "lab-alice"),
                      Principal(A, "lab-unknown")):
        with as_principal(principal) as client:
            resp = client.get("/v1/meetings")
            check(resp.status_code == 403,
                  f"Unknown/cross-tenant membership denied for {principal.subject} / {principal.tenant_id}")
    print("PASS: REAL SQL + in-process API ACL integration completed (NO OIDC/LLM test).")


if __name__ == "__main__":
    main()
