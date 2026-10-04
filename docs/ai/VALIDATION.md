# Validation — meeting pair and secretary desk, 2026-10-04

Integrated onto c19ae38963f59710cadd903ec231ddff076650f1, preserving latest voice,
structured parsing/retry and safe grid-merge work.

- Full Python suite: 463 passed,
  55 subtests passed. No skipped baseline failures.
- Real runtime and REST adapter exercised for all seven stages with mock PM HTTP.
- Context budgets, evidence quotes, pair merge/revision checks and installed
  contract drift rejection tested.
- Secretary and process navigation DOM tests passed after correcting stale fixtures.
- Chromium renders actual HTML/CSS/JS with API fixtures; desktop/mobile screenshots
  inspected. Counts, ordered stages, empty-stage disabling, filtering and task editor
  checked. This is not live PM/Keycloak or paid-model verification.
- Runtime accepts documented PM document-download success statuses 200 and 206.
- Docker and PowerShell execution are unavailable locally; production packaging is
  checked by the Python COPY-layout test. CI retains container/browser gates.
- PMX originals unchanged. Native original-file upload remains separate from text
  extraction; exported multiple-file controls refer to f1/all without Input Document
  definitions. Live mapping/API-version verification is required for that path.
