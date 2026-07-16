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
- [x] Task M6.2d6: Add opt-in protected rendering to `PhotoAttachmentField` and enable it only in the work-journal edit form, preserving every other caller. Deployed in `8805175b`; public, authenticated file, and prorab work-journal edit checks passed.
- [x] Task M6.2d7: Enable protected preview only for the two master work-submission photo fields with `context="work-journal"`, preserving their compatibility upload contract and every other master form. Deployed in `7c0d2570`; public, authenticated file, and master-cabinet browser checks passed.
- [ ] Task M6.4: Scope company messages, estimate versions, changes, and estimate chat by stored company or verified project/estimate parents. Company messages, estimate versions, estimate chat, and the read-only estimate-change ownership audit are complete; stored ownership and runtime scoping for `unexpected_works` remain.
- [x] Task M6.4a: Scope the existing company `/messages` list, create, and mark-read routes by selected company while preserving one explicitly marked legacy fallback. Deployed in `38d67411`; migration, public/negative API checks, and authenticated browser chat passed.
- [x] Task M6.4b: Add a read-only legacy company-message ownership report with fail-closed candidate classification and no backfill. Released in `d81939d5`; production reported one ready row and identical before/after counts.
- [x] Task M6.4c: Backfill only revalidated unambiguous company-message rows, remove the runtime legacy fallback, isolate chat attachments, and synchronize frontend chat state with the selected company. Deployed in runtime `44380a2a`; atomic backfill, zero-legacy post-check, strict API scope, and authenticated chat UI passed.
- [x] Task M6.4d: Scope estimate-version list and direct-detail reads through tenant context and a verified parent estimate, preserving effective per-company roles and worker sanitizing. Deployed in `b79ae5d2`; public, health, read-only API, and cleanup checks passed.
- [x] Task M6.4e: Scope estimate-chat history, AI message creation, and clear-history through the selected company and verified estimate parent; invalidate stale frontend chat state on company changes. Deployed in `cf006af7`; request-race hardening followed in `80f1e8df`, with production no-write API and browser checks passing.
- [x] Task M6.4f: Audit `unexpected_works` ownership using stored IDs, estimate parents, and only globally unique legacy project names without reading business content or changing rows. Production dry-run on `80f1e8df` classified all `4` rows as ready for company `1` / project `1`, with no review rows and `writesAttempted=0`.
- [x] Task M6.4g: Add a separately reviewed, reversible ownership migration for `unexpected_works`, guarded by the exact production audit counts; do not change runtime CRUD in the migration slice. Deployed in `e8003a1d`; guarded apply stored all `4` owners, post-audit is clean, and business fields remained byte-for-byte equivalent by hash.
- [x] Task M6.4h: Make only `POST /unexpected-works` resolve one concrete company/project and store `company_id/project_id`, so new rows cannot become invisible when strict reads are enabled; keep every existing-row mutation and AI/reconcile flow unchanged. Deployed in `ab9d9bf0` and included in runtime `3aa3bba4`.
- [x] Task M6.4i: Scope only `GET /unexpected-works` by stored company/project ownership and effective tenant role while preserving its response shape and every remaining route. Deployed and verified read-only in runtime `3aa3bba4`.
- [x] Task M6.4j: Scope direct `PUT/DELETE /unexpected-works/{id}` by the selected-company actor and exact stored owner; carry `company_id` into the approval-created work journal. Deployed and verified in runtime `52ec9af4`.
- [x] Task M6.4k: Scope `/estimates/{id}/include-changes` and `/estimates/{id}/reconcile-changes` through one verified estimate/project owner and update only same-owner change IDs. Deployed and verified in runtime `52ec9af4`.
- [x] Task M6.4l: Scope estimate-reconciliation CRUD and its unexpected-work candidates through verified estimate parents instead of project names. Deployed and verified in runtime `6648dd738d23` after a clean production audit.
- [x] Task M6.4m: Scope `/unexpected-works/{id}/ai-estimate` and `/unexpected-works/limit-check` by stored ownership and selected-company read context. Deployed and verified in runtime `26818ea40322`.
- [x] Task M6.5a: Audit `work_journal` ownership through its unique project and explicit estimate, unexpected-work, and brigade-contract parents without changing rows. Production report verified all `8` rows with no backfill or review.
- [x] Task M6.5b: Make direct `POST /work-journal` resolve one selected company/project and store `company_id`; deployed and verified in runtime `e74dafc5d0f6`.
- [x] Task M6.5c: Scope `GET /work-journal` by stored owner and effective per-company role while preserving project/package/worker/customer filters and money masking. Deployed and verified in runtime `2a559a9149fe`.
- [x] Task M6.5d: Scope direct `PUT/DELETE /work-journal/{id}` through one selected-company actor and the exact stored journal/project owner; deployed and verified in runtime `0f0575f69aaa`.
- [x] Task M6.5e: Scope `POST /work-journal/{id}/ai-prefill` by stored owner before the AI call and repeat the owner lock before saving the AI result. Included in production runtime `8ef743a6`; protected owner smoke remains grouped with the final M6 verification.
- [x] Task M6.6a: Audit ownership of `project_ai_summary`, `ai_findings`, `ai_tasks`, `ai_task_reports`, and `ai_task_attachments` without changing runtime or rows. Production verified all `3382` retained rows with `unresolved=0`, `mismatched=0`, and `writesAttempted=0` after guarded smoke cleanup.
- [x] Task M6.6b1: Add and guarded-backfill `project_ai_summary.company_id/project_id` from the exact unique project parent without changing runtime. Production migrated `1` row and the post-audit is strict-ready.
- [x] Task M6.6b2: Scope only `GET/POST /project-ai-summary` through one selected company and stored company/project owner; preserve the response and summary payload. Production runtime `b155491cab86` and public smoke passed.
- [x] Task M6.6b3: Remove the legacy global primary key on `project_name` only after M6.6b2 is live, preserving unique `(company_id,project_id)` so different companies may use the same project name. Production cutover and post-audits passed on runtime `1dbd04db211a`.
- [x] Task M6.6c1: Add and guarded-backfill `ai_findings.company_id/project_id` through exact project and supported linked-entity parents without changing findings runtime. Production migrated all `1342` rows and post-audit is strict-ready.
- [x] Task M6.6c2: Scope `ai_findings` list/create/update, upsert/dedupe and stale-close through stored owner; validate supported polymorphic entity parents fail-closed. Production runtime `88fbc832a5b1`, protected smoke and post-audit passed.
- [x] Task M6.6d1: Add guarded `ai_tasks` ownership with explicit `company` or `platform` scope without changing task runtime. Production migrated all `2039` rows and post-audit is strict-ready.
- [x] Task M6.6d2a: Make every company/platform task insert and AI upsert persist and constrain stored owner. Production runtime `337fdba2ffc3`; post-audit strict-ready.
- [x] Task M6.6d2b: Scope direct `ai_tasks` list/create/update and assignment actions through stored owner while keeping `Система` in platform-only scope. Production runtime `337fdba2ffc3`; public smoke passed, protected smoke still requires credentials.
- [x] Task M6.6e1: Add guarded owner migration for task reports and attachments through stored task/report parents without changing child runtime. Production schema and post-audit are strict-ready with both child tables empty.
- [x] Task M6.6e2: Persist owner on report/attachment writes and scope child reads through the verified parent task. Production runtime `52cf98630067`; live assignment/report/attachment smoke and strict post-audit passed.
- [ ] Task M6.6f1: Scope single-project `/ai-control/run` and `/ai-findings/generate` through selected company, effective role and exact project owner; fail closed on duplicate name-only source scope. Production `c6dfddaa321b`, public smoke passed; protected run deferred into final M6.6 smoke.
- [ ] Task M6.6f2: Scope `/ai-control/run-all` and automatic event runs; finish with combined protected single/batch/event and negative cross-company smoke. Production runtime `8ef743a6a7d6`; public smoke passed, combined protected smoke deferred.
- [x] Task M6.7a: Audit ownership candidates for `messenger_files` and `messenger_outbox` through exact project/entity parents and verified recipient memberships without changing rows. Production found `8` unresolved outbox rows: `5` deleted supply parents and `3` ownerless channels; no writes.
- [x] Task M6.7a1: Distinguish deleted supported parents from unsupported entity types and expose recipient-company evidence without accepting it as ownership. Production confirmed `5` orphan supply notifications and `3` ownerless channel notifications, all without recipient-company evidence.
- [x] Task M6.7a2: Expand the read-only audit to `messenger_channels` and outbox operational status; register global messenger account/channel routes before schema work. Production found four ownerless internal channels, three sent channel messages and five failed orphan supply messages.
- [x] Task M6.7a3: Fix `smoke:supply-chain` cleanup so every generated request removes its own MAX outbox rows before the request parent. Released in `9991ee5d`; production cleanup verification remains grouped with the next supply smoke.
- [x] Task M6.7b: Add guarded nullable company/project ownership migration for messenger channels with explicit operator mappings, expected count and SHA plan. Production migrated all `4` channels to company `1`; post-audit is strict-ready.
- [x] Task M6.7c: Make the read-only messenger ownership audit consume stored channel ownership and propagate it to channel outbox diagnostics. Production verified `7` company-owned rows and left only `5` failed deleted-parent rows unresolved.
- [x] Task M6.7d1: Add guarded owner scope migration for messenger files/outbox; preserve explicitly selected failed deleted-parent rows as terminal legacy history. Production migrated all `8` rows and the post-audit is strict-ready.
- [x] Task M6.7d2a1: Persist exact company/project owner on internal MAX file and outbox writes using stored entity owner or active employee memberships. Production runtime `e6f4934859bc`; public smoke and strict item-ownership audit passed.
- [x] Task M6.7d2a2: Persist exact owner on supplier-KP and marketing-publication outbox writes and on authenticated messenger-channel upsert. Production supply and marketing publication smokes passed on runtime `2a9c48f18e54`; strict item-ownership audit remains clean.
- [x] Task M6.7d2b1: Scope authenticated `/messenger-outbox` reads to stored company-owned rows visible through the selected company context and effective leadership role. Production runtime `1cc73b4de724`; protected selected-company and cross-company smoke passed.
- [x] Task M6.7d2b2: Restrict bot-token outbox list/summary/dispatch/status to stored company-owned rows and lock real dispatch selection with `FOR UPDATE SKIP LOCKED`. Production `smoke:max-bot-adapter` passed with company owner, terminal legacy exclusion and dispatch dry-run.
- [x] Task M6.7e1: Audit shared `messenger_accounts` identities through active user memberships or stored staff company without adding `company_id` to the identity row. Production report is strict-ready with zero account rows and no unresolved/ambiguous identities.
- [x] Task M6.7e2: Scope authenticated `/messenger-accounts` list/upsert through selected-company leadership and target employee memberships while keeping one shared messenger identity. Production runtime `3944b80d39a4`; protected account smoke, cleanup, strict ownership audit and public production smoke passed.
- [x] Task M6.8a1: Audit legacy `audit_log` ownership through exact project/entity parents, active actor memberships and explicit platform identity events without changing rows. Production report found `910/1037` verified, including `800` platform and `110` company rows; `127` deleted-parent rows need an explicit legacy decision, with no ambiguous or mismatched owners.
- [x] Task M6.8a1b: Prevent `smoke:platform-crm` from leaving ordinary audit-log orphans and add stable review counts/SHA to the read-only report. Released in `6620cb35`; the stable production review set was used by the guarded migration.
- [x] Task M6.8a2: Add and apply the guarded nullable owner migration for `audit_log`. Production migrated all `1037` rows into `110 company + 800 platform + 127 legacy`; post-audit is strict-ready with zero unresolved, ambiguous or mismatched rows.
- [x] Task M6.8a3: Persist owner scope on every new audit event and restrict `/audit-log` to company-owned rows allowed by the selected company context. Production protected activity-log smoke and strict migration audit passed.
- [x] Task M6.8b1: Add a read-only ownership report for `api_errors` before changing schema, writers or `/system-status`. Production classified `76/94` rows as company `1` and left `18` inactive/missing actor rows for explicit legacy review; no ambiguous or mismatched rows.
- [x] Task M6.8b2: Add and apply a guarded nullable owner migration for `api_errors`, accepting the exact production review set only by SHA. Production migrated `94/94` rows into `76 company + 18 legacy`; strict post-audit and public smoke passed.
- [x] Task M6.8b3: Persist exact owner on middleware and client-error writes, and tenant-filter all `api_errors` counts/list reads in `/system-status`. Runtime `f1842f19`, nginx proxy guard, protected ownership smoke, strict post-audit and full production smoke passed.
- [ ] Task M7: Run dry-run backfill, add database constraints/indexes, and verify the pilot tenant matrix.
- [x] Task M7a: Add a fail-closed read-only tenant readiness report over the M6 registry and stored owner columns. Initial production report completed with zero writes and no orphan/mismatched stored owners; optional empty project columns no longer create false index blockers.
- [x] Task M7b: Add a guarded, reversible index-only migration for the verified `work_journal(company_id, project)` gap. Production readiness now reports the project index present and zero schema blockers; runtime ownership release remains a separate registry blocker.
- [x] Task M7c: Add a fail-closed read-only coverage report that compares every public database table with the M6 tenant registry before constraints. Current production coverage: `127` tables, `49` registered physical tables and `78` unregistered (`25 critical`, `26 high`, `27 unclassified`); registry freeze remains blocked.
- [x] Task M7d: Register the three CRM tables as explicit blockers and add a PII-free read-only ownership report over exact project and lead parents. Production found one standalone lead without project owner and no child rows; zero rows were changed.
- [x] Task M7e: Add and apply a guarded nullable CRM ownership migration with explicit standalone-lead mapping, exact count/SHA guards and strict post-check. Current production audit is strict-ready with one stored lead and no legacy, unresolved or mismatched rows.
- [x] Task M7f1: Persist exact CRM owner on authenticated, public-site, MAX, document and task writes. Runtime `d97e88b5`; full platform/public CRM smoke, all five public lead types, self-contained MAX marketing smoke with verified cleanup, deploy smoke and strict audit passed.
- [x] Task M7f2: Reads, mutations, approvals/invites/transfers and both project-creation URLs enforce stored ownership. Runtime `f8c66354`, protected CRM smoke (`projectCreationOwnershipChecked=true`, six foreign workflow `403`) and strict audit passed.
- [x] Task M7f2a-legacy: Compatibility `GET /crm-leads` is scoped through effective CRM company roles; negative production smoke confirmed legacy isolation.
- [x] Task M7g: Register `file_ownership` and `public_lead_uploads`; production read-only audit verified all `11/11` rows with zero unresolved/mismatched and coverage dropped to `82` unregistered tables.
- [x] Task M7h: Register `company_supplier_links` and audit exact company/global-supplier/optional platform-account ownership without reading supplier or contract data. Production confirmed the table is empty, strict-ready and unchanged (`unresolved=0`, `mismatched=0`, `writesAttempted=0`).
- [x] Task M7i: Register `supply_requests`, `supply_request_recipients` and `supplier_offers`, then audit their exact stored company/project/request ownership. Production guarded cleanup removed the exact `25` orphan children; strict post-audit verified `1628/1628` rows.
- [x] Task M7i1: Diagnose the `25` orphaned core-supply children and their downstream references read-only. Production matched the exact source SHA: `16` have no references and `9` point only to five preserved terminal legacy MAX outbox rows; no business-document or owner-mismatch links exist.
- [x] Task M7i2: Guarded production cleanup deleted the exact `17` orphan recipients and `8` orphan offers, preserved terminal legacy MAX outbox `30/32/34/36/38`, and passed strict post-audits.
- [x] Task M7j: Register and audit `supplier_invoices` and `supply_deliveries`; production read-only post-audit verified `53/53` rows with no review rows.
- [x] Task M7k: Register and audit `warehouse_invoices` and `warehouse_history`; production read-only post-audit verified `404/404` rows with no review rows.
- [ ] Task M7k1: Separate supplier documents from inventory-only main-warehouse receipts. Local backend policy, director/deputy UI, accounting exclusion and targeted production smoke are complete; production deploy and smoke remain pending.

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
- [x] Task 15.2: Build the frontend outside the live nginx directory, publish assets before an atomic `index.html` swap, and reject overlapping deploys. Deployed through `3e20b60e`; the Linux publisher tests, production smoke, lock probe, and a 180-second zero-error monitor passed.

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
