# Commercial Agent | Milestone 1–2: tenant identity + per-user ACL (LAB ONLY)

**Current status: security + evidence-retrieval foundation / prototype, NOT a production-ready or sellable AI service.**
The existing `06_meeting_ai_agent.py` and `knowledge_tools.py` remain synthetic research tools; **do not expose them directly to customers**. Their shared SQL login is NOT a user-by-user authorization system.

## Repository deliverables in this milestone

- `commercial/security.py`: validate a real IdP-signed RS256 JWT against an ADMIN-CONFIGURED HTTPS issuer, audience and JWKS endpoint; reject bad signature, issuer, audience, lifetime, empty/invalid tenant and missing bearer tokens. The `tenant_id` must be a trusted claim issued by the IdP. A request header or a field in the user's question is never accepted as tenant identity.
- `commercial/api.py`: authenticated `GET /v1/me` and `GET /v1/meetings` skeleton; zero unfiltered SQL endpoints; `POST /v1/chat/preview` for explicitly authorized *evidence only*; no external model completion endpoint at this stage.
- `commercial/sql_store.py`: each request creates a NEW SQL connection, sets `AgentTenantID` SQL session context, checks the database's active membership + active tenant + unexpired subscription, and queries a tenant-scoped meeting index. The commercial SQL user MUST be separate from `AI_MeetingAgent`.
- `commercial/sql/01_tenant_boundary_TEST_ONLY.sql`: isolated tenant, meeting-index, document-index, chunk, subscription and audit contracts with SQL Server row-level security (RLS).
- `commercial/sql/03_membership_usage_TEST_ONLY.sql`: per-tenant memberships and token usage storage contracts.
- `commercial/sql/02_test_tenant_isolation.sql`: rollback-only SQL smoke test for tenant A/B and missing tenant context; test rows do not persist.
- `commercial/sql/04_reader_permissions_TEST_ONLY.sql`: least-privilege SELECT grants for a separately provisioned login and explicit DENY on the original unscoped `MTG` and `AI` lab schemas.
- `commercial/tests`: offline JWT/API access-gate unit tests.

**Important limitations:** The gateway currently reads only `AgentProduct.MeetingIndex` test rows, not real ProcessMaker sessions. No production document import, LLM chat completion, token metering enforcement, billing, customer onboarding, audit writer, rate limiting, or real license enforcement has been shipped. Meeting/document per-user ACL is implemented at the new API query layer, NOT as a separate per-user database RLS policy. Do not describe the `Subscription` table as a billing integration: it is only an admission flag/date. Do not treat the JWT `tenant_id` claim as sufficient: membership is checked in SQL on every request.

## Development safety

Run SQL scripts ONLY on `EnterpriseProcess2_AI_Test` using a test DBA. Scripts do not modify `MTG` tables. Never run the synthetic lab scripts on operational `EnterpriseProcess2`. In production use a **separate commercial database** and migrate the tested schema after a security review. RLS limits data returned when session context is correct; an attacker with direct access to the commercial SQL login could set that context themselves. Restrict that login to the internal API host/network and never expose SQL credentials to a browser, WordPress plugin or an untrusted client.

## Runnable checks on the existing Windows workstation

First exit any running command-line Agent by typing `exit`. From PowerShell:

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
git -C $repo pull --ff-only origin main
cd $repo
python -m pip install -r .\commercial\requirements.txt
python -m py_compile .\commercial\security.py .\commercial\sql_store.py .\commercial\api.py
python -m unittest discover -s commercial\tests -v
```

Unit tests are offline and do NOT connect to SQL, OpenAI or a live identity provider. **The test suite is committed but has NOT been executed on the user's computer yet.**

In SSMS, Windows Authentication, instance `.\SQLSERVER2022`, run IN THIS ORDER:

```
commercial/sql/01_tenant_boundary_TEST_ONLY.sql
commercial/sql/03_membership_usage_TEST_ONLY.sql
commercial/sql/02_test_tenant_isolation.sql
commercial/sql/05_resource_acl_TEST_ONLY.sql
commercial/sql/06_test_resource_acl.sql
```

Expected message from the third script:

```
PASS: tenant A, tenant B, and missing-context SELECT isolation.\nPASS: same-tenant user meeting/document grants and missing-context isolation.
```

Both SQL isolation tests run inside transactions and roll back all fictional tenant/resource test rows. After it passes, create the NEW server login `AI_CommercialReader` in SSMS with a separately generated password; do not add it to any administrative or bulk-reading role. Then execute `commercial/sql/04_reader_permissions_TEST_ONLY.sql` (script 05 can be rerun afterward to grant read-only access to new grant/document tables). Do not type passwords into chat or commit them to Git.

## Gateway is deliberately not ready to start without a real trusted IdP

Only after your identity provider is configured to issue **signed RS256 ACCESS tokens** with verified `iss`, `aud`, `sub`, `iat`, `exp` and trusted `tenant_id`, and its public JWKS is available over HTTPS, set:

```powershell
$env:COMMERCIAL_OIDC_ISSUER = "https://YOUR-REAL-IDP/issuer/"
$env:COMMERCIAL_OIDC_AUDIENCE = "YOUR-REGISTERED-API-AUDIENCE"
$env:COMMERCIAL_OIDC_JWKS_URL = "https://YOUR-REAL-IDP/.well-known/jwks.json"
$env:COMMERCIAL_MODE = "lab"
$env:COMMERCIAL_SQL_SERVER = ".\SQLSERVER2022"
$env:COMMERCIAL_SQL_DATABASE = "EnterpriseProcess2_AI_Test"
$env:COMMERCIAL_SQL_USER = "AI_CommercialReader"
$pw = Read-Host "Commercial SQL password" -AsSecureString
$env:COMMERCIAL_SQL_PASSWORD = [System.Net.NetworkCredential]::new("", $pw).Password
python -m uvicorn commercial.api:app --host 127.0.0.1 --port 8088
```

Placeholders are intentionally NOT real provider settings. Without a configured provider, protected routes fail closed. `GET /health` is a process-health endpoint only, not an authenticated application-readiness check. Even when /v1/me succeeds, /v1/meetings is empty until a tenant's synthetic `MeetingIndex` data has been provisioned; DO NOT seed the production tables automatically from the old, unscoped `MTG` records.

## Next engineering milestones before any sale

1. **Identity & ACL:** configure a real organization identity provider or an audited first-party .NET 8 Identity service, enforce per-user meeting/document ACL *before* retrieval, verify membership revocation and role changes, add SSO/MFA and invite/onboarding.
2. **Real product data and hybrid retrieval:** per-tenant ETL from approved ProcessMaker/SQL sources, versioned document ingestion with permission metadata, scalable indexed vector+full-text retrieval, evidence/citation validator, no leakage across tenants.
3. **Reliable agent & workflows:** orchestrator that uses authorized SQL and authorized RAG tools; read-only by default; draft actions + explicit approval before controlled write, idempotency and audit trail.
4. **Sales/operations:** signed licenses, plan/seat limits, *atomic* token/request quotas, payment-webhook verification, cost and usage metering, backup/DR, observability, disaster recovery, security review, and documented data-processing agreements.

A WordPress/WooCommerce frontend can later sell subscriptions and display the chat UI, but it MUST NOT hold SQL credentials or be the authorization authority for tenant data. An ASP.NET Core 8 gateway remains a natural integration option for the user's existing .NET stack.

## Milestone 2: query-layer access control and cited evidence preview

- `commercial/sql/05_resource_acl_TEST_ONLY.sql` creates `MeetingGrant` and `DocumentGrant` tables with FK-scoped tenant/user membership; no grant = no resource in normal API response. The SQL tenant RLS policy is a second, independent filter.
- `commercial/sql/06_test_resource_acl.sql` checks two users of ONE fictional tenant with different meeting/document grants and missing SQL tenant context. It rolls back test rows.
- `GET /v1/meetings` now requires explicit `MeetingGrant` for the verified JWT subject.
- `GET /v1/knowledge/search?q=...` retrieves a bounded set of fragments only after joining `DocumentGrant` for the subject and selecting the active document version; this lab search is **lexical only**.
- `POST /v1/chat/preview` accepts `{"question":"...","meeting_id":71}` and returns up to six attributed, authorized evidence items, **not a synthesized answer**. Request bodies reject `tenant_id`, `subject`, and other extra fields. `meeting_id` must refer to a record granted to the verified principal or its existence is not disclosed.
- `commercial/tests/test_acl_preview.py` has offline tests of grant-bound SQL query construction and API preview behavior. Run `python -m unittest discover -s commercial/tests -v` again after pulling.
- Access to *all* a tenant's documents using the commercial SQL login remains technically possible outside the API because per-user grants are enforced in application SQL JOINs. Keep the SQL login private to a trusted API host and use database stored-procedure/policy hardening in the next milestone. **Do not expose this MVP over the internet.**

This step does **not** automatically import data from the original `MTG` or `AI` tables into the commercial index. The evidence preview remains empty until test tenants, subject memberships, explicit resource grants and fictional indexed data are deliberately provisioned. End-to-end integration with a real identity provider, SQL instance and model must still be tested.


## Milestone 3: gated answer, scoped document context, atomic request quotas (TEST ONLY)

The new endpoint `POST /v1/chat/answer` is **disabled by default**. It accepts the same strictly validated request as the evidence preview. It first verifies the signed OIDC identity and current DB membership/subscription, then retrieves up to SIX explicitly granted, bounded evidence items. With a specified meeting ID, ungranted meetings get HTTP 404 and documents linked to other meetings are excluded. Tenant-wide documents (`RelatedMeetingID=NULL`) can be referenced as **general guidance only**, never as an attachment or decision of a specific meeting.

If evidence is absent, the endpoint returns `no_authorized_evidence` without calling the model or charging a request. Otherwise it calls the SQL stored procedure `ReserveChatRequest` **before** the external model request. The procedure serializes reservations per tenant using `sp_getapplock` and atomically checks the tenant's ACTIVE membership, unexpired subscription and `MonthlyRequestLimit` against the number of requests reserved since the beginning of the current UTC month. A server-generated RequestID cannot be reused. Failed model requests and invalid model responses still consume one request slot, because external costs may have occurred. After the model call, `FinalizeChatRequest` stores state and available input/output token counts; unknown token counts remain SQL NULL, not a fabricated zero. The current limit is **number of requests per UTC calendar month**, NOT a monetary or token budget. Billing, reconciliation, pricing and retry/refund policy are NOT implemented.

The LLM receives **only** the authorized question and retrieved evidence. It has NO SQL, external tools, ProcessMaker write actions or arbitrary retrieval access. The requested output is bounded structured claims, each with a source ID. The application checks that every returned source ID belongs to the authorized evidence set before returning an answer. **A valid citation identifier does not prove that the claim is factually correct**; semantic evidence-grounding and retrieval quality still require human/automated evaluation. The lab supports only fictional data. Do not pass real company data or credentials to the model.

### Installation and tests

Before starting, ensure the PREVIOUS SQL isolation tests `02_test_tenant_isolation.sql` and `06_test_resource_acl.sql` have passed; if not, run the existing baseline/ACL scripts first. Run these NEW scripts in **SSMS on EnterpriseProcess2_AI_Test as test DBA**, in order:

```
commercial/sql/09_document_context_TEST_ONLY.sql
commercial/sql/07_chat_quota_TEST_ONLY.sql
commercial/sql/08_test_chat_quota.sql
```

Expected SQL output (only after executing on your test server):

```
PASS: chat quota reserve and usage finalization (all fictional data rolled back).
PASS: second chat request rejected at monthly quota (all fictional data rolled back).
PASS: missing SQL tenant context rejected before quota reservation.
```

The first two migrations are additive/test-only. If `AI_CommercialReader` does not exist yet, follow the baseline `04_reader_permissions_TEST_ONLY.sql` instructions to create a **separate least-privilege SQL login** (never share its password). Then rerun `05_resource_acl_TEST_ONLY.sql` and `07_chat_quota_TEST_ONLY.sql` so new object permissions are granted to that login. The original `AI_MeetingAgent` account is never used by the commercial endpoints.

Update and test Python in the SAME activated virtual environment:

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
git -C $repo pull --ff-only origin main
cd $repo
python -m pip install -r .\commercial\requirements.txt
python -m py_compile .\commercial\security.py .\commercial\sql_store.py .\commercial\quota.py .\commercial\answer.py .\commercial\api.py
python -m unittest discover -s commercial\tests -v
```

The new tests are offline: all SQL and model calls are mocked. They DO NOT prove that the SQL migrations, model provider or external identity provider are working on the user's environment. Before *any* end-to-end chat test, provision a fictional tenant, a real test identity from an authorized IdP, an active test subscription, and explicit MeetingGrant/DocumentGrant records. Until that point, empty results or 403 responses are expected.

For a local test only, after the existing real OIDC configuration and commercial SQL configuration from this README are completed, an operator may enable the isolated endpoint with:

```powershell
$env:COMMERCIAL_MODE = "lab"
$env:COMMERCIAL_SQL_DATABASE = "EnterpriseProcess2_AI_Test"
$env:COMMERCIAL_CHAT_ENABLED = "1"
# OPENAI_API_KEY must already be configured securely for approved FICTIONAL data.
python -m uvicorn commercial.api:app --host 127.0.0.1 --port 8088
```

Do **not** set `COMMERCIAL_CHAT_ENABLED=1` on an internet-facing server. The endpoint is still a technical test: no audited production tenant onboarding, production database migration, independent penetration test, per-resource database-level user RLS, cost/billing reconciliation or actual ProcessMaker integration exists. HTTPS/TLS termination and a production-ready identity service are separate deployment tasks.

### Response example

```json
{
  "request_id": "server-generated-uuid",
  "answer": "یک ادعای مبتنی بر مدرک [MEETING:SIM-EXAMPLE]",
  "claims": [{"text":"یک ادعای مبتنی بر مدرک","source":"MEETING:SIM-EXAMPLE"}],
  "sources": ["MEETING:SIM-EXAMPLE"],
  "quota": {"used_this_month": 1, "monthly_limit": 100},
  "charged_request": true,
  "data_scope": "synthetic-authorized-commercial-evidence-only"
}
```

This is an **illustrative shape**, not an observed provider response. Real answers depend on test data, explicit ACLs and a valid IdP token.
