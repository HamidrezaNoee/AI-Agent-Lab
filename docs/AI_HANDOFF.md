# AVAN handoff — 2026-10-01

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
