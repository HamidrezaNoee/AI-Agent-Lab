# ECC adoption — AI-Agent-Lab

Vendored MIT-licensed ECC `security-review` skill from https://github.com/affaan-m/ECC/tree/b38be6a7f6350964d59328b52f0624e1d1d552d1/skills/security-review at `.agents/skills/security-review/SKILL.md`.

## Specific security constraints
ProcessMaker/SQL Server agent lab; use synthetic fixtures only, no production participant data, .env secrets, real SQL backups or external communications. Preserve separation between local test SQL and production ProcessMaker.

## Review workflow
1. Read README, existing security instructions, tests, deployment docs, and language stack before applying the skill. `$security-review` gives generic examples (some in TypeScript); translate principles to this repository's actual language, framework, and version.
2. Perform read-only threat review first: inputs, authentication and authorization, CSRF/SSRF/SQL injection, secret storage, personal data exposure, external requests, deployment permissions, and dependency/supply-chain risks.
3. Report exact affected paths, impact, evidence, and recommended smallest fix. Never report vulnerability exploitability or a clean bill of health without verification.
4. Keep secrets, operational credentials, beneficiary/customer records and private attachments out of commits, logs and AI prompts. Use synthetic data for tests.
5. Implement only explicitly approved changes and only use existing safe validation in a controlled environment; do not deploy, submit payment, contact external systems, or run destructive tools.

## Installation boundary
This PR only adds documentation and one upstream skill. No hooks, auto-run tools, MCP servers, CI workflows, elevated permissions, packages, or real security scanning have been enabled or run. Existing project rules override generic ECC advice.
