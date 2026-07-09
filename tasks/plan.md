# Implementation Plan: Safe Stroyka Program Improvements

## Overview

Improve `stroyka-app` in small, safe steps so the current working ERP can move toward a production-grade SaaS platform without destabilizing existing object, estimate, supply, warehouse, journal, accounting, and public-site flows. The plan prioritizes security, company data boundaries, verification, and reversible refactors before adding new product surface.

## Assumptions

- The next improvement cycle should reduce production risk before adding large new features.
- Existing product rules in `ONBOARDING.md`, setup rules in `README_LOCAL_RUN.md`, and architecture rules in `docs/project-structure.md` remain the source of truth.
- Backend changes should be extracted one domain at a time; no broad rewrite of `backend/main.py`.
- Every task must keep `uvicorn backend.main:app`, frontend build, and current smoke scripts usable.
- Generated artifacts under `output/` and `graphify-out/` are not part of the product unless explicitly promoted.

## Architecture Decisions

- Use vertical slices: API policy, tests/smoke, frontend behavior, and docs move together only when the slice requires it.
- Treat `platform_account` as the hard customer boundary and `company_id` as the required working context inside that account.
- Keep SaaS isolation compatible: add a central tenant-context kernel and enforce one domain at a time, then backfill/strict filtering only after dry-run evidence.
- Keep `Все компании` read-only. Every mutation must resolve one concrete company and verify membership on the backend.
- Treat client company headers as untrusted routing hints, never as authorization proof.
- Prefer small auth hardening over a big auth rewrite: cookie-first frontend, then CSRF, then shorter Bearer fallback.
- Move schema ownership from `init_db()` into Alembic one small table/column group at a time.
- Keep UI changes inside existing modules and screens; do not add parallel screens for the same workflow.

## Task List

### Phase 0: Baseline And Worktree Hygiene

- [ ] Task 1: Record baseline status and keep generated artifacts out of the implementation scope.
- [ ] Task 2: Add a repeatable local validation checklist for this improvement cycle.

### Checkpoint: Baseline

- [ ] `git status --short` reviewed.
- [ ] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py` passes.
- [ ] `CI=true npm test -- --watchAll=false` passes or failures are documented.
- [ ] `npm run build` passes.

### Phase 1: Security First

- [ ] Task 3: Protect `/parse-smeta` or explicitly harden it as a public endpoint.
- [ ] Task 4: Add a focused smoke/test for smeta upload access behavior.
- [ ] Task 5: Move frontend API requests toward cookie-first auth while keeping Bearer fallback.
- [ ] Task 6: Add CSRF design notes and a small server/client compatibility slice for mutating requests.

### Checkpoint: Auth And Upload Safety

- [ ] Auth/session smoke passes.
- [ ] Smeta parser access behavior is covered.
- [ ] Existing login, 2FA, public site, and MAX paths are not broken.

### Phase 2: Multi-Company Kernel And Domain Isolation

- [x] Task M1: Add the compatible Tenant Context Kernel and connect supply-request creation as the first consumer. Verified and released as an independent production slice.
- [ ] Task M2: Enforce company-scoped supply reads/writes and effective membership roles.
- [ ] Task M3: Scope supplier visibility, recipients, offers, invoices, and company-supplier terms.
- [ ] Task M4: Scope warehouse balances, invoices, history, and explicit cross-company transfers.
- [ ] Task M5: Scope payments, accounting, contracts, and financial reports.
- [ ] Task M6: Scope remaining projects, estimates, journals, acts, files, notifications, audit, and AI jobs.
- [ ] Task M7: Run dry-run backfill, add database constraints/indexes, and verify the pilot tenant matrix.

### Checkpoint: SaaS Boundary

- [ ] One user with two companies cannot mutate in `Все компании`.
- [ ] Two independent `platform_account` tenants cannot see or address each other's companies.
- [ ] Supply request, KP recipient, supplier invoice, delivery, warehouse invoice, and warehouse history keep the same `company_id`.
- [ ] Old records remain readable under legacy fallback.

### Phase 3: Backend Reliability

- [ ] Task 12: Extract auth/session helpers from `backend/main.py` into `backend/auth.py`.
- [ ] Task 13: Extract audit/client-error route group into a small backend feature module.
- [ ] Task 14: Move one low-risk `init_db()` schema slice into Alembic.
- [ ] Task 15: Add a minimal CI workflow for backend compile, frontend tests, and frontend build.

### Checkpoint: Backend Shape

- [ ] `backend/main.py` still owns legacy routes but has less auth/audit boilerplate.
- [ ] Alembic upgrade works on a local initialized database.
- [ ] CI catches syntax/build failures before deploy.

### Phase 4: Operator UX And QA Coverage

- [ ] Task 16: Improve supply/operator UI only after backend contracts are stable.
- [ ] Task 17: Add browser smoke coverage for the highest-risk role flow.
- [ ] Task 18: Update `ONBOARDING.md`, `TESTING.md`, and deploy notes with accepted rules.

### Checkpoint: Ready For Production Rollout

- [ ] Local tests and build pass.
- [ ] Relevant smoke scripts pass.
- [ ] Production deploy checklist is ready.
- [ ] Rollback path is explicit.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Mixing feature work with backend extraction | High | Keep each task scoped to one vertical slice and one domain. |
| Breaking existing ERP data while adding SaaS isolation | High | Use compatible `company_id` defaults, dry-run diagnostics, and read-only checks before strict filtering. |
| Auth migration breaks mobile/MAX/public flows | High | Keep Bearer fallback temporarily and add smoke coverage before removing it. |
| Alembic and `init_db()` conflict | Medium | Move one schema slice at a time and keep idempotent guards until production is upgraded. |
| Tests stay green while runtime flows break | Medium | Add targeted smoke/browser checks for role and workflow paths. |
| Generated files pollute commits | Low | Keep `output/` and `graphify-out/` out of commits unless explicitly requested. |

## Open Questions

- Do we have a stable production smoke user with 2FA/TOTP support for protected production smoke?
- Should CI run only local build/tests first, or also selected smoke scripts against a disposable local DB?
- Which five or six pilot companies should be modeled as independent accounts, and which belong to one holding with shared summary access?
