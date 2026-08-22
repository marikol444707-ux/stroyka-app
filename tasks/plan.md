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
- [x] Task M7k1: Separate supplier documents from inventory-only main-warehouse receipts. Production runtime `2f5ac37717cb` passed public and protected smoke; the temporary receipt, stock, history and supplier rows were removed and the QA user was disabled.
- [ ] Task M7l: Audit and migrate `tools`, `tool_history`, and inventory ownership before a second company uses the shared warehouse module.
- [x] Task M7l1: Add a no-write ownership report for `tools`, `tool_history`, `inventory`, and `inventory_items`; it accepts only exact project/parent chains and leaves empty or ambiguous legacy scope for review. Production audit found three company-wide main-warehouse tools, explicitly confirmed for company `1`.
- [x] Task M7l2: Add the guarded schema/backfill migration for explicitly confirmed company-wide tools, then run the production dry-run and apply only with its exact row count and SHA-256 plan. Production applied 2026-08-03: `tools` 3 stored rows, child tables empty, zero unresolved/ambiguous/mismatched rows.
- [x] Task M7l3: Enforce selected-company owner filtering and owner-stamped writes for tools, history and inventory without altering operational status/location data. Production runtime `5ff69f3d` passed protected smoke: company-owned tool, inherited history, project inventory, inherited item and all-companies write rejection; cleanup, strict audit and deploy smoke passed.

### Checkpoint: SaaS Boundary

- [x] One user with two companies cannot mutate in `Все компании`. Production `smoke:platform-crm` passed on 2026-08-03: selected-company isolation for tools, inventory and CRM was verified across two companies in one `platform_account`; aggregate writes were rejected.
- [x] Two independent `platform_account` tenants cannot see or address each other's companies. Production `smoke:platform-crm` passed on 2026-08-03: a temporary director of account `2` was given a deliberately invalid membership in company `1` of another account; both tools and CRM rejected selected-company access with `403`.
- [x] Supply request, KP recipient, supplier invoice, delivery, warehouse invoice, and warehouse history keep the same `company_id`. Production runtime `97fc1dd8` passed protected `smoke:supply-chain` on 2026-08-03; the exact receipt lineage was company `1`, delivery `15`, warehouse invoice `138` and both linked history rows.
- [x] Remaining legacy fallback rows are audited before strict cutover. Production `npm run audit:legacy-fallback` passed on 2026-08-03: all `39/39` rows across projects, staff, estimates, brigade contracts and acts have verified stored ownership; `fallback=0`, `unresolved=0`, `needsReview=[]` and the read-only transaction rolled back.

### Phase 3: Backend Reliability

- [x] Task 12: Extract auth/session helpers from `backend/main.py` into `backend/auth.py`. Released and verified in production 2026-07-27 (runtime `a82edc9`): 37 pure auth/session primitives moved verbatim (−170 lines in `main.py`), call sites untouched via import-back; `py_compile`, full backend suite (755), pyflakes parity, `smoke:prod` and full `smoke:auth-session` all pass.
- [x] Task 13: Extract audit/client-error route group into a small backend feature module. Released 2026-07-27 (runtime `b8c0fb5`): `/audit-log` was already extracted by M6.8a3; this slice moved `POST /client-errors` and `GET /system-status` into `backend/features/api_error_ownership/routes.py` with deps-injection registration; deploy smoke and direct route checks pass, `main.py` is down to 31,263 lines (−362 today).
- [ ] Task 14: Move one low-risk `init_db()` schema slice into Alembic.
- [x] Task 15: Add a minimal CI workflow for backend compile, frontend tests, and frontend build. Completed 2026-07-27: `ci.yml` now also runs full backend unittest discovery (`755` tests) and the frontend jest suite (`247` tests) on every push and pull request; first extended run finished green on `8540cf56`.
- [x] Task 15.1: Apply only compatible frontend security updates without `--force`; latest lock refresh pins transitive `websocket-driver@0.7.5`, with clean `npm ci` reporting zero critical findings and `28` total advisories.
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

### Phase 5: Session UX And Data-Entry Guardrails (added 2026-07-27)

Priority note: the tenant-isolation queue (M6.6f, M6.7, M6.8a, M7l) stays first. The tasks below are independent, small, and can be picked up between isolation slices.

- [x] Task U1: Show a clear expired-session state in the frontend instead of silent zeroed data; offer re-login without wiping local state. Found already implemented during the 2026-07-27 review (`expireFrontendSession` in `src/api.js` plus the login-screen notice in `useAppShellState.js`); the review added the missing double-401 expiry jest test.
- [x] Task U2: Warn on unparseable numbers during estimate import instead of silently coercing them to `0`. Completed 2026-07-27 inside the deterministic quality engine (`estimateQualityRows`): a non-numeric quantity now yields a critical `Нечитаемое количество` row quoting the original text, at import time and on every later open of the estimate; `toNum()` itself is untouched.
- [ ] Task 13.1: Continue extracting route groups from `backend/main.py` domain by domain after Task 13 proves the pattern; smallest domains first, one domain per slice.

### Checkpoint: Guardrails

- [ ] Expired session shows an explicit message and a re-login path in a manual smoke.
- [ ] Import of a file with a non-numeric quantity produces a visible warning row, not a silent `0`.
- [ ] `backend/main.py` line count decreases with each extraction slice while the full backend suite stays green.

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

## Focused Track: Bank Sync Platform (T-Bank pilot)

Full plan: docs/tbank-integration-plan.md. Multi-tenant bank statement sync as a platform feature: per-company connection (director enters a read-only-scope token in company settings), adapter architecture (T-Bank first, Tochka/Modulbank/Alfa/Sber later, converging on the CBR Open API standards mandated from 2026), unified bank_operations table with company_id scoping, matching engine (counterparty INN / payment purpose markers / amount+date) driving auto project_payments and paid-status on acts and supplier invoices.

- [ ] Task B1: Sandbox module `backend/features/bank_sync/` — adapter interface, T-API client against the sandbox, additive schema (company_bank_connections, bank_operations), tests. No production access, no owner action needed.
- [ ] Task B2: Company connection UI + manual statement pull (write-only token field in company settings; requires owner's T-Business token to go live).
- [ ] Task B3: Matching v1 + unmatched-operations screen + auto project_payments (DB-additive; confirm with owner before prod migration).
- [ ] Task B4: Webhook real-time sync (nginx location!) + auto paid-statuses + per-project bank line on dashboard.
- [ ] Task B5+: self-employed receipts (НПД), then payment drafts — each gated on explicit owner approval.

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

- [x] Add a pure no-write comparator for legacy and corrected projection rows, including quantity, added/removed identity and legacy aggregate split detection.
- [x] Show the read-only comparison inside the opened project's material control, with old/new quantities and split source identities; no apply action is exposed.
- [x] Add a read-only review of active supply-request items for the opened project, flagging proven legacy aggregates, missing identities, ambiguous names and unit/package mismatches.
- [x] Compare old/new quantities and row identities for every active project without changing business records.
- [x] Produce a read-only, item-level review list for existing active requests created from obsolete or ambiguous calculation rows.
- [x] Keep all cleanup actions preview-only until director confirmation.
- [x] Route recognized supplier containers (cable coils, metal bundles, bags, boxes, drums and canisters) through one confirmed packaging rule with normalized base units; old receipts remain preview-only.
- [x] Add director/deputy manual review confirmation with server-recomputed evidence and audit log; it never changes stock, invoices or history.
- [ ] Add a stock-affecting packaging correction only after future movements obtain a direct invoice-line link and a separate reconciliation design is approved. The design is recorded in `docs/material-packaging-stock-correction.md`: first receipt lots and lot movements for new data, then one reversible, director-confirmed correction; historical aggregate stock remains manual-only.
- [x] Add a read-only receipt-to-movement traceability report before changing warehouse movement schemas or stock data.
- [x] Persist a verified receipt-line source for new object/main warehouse receipts and invoice-selected transfers; protected smoke verifies the main-warehouse receipt path. Generic warehouse movements remain a separate source-linking slice.
- [x] Add an optional explicit receipt-line selection to new warehouse movements, with server validation of company, source location, material, unit and remaining linked quantity. Old movements remain untouched.
- [x] Show read-only packaging traceability state in the historical correction preview; a matching name never substitutes for a saved invoice-line source.
- [x] Add a director/deputy read-only registry of historical packaging reviews with immutable review evidence.
- [x] Require an explicit non-stock decision for each new historical packaging review; legacy reviews remain unclassified.
- [x] Add protected smoke coverage proving a packaging review records the decision without changing stock or the invoice item.
- [x] Start receipt lots for new warehouse receipts without rewriting historical stock. Production runtime `9a90bf19` passed protected `smoke:main-warehouse-receipt`: a temporary inventory-only receipt created a company-owned lot with the exact invoice line, normalized quantity and available balance; cleanup removed the smoke rows.
- [x] Consume exact receipt lots for new invoice-selected warehouse movements. Production runtime `821c24f0` passed protected `smoke:receipt-lot-movement` on 2026-08-03: a temporary project receipt created one lot, the project-to-main movement consumed only that lot, and its source line plus immutable lot movement matched the created warehouse movement; cleanup removed all smoke rows.

### Phase P4: Supply Reconnection

- [x] Create requests only from confirmed material identities with project, package, estimate, and source-row lineage. Production runtime `30563c87` passed protected single/batch smoke against active estimates, including stale-line rejection and cleanup.
- [x] Deploy the strict lineage slice and verify single/batch material-control request creation against production estimates.
- [x] Add an idempotency key for batch creation and prevent repeated requests for the same uncovered quantity. The exact estimate source coordinate is transaction-locked while an active request exists; protected production smoke verifies the `409` duplicate rejection.
- [x] Verify supplier, KP, delivery, invoice, warehouse, and accounting linkage end to end. Production `smoke:supply-chain` passed on 2026-08-02: recipient scope, KP notification, supplier response, tenant invoice/delivery, warehouse receipt, history, accounting dedupe and supplier duplicate-group reads; cleanup removed all QA rows.
- [x] Recalculate saved estimate control for open supply requests when an active estimate is created, materially changed, or activated; preserve request quantity, status, suppliers, and closed history.

### Phase P5: Performance And Cutover

- [x] Calculate the projection once per estimate/material/norm revision and cache it outside React render paths. Production runtime `b111c476` includes `28a4a7bf`; focused cache tests and build passed.
- [x] Load large projects by work package and paginate detail rows. Production browser smoke on 2026-08-02 opened `Кисловодск Лицей 4` with `889` material positions while rendering the first `80` only.
- [x] Run shadow comparison, profile browser responsiveness, deploy incrementally, and switch only after smoke checks pass. Production browser smoke on 2026-08-02 verified identical cold/warm projections for `Кисловодск Лицей 4` (`80/889` rows). After the protected detail batch in `a9ef55af`, the cold opening was `3.923 s`, warm repeat `3.697 s`, and the only post-click estimate request was `/estimates` (`308 ms`), replacing the prior fan-out of per-estimate requests.

### Safety Rules

- No destructive migration or request deletion in P1-P2.
- Incoming warehouse documents remain receivable when matching is uncertain; uncertainty becomes review state.
- Raw estimate resource rows remain immutable and available as the audit source.
- Each phase is an independent commit and rollback point.

## Focused Track: Estimate Revision Lineage

- [x] Task E1: Compare full old/new estimate rows, print only changed positions, and add one project-wide summary across estimate packages.
- [x] Task E2: When an existing draft is activated, save a server reconciliation before background AI comparison; direct imports also load full revisions before comparison.
- [x] Task E3: Add immutable source estimate/version ownership to brigade assignment rows and prevent a new revision from overwriting historical quantities or manual brigade prices. Completed in production through runtime `cb1b59341c5e`; all `151` historical rows remain explicit legacy records, every runtime writer uses the reviewed source contract, strict catalog/data/delete gates are green, and the final audit was read-only and rolled back.
  - [x] Task E3.1: Add a read-only, rolled-back lineage audit and record the minimal immutable source contract; do not change schema or runtime writers.
  - [x] Task E3.2: Add nullable lineage/snapshot columns, explicit legacy classification and production data audit without enabling strict runtime; verify/hash each distinct snapshot once and fail closed on excessively nested snapshot JSON. Production migrated all `151` legacy rows without conflicts and deployed runtime `857b0b622de9` with public smoke passing.
  - [x] Task E3.3: Cut every assignment writer over atomically, preserve issued quantity/manual brigade price, remove fuzzy matching and add idempotency. Production runtime `6f5ab8a4430a` passed the full public smoke and reported writer readiness with exactly `3` INSERT and `3` UPDATE statements and zero violations.
    - [x] Task E3.3.1: Add the inert, tenant-bound batch resolver that locks one exact estimate, creates or reuses one canonical immutable snapshot and validates only exact row coordinates/keys; do not connect runtime writers yet.
    - [x] Task E3.3.2: Cut all assignment writers over to explicit estimate/manual/pricelist origins, exact immutable coordinates and idempotent insert-only issuance; add a bounded static writer audit. Production runtime `6f5ab8a4430a` passed deployment smoke and the post-deploy writer audit on 2026-08-06.
  - [x] Task E3.4: Add FK/CHECK/index/immutability and delete-restriction gates, then prove writer and constraint readiness before enforcement.
    - [x] Task E3.4.1: Add a read-only, rolled-back constraint/default/index/trigger/data preflight plus a static estimate-delete policy audit; do not execute DDL or change runtime mutation behavior. Production runtime `4247630c92bb` completed the read-only audit; after backed-up removal of 13 orphaned versions, every aggregate integrity counter is zero and the remaining gaps are catalog enforcement plus the known delete-policy gap.
    - [x] Task E3.4.2: Fix exact estimate deletion blocking and apply the separately guarded, idempotent strict-lineage schema only after E3.4.1 production evidence is reviewed.
      - [x] Task E3.4.2a: Follow stored `source_estimate_version_id` exactly during estimate deletion and scope compatibility-key matching to explicit `legacy` rows. Production runtime `ce1f568d3cdc` passed public smoke and the rolled-back audit with `deleteRestrictionsReady=true`, no deletion-policy violations and every integrity count at zero.
      - [x] Task E3.4.2b: Apply the separately reviewed guarded FK/CHECK/index/trigger/default migration only after E3.4.2a is production-green. Production runtime `cb1b59341c5e` passed public smoke; the reviewed 13-change plan applied successfully and the final rolled-back audit reports every catalog, data, writer and delete-policy gate green with all 151 explicit legacy rows preserved.
- [x] Task E4: Build a reviewed `old row -> new row` transfer that moves only uncompleted assignment and open-request balances; never move confirmed JPR, signed acts, warehouse history or payments. Production runtime `dc0f86558ecf` passed the full public smoke and the rolled-back read-only cutover report with `readyForCutover=true`; production remains empty of transfer plans and receipts, so no business transfer was manufactured for verification.
  - [x] Task E4.1: Add a tenant-bound, read-only impact audit for one approved reconciliation; report only exact candidate IDs/coordinates, transferable quantities, protected-history counts and fixed blockers. Production runtime `2c816ccb789e` passed public smoke; all 13 stored reconciliations are drafts, and draft `#15` failed closed read-only with `reconciliation_not_approved`, zero writes and rollback.
  - [x] Task E4.2: Add an inert reviewed-mapping ledger and draft/approve API with exact owners, source/target snapshots, explicit quantities and deterministic plan hash; do not move balances yet. Production runtime `c700e043`, the reviewed 11-change strict schema, public smoke and authenticated fail-closed `404 / 409 / 404` API smoke all pass without manufacturing business data.
  - [x] Task E4.3: Apply approved assignment balances transactionally, preserving confirmed JPR links and negotiated brigade price while recording immutable before/after evidence. Production runtime `b1ff981db5be`, the exact guarded 5-change schema, repeated zero-change audit, public smoke and authenticated missing-plan `404` all pass; production has zero transfer plans, receipts or approved reconciliations, so no business transfer was manufactured for testing.
    - [x] Task E4.3.1: Extend the separately guarded schema with an immutable assignment-transfer receipt, exact entry/plan owner linkage and database mutation guards; keep deploy/init free of automatic DDL.
    - [x] Task E4.3.2: Add a leadership-only exact-hash assignment-apply endpoint that locks rows in deterministic order, recomputes confirmed JPR, rejects drift/conflicts, splits quantity without changing brigade value and returns an idempotent bounded receipt.
    - [x] Task E4.3.3: Prove rollback, concurrency, repeated apply and zero writes to JPR/acts/payments/supply/warehouse tables in real PostgreSQL before any production schema or balance action.
  - [x] Task E4.4: Attribute only unreceived open-request balances to target rows through a ledger consumed by material control; never rewrite request, delivery, warehouse or accounting history. Production runtime `bf078924852b` passed public smoke; the exact guarded five-change schema applied, its repeat audit is schema-ready with zero changes, and the read-only state check found zero plans, receipts, allocations or approved reconciliations.
    - [x] Task E4.4.1: Extend the separately guarded schema with one immutable supply-allocation receipt per reviewed entry, exact request/item/plan ownership, cumulative-balance indexes and database mutation guards; keep deploy/init free of automatic DDL.
    - [x] Task E4.4.2: Add a leadership-only exact-hash supply-apply endpoint that locks the plan, request, deliveries and prior allocations deterministically, recomputes the finite unreceived/unallocated balance, rejects drift or over-allocation and returns an idempotent bounded receipt.
    - [x] Task E4.4.3: Expose only tenant-bound allocation projection metadata with visible supply requests and make material control move the allocated open quantity to the exact target estimate coordinate while fulfilled and unallocated quantities remain on the original request identity.
    - [x] Task E4.4.4: Prove rollback, concurrent double-apply, repeated apply, cumulative allocation bounds, fail-closed projection and zero writes to request/delivery/offer/invoice/warehouse/accounting history in real PostgreSQL and frontend tests.
  - [x] Task E4.5: Add cutover/readiness audits, concurrency/idempotency integration checks and a separately reviewed production dry-run/apply sequence. Production runtime `dc0f86558ecf` reported schema and ledger ready, zero issues/writes, the complete `8`-statement writer and `6`-check integration inventory, rollback and `readyForCutover=true`.
    - [x] Task E4.5.1: Add one rolled-back read-only readiness report for the complete E4 schema, deterministic plan hashes, all-or-none per-kind receipts and exact ledger quantities; bound every issue preview and expose fixed reason codes only.
    - [x] Task E4.5.2: Add a static writer/test inventory that permits only the reviewed E4.2-E4.4 statements and requires the real PostgreSQL rollback, repeat and concurrent-double-apply cases.
    - [x] Task E4.5.3: Add an exact optional `plan_id + plan_sha256` cutover gate and document a separately reviewed production sequence; keep business apply behind the existing leadership APIs and never add a direct database apply command.
- [x] Task E5: Make active-estimate material control use stored `company_id + project_id` throughout instead of project name, then add cross-company collision tests. Completed in production on runtime `ded68df1ad00`; the final read-only audit and both public smoke runs passed.
  - [x] Task E5.1: Add a bounded, rolled-back readiness audit for project/active-estimate owner tuples and the static name-only selector/query inventory; do not change schema or runtime behavior. Production runtime `1bfae554aa47` reported clean owner data, the six expected name-scoped boundaries, zero writes and rollback.
    - [x] Task E5.1.1: Implement the read-only schema/data audit, bounded ID-only diagnostics, six-boundary static inventory and guarded dedicated-PostgreSQL fixture.
    - [x] Task E5.1.2: Deploy the inert audit command and capture production `dataReady`, six expected name-scoped boundaries, zero writes and rollback evidence.
  - [x] Task E5.2: Expose stored estimate `companyId` and cut material-control active-estimate discovery over to an exact fail-closed company/project matcher with same-name cross-company tests. Production runtime `9c8ba525932f` passed public smoke and the read-only audit reported `ownerScopedCount=1`, the expected five remaining backend boundaries, zero writes and rollback.
  - [x] Task E5.3: Propagate the exact owner through material plan/reconciliation/summary functions, tuple-key runtime caches and UI consumers without changing display names or historical data. Production runtime `fbc6374cc221` deployed atomically, remained active and passed complete public smoke; the read-only audit verified all `15/15` active estimates, zero owner-data issues or writes, rollback, and only the five expected E5.4 backend boundaries.
  - [x] Task E5.4: Version and validate material-control supply lineage with exact owner IDs, then replace backend name-only active-estimate selection and refresh queries with parameterized company/project predicates. Production runtime `d0f52ad81832` passed atomic deploy, service health, two public smoke runs and the read-only audit with all `6/6` boundaries owner-scoped, zero violations/writes and `readyForCutover=true`.
  - [x] Task E5.5: Prove rollback and same-name isolation in real PostgreSQL, add the final read-only cutover gate and run a separately reviewed production sequence. Production runtime `ded68df1ad00` remained active, both public smoke runs passed, and the final audit reported exact `5/5` writer/test inventory with zero violations/writes, rollback and `readyForCutover=true`.
- [x] Task E6: Add an explicit approved budget-adjustment event so a new estimate total can update project economics without rewriting accounting history. Completed in production on runtime `4b934847d41c`: atomic deploy, active service, both public smoke runs and the bounded read-only cutover audit passed with exact schema/data/ledger/writer/backend/frontend inventories, zero writes, rollback and `readyForCutover=true`; no reconciliation or financial event was manufactured.
  - [x] Task E6.1: Add a bounded, rolled-back baseline audit for budget precision, approved-reconciliation owner/source readiness and the existing project-budget writer surface; do not change schema, routes or business data. Production runtime `e08eddea662f` passed atomic deploy and smoke; all `4/4` budgets are conversion-safe, all `13` reconciliations have zero issues, the writer inventory is exact `3/3`, E6 DML is zero and the read-only report rolled back with no writes.
    - [x] Task E6.1.1: Test-first pure classification of project budget values and approved reconciliation candidates with fixed, ID-only, bounded diagnostics. Focused classifier tests cover exact bounds, invalid money, owner/type/package/status drift and bounded output.
    - [x] Task E6.1.2: Add the repeatable-read zero-write database collector and `audit:project-budget-adjustments` command, including exact catalog/type reporting and hard scan limits. The local older database failed closed without writes while the complete backend suite remained green.
    - [x] Task E6.1.3: Add a static inventory that recognizes only the reviewed existing manual budget writers and proves E6 has no runtime writer before schema review. It reports the exact existing `3/3` project-budget writers and zero E6 DML, including split-static-SQL evasion coverage.
    - [x] Task E6.1.4: Deploy the inert audit, pass public smoke and capture the bounded production precision/source/writer report with `writesAttempted=0` and rollback before planning E6.2 schema changes. Runtime `e08eddea662f` returned `readyForSchemaPlan=true`; no schema or business data changed.
  - [x] Task E6.2: Add deterministic decimal plan/hash logic and a guarded additive schema plan for exact project money plus immutable adjustment receipts; keep startup initialization and runtime mutation unchanged. Production runtime `fecbe019380b` applied the exact reviewed 7-change plan, then reported zero remaining changes, exact `NUMERIC(14,2)`, clean data/writer audits, active service and complete public smoke.
    - [x] Task E6.2.1: Implement and test canonical two-decimal normalization, delta/before/after rules, zero-delta no-op and deterministic SHA-256 planning. The pure kernel has no DB/runtime dependencies, uses canonical money strings and passes golden-hash, signed-zero, range and fixed-error tests plus the full backend regression.
    - [x] Task E6.2.2: Add an idempotent dry-run/apply schema tool for a lossless `projects.budget -> NUMERIC(14,2)` conversion, receipt table, restrictive FKs, checks, indexes and immutability trigger. The local dry-run reports 7 reviewed changes with zero writes and rollback; an execute/post-check/rollback PostgreSQL proof reaches zero remaining changes without persisting schema.
    - [x] Task E6.2.3: Apply only the exact reviewed production change count/hash after E6.1 reports all stored values safe, then repeat the audit with zero remaining changes. The guarded apply committed all 7 statements for SHA `6ee2d241…57f3d0`; repeat audit returned `changeCount=0`, no blockers and rollback.
  - [x] Task E6.3: Expose an authenticated, tenant-bound read-only preview for one approved customer reconciliation; recompute exact current source evidence but attempt zero writes. Production runtime `39af888a3ee5` passed atomic deploy, service health, two public smoke runs and both read-only readiness audits; the preview route failed closed with `401`, all `7/7` active-estimate boundaries were owner-scoped, exact budget schema/data remained ready and E6 runtime DML remained zero. No genuine approved reconciliation existed, so no production data was manufactured for a successful preview.
    - [x] Task E6.3.1: Add the fail-closed preview service/storage boundary with exact owner/package/type/active-revision and total-drift checks. The source read is a single parameterized company-bound query, totals are independently recomputed with bounded Decimal parsing, and foreign/missing IDs are indistinguishable.
    - [x] Task E6.3.2: Register the bounded preview route, response allowlist and unauthenticated production smoke contract without enabling approval. The route is leadership-only, repeatable-read/readonly, always rolls back, and registers no POST or runtime DML.
  - [x] Task E6.4: Add leadership-only exact-hash approval that atomically inserts one immutable event and applies its delta once, plus tenant-bound adjustment history. Production runtime `b3ffc00a4a80` passed atomic deploy, service health, public smoke and the complete read-only readiness report with exact schema/data/ledger/writer/route/integration gates, zero writes, rollback and `readyForCutover=true`.
    - [x] Task E6.4.1: Prove the transactional kernel in dedicated PostgreSQL, including deterministic locks, rollback, stale hash, source drift, concurrent double approval, idempotent repeat and unchanged protected history. The local kernel requires `SERIALIZABLE`, locks tenant/source state in deterministic order, revalidates exact totals/hash, performs only the reviewed receipt insert plus guarded budget update, and passed all `6/6` real-PostgreSQL scenarios with one receipt/delta under concurrency and unchanged SHA-256 history across 21 protected tables.
    - [x] Task E6.4.2: Register approval/history routes with server-resolved director/deputy authorization and fixed error codes; ordinary manual initial budget editing remains available. The local POST accepts only the exact preview hash, executes the E6.4.1 kernel in `SERIALIZABLE`, commits only a new receipt and rolls back idempotent/error paths; the leadership-only history GET is company-bound, read-only, newest-first and cursor-paginated with a hard 100-row page cap. Real FastAPI boundary tests preserve fixed validation codes, public smoke covers both routes, focused/full regressions and the production build pass, and no production deploy or business-data write occurred.
    - [x] Task E6.4.3: Add the exact writer/test inventory and rolled-back ledger readiness gate before production enablement. The local gate hard-caps receipt scanning, returns fixed ID-only diagnostics, recomputes every stored plan hash and money equation, verifies current owner/source links, and requires the exact `3` routes, `2` registrations, `3` public smoke checks, single approval-kernel entrypoint and `13` integration proofs. A dedicated PostgreSQL run passed `7/7`, including a green read-only final gate with unchanged receipt count.
  - [x] Task E6.5: Add an explicit preview/confirm/history UI for authorized leaders, with no automatic apply during reconciliation approval or estimate activation. Runtime `4b934847d41c` deployed the UI after `31/31` focused tests, `342/342` full frontend tests and desktop/mobile Chromium verification with zero console errors; production smoke covers all three authenticated E6 routes.
  - [x] Task E6.6: Run final focused/full tests, real-PostgreSQL concurrency and protected-history proofs, build, deploy smoke and read-only production cutover audit; never manufacture a production reconciliation. Runtime `4b934847d41c` passed atomic deploy, service health and both public smoke runs. The production audit was read-only and rolled back with `writesAttempted=0`, exact frontend wiring `11/11`, named UI/action proofs `17/17`, no issues and `readyForCutover=true`; production still has zero approved reconciliations and zero adjustment receipts.

## Focused Track: Safe Agent Automation

- [x] ~~Task A0.1: Make every existing director-agent read tool fail closed and constrain projects, warehouse, supply, estimates, finances, staff and AI tasks to the server-resolved company context. Focused tests, full backend suite, frontend tests/build and a manual no-write dry-run passed.~~
- [x] ~~Task A0.2: Deploy A0.1 and verify production authentication, protected API reads and blocked aggregate-company access on runtime `3c0f09fa6396`; two-company isolation and empty-context no-query behavior remain covered by the focused regression suite and manual no-write dry-run.~~
- [x] ~~Task A1: Add a durable background job/outbox with tenant context, idempotency, retries, status, audit and failure isolation from normal application work. Queue storage, lifecycle, tenant status/cancel APIs and the separate runner are production-verified; the permanent process remains disabled until A3.~~
- [x] ~~Task A1.1: Add the local `agent_jobs` schema, company/project-scoped idempotent enqueue validation, actor membership and sensitive-payload guards, plus a read-only readiness report. Focused tests, full backend/frontend tests and production build pass.~~
- [x] ~~Task A1.2: Deploy the schema and verify `npm run audit:agent-jobs` reports the complete empty schema, zero invalid rows and `readyForWorker=true`.~~
- [x] ~~Task A1.3: Add a separate claim/lease worker with heartbeat, bounded retry/backoff and stale-job recovery so AI failure cannot block HTTP work. Lifecycle and the separate process are production-verified without enabling a daemon.~~
- [x] ~~Task A1.3.1: Add the local transactional lifecycle kernel: allowlisted `SKIP LOCKED` claim, one-use lease token, owner-only heartbeat/complete/fail, bounded exponential retries, batched stale recovery, safe result/error storage and rollback smoke.~~
- [x] ~~Task A1.3.2: Deploy the lease schema, rerun the readiness audit and verify the real-PostgreSQL claim/heartbeat/retry/complete/recovery lifecycle with `rolledBack=true` and `persistedRows=0`.~~
- [x] ~~Task A1.3.3: Add a separate single-job runner with an immutable handler registry, short claim/heartbeat/completion/recovery transactions, graceful stop and metadata-only JSON logs. The default registry exposes only a deterministic `system.worker_probe`; `director.daily_brief` stays unregistered until A3.~~
- [x] ~~Task A1.3.4: Deploy runtime `82ba1b63f9ce`, pass public smoke, confirm the complete empty queue with `readyForWorker=true`, and run exactly one probe-only cycle that exits idle. No permanent service was enabled.~~
- [x] ~~Task A1.4: Add tenant-scoped status/audit reads and safe cancellation for jobs that have not completed.~~
- [x] ~~Task A1.4.1: Add leadership-only, single-company, cursor-paginated read APIs with an explicit public field allowlist that excludes payload, model result, worker identity and lease token.~~
- [x] ~~Task A1.4.2: Deploy the read API and verify authenticated production access plus fail-closed all-companies behavior on runtime `44984a91030f`; leadership read returned `200`, all-companies `409`, foreign company `403`, and the public field allowlist passed.~~
- [x] ~~Task A1.4.3: Add leadership-only, single-company audited queued-job cancellation with restricted reason codes and same-transaction audit; keep running jobs unchanged until cooperative cancellation exists. Focused/full backend tests, frontend tests and production build pass locally.~~
- [x] ~~Task A1.4.4: Deploy queued-job cancellation on runtime `baa79b6bc6d3`; protected API checks blocked aggregate/foreign context and returned `404` for a missing job, while rollback smoke proved queued cancellation, tenant audit, running protection and zero persisted test rows.~~
- [x] ~~Task A2: Define the agent execution contract: allowed tools, minimal model payload, time/cost limits and no direct model access to the database.~~
- [x] ~~Task A2.1: Add a local fail-closed registry for `director.daily_brief` with one-company ownership, immutable existing tenant-scoped read tools, per-tool result schemas, an explicit minimal model payload, fixed time/call/token/cost limits, one read-only SELECT boundary and `database_access=none`; focused `16/16`, backend `1086/1086`, frontend `289/289`, production build and manual no-model checks pass.~~
- [x] ~~Task A2.2: Deploy runtime `0d2754bcfe4f`; atomic publish and public smoke pass, health confirms the backend/database and unauthenticated `/director-agent/tools` is protected with `401` rather than SPA fallback. Authenticated smoke remains skipped because deployment credentials were not supplied.~~
- [x] ~~Task A3: Build a deterministic read-only director daily brief for each company/group: overdue work, shortages, documents, estimate deviations, payments and tasks.~~
- [x] ~~Task A3.1: Add the local deterministic `director.daily_brief` handler on the existing queue/runner. Read all seven immutable tenant-scoped tools for exactly one queue-owned company in one rolled-back read-only transaction, validate/cap the result, and keep models plus business mutations out. Focused `49/49`, backend `1119/1119`, frontend `289/289` and production build pass.~~
- [x] ~~Task A3.2: Deploy runtime `a3ab56bb6f29`; readiness, public/protected smoke and one controlled company `1` brief job pass, with zero persisted smoke jobs. Permanent daemon and bulk scheduling remain disabled.~~
- [ ] Task A4: Add model explanations and in-app/MAX delivery to the daily brief without business-record mutations.
- [x] ~~Task A4.1: Add a leadership-only, single-company read model and compact dashboard view for the latest succeeded deterministic daily brief. Validate and allowlist schema v1, fail closed for aggregate/invalid data, expose no raw queue internals, and keep scheduling, model use, MAX delivery and business writes disabled. Runtime `7d8c615c09a3` and public smoke pass; protected director smoke remains pending.~~
- [x] ~~Task A4.2.1: Deploy the dry-run-by-default, explicit-apply producer on runtime `3210bbe905f7`; company `1` dry-run attempted zero writes, apply created job `8`, one `--once` completed that exact job, and repeat returned the same succeeded job without a duplicate. No schedule, daemon, model, MAX or bulk fan-out was enabled.~~
- [x] ~~Task A4.2.2: Deploy the fail-closed exact-job runner hand-off on runtime `ed11051bb8d8`. `--once --job-id <id>` atomically claims only that queued, due, attempt-eligible ID from the immutable handler allowlist, skips global recovery and never falls through to a neighboring row. Unclaimable targets return metadata-only `not_claimed` with exit code `2`; `--job-id` without `--once` is rejected. Public smoke passes; no schedule, daemon, model, MAX or business mutation is enabled.~~
- [x] ~~Task A4.2.3: Deploy the dry-run-by-default controlled cycle for one explicit company/date on runtime `ed11051bb8d8`. Explicit apply commits the idempotent producer first and then executes only its returned exact job ID after validating company/date/type. Existing success is not rerun; every other nonqueued or unclaimable state fails closed. Public smoke passes; business writes remain zero and no schedule, daemon, model, MAX or fan-out is enabled.~~
- [x] ~~Task A4.2.4: Deploy runtime `2e14a3a2ca3c` and enable the prepared one-company daily one-shot schedule. Linux unit validation and public smoke pass; manual company `1` job `9` for Moscow date `2026-08-06` succeeded in `268 ms` with zero business writes. The timer is enabled for about `07:10 Europe/Moscow`; the generic daemon, model, MAX and fan-out remain disabled. Protected smoke was skipped because credentials were not supplied.~~
- [ ] Task A5: Add one `Требует внимания` queue with reason, priority, owner, project and the next safe action.
- [x] ~~Task A5.1: Deploy and verify the read-only attention projection. It exposes only critical/warning items from the latest validated single-company brief, caps visible rows at 12, uses immutable server-owned reason/action policy, and renders no action buttons. Runtime `74344e8692f9`, public smoke, protected selected-company access, aggregate-company denial and public-field policy all pass.~~
- [ ] Task A6: Run checks automatically after data changes and keep only resolve/approve commands visible; move history, export and rare actions to an overflow menu.
- [x] ~~Task A6.1: Add a pure fail-closed change-event contract and deterministic dispatch plan for the first allowlisted `estimate.version_activated -> director.daily_brief` path. It performs no SQL, queue/model/network call or business mutation. Runtime `61187fa63f69` and public smoke pass.~~
- [x] ~~Task A6.2: Wire the activation contract in metadata-only shadow mode after the three committed estimate activation paths. Runtime `61187fa63f69` and public smoke pass; a manual activation of test estimate `84` returned bounded `state=planned`, `enqueueAttempted=false` and `writesAttempted=0`, while the `agent_jobs` row count remained `2`. Repeated active state, deactivation and drafts remain ignored.~~
- [x] ~~Task A6.3.1: Add a dry-run-by-default queue adapter for a revalidated deterministic change plan. Explicit apply performs one idempotent enqueue attempt for the exact allowlisted `director.daily_brief` plan and validates the returned queue identity; local focused `23/23` and full backend `1202/1202` pass. No runtime hook, commit, runner, model or production behavior is enabled.~~
- [x] ~~Task A6.3.2: Deploy the post-commit activation handoff with both controls absent (`AGENT_CHANGE_DISPATCH_APPLY=true` plus strict `AGENT_CHANGE_DISPATCH_COMPANY_IDS` are both required). Local focused `30/30`, backend `1209/1209`, frontend `299/299` and production build pass. Runtime `053bb218987d` and public smoke pass. A manual activation of test estimate `85` remained in shadow mode with `state=planned`, `enqueueAttempted=false` and `writesAttempted=0`; the `agent_jobs` row count stayed `2`. Dispatch, runner, model and business writes remain disabled.~~
- [x] ~~Task A6.3.3: Run one reversible company `1` enqueue canary. Test estimate `86` created exactly one queued `director.daily_brief` job `10` with `mode=enqueue`, `state=enqueued`, `writesAttempted=1` and `committed=true`; readiness stayed green and total rows changed from `2` to `3`. Both runtime controls were removed immediately afterward and the backend remained active. The runner was not started; exact execution of job `10` remains a separate step.~~
- [x] ~~Task A7: After Tasks E3-E6, run deterministic estimate-revision impact analysis in shadow mode across assignments, materials, supply, warehouse and project economics; do not expose recommendations or mutate business records.~~ Production runtime `362e3cd68589` and exact company `1` canary job `13` completed the five-domain shadow path with zero business-table count changes; controls and the generic runner remain disabled.
  - [x] Task A7.1: Resolve one exact tenant/project/activation/reconciliation source and add a bounded read-only baseline audit with a canonical source revision; do not register a handler or enqueue work. Runtime `f0b1d251ea33` passed public smoke. Production reconciliation `#15` failed closed as inactive with zero writes, then the exact eligible `#4` source (`30 -> 80`) passed with `sourceReady=true`, `readyForDomainScan=true`, zero issues, zero writes and rollback; the operator command remains unregistered.
  - [x] Task A7.2: Project assignment exposure and protected work/act/payment history from immutable E3/E4 lineage without proposing or applying a transfer. Runtime `6aca84ccbc88` passed public smoke; the exact production source `30 -> 80` returned a complete zero-exposure projection with no review, zero writes and rollback.
  - [x] Task A7.3: Project material, open-supply and warehouse exposure from exact estimate coordinates, saved allocations, receipt lines, lots and movements; uncertain lineage becomes a fixed review reason. Runtime `329d87bf46eb` completed both inert production audits for exact source `30 -> 80` with zero writes and rollback. Supply/warehouse completed with no exposure or review. Material correctly remained non-actionable: 341 bounded base-only and 341 target-only coordinates could not be joined without stored lineage, while 100 rows received fixed `material_quantity_invalid` review; no name-based match or production-data rewrite was attempted.
  - [x] Task A7.4: Project the exact E6 budget delta/eligibility and compose one versioned, deterministic, bounded five-domain result with counts, IDs and fixed reason codes only. Runtime `d449c491bec6` passed deploy, smoke, the exact guarded E6 function replacement and all post-audits. Production exact source `30 -> 80` returned complete non-actionable economics for draft reconciliation `#4`; the combined report correctly remained incomplete only for stored material-lineage evidence, with zero writes, rollback and evidence SHA `11562e9a…757`.
  - [x] Task A7.5: Add a controlled `estimate.revision_impact` queue handler and post-commit shadow handoff behind separate disabled-by-default controls; no model, notification, generic runner or business mutation. Production runtime `f6456ae800ad` passed public smoke and agent-job readiness; both controls remained absent, the generic runner remained inactive and an exact source dry-run returned `would_enqueue` with zero writes.
    - [x] Task A7.5.1: Add the strict source-bound job payload, read-only combined-report handler, dry-run-first idempotent producer and explicit default-registry entry; keep runtime activation handoff absent and the generic runner disabled. RED/GREEN contract/handler/producer coverage, exact-job registry/runner coverage, focused `124/124`, full backend `1693/1693` with `28` expected skips and compile all pass.
    - [x] Task A7.5.2: Add the fail-soft post-commit activation handoff behind both `ESTIMATE_REVISION_IMPACT_APPLY=true` and an exact company allowlist; ignored transitions and disabled defaults attempt zero queue writes. All three activation paths call it after commit; focused `164/164`, backend `1701/1701` with `28` expected skips, frontend `342/342` and production build pass. Deploy and reversible canary remain separate approvals.
  - [x] ~~Task A7.6: Add exact writer/handler/handoff/test inventory, real-PostgreSQL rollback and tenant-isolation proofs, then run a separately reviewed production canary and read-only cutover audit.~~ Runtime `362e3cd68589` passed service health, public smoke and exact readiness before and after the canary; final ledger state is `succeeded` with evidence SHA `11562e9a…757`.
    - [x] Task A7.6.1: Add a bounded static execution inventory that fixes the exact handler, producer, registry and three post-commit handoff boundaries; allow only the reviewed operational queue/result mutations and reject business DML, unreviewed feature imports, model calls, notifications, automatic apply routes and missing PostgreSQL proofs. The repository inventory is green with zero A7 DML, three exact operational boundaries, one handler registration, three post-commit handoffs and all five named PostgreSQL proofs.
    - [x] Task A7.6.2: Add one exact read-only readiness command for a canonical source. It combines source validity, combined-report integrity, queue schema/ledger state and the static inventory in one rolled-back report without requiring the business projection itself to be actionable. Unit/fake-DB tests prove absent/pending/succeeded exact ledgers and fail closed on scope, payload, lease, terminal-state, result and evidence drift.
    - [x] ~~Task A7.6.3: Prove the exact enqueue/claim/handler/complete lifecycle in dedicated PostgreSQL under rollback, same-name tenant collision, repeat and concurrent enqueue while preserving protected business-table snapshots; only then deploy the readiness command and separately review a genuine-source production canary or record a valid no-canary outcome.~~ Local PostgreSQL passed `5/5`; production source `30 -> 80` created exactly one job `13`, which the exact-ID runner completed on attempt `1` in `180 ms`. Readiness remained green, all 22 business-table counts were unchanged and public smoke passed afterward.
- [ ] Task A8: Add preview-only supply recommendations and RFQ drafts with exact source lineage.
  - [x] ~~Task A8.1: Derive bounded ID-only recommendation-preview candidates from one validated A7 report by joining open supply coordinates to one exact base-to-target material lineage; fail closed before any content, supplier ranking, RFQ send or business write.~~ Local RED/GREEN, focused `68/68`, A7 `117/117`, full backend `1726/1726`, compilation, static boundary scan and independent review pass; no runtime/API/UI/database surface was added.
  - [x] ~~Task A8.2: Re-read one selected A8.1 candidate in a single rolled-back `REPEATABLE READ`/read-only transaction, revalidate current material and supply lineage, and derive a canonical non-sendable RFQ content draft for the exact existing open request balance.~~ A8 `13/13`, focused `73/73`, A7 `117/117`, full backend `1733/1733`, compilation/static checks and three independent reviews pass; supplier selection, target-need adjustment, persistence, routes, jobs, UI and sending remain separate slices.
  - [x] ~~Task A8.3: In the same rolled-back read-only snapshot, rebuild A8.2 and derive only bounded ID-only company-link/account-ready supplier candidates for human review; material qualification, ranking, selection and sending remain forbidden.~~ Local A8 `24/24`, A7 `117/117`, full backend `1744/1744`, compilation/static checks and independent reviews pass. The production schema still lacks the required `suppliers(user_id,id)` read index, so a nonempty candidate path remains explicitly `incomplete` until the guarded A8.3a migration is separately applied in A8.3b; no route/UI/job/schema write or deployment was added.
  - [x] ~~Task A8.3a: Add a separately invoked, dry-run-first and transactionally guarded canonical `suppliers(user_id,id)` read-index migration; verify exact catalog semantics, count/SHA drift guards, rollback and the A8.3 gate transition before any production apply.~~ Local supply-preview `47/47`, A7 `117/117`, full backend `1767/1767`, compilation/static checks, disposable PostgreSQL 15 rollback/apply/custom-opclass proofs and three independent final reviews pass. No production connection, index apply, runtime registration or supplier action occurred.
  - [x] ~~Task A8.3b: Run a fresh production read-only index audit, separately approve a short maintenance window, apply only its exact count/SHA-guarded A8.3a plan, then repeat the audit, A8.3 gate check and public smoke; do not change supplier data or enable ranking/selection/send.~~ Production runtime `5b0baa81f4a3` first reported the exact one-change plan SHA `a662d85f…11af` for 26 supplier rows, applied and committed only `idx_suppliers_user_id_id`, then returned a complete zero-change audit with matching canonical index; public smoke passed and no supplier data, ranking, selection or send path was enabled.
  - [ ] Task A8.4: Add authoritative, tenant-bound supplier-material capability evidence before any ranking or supplier selection.
    - [x] ~~Task A8.4a: From strict completed A8.2 and A8.3 results, derive bounded deterministic ID/hash-only material-capability confirmation subjects; this pure staging contract must never claim eligibility, rank, select, send, persist or call an LLM.~~ Pure stdlib-only implementation passes focused A8 `37/37`, all supply-preview `59/59`, A7 `117/117`, full backend `1779/1779`, compilation/static checks and two adversarial review cycles. It remains internal and always keeps material eligibility, ranking, selection and sending false; authoritative confirmation storage/collection remains A8.4b.
    - [x] ~~Task A8.4b: Add an inert authoritative confirmation foundation without exposing a writer: first a separately invoked guarded append-only schema migration, then one bounded read-only proof collector that rebuilds A8.2/A8.3/A8.4a and reads confirmations in the same rolled-back snapshot.~~ Both slices are complete: b1's exact append-only schema is now applied and post-audited in production, while b2 proves exact current subjects through one rollback-only read snapshot; the runtime remains disabled and no assertion row, model action, ranking, selection or send was enabled.
      - [x] ~~Task A8.4b1: Add the exact append-only `supplier_material_capability_assertions` schema contract and dry-run-first count/SHA-guarded migration.~~ Pure contract/runtime split, local unit `10/10`, supply-preview `78/78`, backend `1798/1798`, disposable PostgreSQL 15 `9/9`, compilation/static checks and independent final review pass. Production dry-run approved the exact 9-change plan SHA `1c396f82…bd8e`, apply committed all 9 schema writes, and post-audit returned complete with zero changes; no assertion row or runtime action was created.
      - [x] ~~Task A8.4b2: Add the same-snapshot authoritative proof preview. Missing evidence remains unproven, explicit revocation removes proof, partial proof never promotes the overall result, and ranking, selection and sending remain forbidden.~~ One caller-owned read-only `REPEATABLE READ` cursor rebuilds A8.2/A8.3/A8.4a, audits the exact b1 schema and reads at most two exact events per subject. Local focused `57/57`, supply-preview `97/97` with `13` expected skips, A7 `117/117`, backend `1817/1817` with `46` expected skips, disposable PostgreSQL 15 `3/3`, compilation/static checks and two independent final reviews pass; production/schema/runtime surfaces remain unchanged.
    - [ ] Task A8.4c: Add a separately reviewed 2FA-authenticated, exact-company-director confirmation/revocation path; YandexGPT may explain fixed results but can never create, revoke or promote proof.
      - [x] ~~Task A8.4c1: Add the unregistered local confirmation/revocation core. Confirmation must rebuild the current exact subject in one `SERIALIZABLE` transaction; revocation must copy one immutable confirmed assertion. Both require a live cookie-backed server session with passed 2FA and an exact active director membership. No route, UI, schema apply, model action, ranking, selection or send.~~ Public caller-owned proof seam, strict proof-owned write projection, shared assertion decoding, 2FA/director auth, migration-safe locking and append-only confirm/revoke pass focused `71/71`, supply-preview `112/112`, A7 `117/117`, backend `1832/1832`, disposable PostgreSQL 15 `7/7`, compilation/static checks, independent final reviews and an ephemeral read-only Codex CLI `gpt-5.6-terra` `APPROVE`. The append-only schema is now present, but the core remains unregistered and no assertion, model, ranking, selection or send action is enabled.
      - [ ] Task A8.4c2: Add the separately approved cookie-only runtime in four
        gated slices; Bearer compatibility tokens remain forbidden for every
        capability endpoint.
        - [x] ~~A8.4c2a: Add the strict DB-free cookie/CSRF adapter and bounded
          server-side resolver for the exact succeeded A7 report; expose a
          read-only proof endpoint only after contract-first RED tests.~~
        - [x] ~~A8.4c2b: Register single-subject confirmation and immutable
          revocation endpoints over the reviewed c1 writer, with fixed HTTP
          errors, no client report/auth/evidence inputs and no model/send side
          effects.~~
        - [x] ~~A8.4c2c: Add an explicit per-request-item human review panel;
          keep ranking, supplier selection and RFQ send disabled and outside
          this slice.~~
        - [ ] A8.4c2d: Complete staged backend-then-UI enablement and protected
          cookie/CSRF smoke; any canary write remains a separate
          operator-approved gate. Automated local regressions, both flag
          builds, two independent reviews and the strict-mock local Chromium
          interaction pass are green. Production's executable backend/frontend
          artifacts and completed backend-only gate are based on
          `5e9295e03961`, with the backend runtime enabled and the compiled
          frontend/UI flag still off; later documentation-only checkout
          advances do not rebuild or restart those artifacts. Package-mode
          systemd startup, explicit strong `AUTH_SECRET`, the
          append-only schema post-audit, Nginx routing, public smoke and the
          dedicated cookie/2FA/CSRF negative/read-only gate are green with zero
          scoped capability/business/sequence delta. Frontend/UI enablement and
          any positive canary write remain separate open approvals.
- [ ] Task A9: Add preview-only warehouse anomaly and reconciliation recommendations without automatic stock movement.
  - [x] ~~Task A9.1: Add the pure exact A7 warehouse-lineage anomaly readiness
    contract described in `docs/warehouse-anomaly-recommendation-preview.md`;
    keep inventory discrepancies, database collection, routes, UI and every
    stock movement outside this slice until separately reviewed.~~
  - [x] ~~Task A9.2: Revalidate one selected A9.1 candidate against one current
    bounded supply/warehouse A7 snapshot, roll back before finalization and
    return only fixed preview text; keep API/UI/jobs/models/writes disabled.~~
    - [x] ~~A9.2a: Use RED/GREEN to add strict stored-report/selection
      preparation and one private immutable prepared value without opening a
      connection.~~
    - [x] ~~A9.2b: Use RED/GREEN to freeze and validate the exact current A7
      wrapper/raw supply-warehouse producer contract before normalization.~~
    - [x] ~~A9.2c: Use RED/GREEN to add pure current revalidation,
      relevant/content hashes, fixed text and exact blocked/stale/ready
      precedence.~~
    - [x] ~~A9.2d: Use RED/GREEN to add the single read-only `REPEATABLE READ`
      runner with unconditional rollback, cleanup/control-flow precedence and
      no content before successful rollback and cleanup.~~
    - [x] ~~A9.2e: Run focused/A7/full-backend regressions, static dependency and
      write-boundary checks plus fresh review; keep runtime and production
      unchanged and close only this internal slice after evidence is recorded.~~
  - [x] ~~Task A9.3: Build the bounded, authorized and still-unregistered runtime
    substrate defined in `docs/warehouse-anomaly-runtime-readiness.md`; HTTP,
    UI, package exports, feature flags and production remain separate approvals.~~
    - [x] ~~A9.3a: Bound every variable-width A7 relevant query before libpq with
      exact UTF-8 field/query/cumulative budgets and existing fail-closed reason
      codes, preserving all public A7 report/function contracts.~~
      - [x] ~~A9.3a1: Add the private exact byte-budget/value-metadata contract
        after an observed focused RED.~~
      - [x] ~~A9.3a2: Gate target/reconciliation baseline query payloads and
        thread one private budget through the public-compatible baseline core.~~
      - [x] ~~A9.3a3: Gate source-context and supply-request JSON/text payloads,
        including query-wide mixed-row rejection and early short-circuiting.~~
      - [x] ~~A9.3a4: Gate delivery/allocation/invoice/history/movement payloads,
        including 64-byte NUMERIC text and dependent-read short-circuiting.~~
      - [x] ~~A9.3a5: Prove CASE/window/UTF-8 behavior in the approved isolated
        `a93_<lowerhex>` Unix-socket-only disposable PostgreSQL fixture, then
        run parity/full regressions and fresh review before local A9.3a
        closure.~~
    - [x] ~~A9.3b: Add per-process capacity, bounded connect, guarded explicit
      read-only transaction lifecycle and cooperative deadline controls.~~
      - [x] ~~A9.3b1: Add the private one-slot lease and immutable 30-second
        monotonic operation budget after an observed missing-contract RED.~~
      - [x] ~~A9.3b2: Add the strict A9-only libpq connection factory with fixed
        `connect_timeout=5`/startup controls and pre/post-connect clock guards.~~
      - [x] ~~A9.3b3: Add the guarded cursor, explicit read-only BEGIN, one exact
        settings SELECT and rollback/close/control-flow lifecycle matrix.~~
      - [x] ~~A9.3b4: Reuse the approved isolated PostgreSQL launcher to prove
        BEGIN→single rollback→backend idle, then run full regressions/reviews.~~
    - [x] ~~A9.3c: Add the pure exact cookie-session/director authorization,
      selector and minimal public disclosure contracts.~~
      - [x] ~~A9.3c1: Add the private immutable authentication/request selector
        contract after an observed missing-module RED.~~
      - [x] ~~A9.3c2: Add the pure actor/project authorization outcome truth
        table with authentication-before-resource precedence.~~
      - [x] ~~A9.3c3: Add the detached minimal public projection for all 18
        allowlisted warehouse anomaly candidates and three public states.~~
      - [x] ~~A9.3c4: Run focused/full regressions and static/privacy reviews
        without adding SQL, routes, exports or production call sites.~~
    - [x] A9.3d: Add the caller-cursor live auth/project and exact succeeded
      system-job artifact resolver with pre-libpq CASE sentinels.
      - [x] A9.3d1: Add one exact actor/project authorization SELECT and bind
        its two-field result to the A9.3c precedence contract.
      - [x] A9.3d2: Add one opaque exact-job lookup with query-wide 128 KiB
        CASE sentinels and fixed not-found/artifact-invalid outcomes.
      - [x] A9.3d3: Rebuild and validate source, full job plan, result/report
        provenance and return only a detached internal artifact.
      - [x] A9.3d4: Reuse the approved isolated PostgreSQL fixture for auth
        and artifact SQL, then complete regressions and three fresh reviews.
    - [x] ~~A9.3e: Compose one same-snapshot unregistered runner and complete
      regression/security review without registering or deploying it.~~
      - [x] A9.3e1: Add the private composition boundary and prove claims are
        parsed before capacity/DB while the happy path owns one lease/snapshot.
      - [x] A9.3e2: Map auth/artifact/content/finalizer outcomes with exact
        cleanup/deadline/control precedence and exactly-once lease release.
      - [x] A9.3e3: Close the exact 18-statement SELECT-only call graph and
        prove auth, artifact and one 14-query A7 pass use one guarded cursor.
      - [x] ~~A9.3e4: Run focused/full regressions and three final review axes
        while keeping routes, exports, registration and production untouched.~~
  - [x] ~~Task A9.4: Add the default-off cookie/CSRF HTTP adapter defined in
    `docs/warehouse-anomaly-http-adapter.md` without adding UI or enabling it
    in production.~~
    - [x] ~~A9.4a: Add one unregistered exact route contract with bounded body,
      cookie/CSRF, company allowlist, fixed errors and no-store responses.~~
    - [x] ~~A9.4b: Compose the route with the real private A9.3e runner and prove
      one 18-statement snapshot, zero writes and privacy-safe telemetry.~~
    - [x] ~~A9.4c: Register default-off in `main.py`, exclude only this route
      from DB error logging and add the local nginx global-capacity contract.~~
    - [x] ~~A9.4d: Run focused/full HTTP, role/tenant/CSRF, ops and security
      reviews; keep UI, production enablement, commit, push and deploy
      separate.~~
- [ ] Task A10: Add preview-only assignment and daily-work-report drafts from
  confirmed source data under
  `docs/assignment-daily-work-drafts.md`; never apply or save automatically.
  - [x] ~~A10.1: Add pure immutable scope/result contracts and a bounded daily-
    work projection from exact confirmed work-journal facts.~~
  - [x] ~~A10.2: Add a pure assignment-availability projection using only exact
    active-estimate lineage and non-cancelled assigned quantities.~~
  - [x] ~~A10.3: Compose one tenant/project-scoped read-only snapshot with zero
    business writes and disposable-PostgreSQL proof.~~
  - [x] ~~A10.4: Add a default-off director/deputy HTTP preview adapter with
    cookie-only authentication, CSRF and exact company/project scope.~~
  - [x] ~~A10.5: Add a review-only UI and printable document with no apply
    action.~~
  - [x] ~~A10.6: Run full regression/review and prepare a separate canary plan.~~
  - [ ] Production checkpoint: receive explicit approval, deploy inert code,
    run the one-company canary and record production smoke/rollback evidence.
- [ ] Task A11: Add the one-company, read-only accounting exception checks
  specified in `docs/accounting-exception-checks.md`; never create, approve,
  execute, reverse or mark payments automatically.
  - [x] ~~A11.1: Add a dry-run ownership inventory and idempotent schema contract
    for staff, accountable payments/expenses, expense reports, salary,
    `own_expenses` and manual `expenses`.~~
    - [x] ~~A11.1a: Add the private bounded read-only classifier/inventory with
      fixed allowlisted output and no registration or write path.~~
    - [x] ~~A11.1b: Add the idempotent schema metadata contract and disposable-
      PostgreSQL inventory proof without applying it to production.~~
  - [x] ~~A11.2: Backfill only provable legacy owners, quarantine every ambiguous
    row and provide a separately approved exact-record remediation path.~~
    - [x] ~~A11.2a: Add the guarded provable-only dry-run/apply backfill with
      plan drift protection, quarantine and disposable-PostgreSQL proof.~~
    - [x] ~~A11.2b: Add exact-record remediation with validated owner IDs, an
      audit event and a separate production-approval boundary.~~
      - [x] ~~A11.2b1: Freeze the pure closed exact-ID request/fingerprint
        contract with no database or automatic apply capability.~~
      - [x] ~~A11.2b2: Validate stored company/project/parent/staff ownership in
        one transaction, apply one exact row and write the audit event.~~
      - [x] ~~A11.2b3: Add the dry-run-first operator CLI/runbook, replace broad
        table locks with exact-row locking where the proof remains equivalent,
        and keep production execution behind a new explicit approval.~~
  - [x] ~~A11.3: Harden all future accounting writers and readers to exact server-
    resolved company/project/staff IDs, including both expense mirrors, before
    trusting the new scope.~~
    - [x] ~~A11.3a: Scope accountable payment/expense reads and writes to one
      selected finance actor, verified stored owners and locked exact parents;
      update the UI to submit IDs and prove the route in disposable PostgreSQL.~~
    - [x] ~~A11.3b: Scope expense-report reads and mutations to one selected
      finance actor, verified exact owners and locked stored rows; submit owner
      IDs from the UI and prove cross-company isolation in disposable
      PostgreSQL.~~
    - [x] ~~A11.3c: Harden salary/staff routes.~~
      - [x] ~~A11.3c1: Scope salary-payment reads/writes/deletes to one selected
        finance actor and one verified staff owner; derive display/actor/date
        fields on the server and prove the route in disposable PostgreSQL.~~
      - [x] ~~A11.3c2: Scope staff reads and lifecycle mutations to one selected
        company without exposing quarantined or foreign personnel records.~~
    - [x] ~~A11.3d: Harden `own_expenses` and manual `expenses` routes.~~
  - [x] ~~A11.4: Add a pure immutable projection for the expanded hard
    accounting contradiction set.~~
  - [x] ~~A11.5: Compose bounded company-owned collectors in one `REPEATABLE
    READ READ ONLY` snapshot with disposable-PostgreSQL proof.~~
  - [x] ~~A11.6: Add a default-off finance-role API with exact company scope and
    no payment mutation capability.~~
  - [x] ~~A11.7: Add a separately gated review-only Accounting panel with no
    apply/pay/status action.~~
  - [x] ~~A11.8: Run full regression/security review and prepare separate schema
    migration and one-company canary plans; production remains distinct.~~
  - [ ] Production checkpoint: receive explicit approval for the exact schema/
    data migration, deploy inert code, then run and observe the one-company
    canary from `docs/accounting-exception-checks-canary.md`.
- [ ] Task A12: Add controlled `preview -> human approval -> apply -> audit`
  actions under the proposed closed-registry design in
  `docs/human-approved-actions.md`; stock, payments, salary/accountable
  reports, signed documents, project budgets and estimates remain blocked
  pending separate human-approved ADRs.
  - [x] ~~A12.1: Approve and freeze the pure action/proposal/event contract,
    threat model and exact writer inventory; no schema, route or business
    write.~~
  - [x] ~~A12.2: Add the immutable append-only ledger schema contract and
    dry-run/count/SHA-guarded disposable-PostgreSQL migration proof; do not
    apply it to production.~~ The exact 12-change plan SHA
    `6d570c93…d34951`, focused `100/100`, backend `2350/2350` with 56 expected
    skips and disposable PostgreSQL 15 `52/52` pass. Exact catalog drift,
    append-only triggers, one decision/apply, rollback and unchanged protected
    business rows are proven; the production schema remains unchanged.
  - [x] ~~A12.3: Implement the single audit-only
    `warehouse_anomaly_review_acknowledged` kernel with exact current-preview
    revalidation, 2FA, tenant scope, expiry, idempotency and rollback.~~ The
    private unregistered kernel writes only proposal/event/audit rows; focused
    A12 `34/34`, related `102/102`, backend `2350/2350` and disposable schema
    PostgreSQL `52/52` pass. Exact `source_job_id` binding was added before any
    production migration; the corrected 12-step plan SHA is
    `6d570c93…d34951`.
  - [x] ~~A12.4: Add a default-off one-company API with cookie/CSRF
    authorization and a statically closed one-action registry.~~ Three exact
    routes now expose proposal, decision and bounded immutable history only
    when `HUMAN_APPROVED_ACTIONS_HTTP_ENABLED=true` and one canonical company
    ID is allowlisted. Cookie/CSRF, selected company, exact JSON/query shapes,
    no-store responses, one in-process slot and fixed per-minute limits fail
    before the private kernel. Tenant-bound decision/history checks, closed
    route/import/SQL inventory, focused A12 `47/47`, related `117/117` and full
    backend `2363/2363` with 56 expected skips pass. No schema migration,
    feature enablement, UI, production write, push or deploy occurred.
  - [x] ~~A12.5: Add the explicit review/decision/receipt UI; do not add a
    business correction control.~~ The default-off warehouse control panel is
    restricted to the director of the one allowlisted company, obtains a
    separate read-only preview, shows exact consequence and expiry, and uses
    separate proposal and approve/reject requests. Approval records only the
    immutable review receipt; there is no business correction control.
    Cookie-only routing, strict detached shapes, double-submit, expiry and
    stale company/project/source guards are covered. Focused UI/API `28/28`,
    full frontend `414/414`, backend A12 `47/47`, production
    build and isolated desktop/mobile browser checks pass. No flag, migration,
    production data, commit, push or deploy changed.
  - [x] ~~A12.6: Complete disposable-PostgreSQL, concurrency, full regression,
    security, operations and separate migration/canary proof.~~ Local closure
    is complete; production remains separately gated.
    - [x] ~~A12.6.1: Extend the existing launcher-owned PostgreSQL 15 proof with
      the real preview -> proposal -> decision -> immutable receipt lifecycle,
      stale-source rollback, reject/replay and simultaneous approval. Require
      exact ledger/audit counts and byte-identical protected tables.~~ The
      launcher-owned PostgreSQL 15 suite passes `52/52`, including bounded
      newest-first history and clean server teardown.
    - [x] ~~A12.6.2: Freeze the release package: exact nginx locations, a
      dry-run/count/SHA-guarded migration runbook and a one-company canary with
      explicit stop/rollback/no-manufactured-candidate rules.~~ The package
      includes fixed JSON/no-store `429`, 4 KiB POST limits and loopback-only
      proxying; it grants no production authority.
    - [x] ~~A12.6.3: Run focused/full backend and frontend regressions, optimized
      build, dependency audit, static writer/secret checks and final review.
      Production migration, flags, nginx, data and deployment stay untouched.~~
      A12 passes `49/49`, backend `2365/2365` with 56 expected skips,
      unchanged frontend `414/414`, production build/browser evidence remains
      green, and the offline dependency audit reports 0 findings in 1319
      dependencies.
  - [ ] Production checkpoint: receive exact approval, migrate the ledger,
    deploy inert code and run the one-company audit-only canary.
  - [ ] A12.7+: Add at most one separately approved business action per ADR
    and proof slice; no generic executor.
- [ ] Task A13: Run the worker separately on the current rented server and monitor queue depth, errors, duration and cost.
- [ ] Task A14: Put model access behind a provider-neutral gateway; keep the cloud model first and evaluate a local model only after quality/load/cost measurements.

Close and strike through a task only after applicable focused tests, full backend/frontend verification, manual browser checks, tenant/role isolation and production smoke. Record the evidence in `tasks/todo.md`.
