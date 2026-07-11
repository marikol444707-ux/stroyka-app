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
- [x] Task M2: Enforce company-scoped supply reads/writes and effective membership roles.
- [x] Task M2.1: Scope `GET /supply-requests` by selected company or current-account summary. Verified and released as an independent production slice.
- [x] Task M2.2: Protect `PUT /supply-requests/{id}` with the stored request company and its effective membership role. Verified and released as an independent production slice.
- [x] Task M2.3: Protect `DELETE /supply-requests/{id}` and its optional stock rollback by request company. Verified and released as an independent production slice.
- [x] Task M2.4: Protect `POST /supply-requests/{id}/request-kp` by the stored request company and effective membership role. Verified and released as an independent production slice.
- [x] Task M2.5: Protect `GET /supply-requests/{id}/recipients` by stored request company and effective membership role. Verified and released as an independent production slice.
- [ ] Task M3: Scope supplier visibility, recipients, offers, invoices, and company-supplier terms.
- [x] Task M3.1: Scope `GET /supplier-offers` by internal company context and explicit supplier-recipient evidence. Verified and released as an independent production slice.
- [x] Task M3.2: Protect `GET /supplier-offers/{id}/history` and `PUT /supplier-offers/{id}` with the verified offer/request company and supplier recipient scope. Verified and released as an independent production slice.
- [x] Task M3.3: Protect `POST /supplier-offers` with stored request company, explicit recipient scope, and idempotent pending-offer reuse. Verified and released as an independent production slice.
- [x] Task M3.4: Protect `POST /supplier-offers/{id}/create-invoice` with verified offer/request company and supplier recipient scope. Verified and released as an independent production slice.
- [ ] Task M3.5: Protect `GET /supplier-invoices` with internal company context, supplier identity scope, and same-company document joins. Implemented locally; release pending.
- [ ] Task M4: Scope warehouse balances, invoices, history, and explicit cross-company transfers.
- [ ] Task M4.1: Scope `GET /warehouse-main` by the selected company context. Implemented locally; release pending.
- [ ] Task M4.2: Add company identity and read isolation to warehouse movements. Implemented locally; release pending.
- [ ] Task M4.3: Require company context when creating warehouse movements. Implemented locally; release pending.
- [ ] Task M4.4: Scope warehouse history reads by company context. Implemented locally; release pending.
- [ ] Task M4.5: Require selected-company leadership for manual warehouse history corrections. Implemented locally; release pending.
- [ ] Task M4.6: Protect access to individual warehouse history records by stored company. Implemented locally; release pending.
- [ ] Task M4.7: Scope warehouse invoice list reads by company context. Implemented locally; release pending.
- [ ] Task M4.8: Require one verified company across warehouse invoice creation and stock updates. Implemented locally; release pending.
- [ ] Task M4.9: Protect warehouse invoice accounting updates by stored company and effective finance role. Implemented locally; release pending.
- [ ] Task M4.10: Protect warehouse invoice annulment and stock reversal by stored company. Implemented locally; release pending.
- [ ] Task M4.11: Protect main-warehouse card creation and updates by selected company. Implemented locally; release pending.
- [ ] Task M5: Scope payments, accounting, contracts, and financial reports.
- [x] Task M5.1: Isolate company requisites by selected company and remove the global destructive replace. Deployed in `69f55f4b`; authenticated tenant smoke pending.
- [x] Task M5.2: Isolate `project_payments` reads, writes, reversals, automatic document payments, and AI payment context by company. Deployed in `5db2e496`; authenticated tenant smoke pending.
- [ ] Task M5.3: Add stored company ownership to brigade contracts/payments and close their remaining global read paths.
- [ ] Task M5.3a: Scope brigade contract, payment, item, and act reads by effective company membership. Pushed in `937d7a4f`; production release pending.
- [ ] Task M5.3b1: Store brigade payment ownership and authorize create/reversal from the parent contract company. Pushed in `83529e6c`; production release pending.
- [x] Task M5.3b2: Enforce selected-company ownership for brigade contract create/update/cancel and contractor assignment. Deployed in `8c971801`; public production smoke passed.
- [x] Task M5.3b3: Enforce parent-company ownership for pricelist loading, contract items, brigade acts, and estimate distribution. Deployed in `d885ba52`; public production smoke passed.
- [x] Task M5.3b4: Isolate the primary `Назначить мастеру` work-assignment route by the estimate's stored company and exact project. Deployed in `d885ba52`; public production smoke passed.
- [ ] Task M6: Scope remaining projects, estimates, journals, acts, files, notifications, audit, and AI jobs.
- [x] Task M6.2a: Register selected-company ownership for new uploads and bind a file to a project only by exact `projectId`. Deployed in `51550487`; public smoke passed.
- [x] Task M6.2b: Add authorized tenant-file metadata/delete APIs and an authenticated upload/read/cleanup smoke. Deployed through `7fcda405`; authenticated production smoke passed.
- [x] Task M6.2c: Add authorized local/S3 tenant-file byte serving while legacy public URLs remain compatible; keep private S3 ACL cutover as the next storage step. Deployed in `f1d9e1de` with hotfix `7fcda405`; authenticated content smoke passed.
- [x] Task M6.2c1: Harden tenant files against ambiguous project names, cross-tenant storage pointers, redirecting/unbounded S3 reads, symlink races, and unverified physical cleanup. Deployed through `224238cd`; public and authenticated production smoke passed.
- [ ] Task M6.2d: Migrate file consumers to protected content URLs, then switch new S3 objects to private storage after a usage audit.
- [x] Task M6.2d1: Move new project-letter attachments to opt-in protected `contentUrl` with exact `projectId`, while preserving every existing upload caller. Deployed in `8132954e`; public smoke and authenticated director UI check passed.
- [x] Task M6.2d2: Move direct project-document registry scans to protected `contentUrl`; keep OCR source uploads compatible while binding them to exact `projectId`. Deployed in `7abf86e1`; runtime `b05fac7e` passed public, authenticated file, API, and registry UI checks.
- [x] Task M6.2d3: Add an authenticated Blob URL loader with strict local-path detection, request cancellation, and object-URL cleanup. Deployed in `6a45a2ea`; public and authenticated tenant-file production smoke passed.
- [x] Task M6.2d4: Migrate the main company-chat message thumbnail to the protected Blob loader without changing uploads or stored messages. Deployed in `845532f5`; public, authenticated file, and main-chat browser checks passed.
- [x] Task M6.2d5: Migrate the project work-journal list thumbnail to the protected Blob loader without changing uploads, stored rows, or backend. Deployed in `6fe3a6aa`; public, authenticated file, and work-journal browser checks passed.
- [ ] Task M6.2d6: Add opt-in protected rendering to `PhotoAttachmentField` and enable it only in the work-journal edit form, preserving every other caller.
- [ ] Task M6.4: Scope company `messages`, estimate versions, changes, and estimate chat by stored company and verified project parents; `/messages` currently remains a critical legacy global table.
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
- [x] Task 15.1: Apply only SemVer-compatible frontend security updates without `--force`; deployed in `0d95c3d5`, critical audit findings removed, public production smoke passed.

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

## Focused Track: Safe Estimate Material Calculation

### Goal

Replace unsafe family-level aggregation and broad substring norms with a traceable material plan. Existing estimates, warehouse receipts, movements, and supply requests remain unchanged until a separate dry-run proves how they should be relinked.

### Phase P1: Calculation Safety

- [x] Stop family-only auto-merging inside procurement/material reconciliation; keep exact canonical identity and confirmed aliases.
- [x] Match AI/override norms to their source work and reject known false-positive work patterns.
- [x] Make scoped overrides replace their linked base norm.
- [x] Add regression tests for distinct fasteners/profiles/cables, brick vs air-duct installation, plaster finishing, and screed adjustment rows.

### Phase P2: Traceability And Review

- [x] Show estimate, package, section, work, source quantity, unit conversion, norm, and formula for every calculated row.
- [x] Route uncertain aliases, units, and norm matches to `Проверить`, never directly to `Докупить`.
- [x] Separate explicit estimate plan from normative hints in totals and filters.

### Phase P3: Production Dry-Run

- [ ] Compare old/new quantities and row identities for every active project without changing business records.
- [ ] Produce a review list for existing requests created from obsolete or ambiguous calculation rows.
- [ ] Keep all cleanup actions preview-only until director confirmation.

### Phase P4: Supply Reconnection

- [ ] Create requests only from confirmed material identities with project, package, estimate, and source-row lineage.
- [ ] Add an idempotency key for batch creation and prevent repeated requests for the same uncovered quantity.
- [ ] Verify supplier, KP, delivery, invoice, warehouse, and accounting linkage end to end.

### Phase P5: Performance And Cutover

- [ ] Calculate the projection once per estimate/material/norm revision and cache it outside React render paths.
- [ ] Load large projects by work package and paginate detail rows.
- [ ] Run shadow comparison, profile browser responsiveness, deploy incrementally, and switch only after smoke checks pass.

### Safety Rules

- No destructive migration or request deletion in P1-P2.
- Incoming warehouse documents remain receivable when matching is uncertain; uncertainty becomes review state.
- Raw estimate resource rows remain immutable and available as the audit source.
- Each phase is an independent commit and rollback point.
