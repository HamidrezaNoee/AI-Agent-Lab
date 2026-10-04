# AVAN handoff — 2026-10-01

## Update 2026-10-04: realm readiness and existing-process role activation

Baseline 721bc48. The owner's transcript confirms `down -v` removed four persistent
volumes; the last HTTP error is Keycloak bootstrap, not a demonstrated password error.
Compose now waits for the AVAN realm's discovery HTTP 200 before starting AVAN.
Build health/metrics options into Keycloak and start optimized. Normalize Compose
dollar escaping in the theme initializer. Add a fail-fast Windows Live start script;
it preserves secrets/volumes and waits for realm/app readiness without claiming login.

Admin process settings can now explicitly select a read-only native meeting pack
for upgrade using reviewed meeting/action PMX. Preserve its ID/revision history;
reject upgrades to an unrelated process. Validate five meeting vs two action stages
and unique task IDs before accepting a pack, avoiding ambiguous role dispatch.
No runtime grants, user bindings or live process assignments were changed here.

Validation: 75 focused Python tests passed, including the actual Bash readiness
probe against local HTTP 200/302/404/500/503 responders. Admin JavaScript syntax passed.
Dependencies installed from production requirements; PyYAML added to CI test setup.
No Docker daemon/CLI, PowerShell, live Keycloak/PM/SQL or rendered browser validation.
See `docs/AVAN_RECOVERY_AND_ROLES_20261004_FA.md` for recovery, activation and limits.

## Update 2026-10-03: user deletion

Add on-demand deletion confirmation to Users, excluding local/bound GodAdmin.
POST users/delete uses existing admin/MFA/CSRF gates, validates tenant and excludes
service accounts before mutations, and rejects bound/current administrator deletion.
Remove AVAN grants and tenant-scoped BPMS bindings atomically in the dedicated SQL
store, revoke sessions, delete Keycloak identity, then clear pending approval.
Keep BPMS users, process cases and historical records. External deletion failure
keeps access removed and reports retry; missing identity supports interrupted retries.
No login assets changed; canonical scene sync run (identical outputs).
Validation: 20 focused account/login/release tests passed; mocked Users DOM covers
confirmation, cancel, selected-subject deletion and no local GodAdmin delete action.
JS syntax and Python compilation passed. This does not certify live Keycloak.

## Update 2026-10-03: unified user administration

Replace the explanatory identity screen and always-open account forms with one
searchable Users list. Include local GodAdmin, mapped/pending users and paginated
tenant-scoped Keycloak users. Create/profile/password/access editors open on demand,
one at a time; saves/cancels clear password fields. Keep per-source native identity
selection and license-scoped AVAN module grants. Identity provider failure is visible
without hiding the local account. New user_accounts.py APIs use current admin/CSRF
dependencies, tenant checks, temporary passwords, session revocation and no OTP removal.
Email changes invalidate prior email verification. Docker COPY updated.

Fix organizational login previously blocked by permanent local GodAdmin: OIDC entry,
callback, home, me and organization authorization now coexist with the local session.
Local administrator remains at /admin/; normal user /auth/login remains OIDC. No
automatic business-data entitlement added to local GodAdmin. Legacy identity/status
API retained for other diagnostics; obsolete duplicate safe-status assertion removed.
Management browser smoke selectors updated; meaningful authorization/MFA tests retained.

Validation: full commercial suite 347 tests plus 55 subtests passed with writable
temporary state directories; focused final account/release tests and mocked Users
DOM passed. Actual Keycloak writes and rendered browser screenshots were not available.
Owner's earlier service-account authorization failure is not proven resolved: new
account APIs report HTTP failure and use the configured issuer, without regenerating
secrets. See USERS_FA.md.

## Update 2026-10-03: retain local GodAdmin by owner request

Continue from `6203116` on the same feature branch. Owner explicitly overrides the
previous bootstrap-only GodAdmin policy: retain the installed local account for
permanent system management, offer current-password+TOTP protected username/password
updates, and remove the forced create/bind UI. Internal singleton row remains stable;
display/login username is stored in encrypted `godadmin_account` settings. Revoke
local sessions after credentials change. Permanent local `/auth/login` uses existing
admin sign-in; normal users remain Keycloak identities. Local GodAdmin does not
gain an impersonated BPMS Principal.
Host-only `commercial.local_godadmin` validates the existing local password/TOTP,
restores local access and optionally deletes other human AVAN realm identities,
preserving service accounts and business history. Restart AVAN afterward to clear
old live sessions. It has NOT been run on the owner's machine. No secrets or volumes
regenerated. See `LOCAL_GODADMIN_FA.md`. Identity cleanup and credential tests are
mock/local tests; live Docker/Keycloak deletion remains user-executed and unverified.

## Update 2026-10-03: identity recovery and login panel option

Continue branch `feature/pm-native-agent-store-20260922` from `8d2112d`.
Add persisted `login_auto_collapse` through Appearance normalization/schema/editor
and canonical scene; false keeps the password panel expanded. OTP remains open.
Synchronize canonical scene to Keycloak resources. Add Docker-host-only
`commercial.identity_recovery` for exact-user unlock and optional hidden-input
temporary-password reset in bundled realm; preserve OTP/roles/tenant/bindings,
reject disabled accounts and wrong bound GodAdmin, revoke sessions on password reset.
No public reset route, weakened CAPTCHA, or rate-limit bypass added.
Reported live login rejection has not been reproduced: bootstrap vs Keycloak must
be distinguished, and wrong-password root cause needs local identity events.
See `IDENTITY_RECOVERY_FA.md`. Mock recovery tests do not certify live Keycloak.
Full commercial tests and JS syntax are rerun; rendered screenshots and actual
Docker login remain unavailable in this environment.

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
