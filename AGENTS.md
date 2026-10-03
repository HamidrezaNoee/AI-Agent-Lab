# AVAN contributor instructions

Read `docs/AI_HANDOFF.md` before changing this project. For login or Appearance work,
read `docs/skills/avan-login/SKILL.md` and `docs/LOGIN_APPEARANCE_FA.md`.

- Keep normal-user production identity in Keycloak. At the owner's explicit request,
  the existing local GodAdmin may remain the permanent system-management account;
  retain CAPTCHA, current-password proof and Authenticator. Normal users, Admin and bound GodAdmin use
  the same `/auth/login` route. `/admin/` is the installation bootstrap/recovery
  surface; never create a second public role-specific login.
- Never issue a session before required OTP verification. Keep CAPTCHA verification
  server-side, fail-closed, with expiry, attempt limits and CSRF/origin protections.
- ProcessMaker MySQL is read-only; AVAN owns its separate SQL Server store.
- Docker is the delivery path. Never regenerate existing installation secrets or
  delete persistent volumes as part of a UI update.
- Canonical scene JS/CSS/assets live in `commercial/web/admin`. Run
  `python scripts/sync-login-assets.py` after editing them. Commit the generated
  Keycloak copies too; both deployment surfaces must remain identical.
- Use scoped tests and inspect actual browser screenshots. Clearly distinguish
  mocked UI tests, backend tests and live Docker/Keycloak verification.
- Update the handoff when behavior or deployment instructions change.
