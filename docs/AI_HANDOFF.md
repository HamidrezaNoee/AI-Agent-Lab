# AVAN current handoff — 2026-10-04

Baseline: `4a0b583cf098268ba8c3784e22b87df10b0fc5f2` on
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
