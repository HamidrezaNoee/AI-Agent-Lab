# Commercial Agent | Milestones 1–3: identity, ACL, cited chat and request quotas (LAB ONLY)

**Current status: isolated commercial prototype with an optionally enabled cited chat endpoint; NOT a production-ready or sellable AI service.**
The existing `06_meeting_ai_agent.py` and `knowledge_tools.py` remain synthetic research tools; **do not expose them directly to customers**. Their shared SQL login is NOT a user-by-user authorization system.

## Repository deliverables in this milestone

- `commercial/security.py`: validate a real IdP-signed RS256 JWT against an ADMIN-CONFIGURED HTTPS issuer, audience and JWKS endpoint; reject bad signature, issuer, audience, lifetime, empty/invalid tenant and missing bearer tokens. The `tenant_id` must be a trusted claim issued by the IdP. A request header or a field in the user's question is never accepted as tenant identity.
- `commercial/api.py`: authenticated `GET /v1/me` and `GET /v1/meetings` skeleton; zero unfiltered SQL endpoints; `POST /v1/chat/preview` for authorized evidence only; optional lab-only `POST /v1/chat/answer` and narrow quota procedures are described in milestone 3 below.
- `commercial/sql_store.py`: each request creates a NEW SQL connection, sets `AgentTenantID` SQL session context, checks the database's active membership + active tenant + unexpired subscription, and queries a tenant-scoped meeting index. The commercial SQL user MUST be separate from `AI_MeetingAgent`.
- `commercial/sql/01_tenant_boundary_TEST_ONLY.sql`: isolated tenant, meeting-index, document-index, chunk, subscription and audit contracts with SQL Server row-level security (RLS).
- `commercial/sql/03_membership_usage_TEST_ONLY.sql`: per-tenant memberships and token usage storage contracts.
- `commercial/sql/02_test_tenant_isolation.sql`: rollback-only SQL smoke test for tenant A/B and missing tenant context; test rows do not persist.
- `commercial/sql/04_reader_permissions_TEST_ONLY.sql`: least-privilege SELECT grants for a separately provisioned login and explicit DENY on the original unscoped `MTG` and `AI` lab schemas.
- `commercial/tests`: offline JWT/API access-gate unit tests.

**Important limitations:** The gateway currently reads only `AgentProduct.MeetingIndex` test rows, not real ProcessMaker sessions. No production document import, production-certified AI chat, atomic TOKEN/cost budgets, billing, customer onboarding, audit writer, rate limiting, or real license enforcement has been shipped. The lab can reserve monthly REQUEST counts and record returned token usage; this is NOT commercial billing. Meeting/document per-user ACL is implemented at the new API query layer, NOT as a separate per-user database RLS policy. Do not describe the `Subscription` table as a billing integration: it is only an admission flag/date. Do not treat the JWT `tenant_id` claim as sufficient: membership is checked in SQL on every request.

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


## Recovery from SQL 57001 / 56801 / 56901 (missing AgentProduct schema)

If scripts 09, 07 and 08 report missing `AgentProduct` objects, **stop**: the base schema creation has not run successfully, is not visible to the SSMS login, or a wrong database/instance was selected. Python unit tests are mocked; they cannot create database tables. SQL Server Management Studio `GO` separates batches, so a `THROW` in an early batch of a migration does **not** guarantee that later batches will not execute. Never run all migrations together blindly. Use an ADMIN login against the synthetic test DB, NOT `AI_MeetingAgent`.

1. Run `commercial/sql/00_preflight_ADMIN_TEST_ONLY.sql` ALONE in SSMS and verify it prints PASS and names the expected database, server, and administrator login. If it reports 58002, reconnect with a TEST DB `db_owner` or server `sysadmin` account; do not grant admin privileges to the read-only agent.
2. Execute `01_tenant_boundary_TEST_ONLY.sql` ALONE, check Messages, then verify `SELECT SCHEMA_ID(N'AgentProduct'), OBJECT_ID(N'AgentProduct.DocumentIndex',N'U'), OBJECT_ID(N'AgentProduct.Tenant',N'U');` gives NON-NULL values in the same test database.
3. Execute `03_membership_usage_TEST_ONLY.sql` ALONE, then `05_resource_acl_TEST_ONLY.sql` ALONE. Stop at the first error.
4. Execute `09_document_context_TEST_ONLY.sql` ALONE, then `07_chat_quota_TEST_ONLY.sql` ALONE. Check all object IDs returned by each.
5. Run `10_verify_schema_ADMIN_TEST_ONLY.sql` ALONE. Only when this prints PASS, run the rollback-only tests `02_test_tenant_isolation.sql`, `06_test_resource_acl.sql`, and `08_test_chat_quota.sql` individually. SQL tests are not considered passed until their actual PASS messages are observed.
6. If a schema object remains missing, do NOT drop the synthetic database or rerun seed/import scripts; share only the preflight diagnostic (no passwords) and the FIRST SQL error from the failed migration.

IMPORTANT: The original README's examples assume that the SQL base migration 01 was executed successfully. An SSMS error 57001 in 09 is NOT fixed by rerunning 09 before creating `AgentProduct.DocumentIndex`. Before enabling lab chat, the commercial SQL reader needs separate least-privilege login, grants from 04, 05 and 07, a real trusted OIDC test identity, tenant-scoped synthetic fixtures and verified ACL tests.


## Milestone 4: real SQL / API ACL integration WITHOUT a web server or OpenAI

The user confirmed that synthetic SQL tests for cross-tenant isolation, per-user grants and quota all print their expected PASS messages. The next target is to prove that an independently provisioned SQL login can read the *correct fictional records through the actual FastAPI query functions*. This still is NOT an end-to-end OIDC or live model-provider test.

**1. Provision the dedicated LAB SQL login once.** In SSMS, connect to `.\\SQLSERVER2022` as the TEST administrator, expand `Security > Logins > New Login` and create `AI_CommercialReader` using SQL Server Authentication and a strong unique locally held password. Set its default database to `EnterpriseProcess2_AI_Test`; under User Mapping, select **only** that test database; do NOT grant `sysadmin`, `db_owner`, `db_datareader`, `db_datawriter`, or any access to the operational ProcessMaker DB. If the server is configured for Windows-only authentication, a SQL Authentication login will not work until an administrator explicitly enables Mixed Mode on the *test instance*, and an instance restart may be necessary. Never enable it on a production instance just to run this demo. Store credentials securely, NOT in Git or this conversation. Do NOT reuse `AI_MeetingAgent`.

**2. As TEST admin in SSMS, run separately:** `commercial/sql/04_reader_permissions_TEST_ONLY.sql`, then `05_resource_acl_TEST_ONLY.sql`, then `07_chat_quota_TEST_ONLY.sql` (the latter two can be rerun to grant access to objects created before the login). After that, run `13_verify_reader_permissions_ADMIN_TEST_ONLY.sql`. It impersonates the dedicated reader WITHOUT needing to know its password and checks that it has narrow read/execute permissions but no admin, schema-wide MTG/AI read, or direct tenant INSERT. Do not proceed if the permission audit fails.

**3. As TEST admin in SSMS, run `12_seed_api_fixtures_TEST_ONLY.sql` ONCE.** It commits deliberately fictional records only into `AgentProduct` of `EnterpriseProcess2_AI_Test`: two tenants, lab-alice / lab-bob in A, lab-carol in B, three meetings, four documents including one tenant-wide fictional guide, per-user grants and 30-day test subscriptions. These seed records intentionally PERSIST for API integration (unlike earlier SQL rollback tests). A second execution safely refuses to overwrite fixed fixture IDs; do NOT drop or recreate existing MTG meeting data.

**4. Run the real-SQL/in-process HTTP route test from PowerShell:**

```powershell
$repo = "D:\\A Project\\17 meeting ai agent\\Azure\\AI-Agent-Lab-GitHub"
git -C $repo pull --ff-only origin main
cd $repo
python -m pip install -r .\\commercial\\requirements.txt
python -m pip check
$env:COMMERCIAL_MODE = "lab"
$env:COMMERCIAL_SQL_SERVER = ".\\SQLSERVER2022"
$env:COMMERCIAL_SQL_DATABASE = "EnterpriseProcess2_AI_Test"
$env:COMMERCIAL_SQL_USER = "AI_CommercialReader"
$securePassword = Read-Host "LAB Commercial SQL password" -AsSecureString
$env:COMMERCIAL_SQL_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
$env:COMMERCIAL_CHAT_ENABLED = "0"
$env:RUN_COMMERCIAL_SQL_INTEGRATION = "LAB_ONLY_NO_SERVER"
python -m commercial.integration_sql_lab
```

**Safety scope:** `integration_sql_lab.py` uses FastAPI's `TestClient` and a local authentication dependency override *inside that one test process* to exercise the actual read paths with fictional principals. It does **NOT** start Uvicorn or bypass authentication in the application, and it does not call OpenAI. Do not copy its dependency override into the API or make it available as an HTTP endpoint. The test checks cross-tenant and within-tenant grant boundaries using the REAL SQL Server account and reports PASS/FAIL lines. A successful result proves only the listed test scenarios, not overall penetration-tested production security. Never set `COMMERCIAL_CHAT_ENABLED=1` during this test.

Once it completes, remove the SQL password from the current PowerShell process with `Remove-Item Env:COMMERCIAL_SQL_PASSWORD -ErrorAction SilentlyContinue` when no further local tests need it. The next distinct milestone is a real configured IdP/JWKS and signed access-token integration, **not** a hardcoded production user or anonymous chat endpoint.


## Milestone 5: in-process signed JWT + real SQL integration (ephemeral LOCAL test signer)

After the user's real-SQL/ACL integration test printed all PASS lines, the next lab check is `commercial/integration_jwt_sql_lab.py`. It exercises the actual FastAPI Authorization header and `_authenticated_principal` (unlike the prior fixture test, it does NOT override a FastAPI dependency), verifies RS256 signatures/issuer/audience/expiry and queries the REAL `EnterpriseProcess2_AI_Test` SQL database with the existing `AI_CommercialReader` account. It generates an RSA private key **in memory** and injects only its public-key resolver within that in-process test via a narrow mock of `commercial.api._verifier`. NO real identity provider or public JWKS endpoint is configured by this test; this is a local signer/verification integration check, NOT production SSO/IdP validation. Do not copy its mock/key injection into `commercial/api.py`, expose its test harness as an endpoint, or run Uvicorn with local test signing keys.

Prerequisites: prior SQL fixtures 12 committed; separate reader grants 04/05/07 and SQL account verified by script 13; `commercial.integration_sql_lab` printed all PASS. Run from the repo root in the SAME PowerShell window with the existing lab-only environment variables and secret SQL password, or re-enter the password securely if this is a new shell:

```powershell
$repo = "D:\\A Project\\17 meeting ai agent\\Azure\\AI-Agent-Lab-GitHub"
$python = "D:\\A Project\\17 meeting ai agent\\Azure\\AI-Agent-Lab\\.venv\\Scripts\\python.exe"
git -C $repo pull --ff-only origin main
cd $repo
$env:COMMERCIAL_MODE = "lab"
$env:COMMERCIAL_SQL_SERVER = "DESKTOP-GJI3D8L\\SQLSERVER2022"
$env:COMMERCIAL_SQL_DATABASE = "EnterpriseProcess2_AI_Test"
$env:COMMERCIAL_SQL_USER = "AI_CommercialReader"
$env:COMMERCIAL_CHAT_ENABLED = "0"
$env:RUN_COMMERCIAL_SQL_INTEGRATION = "LAB_ONLY_NO_SERVER"
# Only in a NEW PowerShell window: securely prompt for the dedicated SQL account password.
# $securePassword = Read-Host "LAB Commercial SQL password" -AsSecureString
# $env:COMMERCIAL_SQL_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
& $python -m commercial.integration_jwt_sql_lab
```

This test does not invoke OpenAI or charge chat quota. No synthetic SQL rows are created. An actual external HTTPS IdP, JWKS key rotation, login/onboarding and a real issued access token are a SEPARATE remaining milestone.


## Milestone 6: modular optional features + 100 automotive scenarios (LAB ONLY)

This milestone adds the requested separately sellable switches, but **does NOT implement any real payment checkout, bank verification, commercial license issuer, production OAuth/OIDC, continuous reminder delivery, speech recognition/voice synthesis, or ProcessMaker write API**. The earlier signed-JWT test used an ephemeral LOCAL signer, not an external IdP. Do not market the prototype as already ready to take production customer payments or process real meeting records.

**Modules and SKU boundaries:**
- M1 / assistant (core): existing ACL-filtered text evidence and opt-in lab-only cited answer. The base assistant is available only to a verified user with ACTIVE tenant membership/subscription; live LLM remains independently disabled unless the operator explicitly and safely enables fictional LAB chat.
- M2 / secretary (optional): `GET /v1/secretary/preparation/{meeting_id}` returns a read-only, human-reviewable agenda, evidence and current synthetic actions for a specifically granted meeting; it DOES NOT transcribe audio, extract actual minutes, or write ProcessMaker.
- M3 / analytics (optional): `GET /v1/analytics/status-overview` counts all grant-visible fictional meetings by status AND all authorized indexed actions (total/open/overdue). It does NOT invent financial KPIs or claim to infer performance from missing data.
- M4 / monitoring (optional): `GET /v1/monitoring/overdue` shows up to 50 open overdue synthetic actions in explicitly granted meetings. It is a request-time preview, NOT an autonomous background job or SMS/email reminder.

**Purchased-vs-on model:** `AgentProduct.TenantModule` has tenant ID, optional module code 2/3/4, `IsLicensed`, `LicenseUntilUtc`, and `IsEnabled`. Both license validity and enabled state are checked on every protected module request AFTER JWT validation and SQL membership/subscription. Missing, expired, unpurchased or disabled means HTTP 403; module visibility in the UI is NOT the security boundary. No one can turn on a module merely by sending `enabled=true`. An active tenant `Owner`/`Admin` can pause/resume only already-licensed modules via `PUT /v1/admin/modules/{module_code}` with `{"enabled":true|false}`; the SQL procedure rechecks the database role/license and appends an AuditEvent. Only a controlled operator/verified fulfillment process, NOT this API, is authorized to issue or renew real module licenses. Test `17` simulates fictional purchases and is NEVER a payment proof. `GET /v1/modules` returns statuses for the current verified tenant; it never accepts a client-supplied tenant ID.

**Optional UI sample:** `commercial/web/ModuleSettings.tsx` is a Persian React administrative toggle component, ready to integrate into a properly authenticated same-origin host using a supplied `authorizedFetch` function. This repository DOES NOT yet contain the hosted customer UI or actual OIDC sign-in flow. Never paste token or SQL credentials into the UI or copy local signer mocks to a web server.

**100 complete synthetic cases:** `commercial/datasets/100_automotive_meeting_scenarios_FA.json` contains precisely 100 distinct Persian automotive meeting topics across ten domains, each with initial request, preparation/agenda, meeting discussion, resolution, three owned/due actions with progress/evidence/secretary review, risk, follow-up and next-meeting prompt (300 fictional actions in total). The full lifecycle fields remain in the JSON. SQL file `16_seed_100_automotive_TEST_ONLY.sql` imports only the 100 *meeting-index projections* and 300 *action-index projections* into fictional tenant A after the structural migrations; it does NOT import all JSON lifecycle narrative into SQL or modify original MTG records.

### One-time installation of the NEW optional modules in the existing isolated LAB

Prerequisites already verified in previous user runs: synthetic fixtures `12` installed; earlier commercial schema, per-user grants, quotas and dedicated limited reader are present; `commercial.integration_sql_lab` and `commercial.integration_jwt_sql_lab` returned PASS. **Do not rerun seed `12`, do not wipe existing database or discard user's edited root `sql/` files.**

In a **NEW SSMS Query** as test SQL sysadmin connected to `DESKTOP-GJI3D8L\\SQLSERVER2022`, execute each NEW file separately, stopping on the first SQL error:

```text
commercial/sql/14_modular_entitlements_TEST_ONLY.sql
commercial/sql/15_action_index_TEST_ONLY.sql
commercial/sql/16_seed_100_automotive_TEST_ONLY.sql     # ONCE: persists 100 + 300 fictional indexes
commercial/sql/17_seed_test_module_licenses_TEST_ONLY.sql  # ONCE: fictional tenant A only
commercial/sql/18_verify_modules_dataset_ADMIN_TEST_ONLY.sql  # READ ONLY
```

`16` and `17` are persistence-only synthetic fixtures and intentionally refuse a second execution so they do not overwrite test history. The expected final `18` output contains three PASS lines for 100 meeting indexes/300 action indexes, test license/administrator fixture, and tenant RLS protection. Running `14` alone does not license anything. Tenant B remains unlicensed. Seed `17` prepares tenant A M2=ON, M3=OFF but licensed, M4=ON, and creates `lab-admin` with Admin membership and two explicit meeting grants.

### Python checks after SQL script 18 passes

Run these in the **same local PowerShell window** as prior working integration tests, from the repo root. Use the virtualenv executable rather than global `python` (the latter caused `No module named fastapi` on the user's machine).

```powershell
$repo = "D:\\A Project\\17 meeting ai agent\\Azure\\AI-Agent-Lab-GitHub"
$python = "D:\\A Project\\17 meeting ai agent\\Azure\\AI-Agent-Lab\\.venv\\Scripts\\python.exe"
git -C $repo pull --ff-only origin main
cd $repo
& $python -m pip check
& $python -m unittest discover -s commercial/tests -v
$env:COMMERCIAL_MODE = "lab"
$env:COMMERCIAL_SQL_SERVER = "DESKTOP-GJI3D8L\\SQLSERVER2022"
$env:COMMERCIAL_SQL_DATABASE = "EnterpriseProcess2_AI_Test"
$env:COMMERCIAL_SQL_USER = "AI_CommercialReader"
$env:COMMERCIAL_CHAT_ENABLED = "0"
$env:RUN_COMMERCIAL_SQL_INTEGRATION = "LAB_ONLY_NO_SERVER"
# Only when the SQL password is NOT already configured in this shell:
# $securePassword = Read-Host "LAB Commercial SQL password" -AsSecureString
# $env:COMMERCIAL_SQL_PASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
& $python -m commercial.integration_modules_lab
```

`commercial.integration_modules_lab` uses an ephemeral in-memory test RSA signing key, actual FastAPI Authorization verification, actual SQL account, tenant grants and the narrow SQL admin toggle. It restores the M3 fixture to OFF after its activation test, creating legitimate synthetic toggle AuditEvents. This new integration test **has not been run on the user's computer yet**; only describe its output as expected until the user executes it.

Formal four-day IT announcement: `commercial/IT_MVP_4DAY_ANNOUNCEMENT_FA.md`. Scope is a staged test-environment MVP subject to IT provision of identity, data permissions and review, NOT an unconditional production rollout.


## Milestone 7: reviewable LOCAL Persian UI + authorized pagination

To review the standalone responsive Persian dashboard NOW, read `commercial/REVIEW_PREVIEW_FA.md` and start `commercial.demo_preview:app` bound ONLY to `127.0.0.1:8090`. The preview serves all 100 wholly fictional meeting lifecycle stories from the checked-in JSON and computes action indicators client-side. Its module switches are explicitly **visual-only, temporary and NOT the licensed tenant module SQL/API switches**; no customer authentication, SQL credentials, OpenAI model or operational ProcessMaker connection is used. It must NEVER be deployed externally or mistaken for the commercial application's sign-in flow.

The UI offers meeting search/filter/detail, read-only secretary draft/action list, lexical synthetic source finder, analytics summaries, on-demand overdue action review and module catalog simulation. It is self-contained and uses first-party HTML/CSS/JS without CDN assets. A separate `commercial.demo_preview` FastAPI app ensures demo routes DO NOT introduce fake authentication into `commercial.api`; the production-facing API remains protected.

The actual authenticated LAB API adds `GET /v1/meetings/page?limit=20&cursor=910080`. Each page is bounded to 1–50 records and uses the authenticated tenant/subject + explicit `MeetingGrant` + SQL tenant RLS for stable descending keyset pages over 100+ synthetic records. Response includes `meetings`, `returned`, `has_more`, and `next_cursor`. `cursor` is the last `meeting_id` returned by the previous page, or omit for page one. The original `GET /v1/meetings` retains its earlier limited response contract for backwards compatibility. Do not send user-defined `tenant_id` or `subject` from a web page to select another user's data.

New offline regression tests: `commercial/tests/test_demo_preview.py`, `commercial/tests/test_pagination.py`. The new real-SQL `commercial.integration_modules_lab` also walks all 101 Alice meeting records and checks Bob/Carol isolation. These NEW assertions have NOT yet been run on the user's workstation. The opt-in GitHub workflow `.github/workflows/commercial-preview-ci.yml` executes offline Python tests and browser JS syntax checking; a workflow file alone does NOT prove CI passed.

**Still not implemented:** real user login and IdP onboarding, connected customer web portal, payment processing, real license fulfillment, speech input/output, background alerts, real SQL-to-ProcessMaker production ingestion, or production security certification.
