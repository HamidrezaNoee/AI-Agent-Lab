# Small context workflow

Start with `docs/AI_HANDOFF.md`, then `python scripts/ai-context.py list`.
Read only the selected card, its entrypoints and relevant implementation/tests:

```powershell
python scripts/ai-context.py show identity
python scripts/ai-context.py affected commercial/security.py
python scripts/ai-context.py check
```

`modules.json` is the single maintained map: purpose, contracts, entrypoints,
dependencies, ownership patterns and focused Python tests. Shared files may belong
to multiple modules. `affected` includes transitive consumers; unknown/empty input
requires the full Python suite. It prints a command; it never executes supplied paths.
Before release, full CI, browser and live integration gates still apply.

Output defaults to 6,000 characters, hard maximum 12,000. Oversize output fails
without truncating a contract. This is a character budget, not an exact tokenizer
count. No model API, embeddings, vector store, source dump or secret reading is
needed. No fixed token-saving percentage is claimed. Measure usage before optimizing
production prompts. Update the manifest and tests when a contract changes.

Validation checks paths, dependency cycles and summary size, not every runtime
behavior. Read the selected source. Historical troubleshooting stays outside default
context. Handoffs contain changed behavior, test results, limitations and next step.

Runtime AI roadmap: bounded tool/results, allowlisted structured fields, paginated
evidence, cached immutable schemas by version, input/output usage measurement and
tenant-scoped cache keys. Never omit authorization or evidence to save tokens.
This developer utility does not impose a runtime token limit.
