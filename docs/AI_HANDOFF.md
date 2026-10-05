# AVAN current handoff — 2026-10-04

Baseline: `c19ae38963f59710cadd903ec231ddff076650f1` on
`feature/pm-native-agent-store-20260922`.

Run `python scripts/ai-context.py list`, then `show <module>`.
Read its contract, entrypoints and focused tests. `affected <changed-paths...>`
includes dependent modules; unknown paths select all Python tests. Full CI remains
the release gate. See `docs/ai/README.md`; do not preload history or large datasets.

## Constraints

- Organizational credentials: Keycloak; authorization: AVAN. Local GodAdmin recovery
  remains separate. Never weaken CAPTCHA, OTP, CSRF, tenant or binding checks.
- PM MySQL is read-only; writes require personal OAuth and verified task ownership.
- Preserve secrets, SQL state and Docker volumes. No `down -v` for repairs.
- Canonical scene assets live in `commercial/web/admin`; synchronize theme copies.
- Owner requires a fixed login card, no dragging/automatic collapse. Older hover
  guidance is superseded. Browser acceptance still needs verification.

## This increment

Bounded module cards, dependency-aware test selection and manifest validation.
Architecture and staged migration: `docs/architecture/BASELINE_20261004.md`.
Results and known baseline failures: `docs/ai/VALIDATION.md`.
Local test success is separate from live Keycloak and production deployment.

## Next gates

Real Keycloak rendering/security challenge, no-OTP and enrolled-OTP login,
invalid/expired/replayed challenge rejection, logout/relogin, canonical-host callback,
and recovery while PM/AI are unavailable. Verify actual tenant bindings and process
role assignments before claiming secretary/chair/action-user activation on the host.

Historical diagnoses/results: `docs/history/AI_HANDOFF_20261004.md`.

## Reviewed meeting/action pair

Version-7 uploaded PMX contracts now ship in secretary_pack_reference.json. Admin
can explicitly install/merge the pair; live forms, trigger order and code fingerprints
must match. Chair hidden votes have typed UI choices. Extraction context is bounded
by stage (48k characters, 80 people, 3500 output tokens); no silent grid truncation.
See docs/AVAN_MEETINGS_V7_FA.md for deployment and live acceptance. Original file
upload to PM is separate from AI document extraction and remains a live integration gap.

## Secretary desk UI

One invitation creation action; seven ordered stages with disabled empty stages
and counts from the current user/source/pack inbox. Native task cards, compact
OAuth settings, editor stage indicator and mobile layout. Browser fixtures cover
counts/filtering/native task opening and return; they are not live PM acceptance.
Preserve latest voice, schema parsing, conservative retry and grid-merge fixes.

## Persian extraction — 2026-10-05

Directory shortlist now matches Persian name tokens (Arabic/Persian letter,
diacritic and half-space normalization), retains all ambiguous candidates and
includes organizational unit without email. Existing 80-person/48k limits remain.
Prompt distinguishes chair, secretary, participants and agenda and consumes prior
clarification questions. Explicit additive participant/agenda requests merge by
identity, preserving existing rows even when the model reuses row 1; explicit edits
retain existing row semantics. No fuzzy identity assignment or live model change.
Validate with test_secretary_ai_context.py; production-model linguistic accuracy
and live PM acceptance still require organization-specific examples.

## Username and relative-date extraction repair — 2026-10-05

Read USR_USERNAME from the same source's USERS directory and expose it in bounded
AI candidates; exact username matching preserves dots and token boundaries.
The runtime supplies Tehran time plus today/tomorrow Jalali dates. Explicit
participant/agenda headings omitted by the model trigger the existing one retry,
then a visible clarification instead of silent success. Summary includes agenda
presenters and minutes. Tests verify data plumbing and simulated model omissions,
not paid-model extraction accuracy; live deployment remains unverified.
