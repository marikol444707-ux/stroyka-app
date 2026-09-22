# STROYKA AGENT RULES

Stroyka is a multi-tenant construction ERP/SaaS platform.

## Source of truth
- GitHub repository is the source of truth.
- Inspect existing architecture before changing code.
- Prefer extending existing modules over creating parallel implementations.
- Keep changes small and scoped.

## Production safety
- Never modify production data directly.
- Never deploy to production automatically.
- Never run destructive database operations.
- Never apply production migrations automatically.
- Never expose or commit secrets, API keys, passwords, tokens, or .env files.

## Multi-tenancy
- Tenant isolation is mandatory.
- Every tenant-owned resource must preserve company_id ownership.
- Data belonging to one company must never be visible to another company.
- Never introduce fallback ownership such as company_id=1 or COALESCE(company_id, 1).
- Authorization and ownership checks must remain server-side.
- Add regression tests when touching tenant-owned resources.

## AI architecture
- LLMs must not access the database directly.
- AI uses restricted backend tools/service interfaces.
- Authoritative amounts, quantities, balances, limits, margins, and financial totals are calculated by deterministic code, not by the LLM.
- AI recommendations should retain evidence/source references where applicable.

## Backend
- backend/main.py is being decomposed gradually.
- Do not perform broad rewrites of backend/main.py.
- Extract one domain at a time while preserving behavior.
- Keep uvicorn backend.main:app working.
- Use existing config.py, db.py, auth.py and feature modules where appropriate.

## Testing
- Bug fixes require regression tests when practical.
- Run the narrowest relevant tests first.
- Before considering a substantial change complete, verify relevant backend tests and frontend build/tests.
- Do not claim success when tests fail.

## Git workflow
- Work on a dedicated branch/worktree.
- Never write directly to main.
- Summarize changed files, tests run, failures, and remaining risks.
