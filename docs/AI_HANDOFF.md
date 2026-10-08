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

## AI model selection
Admin AI settings can list models visible to the saved or draft API key, select
or manually enter an ID and probe visibility before saving. Both endpoints require
_ready, use the official fixed endpoint and never save draft keys during probes.
Visibility does not prove Responses/structured-output compatibility. Save preserves
a blank key and takes effect on the next request. 481 Python tests passed; browser
fixture checks list/select/probe/save. No live key or production deployment tested.

## Server-side person resolution
Extraction now resolves exact usernames/full names/UID casing against active users
of the current BPMS before validation. Ambiguous/inactive/unknown references become
blank fields with specific questions; valid agenda and other facts survive. Missing
participant IDs are explicit gaps blocking invitation submission. Evidence checks,
source boundaries and explicit send authorization remain in place. Regression uses
eight example accounts and simulated model output, not a live model/PM connection.

## Conversational secretary
Text turns now use ConversationExtraction: question/update intent plus Persian reply,
assignments and questions in one model call. Question intent discards assignments,
preserves prior pending questions and cannot auto-advance. Replies persist in both
native-task and invitation-session history and API output. Simple agenda-row queries
use draft facts without a model call; implicit row refers to the current missing
agenda presenter. Payload includes actual pending fields and assistant prompt.
Legacy extraction remains for file ingestion. Full suite: 486 passed before two
additional regressions; focused final set: 66 passed including both additions.
Model quality and production BPMS behavior are not established by fixture tests.


## Secretary and desk regression repair — 2026-10-07

Based on remote e76ec74, preserving the latest meeting/action contracts. Uploaded
meeting-10(1) and action-9(1) compile exactly to secretary_pack_reference.json.
Their SHA256 fingerprints are respectively
153492224d92b8df34aa4502e92ff7a8b4c9ec76cc41acffed184db5e5d72015 and
a44a7703546218ed84f32030822b6f14dccb92c7877ca7114badaa81235d8fdb.

- Structured extraction receives bounded actual conversation history; NEW-message
  evidence remains mandatory. Sparse grid row keys survive deletion and follow-ups.
- Repeating a one-action-per-attendee command reuses assigned draft actions;
  explicit additional/new requests append. Generic role overlap is insufficient.
- Direct minutes send validates the supplied revision and claims the draft while
  REST executes. Foreign/concurrent/stale requests cannot overwrite the draft.
  Failed transport retains the draft revision for an explicit retry; successful
  native routing is not rolled back because a later local audit fails.
- Audit filters run in SQL before TOP, within tenant/actor scope. Completed/failed
  operations retain source/process/case context. Late filter responses are ignored.
- Bound OIDC GodAdmin password changes use Keycloak, not local recovery storage.
- Real child-case branches have measured curved joins, compact desktop spacing and
  visible rework loops; draft action rows remain unbranched. Existing compact form
  and settings layouts retained; log controls have explicit accessible names.

Validation: 594 Python tests + 55 subtests passed in the full local run; the sole
remaining failure was the bundled-font presence check because binary WOFF2 assets
could not be materialized through the connector (they remain in the remote tree).
Two additional focused conversation regressions cover retry and historical evidence.
Real Chromium with deterministic API fixtures exercised stage gates, branch rendering,
mobile overflow, settings save and log filtering; screenshots visually inspected.
This is not live PM/PHP trigger, SQL Server, Keycloak or paid-model validation.
Full remote CI remains a release gate; previous upstream workflow runs already failed.

Deploy only the AVAN service from the existing production checkout/compose project:
`docker compose -p avan-production -f compose.yaml -f compose.pm-local.yaml up -d --build --no-deps avan`
Do not regenerate secrets, reset ProcessMaker, or remove volumes.

## Secretary orchestration and conversation repair — 2026-10-08

Based on remote 419ddff and the same reviewed meeting/action PMX pair. The new
`secretary_orchestrator` selects bounded confirmation, time/attendance, identity,
draft-command, read and extraction tools. It does not persist or execute PM writes;
existing scope, fresh-task, revision, cancellation and explicit-send gates remain.
Legacy `secretary_agent` exports remain intact. `secretary_journal` records visible
field changes and one private undo checkpoint; undo is draft-only and uses the
same revision/native-task gates. Public API responses exclude checkpoint contents.

Persian named dates never become clock hours; HH:mm preserves minutes. Minutes
planning dates remain locked invitation context. Present attendance time is
required by the current PM trigger: “everyone on time” copies the native meeting
start clock to Present rows without changing absences. Short “حاضر بوده” resolves
the latest explicit participant row. Resolved attendance/locked-field questions
are removed from the assistant's outstanding question list.

Model extraction has a shared budget of three attempts for validation failures or
transient connection/429/5xx errors, with short bounded backoff for transport errors.
Authentication/configuration failures are not retried. Unusable model output becomes
an unchanged-draft clarification, retained in conversation, with concrete next steps.
No automatic retry was added to ProcessMaker writes. Mixed cp1252/Latin-1 UTF-8
mojibake is repaired; attendance rejection includes a useful corrective instruction.

Chat uses text-node-only rich formatting, copy/edit actions, visible change receipts
and draft undo. Fields rebuild from the returned server state after each turn, so
open grids and scalar controls cannot keep stale references. Error notices dismiss;
successful draft edits clear the historical submission error. Buttons respect hidden.

Validation: 206 focused Python tests passed, including 24 new regressions. Real
Chromium with mocked APIs verified chat-to-form synchronization, rich text, undo,
responsive desk/graph, settings and logs; screenshots inspected. DOM integration
also passes after updating its stale graph assertions and browser API stubs.
The broad run reached 569 passed +55 subtests before the known missing local binary
YekanBakh WOFF2 fixture failed; remote font assets are unchanged. Full remote CI
remains the release gate. No live PM/SQL/Keycloak/model or production Docker access
was available; do not claim deployment or live native routing verification.

## Attendance optional correction — 2026-10-08 (main)

Supersedes the earlier statement that attendance clock must be supplied. Owner
confirmed it is optional; the native FR-MTG-003 control already has required=false.
AVAN missing-field checks and old assistant questions now honor that requirement.
Nonempty invalid times still fail validation. Existing same-row active UIDs in model
outputs are retained without demanding another identity quote; new/reassigned people
still require evidence. Typo “به موقه” and “سر تایم جلسه” use the attendance tool.
Explicit “همه ... آمدند” marks all listed participants present; general statements
about present attendees preserve existing absences. No unknown clock is fabricated.

PM's reviewed AFTER trigger had a contradictory unconditional regex check. The
complete one-condition correction and exact Designer instructions are in
`docs/processmaker/OPTIONAL_ATTENDANCE_FA.md` and its adjacent PHP file. AVAN does
not write PM MySQL or remotely install trigger code. Existing source verification
accepts only the exact reviewed old/new hashes for that single trigger. Other code
drift remains rejected. An app rebuild alone cannot change the native trigger.

Main aae3e23 contains all 92242f4 code plus the merged OAuth helper. These fixes target
main, preserving those unrelated additions. No UI change in this increment. Focused
Python regressions cover optional blanks, invalid times, both user phrases, preserved
identities, and rejection of unreviewed trigger changes. Live PM routing and full CI
are still required before calling this an operationally verified deployment.

## Invitation completion button and toast dismissal — 2026-10-08

Owner screenshot 39 shows a new invitation whose missing fields became empty during
chat, but the submit button was never created. Build the session-start control for
all draft invitations and update visibility/disabled state on each server response
and while sending. OAuth, dirty-form and server ownership gates remain unchanged.
Toast notifications always expose a close button and expire within 10 seconds;
explicit hidden CSS prevents the flex display rule from overriding hidden state.

Validation: rendered Chromium API fixtures exercise incomplete→complete→incomplete
invitation turns without reopening the editor, accessible manual dismissal, and the
exact 10-second timeout using the browser clock. Existing desk/graph/settings/logs
and DOM integration pass. Screenshot invitation-ready.png inspected locally. No
live ProcessMaker account routing or production deployment was performed.
