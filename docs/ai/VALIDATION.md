# Validation — 2026-10-04

Baseline: 4a0b583cf098268ba8c3784e22b87df10b0fc5f2.

- Manifest: ten modules, paths/dependency cycles/summary budgets valid.
- New context/probe tests plus six identity suites: 46 passed.
- All manifest-selected Python tests: 257 passed, 5 failed, 16 subtests passed.
  Three failures are incomplete local source snapshot assets (preview CSS and
  production theme/fonts). Two reproduce baseline application/test discrepancies:
  `test_processmaker_directory_normalizes_uid_and_status` and
  `test_assistant_state_summarizes_invitation_for_chair`.
- Existing GitHub baseline run 37197473727: 403 passed, 3 failed, 55 subtests passed.
  The two discrepancies above plus
  `test_bootstrap_can_create_unprivileged_identity_without_pm_mapping` fail there.
  Its Docker/browser steps were skipped; no green integration result is claimed.
- Workflow YAML parsing and all embedded Bash syntax checks passed locally.
- No Docker daemon, live Keycloak, server credentials or browser-render acceptance
  available in this environment. Updated CI now starts the actual AVAN security
  bridge and anti-bot alongside Keycloak, checks challenge-bearing rendered HTML,
  and registers cleanup before resources are allocated. This gate is implemented,
  not yet demonstrated green. It does not test password/OTP acceptance.

The context tool maps tests, it does not label a module production-ready. Existing
failures remain visible; none were skipped or weakened to obtain a green build.
Root handoff reduced from 18,776 to 1,693 characters; this is not a measured token
saving percentage and does not measure runtime model usage.
