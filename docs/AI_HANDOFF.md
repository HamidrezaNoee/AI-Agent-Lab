# AVAN handoff — 2026-10-01

## Update 2026-10-03: process workspaces and audit

Starting upstream: `da14de175025efc39da50b534be9889ad3000577`, same feature branch.
`process_workspace.py` registers trusted adapters (`meeting_v2`, read-only
`native_tasks_v1`), validates process UID collisions, and serves source/pack/license
scoped manifests. User menus and inboxes follow the selected pack, with independent
analytical module permissions. `process_context.py` revalidates analytical selection;
native queries and conversation stamps include selected process identities.
Secretary writes now compare fresh REST form data before claiming/submitting and
revalidate active people before creating invitations. Relevant form fields alone
participate in native revision checks. Evidence quotes use actual scalar/document text.
Admin connects read-only native packs and toggles revision-checked activation.
Docker explicit COPY includes both new modules; release test checks every COPY source.

Validation: full commercial suite 335 passed, 55 subtests; both DOM integration
scripts passed; production/admin JavaScript syntax passed. No live SQL/PM/Keycloak/model
integration, Docker daemon or Chromium screenshot validation was available. Root
prototype RAG suites remain blocked locally by missing native libodbc.so.2. See
`AVAN_AUDIT_20261003_FA.md` for limits and `PROCESS_WORKSPACE_FA.md` for extension and
update instructions. No identity, secret or MySQL write architecture changes.

## Starting point and scope

Repository: HamidrezaNoee/AI-Agent-Lab. Branch:
`feature/pm-native-agent-store-20260922`. Starting upstream commit:
`74ff680a33e1ba38c39f2dd8c3a84812e447e729`.

This change targets login, Appearance, and scene rendering. It is not a complete
application performance audit or replacement of the identity/storage architecture.

## Product constraints

One public login for user/Admin/GodAdmin; username/password/server-validated CAPTCHA
first; separate 6-digit Authenticator page only for enrolled accounts. No login
help/tutorial. Preserve the reference's boardroom, bright cyan/orange Earth, orbit
icons and glass form. Appearance must persist image/SVG/text/tags/size/hover/orbits.

## Implementation map

- `commercial/login_appearance.py`: normalization, safe SVG, settings and public
  Keycloak JSON synchronization. Version 4 schema retained for compatibility;
  optional `orbit_mode` added (`drift`, `orbit`, `static`).
- `commercial/setup_routes.py`: bootstrap authentication + protected Appearance API.
- `commercial/web/admin/app.js`: management editor and bootstrap login/OTP views.
- `commercial/web/admin/login-scene.{js,css}`: canonical scene runtime.
- `commercial/web/admin/scene-data/*-v5.webp`: clean boardroom and transparent Earth.
- `infra/keycloak/themes/avan/login/`: real public login and OTP templates.
- `scripts/sync-login-assets.py`: deterministic synchronization to Keycloak resources.

## Fixes and measured facts

- Replaced 140px Earth sprite with 1254px transparent Earth. Boardroom is 1671x941.
  Both were edited from the user's supplied reference with built-in image generation:
  remove UI/globe for clean boardroom; extract/reconstruct the detailed Earth on alpha.
  They are derivative layers, not a pixel-identical extraction.
- Default scene images now use two cacheable WebP URLs (about 789KB combined) instead
  of seven uncached base64 fragments. Better resolution increases first-load bytes;
  do not claim reduced image payload. No new production JS framework/dependency.
- Render canvas at <=30fps, cap DPR at 1.5, cache layout geometry between resizes,
  update card-side classes only when changed, guard asynchronous initialization,
  stop motion in hidden tabs/mobile/reduced-motion mode.
- First login panel expands on hover/focus/tap and collapses on pointer leave. Password whitespace is preserved; username isn't prefilled.
- Keycloak OTP loads the same configurable scene. Existing realm conditional OTP
  already implements the requested enrollment-dependent flow.
- Empty element list stays empty. Add/copy/delete/reorder preserve unsaved edits.
  Full descriptions appear in cards. Globe picker preview is now attached.
- Reject SVG external paint references and nonfinite numeric settings.

## Validation

Run from repository root:

```sh
python -m pytest commercial/tests/test_login_appearance.py commercial/tests/test_operational_bootstrap.py commercial/tests/test_antibot_hybrid.py commercial/tests/test_turnstile.py commercial/tests/test_release_packaging.py -q
node commercial/tests/login_scene_smoke.cjs
node commercial/tests/management_render_smoke.cjs
```

Browser tests need Playwright and Chromium; `CHROMIUM_PATH` can point to an installed
executable. Tests use mocked APIs, not real customer credentials.
The focused Python suite passed 26 tests. Management rendering passed, including
all settings tabs, recoverable BPMS errors and Appearance edit retention/empty-list save.
Scene browser test passed: loaded high-resolution Earth, settings-driven nodes, hover/select, draggable card, blank-username form, reduced-motion pause and mobile width. Desktop screenshot was inspected.

Known unrelated baseline issue: `test_unified_godadmin` expects 403 for a degraded
meeting endpoint but current production code returns 503. Login and binding steps
pass before that assertion. Not changed to hide the discrepancy.
No live Docker, SQL Server, ProcessMaker or Keycloak service was available here;
run live account checks after deployment (enrolled/non-enrolled and each role).

## Deployment

Use the current installation checkout, same Compose overlays, secrets and volumes.
Pull this branch; rebuild AVAN and recreate Keycloak so theme caches refresh.
See `docs/LOGIN_APPEARANCE_FA.md`. Do not reset customized Appearance by default.

## Hover correction — 2026-10-01

Appearance schema is now version 5. The former v4 default drifting preset migrates
once to slow complete orbit (0.22 speed); v5 choices remain editable. The orbit
button is a fixed hit target. Only its pointer-events:none visual child scales on
hover, preventing CSS individual scale from scaling the button's translated world
position. Edge-pointer stability is covered by the browser regression test.


## Identity architecture — multi-BPMS user bindings

AVAN identities are independent from BPMS identities. Do not create AVAN accounts
as a side effect of ProcessMaker synchronization. One AVAN user can bind to a
different external user in each configured BPMS. Username/email matches are only
suggestions and require explicit Admin approval. Effective source access requires
both AVAN authorization and an active per-source binding. See
`docs/ADR-001-AVAN-BPMS-USER-BINDINGS.md`.


## Multi-BPMS authorization implementation — 2026-10-02

Runtime authorization no longer treats a globally active ProcessMaker as identity
evidence. AVAN accounts are independent, and operational BPMS routes are scoped by
an explicit active per-source binding.

- zero ProcessMaker bindings -> unscoped legacy PM routes return 403;
- exactly one active ProcessMaker binding -> legacy unscoped routes may resolve it
  for backward compatibility;
- more than one active ProcessMaker binding -> legacy unscoped routes return 409
  and the caller must choose a source-specific route;
- source-specific routes enforce the exact AVAN subject -> BPMS external user binding;
- user-level AVAN module permissions narrow the organization license and are enforced
  in backend scope construction;
- the management UI edits AVAN module grants separately from BPMS bindings;
- source menus are capability-aware and are derived from binding + implemented
  user-scoped source routes + effective AVAN module grants.


## Configured secretary inbox — 2026-10-02

See `docs/SECRETARY_WORKFLOW_FA.md` for supported PMX, configuration, accounts and deployment.
The native task inbox supersedes the owner-only workflow REST registration. Existing legacy
records are retained; there is no automatic draft migration. Current native cases remain visible
by source + active UID assignment + task + delegation index. No administrator bypass.

`secretary_catalog.py` compiles reviewed meeting/action PMX into source-specific packs and checks
installed task/form/trigger IDs. `secretary_credentials.py` stores encrypted personal PM OAuth
(refreshable; no passwords) and invalidates grants after binding/endpoint changes. New runtime
covers invitation, chair approval/edit, minutes, chair approval/edit, action report, secretary
review and scheduled monitoring/follow-up. Native form BEFORE preparation is explicit;
AFTER triggers run before native route. Claim-before-I/O prevents blind duplicate operations.

`secretary_evidence.py` reads authorized native TXT/text PDF documents with bounded streaming
and a memory/CPU/time-limited PDF subprocess, then returns advisory, quoted review suggestions.
No automatic voting from recommendations, no OCR or upload of new BPMS attachments.
Monitoring lead is configurable; current PMX permits parent closure with reviewed open actions
(the previous zero-open assumption has been corrected). Inbox polling uses current license,
binding and native assignment; background uses the existing delegated AVAN identity lifecycle.

Production/admin JS add process setup, role inbox, forms, text/voice, speech, notifications,
review suggestions and follow-up. Docker copies new modules and installs bounded PDF dependency.
MySQL remains read-only; native writes are exclusively PM REST. No changed login assets/secrets.

Validation: 91 selected backend tests passed, 1 unrelated binary font-asset test excluded from
partial local checkout. JS DOM integration with mocked APIs passed; both JS syntax/Python
compile passed. Chromium installation returned truncated archives, so screenshot QA remains
unperformed. No live model/SQL/PM/Docker/Keycloak verification. See FA guide for acceptance flow.
