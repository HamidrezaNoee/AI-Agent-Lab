# AI-Agent-Lab

Meeting AI Agent lab for SQL Server / ProcessMaker. This repository contains *code and synthetic test fixtures only*; never commit API keys, SQL passwords, `.env`, `.venv`, real database backups, production exports or real participant records.

## Synthetic meetings

Use a separate SQL Server database named `EnterpriseProcess2_AI_Test`, with **schema only** copied from `EnterpriseProcess2`. Do not connect this test database to a live ProcessMaker instance. Seed scripts must be run by a test database administrator, not by the read-only `AI_MeetingAgent` account.

See `sql/README_FA.md` for the setup, import, validation and agent test commands after copying the dataset package into `sql/`.
