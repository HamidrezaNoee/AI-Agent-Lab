# Commercial Agent | Milestone 1: tenant & identity boundary (LAB ONLY)

**Current status: security foundation / prototype, NOT a production-ready or sellable AI service.**
The existing `06_meeting_ai_agent.py` and `knowledge_tools.py` remain synthetic research tools; **do not expose them directly to customers**. Their shared SQL login is NOT a user-by-user authorization system.

## Repository deliverables in this milestone

- `commercial/security.py`: validate a real IdP-signed RS256 JWT against an ADMIN-CONFIGURED HTTPS issuer, audience and JWKS endpoint; reject bad signature, issuer, audience, lifetime, empty/invalid tenant and missing bearer tokens. The `tenant_id` must be a trusted claim issued by the IdP. A request header or a field in the user's question is never accepted as tenant identity.
- `commercial/api.py`: authenticated `GET /v1/me` and `GET /v1/meetings` skeleton; zero unfiltered SQL endpoints; no chatbot endpoint at this stage.
- `commercial/sql_store.py`: each request creates a NEW SQL connection, sets `AgentTenantID` SQL session context, checks the database's active membership + active tenant + unexpired subscription, and queries a tenant-scoped meeting index. The commercial SQL user MUST be separate from `AI_MeetingAgent`.
- `commercial/sql/01_tenant_boundary_TEST_ONLY.sql`: isolated tenant, meeting-index, document-index, chunk, subscription and audit contracts with SQL Server row-level security (RLS).
- `commercial/sql/03_membership_usage_TEST_ONLY.sql`: per-tenant memberships and token usage storage contracts.
- `commercial/sql/02_test_tenant_isolation.sql`: rollback-only SQL smoke test for tenant A/B and missing tenant context; test rows do not persist.
- `commercial/sql/04_reader_permissions_TEST_ONLY.sql`: least-privilege SELECT grants for a separately provisioned login and explicit DENY on the original unscoped `MTG` and `AI` lab schemas.
- `commercial/tests`: offline JWT/API access-gate unit tests.

**Important limitations:** The gateway currently reads only `AgentProduct.MeetingIndex` test rows, not real ProcessMaker sessions. No production document import, chat completion, per-resource ACL, token metering enforcement, billing, customer onboarding, audit writer, rate limiting, or real license enforcement has been shipped. Do not describe the `Subscription` table as a billing integration: it is only an admission flag/date. Do not treat the JWT `tenant_id` claim as sufficient: membership is checked in SQL on every request.

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
```

Expected message from the third script:

```
PASS: tenant A, tenant B, and missing-context SELECT isolation.
```

The SQL script's RLS test runs in a transaction and rolls back its synthetic tenants and meeting indexes. After it passes, create the NEW server login `AI_CommercialReader` in SSMS with a separately generated password; do not add it to any administrative or bulk-reading role. Then execute `commercial/sql/04_reader_permissions_TEST_ONLY.sql`. Do not type passwords into chat or commit them to Git.

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
