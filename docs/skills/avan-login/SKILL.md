---
name: avan-login
description: Maintain AVAN shared login, conditional Authenticator step, animated Earth scene and Management Appearance editor. Use for changes to this repository's authentication UI, orbit controls, visual assets or login performance.
---

Read `AGENTS.md`, `docs/AI_HANDOFF.md` and `docs/LOGIN_APPEARANCE_FA.md` at the repository root.

1. Inspect current authentication flow in `infra/keycloak/avan-realm*.json` and
   `commercial/setup_routes.py`. Preserve conditional OTP and server-side anti-bot
   checks. Keep setup-only enrollment separate from ordinary user login.
2. Inspect the canonical `commercial/web/admin/login-scene.js` and
   `login-scene.css`; do not patch only the Keycloak copy.
3. Keep the first login panel collapsed until hover/focus/tap; reveal username, password, CAPTCHA and submit. Collapse on pointer leave; keep OTP open.
   Do not add help/tutorials, role selection, default usernames or a first-page OTP.
4. Preserve the bright Earth on the left and glass form on the right. Use the
   high-resolution raster layers, editable SVG nodes and text DOM overlays.
5. For new settings, update normalization, Pydantic input schema, management controls,
   save payload and scene consumer together. Preserve existing saved settings.
6. Retain safe SVG validation; never insert unvalidated uploaded markup into the DOM.
   Preserve unsaved edits when adding, deleting, copying or reordering elements.
7. Keep cached raster loading, bounded canvas resolution, 30fps rendering, and pause
   animation in hidden tabs, compact viewports and reduced-motion mode.
8. Run `python scripts/sync-login-assets.py`. Run the focused Python and browser
   tests listed in the handoff; inspect desktop/mobile/OTP screenshots.
9. Record results and limitations in the handoff. Never describe a mocked identity
   test as a live Keycloak login or claim a Docker deployment without running it.
