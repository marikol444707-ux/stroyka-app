# Task List: Safe Stroyka Program Improvements

## Task 1: Baseline Worktree Inventory

**Description:** Record the current repo state before implementation so generated artifacts and unrelated local files do not get mixed into feature work.

**Acceptance criteria:**
- [ ] `git status --short` is reviewed.
- [ ] Generated artifacts under `output/` and `graphify-out/` are excluded from implementation commits unless explicitly requested.
- [ ] Any existing untracked test files are classified as keep, stage, or ignore before code changes begin.

**Verification:**
- [ ] Manual check: current worktree status is documented in the implementation note.

**Dependencies:** None

**Files likely touched:**
- None

**Estimated scope:** XS

## Task 2: Establish Validation Checklist

**Description:** Define the exact local commands that every subsequent slice must pass.

**Acceptance criteria:**
- [ ] Backend compile command is confirmed.
- [ ] Frontend test command is confirmed.
- [ ] Frontend build command is confirmed.
- [ ] Relevant smoke commands for the current slice are listed.

**Verification:**
- [ ] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [ ] `CI=true npm test -- --watchAll=false`
- [ ] `npm run build`

**Dependencies:** Task 1

**Files likely touched:**
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** XS

## Task 3: Secure Smeta Upload Boundary

**Description:** Decide and implement the correct access policy for `/parse-smeta`: authenticated internal endpoint, or explicit public endpoint with rate and size protection.

**Acceptance criteria:**
- [x] Unauthorized behavior is intentional and documented.
- [x] Upload size and file-type checks are explicit.
- [x] Existing internal smeta import still works.

**Verification:**
- [x] `python3 scripts/check-smeta-parser.py` or equivalent parser check passes.
- [x] Static route check: `/parse-smeta` requires `get_current_user`.

**Dependencies:** Task 2

**Files likely touched:**
- `backend/main.py`
- `scripts/check-smeta-parser.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task A1.4.3: Audited Queued Agent Job Cancellation

**Description:** Allow company leadership to cancel an agent job only while it
is still waiting in the queue. A claimed or completed job must not be relabelled
as cancelled.

**Status:** Implemented locally on 2026-08-05; production verification remains
as Task A1.4.4.

**Safety:**
- `POST /agent-jobs/{id}/cancel` resolves exactly one selected company in update
  mode and rejects aggregate-company or non-leadership access before touching
  the queue.
- One parameterized `UPDATE` requires matching `id + company_id + queued`, so a
  concurrent worker claim wins safely and produces `409` instead of a false
  cancellation.
- Cancellation accepts only predefined reason codes; arbitrary text and secrets
  cannot enter the audit description.
- The cancellation and company/project-owned audit record share one database
  transaction. Audit failure or ownership mismatch rolls back the status change.
- The response reuses the existing public allowlist and never returns payload,
  model result, worker identity, lease token or idempotency key.

**Verification:**
- [x] Red tests failed before the cancellation service and route existed.
- [x] Agent-job focused suite passes (`52` tests); audit ownership focused tests
  also cover `agent_job` as a stored company/project parent.
- [x] Full backend discovery passes (`1073` tests).
- [x] Full frontend Jest passes (`289` tests), Python compile, smoke-script
  syntax and production build pass.
- [x] Production protected and transactional cancellation smoke passed in Task
  A1.4.4 on runtime `baa79b6bc6d3`.

**Estimated scope:** S

## Task A1.4.4: Production Cancellation Verification

**Status:** Complete in production on 2026-08-05, runtime `baa79b6bc6d3`.

**Prepared checks:**
- Protected production smoke posts only to a non-existent job ID and confirms
  aggregate-company denial, foreign-company denial and selected-company `404`.
- `npm run smoke:agent-job-cancellation` creates one queued and one running job
  in a single database transaction, cancels only queued, stores company audit,
  preserves the previous diagnostic and proves running remains unchanged.
- The script always rolls back, reconnects and requires zero matching
  `agent_jobs` and zero matching `audit_log` rows.

**Verification:**
- [x] Static red tests were added before the smoke script and API checks.
- [x] Agent-job suite passes (`52` tests), full backend passes (`1073` tests),
  frontend Jest passes (`289` tests), script compile/syntax and production build
  pass.
- [x] A local manual invocation produces a structured failure with
  `rolledBack=true` because the intentionally minimal local PostgreSQL lacks
  the production tenant tables; no local records were written.
- [x] Protected production smoke passed: login and agent-job reads returned
  `200`; aggregate reads returned `409`; foreign company returned `403`;
  cancellation returned aggregate `400`, foreign `403` and missing job `404`;
  the public field allowlist remained valid and `apiErrorsShown=0`.
- [x] Rollback-only PostgreSQL smoke passed with
  `steps=[cancel_queued,audit,protect_running]`, `rolledBack=true`,
  `persistedAgentJobs=0` and `persistedAuditRows=0`.

**Estimated scope:** S

## Task A1.3.1: Agent Job Worker Lifecycle Kernel

**Description:** Add the transaction-level worker controls without starting a
daemon or calling an AI model. A worker may claim only registered job types;
the lease owner alone may heartbeat, finish or retry a still-valid lease.

**Status:** Complete on 2026-08-05. Production schema, readiness audit and
rollback-only lifecycle smoke are verified.

**Safety:**
- Claim uses one atomic `FOR UPDATE SKIP LOCKED` statement, so concurrent
  workers do not wait on or receive the same queued row.
- Claim and stale recovery both require an explicit job-type allowlist.
- Heartbeat, success and failure require the matching worker, one-use
  lease-token and a lease that has not expired; even a stale run with the same
  worker name cannot overwrite a recovered job.
- Attempts increment only on claim. Failure/recovery requeues below the limit
  with bounded exponential backoff and becomes terminal `failed` at the
  configured maximum.
- Stale recovery is ordered, `SKIP LOCKED` and capped at `500` rows per batch.
- Results reuse the 64 KiB sensitive-key guard. Error summaries are capped and
  redact obvious password/token/authorization/cookie/API-key values.
- The production smoke writes only inside one transaction, always rolls back,
  then verifies by correlation IDs that zero test rows persisted.
- No route, UI, AI provider, estimate, warehouse, supply, assignment or
  accounting mutation is connected in this slice.

**Verification:**
- [x] Worker/schema/readiness/enqueue focused suite passes (`30` tests), with
  red tests recorded before lease expiry, one-use token, PostgreSQL array,
  secret redaction and bounded recovery fixes.
- [x] Full backend discovery passes (`1050` tests).
- [x] Full frontend Jest passes (`289` tests); production build and Python
  compile pass.
- [x] After deployment, `npm run audit:agent-jobs` reports the new
  lease column/index with `readyForWorker=true`.
- [x] `npm run smoke:agent-job-worker` on production reports
  `steps=[claim, heartbeat, retry, complete, recover_expired]`,
  `rolledBack=true`, `persistedRows=0` and `ok=true`.

**Estimated scope:** S

## Task A1.3.3: Separate Agent Job Runner

**Description:** Execute the existing queue lifecycle in a process that is
separate from FastAPI and dispatch only explicitly registered handlers.

**Status:** Complete in production on 2026-08-05 as Task A1.3.4. A permanent
service remains blocked on A3.

**Safety:**
- The immutable registry is the exact claim allowlist. Unknown and future job
  types stay queued instead of reaching a fallback handler.
- Claim commits and closes before handler work. Heartbeat, completion, retry and
  stale recovery each open a separate bounded transaction.
- The handler receives one immutable company-owned context and no database
  connection, cursor, worker identity or lease token.
- A dedicated thread renews the lease during long work. A stale worker cannot
  store a result after lease loss; existing bounded retry/recovery remains the
  source of truth.
- Handler errors store only the error class. Structured logs omit payload,
  result, correlation value, exception text, credentials and lease token.
- The default registry contains only deterministic `system.worker_probe`,
  which does not read or mutate business data and does not call a model.
  `director.daily_brief` remains unavailable until A3.
- `SIGTERM`/`SIGINT` stop new polling while an active handler finishes. Normal
  HTTP work never imports or invokes the runner.

**Verification:**
- [x] Registry and runner tests failed before the modules existed.
- [x] Focused registry/runner/lifecycle suite passes (`32` tests).
- [x] `python3 -m backend.features.agent_jobs.runner --help` succeeds without a
  database connection or HTTP application import.
- [x] Full backend discovery passes (`1104` tests), frontend Jest passes and
  the production build compiles successfully.
- [x] Production readiness plus one-cycle runner check passed in Task A1.3.4.

**Operations:** `docs/agent-job-runner.md`

**Estimated scope:** M

## Task A1.3.4: Production Runner Verification

**Status:** Complete on 2026-08-05 for runtime `82ba1b63f9ce`.

**Verification:**
- [x] Production deploy and full public smoke passed; health reported the exact
  new runtime and a healthy database.
- [x] `npm run audit:agent-jobs` reported the complete table, indexes and
  constraints, `total=0`, zero invalid owner/status/lease rows and
  `readyForWorker=true` without writes.
- [x] Exactly one `npm run worker:agent-jobs -- --once` cycle started with only
  `system.worker_probe` allowed, found no queued work and stopped with
  `processed=false`, `status=idle`.
- [x] No daemon or permanent worker service was enabled; `director.daily_brief`
  remains unavailable until A3.

**Estimated scope:** XS

## Task A1.4.1: Tenant-Scoped Agent Job Status API

**Description:** Add a read-only operational view of background jobs before
connecting a UI or AI provider. Leadership may inspect only one selected
company at a time.

**Status:** Production verification complete on 2026-08-05 as Task A1.4.2.

**Safety:**
- `GET /agent-jobs` and `GET /agent-jobs/{id}` resolve the server-side company
  actor and reject aggregate-company mode before querying `agent_jobs`.
- Access is limited to company leadership roles; a job from another company is
  returned as not found.
- The query always starts with stored `company_id` and supports only validated
  status, project, cursor and a bounded `1..100` page size.
- The public response is an explicit field allowlist. It does not expose
  `payload_json`, `result_json`, `locked_by`, `lease_token` or idempotency keys.
- This slice is read-only: no job, AI, estimate, warehouse, supply or accounting
  record is mutated.

**Verification:**
- [x] Agent-job focused suite passes (`40` tests), including cross-company 404,
  all-companies rejection, role denial, field redaction and pagination.
- [x] Full backend discovery passes (`1060` tests).
- [x] Full frontend Jest passes (`289` tests) and production build compiles.
- [x] Backend deployed as runtime `124796b581aa`; the first public smoke proved
  that Nginx still returned SPA `index.html` for `/agent-jobs` instead of the
  protected API response.
- [x] Add exact list/detail Nginx locations, an idempotent backup-first installer
  and regression checks for both `/agent-jobs` and `/agent-jobs/{id}`.
- [x] Runtime `1e04e1075409` returns backend `401` for unauthenticated
  `/agent-jobs` and `/agent-jobs/1`; the SPA fallback is closed.
- [x] Add a tested `SMOKE_PROTECTED_ONLY=1` mode after the full smoke proved
  that shared Nginx `login_limit` traffic could rate-limit `/login` before the
  authenticated checks started; production security limits are unchanged.
- [x] Runtime `44984a91030f` passed protected smoke: leadership read returned
  `200`, `X-Company-Mode: all_companies` was blocked with `409`, a foreign
  company was blocked with `403`, and the public field policy passed.

**Estimated scope:** S

## Task 4: Add Smeta Access Smoke

**Description:** Add or extend a smoke check that proves the parser access rule from Task 3 does not regress.

**Acceptance criteria:**
- [x] Smoke covers protected-route access policy through static route inspection.
- [x] Smoke covers allowed parser behavior through direct parser execution.
- [x] Failure output explains the broken condition clearly.

**Verification:**
- [x] New/updated smoke script passes locally.
- [x] `npm run build` passes if frontend code was touched.

**Dependencies:** Task 3

**Files likely touched:**
- `scripts/check-smeta-parser.py`
- `package.json`
- `TESTING.md`

**Estimated scope:** S

## Task 5: Frontend Cookie-First Auth Slice

**Description:** Change the frontend fetch wrapper so cookie session is the primary path and Bearer token remains only as a compatibility fallback.

**Acceptance criteria:**
- [x] Requests include credentials by default.
- [x] Existing Bearer fallback still works during transition.
- [x] Logout/session-expired behavior remains clear to the user.

**Verification:**
- [ ] `npm run smoke:auth-session` (blocked locally: PostgreSQL password authentication failed for user `stroyka`)
- [x] `CI=true npm test -- --watchAll=false`
- [x] `npm run build`

**Dependencies:** Task 2

**Files likely touched:**
- `src/api.js`
- `src/hooks/useAuth.js`
- `ONBOARDING.md`

**Estimated scope:** S

## Task 6: CSRF Compatibility Slice

**Description:** Add a minimal CSRF design and first compatible server/client path for mutating requests without breaking current sessions.

**Acceptance criteria:**
- [x] CSRF requirement is documented before broad enforcement.
- [x] One safe mutating endpoint proves the pattern: `/logout` has flag-gated CSRF checks for cookie sessions.
- [x] Public endpoints remain intentionally public.

**Verification:**
- [x] `CI=true npm test -- --watchAll=false`
- [x] `npm run build`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile scripts/smoke-auth-session.py`
- [x] Production deploy passed `bash deploy.sh` at `340a91a` and production moved forward to `05e6354`.
- [x] `/csrf-token` is proxied by production nginx and returns `401` without a cookie session.
- [x] `EXPECT_CSRF_LOGOUT_ENFORCED=true npm run smoke:auth-session` passes on production.
- [x] Target endpoint accepts valid CSRF and rejects missing/invalid CSRF in live auth/session smoke.

**Dependencies:** Task 5

**Files likely touched:**
- `backend/main.py`
- `src/api.js`
- `ONBOARDING.md`
- `scripts/smoke-auth-session.py`

**Estimated scope:** M

## Task 6.1: Revoke Sessions When User Is Disabled

**Description:** When an admin disables a user through `PUT /users/{id}` with `active:false`, revoke that user's active cookie sessions without changing the broader auth flow.

**Acceptance criteria:**
- [x] Disabling a user revokes active `user_sessions` rows for that user.
- [x] Existing cookie login/logout and Bearer fallback remain compatible.
- [x] Password, role, 2FA, and staff-card revocation remain separate follow-up steps.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile scripts/smoke-auth-session.py`
- [x] `npm run smoke:auth-session` on production after deploy.

**Dependencies:** Task 6

**Files likely touched:**
- `backend/main.py`
- `scripts/smoke-auth-session.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task 6.2: Revoke Sessions When User Password Changes

**Description:** When an admin changes a user's password through `PUT /users/{id}`, revoke that user's active cookie sessions without removing the Bearer compatibility path.

**Acceptance criteria:**
- [x] Changing a user's password revokes active `user_sessions` rows for that user.
- [x] The old cookie session stops opening protected endpoints.
- [x] The new password can still log in normally after the change.
- [x] 2FA, role, and staff-card revocation remain separate follow-up steps.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile scripts/smoke-auth-session.py`
- [x] `npm run smoke:auth-session` on production after deploy.

**Dependencies:** Task 6.1

**Files likely touched:**
- `backend/main.py`
- `scripts/smoke-auth-session.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task 6.3: Revoke Sessions When User Role Changes

**Description:** When an admin changes a user's role through `PUT /users/{id}`, revoke that user's active cookie sessions without changing the broader Bearer compatibility path.

**Acceptance criteria:**
- [x] Changing a user's role revokes active `user_sessions` rows for that user.
- [x] The old cookie session stops opening protected endpoints.
- [x] The unchanged password can still log in normally after the role change.
- [x] 2FA and staff-card revocation remain separate follow-up steps.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile scripts/smoke-auth-session.py`
- [x] `npm run smoke:auth-session` on production after deploy.

**Dependencies:** Task 6.2

**Files likely touched:**
- `backend/main.py`
- `scripts/smoke-auth-session.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task 6.4: Revoke Sessions When User 2FA Is Reset

**Description:** When an admin resets a user's 2FA through `POST /users/{id}/2fa-reset`, revoke that user's active cookie sessions without changing the Bearer compatibility path.

**Acceptance criteria:**
- [x] Resetting a user's 2FA revokes active `user_sessions` rows for that user.
- [x] The old cookie session stops opening protected endpoints.
- [x] The smoke test covers a real 2FA login before reset.
- [x] Staff-card revocation remains a separate follow-up step.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile scripts/smoke-auth-session.py`
- [x] `npm run smoke:auth-session` on production after deploy.

**Dependencies:** Task 6.3

**Files likely touched:**
- `backend/main.py`
- `scripts/smoke-auth-session.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task 6.5: Revoke Sessions When Staff Card Is Disabled

**Description:** When an admin disables a staff card through `DELETE /staff/{id}`, revoke active cookie sessions for the linked user access without changing the Bearer compatibility path.

**Acceptance criteria:**
- [x] Disabling a staff card disables the linked user access by email.
- [x] Active `user_sessions` rows for that linked user are revoked.
- [x] The old cookie session stops opening protected endpoints.
- [x] Existing user disable, password change, role change, 2FA reset, logout, and Bearer fallback checks remain covered.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile scripts/smoke-auth-session.py`
- [x] `npm run smoke:auth-session` on production after deploy.

**Dependencies:** Task 6.4

**Files likely touched:**
- `backend/main.py`
- `scripts/smoke-auth-session.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task M1: Tenant Context Kernel

**Description:** Add one compatible request-context path from the selected frontend company to a backend membership check. Use supply-request creation as the first real consumer without changing the database schema or filtering all existing screens.

**Status:** Completed, verified, and released as an independent production slice on 2026-07-09.

**Acceptance criteria:**
- [x] Protected frontend requests send `X-Company-Mode` and, for a concrete company, `X-Company-Id` from the current user's saved selection.
- [x] Public auth requests do not receive tenant headers.
- [x] The kernel rejects malformed headers, `all_companies` mutations, cross-source company conflicts, inaccessible companies, and cross-account membership mismatches.
- [x] Backend returns the effective membership role in the resolved context.
- [x] `POST /supply-requests` resolves its company through the kernel and still supports clients that send no tenant headers.
- [x] No schema migration, backfill, broad read filtering, or role rewrite is included.

**Verification:**
- [x] `CI=true npm test -- --watchAll=false src/api.test.js`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.company_context.test_service`
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/features/company_context/service.py`
- [x] `CI=true npm test -- --watchAll=false` (48 tests passed)
- [x] `npm run build`

**Dependencies:** Tasks 2 and 6

**Files likely touched:**
- `src/api.js`
- `src/api.test.js`
- `src/features/company-context/`
- `backend/features/company_context/service.py`
- `backend/features/company_context/test_service.py`
- `backend/main.py`
- `ONBOARDING.md`

**Estimated scope:** S

## Task M2: Supply Isolation And Effective Roles

**Description:** Apply the kernel to supply request lists, details, updates, approvals, KP creation, and recipient diagnostics. Authorize each action by the effective role of the selected company.

**Acceptance criteria:**
- [ ] Supply reads are filtered by resolved `company_id` or an allowed account summary.
- [ ] Every supply mutation checks the selected company's effective role.
- [ ] A request cannot cross into another account through project name, request ID, supplier ID, or body `companyId`.
- [ ] Legacy rows use an explicit, logged compatibility rule instead of silent global visibility.

**Verification:**
- [ ] Focused backend tests cover two companies and two independent accounts.
- [ ] `npm run smoke:supply-chain` against a safe test database.

**Dependencies:** Task M1

**Estimated scope:** M

## Task M2.1: Supply Request Read Isolation

**Description:** Apply Tenant Context Kernel to `GET /supply-requests` without changing write actions or supplier recipient visibility. Legacy clients without tenant headers resolve through default membership or `users.company_id`, never through an unscoped query.

**Status:** Completed, verified, and released as an independent production slice on 2026-07-10.

**Acceptance criteria:**
- [x] Concrete company mode filters internal supply rows by one verified `company_id`.
- [x] `Все компании` filters rows by company memberships inside the authenticated `platform_account`.
- [x] Existing project, author, and work-package restrictions remain active together with company scope.
- [x] Empty or invalid resolved scope fails closed and cannot become a broad query.
- [x] Supplier users keep the existing recipient-based cross-client view.
- [x] Requests without tenant headers use default membership/legacy company and cannot bypass filtering by omitting headers.
- [x] No schema, backfill, supply mutations, or effective-role authorization is included.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.company_context.test_service` (16 tests passed)
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/features/company_context/service.py`
- [x] Tracked frontend test suite (43 tests passed); untracked P-track tests are excluded from this release.
- [x] `npm run build`

**Dependencies:** Task M1

**Files touched:**
- `backend/features/company_context/service.py`
- `backend/features/company_context/test_service.py`
- `backend/main.py`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task M2.2: Supply Request Update Isolation

**Description:** Apply Tenant Context Kernel to `PUT /supply-requests/{id}` as the first mutation of an existing supply document. Resolve access from the request's stored `company_id`, then run the existing action rules with the selected company's effective membership role and project/package assignments.

**Status:** Completed, verified, and released as production commit `a69b4af5` on 2026-07-10.

**Acceptance criteria:**
- [x] The stored request `company_id` is the source of truth for update authorization.
- [x] Conflicting `X-Company-Id` or body `companyId` is rejected before membership queries or mutation.
- [x] `Все компании` remains read-only and cannot update a request.
- [x] Action authorization, project access, package access, audit role, and response shaping use the selected membership's effective role.
- [x] Legacy users without tenant headers keep the default membership/`users.company_id` fallback.
- [x] A request without `company_id` fails closed and requires an explicit safe data migration.
- [x] Existing confirm, approve, reject, cancel, estimate-control, and status-transition rules are not changed.
- [x] Delete, KP, offers, recipients, deliveries, and warehouse mutations remain outside this slice.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.company_context.test_service` (21 tests passed)
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/features/company_context/service.py`
- [x] Tracked frontend test suite (56 tests passed).
- [x] `npm run build`
- [x] Production health reported version `a69b4af503eb`, database OK, service active, and no warning-level log entries after deploy.

**Dependencies:** Task M2.1

**Files touched:**
- `backend/features/company_context/service.py`
- `backend/features/company_context/test_service.py`
- `backend/main.py`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task M2.3: Supply Request Delete And Rollback Isolation

**Description:** Apply Tenant Context Kernel to `DELETE /supply-requests/{id}`. Keep the existing cancel/rollback behavior, but authorize it from the request's stored `company_id` and prevent the optional received-stock rollback from touching deliveries, documents, materials, or warehouse history of another company.

**Status:** Completed, verified, and released as production commits `a3345b9b` and `01360f07` on 2026-07-10.

**Acceptance criteria:**
- [x] The stored request `company_id` is the source of truth for delete/cancel authorization.
- [x] Conflicting `X-Company-Id`, `Все компании`, a foreign membership, or a request without `company_id` fails before mutation.
- [x] Delete roles, project/package access, rollback leadership check, and audit role use the selected company's effective membership.
- [x] Deliveries linked to the request must have the same `company_id`; inconsistent rows fail closed.
- [x] Linked warehouse invoices and supply history must have the same `company_id` before rollback evaluation.
- [x] Received-stock rollback looks up materials by company and writes `warehouse_history.company_id` explicitly.
- [x] Existing idempotent cancel responses, received-delivery guard, document guard, stock-balance checks, and status names remain unchanged.
- [x] KP, offers, recipients, delivery endpoints, and general warehouse reads/writes remain outside this slice.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.company_context.test_service` (26 tests passed)
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/features/company_context/service.py`
- [x] Tracked frontend test suite (14 suites / 66 tests passed); local untracked tests are outside the release snapshot.
- [x] `npm run build`
- [x] Production health reported version `01360f075407`, service active, no warning-level log entries, HTTP and browser smoke passed.

**Dependencies:** Task M2.2

**Files touched:**
- `backend/features/company_context/service.py`
- `backend/features/company_context/test_service.py`
- `backend/main.py`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task M2.4: Supply Request KP Mutation Isolation

**Description:** Apply Tenant Context Kernel to `POST /supply-requests/{id}/request-kp`. Use the request's stored `company_id` as the immutable source of truth, authorize with the selected membership role, and keep recipients, offers, request status, and notifications in that company.

**Status:** Completed, verified, and released as production commits `44827df7` and `777bcca7` on 2026-07-10.

**Acceptance criteria:**
- [x] The stored request `company_id` is authoritative; body `companyId` cannot reassign the request.
- [x] Conflicting company header/body, `Все компании`, foreign membership, or missing request company fails before mutation.
- [x] KP authorization and project access use the selected company's effective membership role and assignments.
- [x] The request row is locked while recipients, offers, status, and notifications are prepared.
- [x] All recipient and offer rows for the request are locked and checked against the request company before any email/MAX notification.
- [x] The final status update includes `WHERE id AND company_id`, does not rewrite `company_id`, and fails if the target changed.
- [x] Existing supplier grouping, visibility diagnostics, approved-status guard, offer creation, and notification behavior remain unchanged.
- [x] Recipient diagnostics, supplier suggestions/comparison, supplier offer lifecycle, invoices, and deliveries remain outside this slice.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.company_context.test_service` (27 tests passed)
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/features/company_context/service.py`
- [x] Tracked frontend test suite (14 suites / 66 tests passed).
- [x] `npm run build`
- [x] Production health reported version `777bcca7b422`, service active, no warning-level log entries, HTTP and browser smoke passed.

**Dependencies:** Task M2.3

**Files touched:**
- `backend/features/company_context/service.py`
- `backend/features/company_context/test_service.py`
- `backend/main.py`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task M2.5: Supply Request Recipient Read Isolation

**Description:** Apply Tenant Context Kernel to `GET /supply-requests/{id}/recipients`. Resolve access from the request's stored company, authorize with the effective membership role, and fail closed when recipient or legacy offer rows belong to another company.

**Status:** Completed, verified, and released as production commit `7052491b` on 2026-07-10.

**Acceptance criteria:**
- [x] Stored request `company_id` is authoritative for recipient diagnostics.
- [x] Conflicting header, foreign membership, missing request company, or disallowed effective role fails; `Все компании` safely resolves the concrete company stored on the requested document.
- [x] Project access uses the effective membership assignments.
- [x] Recipient rows are validated as one company chain and filtered by that company.
- [x] Legacy fallback from `supplier_offers` validates every offer row before building diagnostics.
- [x] Supplier cabinet reads and recipient/offer mutations remain outside this slice.

**Verification:**
- [x] Company-context unit tests (28 passed).
- [x] Python compile.
- [x] Tracked frontend tests (14 suites / 66 tests passed).
- [x] `npm run build`.
- [x] Production version `7052491bc2d4`; HTTP smoke, active service check, fresh warning log check, and browser rendering of `/` and `/app` passed.

**Dependencies:** Task M2.4

**Estimated scope:** S

## Task M3: Supplier And Procurement Isolation

**Description:** Make `company_supplier_links` and `supply_request_recipients` the source of truth for company-specific supplier relationships, KP visibility, offers, invoices, and deliveries.

**Acceptance criteria:**
- [ ] A global supplier sees only documents explicitly addressed to its linked supplier identities for the correct client company.
- [ ] Contract terms, ratings, categories, and payment conditions belong to the company-supplier link.
- [ ] Supplier invoices and deliveries inherit the verified request/offer company.

**Verification:**
- [ ] Linked and unlinked supplier scenarios are covered.
- [ ] `npm run smoke:supply-chain`
- [ ] `npm run smoke:workflow-invoice`

**Dependencies:** Task M2

**Estimated scope:** M

## Task M3.1: Supplier Offer Read Isolation

**Description:** Make `GET /supplier-offers` respect the selected internal company context and require explicit recipient evidence for supplier-facing reads. This slice is read-only and does not migrate or rewrite existing offers, invoices, deliveries, or warehouse documents.

**Status:** Completed, verified, and released as production commit `13e84bb5` on 2026-07-10.

**Acceptance criteria:**
- [x] Internal supply roles receive offers only from the selected company or companies available in their account summary.
- [x] Supplier-facing offers require the offer and request to have the same `company_id`.
- [x] A recipient must match both the authenticated supplier identity and the concrete offer supplier group, so one supplier cannot see another supplier's offer for the same request.
- [x] Mixed-company recipient rows fail closed for supplier-facing offer reads.
- [x] Legacy fallback is available only when the request has no recipient rows and `selected_suppliers` explicitly contains the authenticated supplier identity.
- [x] Existing data and write endpoints are unchanged in this slice.

**Verification:**
- [x] Supplier access and company-context unit tests (31 passed).
- [x] Python compile.
- [x] Tracked frontend tests (14 suites / 66 tests passed).
- [x] `npm run build`.
- [x] Production version `13e84bb5522c`; HTTP smoke, active service check, fresh warning log check, and browser rendering of `/` and `/app` passed.
- [ ] Protected `smoke:supply-chain` is blocked because production has no `SMOKE_EMAIL`, `SMOKE_PASSWORD`, or `SMOKE_TOTP_SECRET` configured.

**Dependencies:** Task M2.5

**Estimated scope:** S

## Task M3.2: Supplier Offer History And Mutation Isolation

**Description:** Protect the history and update routes for one supplier offer with the same verified chain used by the offer list. Supplier actions require explicit recipient visibility; internal actions require the offer's stored company and effective membership role. Before any mutation, all offers and recipients for the request are locked and checked against one company.

**Status:** Completed, verified, and released as production commit `8d118455` on 2026-07-10.

**Acceptance criteria:**
- [x] Supplier history and updates require explicit visibility to the concrete offer, not only a matching global supplier id.
- [x] Internal history and updates resolve access from the offer's stored company and effective membership role.
- [x] Offer and request `company_id` must match.
- [x] Every offer and recipient row for the request is locked and validated before mutation.
- [x] Recipient status updates and competing-offer rejection include `company_id`.
- [x] Event history records the effective company actor for internal actions.
- [x] Existing offer data, invoices, deliveries, and supplier identities are not migrated or rewritten by the release.

**Verification:**
- [x] Supplier access and company-context unit tests (31 passed).
- [x] Python compile.
- [x] Tracked frontend tests (14 suites / 66 tests passed).
- [x] `npm run build`.
- [x] Production version `8d118455942c`; HTTP smoke, active service check, fresh warning log check, and browser rendering of `/` and `/app` passed.
- [ ] Protected `smoke:supply-chain` remains blocked by missing production smoke credentials and TOTP secret.

**Dependencies:** Task M3.1

**Estimated scope:** S

## Task M3.3: Supplier Offer Creation Isolation

**Description:** Protect `POST /supplier-offers` with the request's stored company and explicit recipient identity. Internal users authorize through the effective company membership; supplier users resolve the recipient from their linked supplier identity. A pending offer generated by the KP request is updated in place instead of duplicated.

**Status:** Completed, verified, and released as production commit `fdf155b3` on 2026-07-10.

**Acceptance criteria:**
- [x] The request is locked and its stored `company_id` is authoritative.
- [x] Internal creation requires an allowed effective role in the request company and project access.
- [x] Supplier creation ignores an untrusted payload supplier id and resolves the explicit recipient for the authenticated supplier.
- [x] All existing recipient and offer rows for the request are locked and checked against one company.
- [x] A supplier not addressed by recipient rows is denied; legacy fallback is used only when no recipient rows exist and `selected_suppliers` explicitly matches.
- [x] An existing pending offer is updated in place; answered, selected, or closed offers cannot be duplicated through POST.
- [x] Reusing a pending offer writes a `draft_updated` event to the existing offer history.
- [x] Existing invoices, deliveries, warehouse documents, and historical offers are not migrated.

**Verification:**
- [x] Supplier access and company-context unit tests (32 passed).
- [x] Python compile.
- [x] Tracked frontend tests (14 suites / 66 tests passed).
- [x] `npm run build`.
- [x] `smoke:supply-chain` now asserts that repeated POST reuses one pending offer and records the update in its history; production run remains pending until release and credentials.
- [x] Production version `fdf155b316cc`; HTTP smoke, active service check, clean warning log, and browser rendering of `/` and `/app` passed.

**Dependencies:** Task M3.2

**Estimated scope:** S

## Task M3.4: Supplier Invoice From Offer Isolation

**Description:** Protect `POST /supplier-offers/{id}/create-invoice`. The invoice inherits the stored offer/request company. Supplier users require explicit visibility to the concrete offer; internal users authorize through the effective company membership. Existing and duplicate invoices are locked and must remain in the same company.

**Status:** Completed, verified, and released as production commit `df174fe3` on 2026-07-10.

**Acceptance criteria:**
- [x] The approved offer and its request are locked and must have the same non-empty `company_id`.
- [x] Payload `companyId` cannot reassign the invoice to another company.
- [x] Supplier creation requires explicit recipient visibility to the concrete offer, including the existing fail-closed mixed-recipient rule.
- [x] Internal creation uses the offer's stored company, effective membership role, project access, and package access.
- [x] All offers and recipient rows for the request are locked and checked against one company before invoice creation.
- [x] Existing invoices for the offer are locked, checked by company, and reused idempotently.
- [x] Concurrent writes for the same company, supplier group, invoice number, date, and project are serialized by a transaction-scoped advisory lock.
- [x] A document duplicate is updated only with `WHERE id AND company_id`; a changed company fails closed.
- [x] A duplicate document must belong to the same supplier group and cannot already belong to another offer or request.
- [x] New invoices write the verified company explicitly; existing invoice, delivery, warehouse, and payment records are not migrated.
- [x] Invoice number, ISO date, positive finite amount, and VAT range are validated before writing.
- [x] New or safely linked invoices write an audit event to the concrete offer history.
- [x] The supplier UI displays non-200 API details instead of reporting false success.

**Verification:**
- [x] Supplier access and company-context unit tests (32 passed).
- [x] Python compile for backend and `scripts/smoke-supply-chain.py`.
- [x] Tracked frontend tests (14 suites / 66 tests passed).
- [x] `npm run build`.
- [x] Supply smoke asserts that repeated invoice creation returns the same invoice with `alreadyExists=true` and verifies the `invoice_created` audit event.
- [x] Production version `df174fe33380`; HTTP smoke, active service, clean warning log, and live in-app browser rendering of `/` and `/app` passed. The standalone headless profile was flaky, while the connected browser showed populated DOM and no console errors.

**Dependencies:** Task M3.3

**Files touched:**
- `backend/main.py`
- `scripts/smoke-supply-chain.py`
- `src/features/supply/supplyActions.js`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task M3.5: Supplier Invoice Read Isolation

**Description:** Protect `GET /supplier-invoices`. Internal users read only the selected company or the companies available in their account context. The external supplier cabinet remains unified across client companies, but only for the authenticated supplier group and explicit offer-recipient chain. Joined delivery and warehouse data must remain in the invoice company.

**Status:** Implemented and verified locally on 2026-07-10; independent production release is pending.

**Acceptance criteria:**
- [x] Internal invoice reads resolve `X-Company-Id` / `X-Company-Mode` through the company-context kernel.
- [x] A selected company uses the effective membership role, project access, and package access.
- [x] `all_companies` reads are limited to available company ids and evaluate each company's own membership role, projects, and packages independently.
- [x] A legacy `users.project_name` fallback is kept only for the default membership without explicit project assignments and cannot leak into another company.
- [x] Supplier reads require an existing positive invoice company and the authenticated duplicate supplier group.
- [x] An invoice linked to an offer requires the same invoice/offer company and explicit supplier offer visibility; direct legacy documents remain visible only by strong supplier identity.
- [x] Joined delivery and warehouse invoice rows require the same `company_id` as the supplier invoice.
- [x] SQL company column aliases are validated before interpolation.
- [x] Existing invoices, deliveries, warehouse documents, and payments are not rewritten.

**Verification:**
- [x] Company-context and supplier-access unit tests (38 passed).
- [x] Python compile and `git diff --check`.
- [x] Tracked frontend tests (14 suites / 66 tests passed).
- [x] `npm run build`.
- [x] Supply smoke selects the internal company explicitly, rejects any foreign-company row, compares supplier/internal invoice company, and verifies linked document visibility.

**Dependencies:** Task M3.4

**Files touched:**
- `backend/features/company_context/service.py`
- `backend/features/company_context/test_service.py`
- `backend/features/supplier_access/service.py`
- `backend/features/supplier_access/test_service.py`
- `backend/main.py`
- `scripts/smoke-supply-chain.py`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task M4: Warehouse Isolation And Transfers

**Description:** Scope warehouse balances, invoices, receipts, write-offs, and history by company. Model cross-company movement as an explicit transfer rather than a normal warehouse edit.

**Acceptance criteria:**
- [ ] Warehouse reads and writes require verified company context.
- [ ] Duplicate invoice checks include company.
- [ ] A cross-company transfer records source, destination, both sides, documents, and audit events.

**Verification:**
- [ ] `npm run smoke:max-warehouse`
- [ ] Company-isolation smoke covers balance and history.

**Dependencies:** Task M3

**Estimated scope:** M

## Task M4.1: Main Warehouse Read Isolation

**Description:** Make `GET /warehouse-main` resolve the selected company context and return only main-warehouse rows belonging to the selected company or the allowed account summary.

**Status:** Implemented and pushed in `83529e6c`; production release pending.

**Acceptance criteria:**
- [x] The endpoint accepts `X-Company-Id` and `X-Company-Mode` using the tenant context kernel.
- [x] Warehouse rows are filtered by `warehouse_main.company_id`.
- [x] Existing role and price visibility rules remain unchanged.
- [x] No warehouse data is rewritten.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Production smoke confirms selected-company warehouse rows.

**Dependencies:** Task M3.5

**Estimated scope:** XS

## Task M4.2: Warehouse Movement Read Isolation

**Description:** Add a compatible `company_id` to warehouse movements and scope movement reads by the selected tenant context. Existing rows use the legacy company `1` until a later audited backfill.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] Existing movement rows receive a non-null legacy company value.
- [x] `GET /warehouse-movements` resolves `X-Company-Id` and `X-Company-Mode`.
- [x] Movement reads apply the company scope for project, warehouse, and finance roles.
- [x] Movement creation and balances remain unchanged in this slice.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Production smoke confirms selected-company movement visibility.

**Dependencies:** Task M4.1

**Estimated scope:** S

## Task M4.3: Warehouse Movement Write Isolation

**Description:** Require a verified company context when creating a warehouse movement and keep source, target, material, and movement rows inside that company.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] The movement write resolves the selected company context.
- [x] Source and destination projects cannot belong to different companies.
- [x] Source and target material lookups include `company_id`.
- [x] New movement rows carry `company_id`.
- [x] Existing balance and audit behavior remains otherwise unchanged.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Production smoke confirms a cross-company movement is rejected.

**Dependencies:** Task M4.2

**Estimated scope:** S

## Task M4.4: Warehouse History Read Isolation

**Description:** Scope warehouse history reads by the selected company while preserving role, project, and package restrictions.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] The endpoint resolves `X-Company-Id` and `X-Company-Mode`.
- [x] Proраб, worker, warehouse, and finance reads include the company boundary.
- [x] Existing project/package/person filters remain active.
- [x] Manual history creation and deletion are unchanged.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Production smoke confirms history does not cross company boundaries.

**Dependencies:** Task M4.3

**Estimated scope:** S

## Task M4.5: Manual Warehouse History Write Isolation

**Description:** Bind manual warehouse history corrections to one selected company and authorize the action through the user's effective role in that company.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] `all_companies` mode cannot create a manual correction.
- [x] A project correction must match the project's stored company.
- [x] Only a director or deputy director in the selected company can create the row.
- [x] Project and package checks use the selected company membership.
- [x] The new history row stores `company_id` and commits transactionally.

**Verification:**
- [ ] Backend compile and company-context tests pass.
- [ ] Frontend tests and production build pass.

**Dependencies:** Task M4.4

**Estimated scope:** S

## Task M4.6: Warehouse History Resource Isolation

**Description:** Verify the stored history-row company and the user's effective company role before returning the existing non-destructive deletion response.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] The endpoint resolves access from the row's stored `company_id`.
- [x] A caller cannot use another company's row id with a mismatched company header.
- [x] Project access is evaluated through the selected company membership.
- [x] Physical deletion remains prohibited and no data is changed.

**Verification:**
- [ ] Backend compile and company-context tests pass.
- [ ] Frontend tests and production build pass.

**Dependencies:** Task M4.5

**Estimated scope:** XS

## Task M4.7: Warehouse Invoice Read Isolation

**Description:** Scope `GET /warehouse-invoices` by the selected company context while preserving existing role, project, package, and price behavior.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] The endpoint resolves `X-Company-Id` and `X-Company-Mode`.
- [x] Every invoice query includes the stored `company_id` boundary.
- [x] Existing project and item-package filtering remains active.
- [x] The response exposes `companyId` for smoke verification.
- [x] Invoice creation, accounting, and cancellation remain unchanged.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Frontend tests and production build pass.

**Dependencies:** Task M4.6

**Estimated scope:** S

## Task M4.8: Warehouse Invoice Creation Isolation

**Description:** Resolve one verified company for manual warehouse invoice creation and keep the invoice, linked documents, stock rows, and history inside that company.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] `all_companies` mode cannot create an invoice.
- [x] Project, supply request, supplier invoice, claimed company, and selected company must agree.
- [x] The effective role in the selected company authorizes warehouse receipt and supplier-invoice linking.
- [x] Duplicate source checks include `company_id`.
- [x] Material and main-warehouse lookups/inserts include `company_id`.
- [x] Invoice and warehouse-history rows use the same verified company.
- [x] Existing automatic Telegram/MAX path remains compatible through resource-derived company context.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Frontend tests and production build pass.
- [ ] Supply/MAX smoke verifies one complete receipt chain after deploy.

**Dependencies:** Task M4.7

**Estimated scope:** M

## Task M4.9: Warehouse Invoice Accounting Isolation

**Description:** Authorize accounting changes through the warehouse invoice's stored company and prevent linking a supplier invoice from another company.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] The stored warehouse-invoice company is the authorization source.
- [x] `X-Company-Id`, `X-Company-Mode`, and an optional payload company are validated.
- [x] Finance role and project/package access use the selected company membership.
- [x] A linked supplier invoice must have the same `company_id`.
- [x] Existing accounting statuses, photo rules, payment calculations, and idempotency remain unchanged.
- [x] Adding `company_id` to project payments remains explicitly deferred to Task M5.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Frontend tests and production build pass.
- [ ] Production smoke verifies the deployed version before protected mutation testing.

**Dependencies:** Task M4.8

**Estimated scope:** S

## Task M4.10: Warehouse Invoice Annulment Isolation

**Description:** Authorize annulment from the stored warehouse-invoice company and reverse stock only inside that company.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] Authorization runs before delivery/status details are returned.
- [x] The effective selected-company role controls annulment access.
- [x] Project and main-warehouse stock lookups include `company_id`.
- [x] Reversal history stores the invoice `company_id`.
- [x] A linked supplier invoice must remain in the same company.
- [x] Existing delivery protection, insufficient-stock checks, and idempotent already-annulled response remain unchanged.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Frontend tests and production build pass.
- [ ] Production version and warehouse smoke pass after deploy.

**Dependencies:** Task M4.9

**Estimated scope:** S

## Task M4.11: Main Warehouse Write Isolation

**Description:** Bind creation and updates of main-warehouse material cards to one selected company and authorize through the effective membership role.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] `POST /warehouse-main` requires one writable company and stores `company_id`.
- [x] `PUT /warehouse-main/{id}` authorizes from the row's stored company.
- [x] Both routes use the effective selected-company role.
- [x] `all_companies` remains read-only.
- [x] Updates include the stored company in the final SQL predicate.

**Verification:**
- [ ] Backend compile and focused tests pass.
- [ ] Frontend tests and production build pass.

**Dependencies:** Task M4.10

**Estimated scope:** S

## Task M5: Finance And Accounting Isolation

**Description:** Scope project payments, supplier payments, accounting records, contracts, and reports by verified company and legal entity.

**Acceptance criteria:**
- [ ] Money movement cannot be created or read across client accounts.
- [ ] Account summaries aggregate only companies inside one `platform_account`.
- [ ] Legal-entity details do not replace the working `company_id` boundary.

**Verification:**
- [ ] Finance role matrix covers company membership roles.
- [ ] Accounting and payment smoke scripts pass against safe test data.

**Dependencies:** Task M4

**Estimated scope:** M

## Task M5.1: Company Requisites Isolation

**Description:** Store and load legal/bank requisites for one selected company. Replace the global delete-and-insert behavior with a company-scoped upsert while preserving the existing frontend object contract.

**Status:** Deployed in `69f55f4b`; production health/version verified. Authenticated selected-company smoke remains pending because the smoke account requires initial 2FA setup.

**Acceptance criteria:**
- [x] Existing requisites receive legacy `company_id=1` without changing their values.
- [x] `GET /company-requisites` resolves the tenant context and returns only the selected company's row.
- [x] `all_companies` returns no arbitrary legal entity and asks the UI to select a company.
- [x] `POST /company-requisites` requires a concrete company and an effective finance role in that company.
- [x] Saving one company no longer deletes or changes another company's requisites.
- [x] One requisites row per company is enforced by a unique index.

**Verification:**
- [x] Backend compile and company-context tests pass.
- [x] Frontend tests and production build pass.
- [ ] Production smoke verifies selected-company reads after deploy.

**Dependencies:** Task M4

**Estimated scope:** S

## Task M5.2: Project Payments Isolation

**Description:** Make `project_payments` a company-owned money ledger. Scope direct and automatic payment paths by verified tenant context without changing the existing amount/sign semantics yet.

**Status:** Deployed in `5db2e496`; production health, database availability, public routes, and unauthenticated route protection verified. Authenticated tenant-data smoke remains pending because the smoke account requires initial 2FA setup.

**Acceptance criteria:**
- [x] Existing payment rows inherit only an unambiguous project company. M5.3b1 hardening quarantines unresolved/invalid legacy rows with `company_scope_verified=false` and `company_id=NULL`; all current server writes pass a non-null company explicitly and use company indexes.
- [x] `GET /project-payments` filters by effective role in every allowed company; customers only see positive payments for assigned projects.
- [x] Direct payment creation requires one selected company, an effective finance role, and a project belonging to that company.
- [x] Payment reversal authorizes from the payment row's stored company and writes the reversal to the same company.
- [x] Deleting a linked brigade payment creates an idempotent reversal instead of physically deleting the central money-ledger row.
- [x] Payments created from interim acts, brigade payments, and warehouse invoice accounting carry the verified company.
- [x] Legacy act/brigade sources with a project name shared by several companies fail closed with `409` until their own tables receive `company_id`.
- [x] General AI chat and the director finance tool cannot read `project_payments` outside the resolved company context.
- [x] The director finance tool omits unscoped manual `expenses` until that table receives `company_id`.
- [x] `all_companies` remains read-only for payment mutations.

**Verification:**
- [x] Payment-access, company-context, and supplier-access unit tests pass.
- [x] Frontend tests and production build pass.
- [x] Production health/version, database availability, public smoke, and unauthenticated `/project-payments` protection pass after deploy.
- [ ] Authenticated selected-company payment reads pass after smoke-account 2FA setup.

**Known follow-up:** M5.3 must finish stored ownership for the brigade chain. Also add ownership to `interim_acts` and `expenses`; then remove the remaining temporary duplicate-project-name guard and restore scoped manual expenses in the director tool.

**Dependencies:** Task M5.1

**Estimated scope:** M

## Task M5.3a: Brigade Read Isolation

**Description:** Close global read paths for brigade contracts, payments, items, and acts using the existing `brigade_contracts.company_id` as the parent tenant boundary. Preserve current calculations and worker price masking.

**Status:** Implemented and pushed in `937d7a4f`; production release pending.

**Acceptance criteria:**
- [x] Contract reads resolve selected/all-company context through effective membership roles.
- [x] Payment reads join their parent contract and cannot bypass its company scope with `contract_id`.
- [x] Aggregate and per-contract item reads filter the outer item row by the worker's assigned package.
- [x] Brigade act reads join the parent contract and inherit its company scope.
- [x] Workers remain restricted by company, assigned project, contractor identity, and package.
- [x] Full-view roles see all brigade data only inside companies where that effective role is assigned.
- [x] Responses include `companyId` without removing existing fields.

**Verification:**
- [x] Brigade access tests cover finance, foreman, worker, package, and fail-closed cases.
- [x] Backend compile and focused tenant-access tests pass.
- [x] Frontend tests and production build pass.
- [ ] Production version and authenticated selected-company reads pass after deploy.

**Known follow-up:** M5.3b1-M5.3b3 must bind payment, contract, item, act, and estimate-distribution mutations to stored company ownership before the brigade chain is pilot-ready.

**Dependencies:** Task M5.2

**Estimated scope:** M

## Task M5.3b1: Brigade Payment Write Isolation

**Description:** Store payment ownership explicitly and derive every brigade payment mutation from the parent contract's saved company. Keep contract/item/act writes out of this step.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] Brigade contract/payment ownership columns are indexed; exact/unique legacy rows are backfilled, while ambiguous rows remain `NULL` and fail closed instead of being assigned to company `1`.
- [x] Payment reads fail closed when the payment and parent contract companies differ.
- [x] Payment creation resolves the effective finance role from the contract's stored company, not from request project text.
- [x] Payment creation stores the same company in `brigade_payments` and linked `project_payments`, plus the exact `project_payment_id` in one transaction.
- [x] Payment deletion validates stored child/parent ownership and reverses only the exact linked `project_payments` row; ambiguous legacy links require manual reconciliation.
- [x] Contract locking serializes available-balance checks so concurrent requests cannot overpay the same completed amount.
- [x] Non-finite payment values (`NaN/Infinity`) and corrupted stored totals fail closed before a write or reversal.
- [x] `NULL`, non-finite, and sub-cent brigade amounts are quarantined or rejected; accepted amounts are rounded to kopecks before both linked inserts.
- [x] Ambiguous/unmapped legacy `project_payments` no longer fall back to company `1`; verified new writes require explicit company ownership at the database boundary.
- [x] Exact `project_id` remains authoritative if the stored legacy project name is stale after a rename.
- [x] `all_companies` and a conflicting `companyId` remain invalid for payment mutations.

**Verification:**
- [x] Brigade access tests cover matching, missing, and conflicting child-company ownership.
- [x] Backend compile and focused tenant-access tests pass.
- [x] Frontend tests and production build pass.
- [x] Isolated PostgreSQL migration test covers exact, unique, ambiguous, stale-id, one-to-one link, duplicate-link, and idempotent rerun cases.
- [ ] Production version and authenticated selected-company payment smoke pass after deploy.

**Known follow-up:** M5.3b2 must close contract create/update/cancel and company-safe contractor assignment. M5.3b3 must close pricelist loading, items, acts, and estimate distribution.

**Dependencies:** Task M5.3a

**Estimated scope:** S

## Task M5.3b2: Brigade Contract Write Isolation

**Description:** Bind brigade contract creation to one selected company and canonical project, then authorize update/cancellation from the company already stored on the contract. Keep item, act, pricelist-load, and estimate-distribution writes out of this step.

**Status:** Deployed in `8c971801`; public production smoke passed. Authenticated selected-company smoke remains pending.

**Acceptance criteria:**
- [x] Contract creation requires one selected company and the effective director/deputy role in that company; `all_companies` cannot mutate.
- [x] The project is resolved and locked inside the selected company by exact ID/name, and the contract explicitly stores the same `company_id`, `project_id`, and canonical project name.
- [x] Contractor lookup is limited to active users/memberships and staff of the selected company; ambiguous names and staff/user ID collisions fail closed instead of guessing.
- [x] A staff card without a system user may remain a named, unlinked brigade; it never receives an accidental foreign `contractor_id`.
- [x] Project/package access is added only to the contractor membership in the selected company. Legacy `users` scope is changed only when `users.company_id` is that same company.
- [x] Contract update and cancellation authorize through the stored contract owner, reject body/header company conflicts, lock the contract/project, and write with both `id` and `company_id`.
- [x] Existing contract fields, status-cancellation semantics, response fields, and creation-time pricelist auto-load remain compatible.
- [x] The create form does not add a phantom local contract after a server rejection and uses the server-confirmed company/project after success.

**Verification:**
- [x] Brigade access tests cover selected-company role checks, cross-company contractor rejection, ambiguous names, staff/user ID collisions, unlinked staff cards, and company-bound membership/legacy update predicates.
- [x] Focused form tests cover rejected and successful tenant-safe creation.
- [x] Backend compile, all feature tests, frontend tests, and production build pass before release.
- [ ] Production version and authenticated selected-company create/update/cancel smoke pass after deploy.

**Known follow-up:** M5.3b3 must close explicit pricelist loading, contract-item mutations, brigade acts, and estimate distribution before the brigade chain is ready for a two-company pilot.

**Dependencies:** Tasks M5.3a-M5.3b1

**Estimated scope:** S

## Task M5.3b3: Brigade Child Write Isolation

**Description:** Authorize pricelist loading, contract-item mutations, brigade acts, and estimate distribution through their stored parent company and canonical project.

**Status:** Deployed in `d885ba52`; public production smoke passed. Authenticated selected-company smoke remains pending.

**Acceptance criteria:**
- [x] Explicit pricelist loading resolves and locks the parent contract, requires the effective selected-company role, and reads estimate quantities only from the same `company_id + project_id`.
- [x] Contract-item create/update/delete resolves the parent contract before mutation and rejects a package that differs from the contract package.
- [x] Estimate distribution resolves the stored estimate company, requires a canonical project ID, and creates contracts with that same company/project identity.
- [x] Contractor lookup and scope grants during distribution stay inside the selected company membership.
- [x] Brigade act creation resolves and locks the parent contract and derives company, project, brigade, package, and available amount from server data.
- [x] Client-supplied company/project names are routing hints only and cannot move a child row to another tenant.

**Verification:**
- [x] Backend compile passes.
- [x] All backend feature tests pass (`89` tests).
- [x] Staged diffs contain only the intended brigade child-write routes.
- [x] Production deploy and public smoke pass.
- [ ] Authenticated selected-company brigade smoke passes.

**Dependencies:** Tasks M5.3a-M5.3b2

**Estimated scope:** M

## Task M5.3b4: Primary Work Assignment Tenant Isolation

**Description:** Protect the primary `Назначить мастеру` workflow so its contract, items, contractor lookup, and access grant always inherit the stored company and exact project of the selected estimate.

**Status:** Deployed in `d885ba52`; public production smoke passed. Authenticated selected-company smoke remains pending.

**Acceptance criteria:**
- [x] `POST /estimates/{estimate_id}/work-assignment` resolves the estimate inside one selected company and checks the effective assignment role before any write.
- [x] Existing contracts are searched and locked by `company_id + project_id + work_package`; same-named projects in another company cannot be reused.
- [x] New contracts explicitly store the estimate's `company_id`, canonical `project_id`, and project name.
- [x] Contractor lookup and project/package scope grants are limited to the same company membership.
- [x] Contract-item updates remain bound to the resolved parent contract; client company/project text cannot move the assignment to another tenant.
- [x] `all_companies`, a conflicting company context, a missing exact project, and a non-finite coefficient fail before commit.
- [x] Existing response fields remain compatible; `companyId` and `projectId` are additive confirmation fields.

**Verification:**
- [x] Focused route tests cover tenant-bound contract creation/update, rejected group mode with rollback, and non-finite/zero coefficient rejection.
- [x] Backend compile and all discovered backend feature tests pass.
- [x] Frontend tests, production build, release diff review, and exact staged-snapshot checks pass.
- [x] Production deploy and public smoke pass.
- [ ] Authenticated selected-company `Назначить мастеру` smoke passes.

**Dependencies:** Tasks M5.3a-M5.3b3

**Estimated scope:** S

## Task M6: Remaining Tenant-Owned Domains

**Description:** Apply the same kernel to projects, estimates, materials, journals, acts, staff, files, notifications, exports, audit records, and AI/OCR jobs.

**Acceptance criteria:**
- [ ] Every new tenant-owned row has a traceable company source.
- [ ] Files and background jobs cannot be fetched or executed from another tenant.
- [ ] Platform support uses expiring, audited support sessions.

**Verification:**
- [ ] Domain-focused tests and the role matrix pass.
- [ ] Browser smoke covers one complete director workflow.

**Dependencies:** Tasks M2-M5

**Estimated scope:** L, delivered as separate domain slices

### Approved M6 Delivery Order

- [ ] `M6.0` Build a read-only registry of tenant-owned tables, routes, parent relations, file surfaces, jobs, and the authoritative source of `company_id`.
- [ ] `M6.1` Make projects the tenant root: selected-company reads/writes, immutable company ownership, and ID-based access instead of `project_name` security.
- [ ] `M6.2` Protect files and document versions with parent ownership; keep legacy `/uploads` compatible while new protected documents use authorized downloads or short signed URLs.
- [ ] `M6.3` Scope staff, memberships, personal documents, consents, and dismissal so one company membership can be disabled without disabling the global account.
- [ ] `M6.4` Scope company messages, estimates, versions, changes, templates, and estimate chat by stored company and verified project ID.
- [ ] `M6.5` Scope work journal, rooms/measurements, contract items, journals, acts, and their cascading material/document writes.
- [ ] `M6.6` Scope assignments, reports, attachments, AI/OCR tasks, summaries, dedupe keys, and background execution.
- [ ] `M6.7` Scope MAX files, notifications, deep links, and outbox dispatch by company and verified recipient membership.
- [ ] `M6.8` Add company-aware audit/export contracts and negative read/write tests for every migrated domain.

## Task M6.2a: New Upload Ownership Kernel

**Description:** Register the selected company for every new `/upload-photo` file, bind project ownership only from an exact `projectId`, and keep legacy `/uploads` readable until the authorized download path is ready.

**Status:** Deployed in `51550487`; public production smoke passed.

**Acceptance criteria:**
- [x] Upload writes require one concrete company; `all_companies` cannot upload.
- [x] `file_ownership` stores the selected `company_id`, optional exact `project_id`, storage identity, context, and uploader.
- [x] A client-supplied project name alone cannot become project ownership; without exact `projectId` the file remains company-common.
- [x] Main warehouse, CRM, company documents, and other non-project namespaces no longer fail project resolution.
- [x] The shared frontend upload action sends `projectId` only when the name has one exact project match or the caller supplies an explicit ID.
- [x] Existing `/uploads` URLs remain available during the compatibility window.

**Verification:**
- [x] Document access tests cover concrete-company ownership, parent-company conflicts, ID-based namespaces, and name-only company-common fallback.
- [x] Frontend upload tests cover one exact project match, non-project names, and duplicate names.
- [x] Backend compile, all feature tests, frontend tests, build, and exact staged snapshot pass.
- [x] Production deploy and public smoke pass.

**Known follow-up:** `M6.2b` must return an authorized URL for newly registered local files and verify the stored file company/project before serving bytes. S3 private objects and signed URLs remain a separate storage step.

**Dependencies:** Tasks M1-M2, M6.1

**Estimated scope:** S

## Task M6.2b: Tenant File Metadata And Cleanup Smoke

**Description:** Return the registered file ID, authorize metadata reads through the stored company/project owner, and provide an ownership-checked cleanup route for smoke artifacts.

**Status:** Deployed through `7fcda405`; authenticated production smoke passed.

**Acceptance criteria:**
- [x] `/upload-photo` returns `fileId` and the stored company/project confirmation.
- [x] `GET /tenant-files/{id}` exposes metadata only to an effective member of the stored company and verifies project access when present.
- [x] `DELETE /tenant-files/{id}` requires one concrete company and allows only the uploader or company leadership.
- [x] Cleanup removes both local files and S3 objects before removing the ownership row.
- [x] Unsafe or missing local storage and unavailable S3 fail closed without deleting the ownership row.
- [x] `smoke:tenant-files` uploads a one-pixel technical PNG, verifies metadata, deletes it, and confirms `404` after cleanup.

**Verification:**
- [x] Backend and smoke script compile.
- [x] Focused document-access tests pass (`10` tests); the full working-tree backend suite passes (`105` tests).
- [x] Baseline production deploy, nginx routing, and authenticated `npm run smoke:tenant-files` pass.
- [x] Fail-closed hardening from `4107a4e4` and cursor hotfix `7fcda405` are deployed and rechecked.

**Known follow-up:** M6.2c serves protected bytes; M6.2d must migrate consumers and complete the private-storage cutover.

**Dependencies:** Task M6.2a

**Estimated scope:** S

## Task M6.2c: Authorized Tenant File Content

**Description:** Serve registered local and S3 file bytes only after authorizing the stored company/project owner, without breaking existing public URLs during migration. Keep private S3 ACL cutover as a separate storage step.

**Status:** Deployed in `f1d9e1de` with cursor hotfix `7fcda405`; authenticated production content smoke passed.

**Acceptance criteria:**
- [x] `GET /tenant-files/{id}/content` authorizes from the stored company and exact project before reading storage.
- [x] Local content resolves only inside the configured uploads directory and returns `404` when the physical object is missing.
- [x] S3 content is fetched by a server-side signed request only after authorization; missing or unavailable storage fails closed.
- [x] Protected responses use `private, no-store`, `nosniff`, sandbox CSP, same-origin resource policy, and an encoded filename.
- [x] PDF/raster images may open inline; HTML, SVG, and other active or unknown types are forced to binary attachment.
- [x] Upload and metadata responses expose additive `contentUrl`; existing compatibility `url` remains unchanged.
- [x] `smoke:tenant-files` verifies the exact uploaded bytes, content type, private cache policy, cleanup, and post-delete `404`.

**Verification:**
- [x] Focused document-access tests cover positive and negative authorization, local/S3 content, unsafe types, cleanup, and unavailable storage (`18` tests).
- [x] Backend and smoke script compile.
- [x] Full working-tree backend suite (`113` tests) and exact staged snapshot (`109` backend, `74` frontend) plus production build pass.
- [x] Production deploy, public/API smoke, authenticated `npm run smoke:tenant-files`, cleanup, and zero remaining smoke ownership rows pass.

**Known follow-up:** M6.2d must migrate document consumers from compatibility URLs to the protected endpoint, switch new S3 objects away from `public-read`, and then retire public access only after a usage audit.

**Dependencies:** Tasks M6.2a-M6.2b

**Estimated scope:** S

## Task M6.2c1: Tenant File Adversarial Hardening

**Description:** Close the authorization, storage-integrity, streaming, and cleanup gaps found by an adversarial review of the deployed M6.2c baseline.

**Status:** Deployed and verified in production through `224238cd`.

**Acceptance criteria:**
- [x] Restricted roles fail closed when duplicate project names cannot be resolved to their exact assigned `project_id`; upload and download use the same rule.
- [x] Metadata, content, and delete reject local/S3 pointers outside the canonical company/project namespace before storage access.
- [x] Local reads use no-follow descriptors and never reopen a validated path.
- [x] Local/S3 deletion is retryable across database or storage failure and keeps an explicit cleanup state until both sides agree.
- [x] S3 reads and deletes require HTTPS and reject redirects; reads require a bounded `Content-Length` and close the source on completion or disconnect.
- [x] Missing, oversized, changed, symlinked, or unavailable storage fails closed.
- [x] `smoke:tenant-files` verifies exact bytes and confirms the compatibility URL stops serving the object after deletion; cleanup failure fails the smoke.

**Verification:**
- [x] Document-access tests pass (`43` tests); project-access tests pass (`11` tests).
- [x] Full local backend feature discovery passes (`140` tests); backend/smoke compile and frontend production build pass.
- [x] Production runtime reports `224238cd`; public smoke and authenticated `npm run smoke:tenant-files` pass, smoke rows are `0`, cleanup statuses are empty, and the temporary user is disabled.

**Dependencies:** Task M6.2c

**Estimated scope:** S

## Task M6.2d1: Protected Project-Letter Attachments

**Description:** Start the consumer migration with one display-only document surface: newly uploaded project-letter attachments use the authorized tenant-file content endpoint, while all other upload flows and existing stored URLs remain compatible.

**Status:** Deployed in `8132954e`; public smoke and authenticated director UI check passed.

**Acceptance criteria:**
- [x] The shared upload helper returns the compatibility `url` by default, so existing consumers do not change behavior.
- [x] An explicitly migrated consumer may request `contentUrl`, with compatibility fallback when an older backend does not return it.
- [x] New project-letter attachments send the current exact `projectId` and store the protected `/tenant-files/{id}/content` path.
- [x] Existing project-letter rows and all OCR, accounting, warehouse, chat, and photo consumers remain unchanged.
- [x] New S3 objects remain `public-read` until the protected consumer audit is complete; private-storage cutover is not part of this slice.

**Verification:**
- [x] Focused upload-helper and project-letter component tests pass (`4` tests).
- [x] Exact tracked frontend suite passes (`17` suites / `76` tests); full working-tree suite also passes (`18` suites / `81` tests), and the production build succeeds.
- [x] Production runtime reports `8132954e`; public smoke passes and the authenticated director browser opens the test-object letter form without console errors.
- [x] Authenticated `smoke:tenant-files` passed under the existing test foreman after the follow-up rollout; exact bytes, protected read, cleanup, compatibility-object disappearance, and zero remaining smoke rows were confirmed.

**Known follow-up:** Continue M6.2d one display-only consumer at a time. Photo previews need a separate authenticated Blob-loader decision because protected responses use same-origin resource policy; do not switch S3 to private until those consumers are migrated and audited.

**Dependencies:** Tasks M6.2c-M6.2c1

**Estimated scope:** S

## Task M6.2d2: Protected Project-Document Registry Scans

**Description:** Continue the consumer migration with the direct scan paths in the existing project document registry. New-document scans and scans added to existing rows use authorized tenant-file content URLs. The OCR source remains on the compatibility URL until recognition can read protected content server-side.

**Status:** Deployed in `7abf86e1`; production runtime `b05fac7e` passed public, authenticated file, API, and registry UI checks.

**Acceptance criteria:**
- [x] Both direct project-document scan upload paths send exact `projectId` and request protected `contentUrl` with compatibility fallback.
- [x] The project screen passes its current immutable project ID into the registry component.
- [x] Document-recognition upload sends exact `projectId` but does not opt in to protected URL yet.
- [x] Existing project-document rows and every non-registry upload consumer remain unchanged.
- [x] S3 remains `public-read`; private-storage cutover is still outside this slice.

**Verification:**
- [x] Focused upload-helper, letter, and document-registry tests pass (`3` suites / `7` tests).
- [x] Exact tracked frontend suite passes (`18` suites / `79` tests); full working-tree suite passes (`19` suites / `84` tests), and the production build succeeds.
- [x] Production deploy and public smoke pass; `/estimates?summary=true` returns `200` with `9` rows and `/material-transfers` returns `200` after runtime import hotfixes `3cf4d84e` and `b05fac7e`.
- [x] A real HttpOnly-cookie browser session opens `Проекты -> Документы -> Реестр -> Добавить документ`; the direct scan and OCR controls render without a new ASGI `500`. No business document or orphan upload was created.
- [x] Authenticated tenant-file smoke passes after the rollout and leaves `0` `smoke-tenant-files` ownership rows.

**Known follow-up:** Migrate OCR only after the recognition backend can consume protected content. Before any inline photo surface moves, add an authenticated Blob URL loader with object-URL cleanup because protected responses enforce same-origin resource policy. `project_documents` itself is still a legacy name-based record surface and must receive stored `company_id/project_id` under the wider M6 project-record isolation; protected file authorization does not replace that row migration.

**Dependencies:** Task M6.2d1

**Estimated scope:** S

## Task M6.2d3: Authenticated Protected Preview Kernel

**Description:** Add the shared frontend primitive needed before protected tenant files can be rendered inside `<img>` or another inline preview. This slice does not migrate a business screen or change stored file URLs.

**Status:** Deployed in `6a45a2ea`; production verification passed.

**Acceptance criteria:**
- [x] Compatibility `/uploads`, `blob:`, `data:`, and absolute external URLs remain direct and do not trigger a Blob fetch.
- [x] Only a strict local `/tenant-files/{positiveId}/content` path enters protected mode; lookalike external or protocol-relative URLs are rejected.
- [x] Protected bytes load through the normal authenticated fetch path with cookies and `no-store`, preserving company-context headers and the temporary Bearer fallback from the global wrapper.
- [x] A failed protected request returns no image source and never falls back to the compatibility URL.
- [x] URL changes or unmount abort unfinished requests; created object URLs are always revoked during cleanup.
- [x] No business component, upload contract, stored document, or S3 ACL changes in this foundation slice.

**Verification:**
- [x] Focused Blob-loader tests pass (`6` tests).
- [x] Exact tracked frontend suite passes (`19` suites / `85` tests); full working-tree suite passes (`20` suites / `90` tests).
- [x] Production build succeeds.
- [x] Production deploy, public smoke, and authenticated tenant-file smoke pass; cleanup leaves `0` `smoke-tenant-files` ownership rows.

**Known follow-up:** `M6.2d4` must migrate one display-only inline photo surface and test loading/error UI before any broader photo rollout. Keep S3 `public-read` until every remaining direct consumer is audited.

**Dependencies:** Tasks M6.2d1-M6.2d2

**Estimated scope:** S

## Task M6.2d4: First Protected Inline Photo Consumer

**Description:** Move one existing display-only thumbnail in the main company chat onto the authenticated Blob loader. Keep message creation, upload return values, stored rows, the floating mini-chat, backend, and S3 ACL unchanged in this slice.

**Status:** Deployed in `845532f5`; production verification passed.

**Acceptance criteria:**
- [x] A strict local `/tenant-files/{positiveId}/content` chat photo renders only after the authenticated Blob request succeeds.
- [x] Clicking the thumbnail opens the resolved Blob URL instead of the protected endpoint path.
- [x] Loading and failure states keep a stable preview frame; a failed protected request renders no `<img>` and never falls back to a public URL.
- [x] Compatibility `/uploads` photos remain direct and trigger no Blob request.
- [x] Component unmount still revokes the created object URL through the shared M6.2d3 loader.
- [x] Company-chat upload calls, message schema, floating mini-chat, backend routes, and storage ACL remain unchanged.

**Verification:**
- [x] Focused chat-preview and Blob-loader suites pass (`2` suites / `9` tests).
- [x] Intended tracked frontend suite passes (`20` suites / `88` tests); full working-tree suite passes (`21` suites / `93` tests).
- [x] Production build succeeds.
- [x] Production deploy, public smoke, authenticated tenant-file smoke, and main-chat browser check pass; cleanup leaves `0` smoke ownership rows.

**Known follow-up:** Do not opt company-chat uploads into protected return URLs until every chat renderer can display them. The legacy `/messages` table/API must also receive stored `company_id`, selected-company reads/writes, and negative tenant tests in `M6.4`. `M6.2d5` moves the project work-journal list thumbnail next; the floating mini-chat photo path remains a separate audited slice.

**Dependencies:** Task M6.2d3

**Estimated scope:** S

## Task M6.2d5: Protected Project Work-Journal Thumbnail

**Description:** Move only the photo thumbnail in the existing project `Производство работ` list onto the authenticated Blob loader. Keep master uploads, work-journal writes, edit/history renderers, backend routes, and S3 ACL unchanged.

**Status:** Deployed in `6fe3a6aa`; production verification passed.

**Acceptance criteria:**
- [x] A strict local `/tenant-files/{positiveId}/content` ЖПР photo renders only after the authenticated Blob request succeeds.
- [x] Clicking the thumbnail stops the journal-row edit click and opens the resolved Blob URL.
- [x] Loading and failure states preserve the existing 32x32 slot; a failed protected request renders no `<img>` and never falls back to a public URL.
- [x] Compatibility `/uploads` photos remain direct and trigger no Blob request.
- [x] Component unmount revokes the created object URL through the shared M6.2d3 loader.
- [x] Upload calls, stored ЖПР rows, edit/history renderers, backend, and storage ACL remain unchanged.

**Verification:**
- [x] Focused work-journal, chat-preview, and Blob-loader suites pass (`3` suites / `12` tests).
- [x] Intended tracked frontend suite passes (`21` suites / `91` tests); full working-tree suite passes (`22` suites / `96` tests).
- [x] Production build succeeds.
- [x] Production runtime reports `6fe3a6aa`; public smoke passes.
- [x] Prorab browser check opens `Кисловодск Лицей 4 -> Журналы -> Производство работ`; the real compatibility thumbnail is 32x32, enlarged preview opens, and the row edit modal stays closed.
- [x] Authenticated tenant-file smoke passes after this frontend release and cleanup leaves `0` smoke ownership rows; the only browser error is an unrelated rate-limit `429` from `/master-profiles`.

**Known follow-up:** Work-journal ownership and read/write isolation remain part of `M6.5`; do not opt ЖПР uploads into protected return URLs until every ЖПР renderer is audited and stored `company_id`/`project_id` checks are complete. `M6.2d6` adds an explicit protected-preview opt-in to the shared attachment field and enables it only for the ЖПР edit form.

**Dependencies:** Tasks M6.2d3-M6.2d4

**Estimated scope:** S

## Task M6.2d6: Protected Photo Field In Work-Journal Edit

**Description:** Add an explicit protected-preview mode to the shared `PhotoAttachmentField`, but enable it only in the existing ЖПР edit modal. Keep every other caller, upload return contract, stored photo URL, backend route, and S3 ACL unchanged.

**Status:** Deployed in `8805175b`; production verification passed.

**Acceptance criteria:**
- [x] `PhotoAttachmentField` defaults to direct rendering, so existing CRM, room, measurement, and master-cabinet callers do not start authenticated Blob requests.
- [x] Only `ProjectWorkJournalEditModal` passes the protected-preview opt-in.
- [x] A strict local `/tenant-files/{positiveId}/content` photo loads through authenticated fetch and opens the resolved Blob URL.
- [x] Loading and failure states preserve the existing 54x54 or 70x70 photo slot; failure renders no image and never falls back to the protected path.
- [x] Compatibility `/uploads` photos remain direct even inside the opted-in ЖПР form.
- [x] Unmount revokes the created object URL through the shared M6.2d3 loader.
- [x] Upload calls retain `{projectName, context}` and continue returning/storing the compatibility URL.

**Verification:**
- [x] Focused Blob-loader, chat, work-journal list, attachment-field, and ЖПР edit suites pass (`5` suites / `18` tests).
- [x] Intended tracked frontend suite passes (`23` suites / `97` tests); full working-tree suite passes (`24` suites / `102` tests).
- [x] Production build succeeds.
- [x] Production runtime reports `8805175bc13d`; public smoke and the prorab ЖПР edit browser check pass.
- [x] Existing compatibility S3 photo remains direct at 70x70 and opens the enlarged preview; the only browser error is an unrelated rate-limit `429` from `/master-profiles`.
- [x] Authenticated tenant-file smoke passes after this frontend release and cleanup leaves `0` smoke ownership rows; no backend route or business row changed.

**Known follow-up:** This slice makes the ЖПР edit renderer compatible with protected URLs but does not request protected return URLs for new ЖПР uploads. `M6.2d7` enables the same opt-in only in the two master work-submission fields; work-journal ownership/read-write isolation and the remaining photo renderers must still be audited before changing the upload contract or S3 ACL.

**Dependencies:** Tasks M6.2d3 and M6.2d5

**Estimated scope:** S

## Task M6.2d7: Protected Master Work-Submission Photos

**Description:** Enable authenticated protected-photo previews only in the two master work-submission fields that write `work-journal` photos. Keep the daily-work act, estimate-change form, upload return value, stored URLs, backend, and S3 ACL unchanged.

**Status:** Deployed in `7c0d2570`; production runtime, public/authenticated file smoke, and master-cabinet browser smoke passed.

**Acceptance criteria:**
- [x] A dedicated master work-journal photo boundary always enables protected preview and forces `context="work-journal"`.
- [x] Exactly two master work-submission fields use that boundary: the estimate-work row and the selected-work row.
- [x] The daily-work act and estimate-change photo fields remain on the default direct-preview component.
- [x] Strict local `/tenant-files/{positiveId}/content` values load through authenticated fetch and open the resolved Blob URL.
- [x] Compatibility `/uploads` values and the existing `appendPhotos(value, files, {projectName, context})` contract remain unchanged.
- [x] Backend routes, stored work-journal rows, protected return values, and S3 ACL are unchanged.

**Verification:**
- [x] Focused master boundary, attachment-field, Blob-loader, and ЖПР edit suites pass (`4` suites / `14` tests).
- [x] Exact tracked frontend suite passes (`24` suites / `99` tests); full working-tree suite passes (`25` suites / `104` tests).
- [x] Production build succeeds.
- [x] Production runtime and frontend assets match `7c0d2570`; public smoke, authenticated tenant-file cleanup, and master login/cabinet flow pass without console errors. The available master project has no linked price list, so the two work-submission fields are verified by focused component tests without creating a business row.

**Known follow-up:** This slice only makes the two master submission renderers ready for protected URLs. It does not request protected return URLs and does not complete work-journal tenant ownership/read-write isolation; those remain separate audited slices.

**Dependencies:** Tasks M6.2d3 and M6.2d6

**Estimated scope:** S

## Task M6.4a: Tenant-Scoped Company Messages

**Description:** Add stored company ownership to the existing general company chat and scope list, create, and mark-read operations to one verified selected company. Keep project chat, estimate chat, protected upload return values, and legacy row backfill outside this slice.

**Status:** Deployed in `38d67411`; production migration, selected-company/negative API checks, and authenticated browser chat passed.

**Acceptance criteria:**
- [x] `messages.company_id` is added as nullable with supporting indexes; startup does not guess or backfill legacy ownership.
- [x] `GET /messages` requires one selected company, returns only that company's general-chat rows, and allows a temporary legacy row only when its stored author belongs to that legacy company without another active company membership.
- [x] `POST /messages` stores the resolved company and server-derived author; client-supplied author/company values cannot override them.
- [x] `POST /messages/mark-read` ignores the claimed `userId` and updates only messages visible in the resolved company.
- [x] Read and mutation requests fail closed in `all_companies`; an unresolved server actor cannot create a message.
- [x] `/project-chat`, estimate flows, frontend payloads, stored legacy rows, protected upload returns, and S3 ACL remain unchanged.
- [x] Public proxy smoke recognizes `/messages` as an API route rather than an SPA fallback.

**Verification:**
- [x] Company-context and company-message focused suites pass (`39` tests); the company-message suite passes `7` tests including negative mutation cases.
- [x] Exact tracked backend plus this slice passes (`145` tests); full working-tree backend suite passes (`149` tests).
- [x] Backend entrypoint/module compile, full working-tree frontend suite (`25` suites / `104` tests), and production build pass.
- [x] Production migration and public smoke pass; selected-company read returns the marked legacy row, GET/create/mark-read reject `all_companies`, and the real master chat renders without console errors. No message row was created, changed, or backfilled.

**Known follow-up:** Run a read-only legacy report again, backfill only unambiguous rows, then add stronger constraints in a separate reversible step. Project chat and estimate chat remain later `M6.4` slices; do not treat this company-chat release as complete two-company E2E coverage.

**Dependencies:** Tasks M1 and M6.0

**Estimated scope:** S

## Task M6.4b: Legacy Company Message Dry-Run Report

**Description:** Add an operator command that reports how legacy general-chat rows could map to companies without reading message content or changing the database. Do not perform backfill, add constraints, or alter runtime chat behavior in this slice.

**Status:** Released in `d81939d5`; production read-only report passed with one ready row and no database changes.

**Acceptance criteria:**
- [x] `python3 -m backend.features.company_messages.legacy_report` opens a consistent read-only transaction and executes only `SELECT` queries without commit.
- [x] The report exposes counts and IDs needed for migration review but never returns message text, author names, photo URLs, or other chat content.
- [x] Candidates are classified as `ready`, `ambiguous`, or `unresolved` from the stored author legacy company and active company memberships.
- [x] A conflicting active membership fails closed as `ambiguous`; missing author/company data fails closed as `unresolved`.
- [x] `readyForBackfill` is true only when candidate/count snapshots match and no ambiguous or unresolved rows exist.
- [x] The command explicitly returns `dryRun=true` and `writesAttempted=0`; routes, schema, stored rows, frontend, and S3 behavior remain unchanged.

**Verification:**
- [x] Focused company-context and company-message suites pass (`43` tests), including `4` report tests.
- [x] Clean `HEAD + staged M6.4b` release snapshot passes the full backend suite (`149` tests); unrelated unstaged drafts are excluded from this release verification.
- [x] Report module compiles; full working-tree frontend suite (`25` suites / `104` tests) and production build pass.
- [x] Production command reports `ready=1`, `ambiguous=0`, `unresolved=0`, and `readyForBackfill=true`; before/after counts remain `(1 total, 1 legacy, 0 scoped)`.

**Known follow-up:** Review and save the production report first. A later reversible `M6.4c` may backfill only candidates still classified as `ready`; it must recheck the same ownership conditions inside the write transaction and leave ambiguous rows untouched.

**Dependencies:** Task M6.4a

**Estimated scope:** S

## Task M6.4c: Strict Company Message Cutover

**Description:** Convert the temporary company-chat compatibility layer into strict stored ownership. Backfill only rows whose author still has one unambiguous company, remove runtime inference, bind chat photos to the same company, and make the frontend discard stale company data immediately when the selected company changes.

**Status:** Completed and deployed in runtime `44380a2a` (`f407350b` feature, `081eaf3e` fail-closed hardening, `44380a2a` executable launcher hotfix).

**Acceptance criteria:**
- [x] `npm run audit:company-messages` is read-only by default and reports only IDs, counts, statuses, and reasons; message text, author names, and photo URLs are never printed.
- [x] Apply mode requires the exact confirmation `APPLY_COMPANY_MESSAGES` and the fresh dry-run `--expected-ready-count`, updates only `chat_type='company'` rows, and rolls back without writes when any row needs review or the count changed.
- [x] Migration classification includes active and inactive historical company memberships; any different company is `needs_review` rather than a guessed backfill.
- [x] The write statement repeats author-company and conflicting-membership checks inside the same transaction; skipped rows are reported as `writeConflicts` and cannot produce `complete=true`.
- [x] Runtime list and mark-read queries use only stored `messages.company_id`, reject `all_companies`, return the latest 200 messages in chronological order, and never infer ownership from the author's current profile.
- [x] A chat photo lookup is scoped to the selected company and row-locked through message commit; the file must have no project, use `context='company-chat'`, and remain active.
- [x] Both company-chat upload entry points opt out of project inference and store the protected tenant-file content URL even when a project was previously open.
- [x] Before paint, the frontend clears messages and both drafts on company changes, aborts or ignores stale responses, skips `/messages` in `all_companies`, preserves the current-company draft on API failure, and never fabricates a local message after a failed write.
- [x] The generic data loader no longer issues competing `/messages` requests; one context-aware hook owns company-chat loading.
- [x] Protected production smoke checks authenticated `/messages` and verifies that `all_companies` cannot read it.

**Local verification required before release:**
- [x] Focused migration/route/report backend tests pass (`28` tests).
- [x] Focused chat/upload frontend tests pass (`6` suites / `19` tests).
- [x] Full tracked backend feature suite (`166` tests), full tracked frontend suite plus the new floating-chat regression suite (`28` suites / `112` tests), M6 registry audit, compile, shell syntax, diff check, and production build pass.
- [x] `npm audit --omit=dev --audit-level=critical` reports no critical advisories; the known CRA/XLSX backlog remains `29` findings (`14 high`) and is not modified with a breaking `--force` update.

**Production release order:**
1. `git pull --ff-only` while the `M6.4a` runtime is still active.
2. Run `npm run audit:company-messages` and stop if any row is `needs_review` or the expected counts changed.
3. If the fresh report still says `readyCount=1` and `reviewCount=0`, run `python3 scripts/migrate-company-messages.py --apply --confirm APPLY_COMPANY_MESSAGES --expected-ready-count 1`.
4. Repeat `npm run audit:company-messages`; require `legacyRows=0`, `readyCount=0`, and `reviewCount=0` before deploy.
5. Run `bash deploy.sh`, then public/protected smoke and a browser check under two selected-company contexts when a safe two-company fixture exists.

**Production verification:**
- [x] Pre-apply dry-run returned one legacy row (`messageId=1`) ready for company `1`, with `reviewCount=0` and `writesAttempted=0`.
- [x] Apply required `--expected-ready-count 1`, updated exactly one row, reported no write conflicts, and committed atomically.
- [x] Post-apply and post-deploy dry-runs both returned `legacyRows=0`, `readyCount=0`, `reviewCount=0`, and `complete=true`.
- [x] Deploy build, public smoke, service health, and logs passed at runtime `44380a2a8d78`.
- [x] A temporary master read exactly the stored company-1 message with `legacyUnscoped=false`; `all_companies` returned `400`, and the cookie-authenticated browser opened `Чат` without console errors. No message was created or changed; temporary user `4380` was disabled after verification.
- [x] The generic protected smoke could not use the existing admin because its first 2FA setup is pending; the dedicated temporary-user API and real browser checks closed the same `/messages` verification without changing the admin's security state.

**Known follow-up:** Do not add `NOT NULL` or a foreign key until the production post-apply report is clean. Project chat, estimate changes, and `unexpected_works` remain separate M6.4 slices. A true two-independent-tenant production E2E remains blocked until the planned fixture infrastructure exists.

**Dependencies:** Tasks M6.4a and M6.4b

**Estimated scope:** M

## Task M6.4d: Tenant-Scoped Estimate Version Reads

**Description:** Isolate the existing estimate-version history and direct version-detail reads through the server-selected company context and the stored parent estimate. Preserve the existing response shape, per-company effective roles, and worker sanitizing; do not change version creation, estimate changes, unexpected works, estimate chat, or schema in this slice.

**Status:** Deployed in `b79ae5d2`; production read-only API and browser checks passed.

**Acceptance criteria:**
- [x] `GET /estimates/{id}/versions` resolves the read company context, applies the existing estimate visibility policy, and verifies the stored estimate parent before reading child versions.
- [x] `GET /estimate-version/{version_id}` joins the parent estimate inside the same visibility filter; an invisible or cross-company direct ID returns `404` before child data is exposed.
- [x] `all_companies` remains read-only and evaluates the effective role separately for the company that owns each parent estimate.
- [x] Accounting denial, active/package/project visibility, worker item filtering, and worker total sanitizing use the effective company actor rather than the global account role.
- [x] `estimate_versions` inherits ownership from its immutable `estimate_id`; no guessed `company_id`, backfill, constraint, or business-data rewrite is introduced.
- [x] Non-document memberships fail closed even when the account is authenticated.

**Verification:**
- [x] Estimate-version and estimate-access focused backend suites pass (`16` tests).
- [x] Full working-tree backend suite passes (`176` tests); M6 registry audit and production entrypoint compile pass.
- [x] Full frontend suite passes (`29` suites / `117` tests) and production build succeeds.
- [x] Public smoke recognizes both estimate-version routes as protected backend APIs rather than SPA fallbacks.
- [x] Production deploy and read-only API probe passed at runtime `b79ae5d25315`: estimate `25` returned its version list, direct version `110` returned `200`, a missing version returned `404`, and the row count/max ID stayed unchanged (`78`/`110`).
- [x] The authenticated director browser opened `Сметы -> Электрика -> История`, rendered all `25` saved versions, and reported no console errors or warnings; no restore or other mutation was triggered.
- [x] Production currently has only company `1`, so a true company-A/company-B negative E2E remains deferred to the isolated `smoke:multi-company` fixture instead of fabricating live tenant data.

**Known follow-up:** Version creation, estimate changes, `unexpected_works`, and project chat remain separate M6.4 slices. Do not add a redundant `company_id` to `estimate_versions` while the verified stored parent is the authoritative owner.

**Dependencies:** Tasks M6.1 and M6.4a-M6.4c

**Estimated scope:** S

## Task M6.4e: Tenant-Scoped Estimate Chat

**Description:** Isolate estimate-chat history, AI message creation, and explicit history clearing through the server-selected company and the stored parent estimate. Preserve existing URLs, response fields, AI prompt behavior, and stored messages; do not add a redundant company column or migrate chat content in this slice.

**Status:** Deployed in `cf006af7`; request-race hardening deployed in `80f1e8df`, and public, no-write API, and authenticated browser checks passed.

**Acceptance criteria:**
- [x] History and direct chat actions first apply the existing estimate visibility policy and re-verify the stored estimate parent before reading or changing `estimate_chat_messages`.
- [x] The effective role in the parent estimate's company controls access; a global director who is a worker in that company cannot read or send estimate-chat messages.
- [x] Read-only history may use `all_companies`, but message creation and history clearing require one concrete selected company and fail before SQL in aggregate mode.
- [x] Clear-history authorization uses the effective company role and deletes only the verified parent estimate's chat after explicit frontend confirmation.
- [x] Existing chat rows keep their immutable `estimate_id` owner; no schema change, backfill, content rewrite, or automatic deletion is introduced.
- [x] Frontend request IDs ignore history/AI responses from an old estimate or company; company changes close the chat/version modals and clear messages, drafts, loading, and version comparison state before rendering the new context.
- [x] Failed clear requests leave visible history intact, and the clear button is disabled while an AI request is in progress.
- [x] The backend re-locks and re-verifies the estimate after AI generation and stores the assistant answer only if the original user message still exists, so a concurrent clear cannot restore deleted history.
- [x] The frontend keeps history loading separate from AI loading, blocks send/clear during history loading, ignores stale version responses, and preserves an in-flight answer when the same chat is closed and reopened.

**Verification:**
- [x] Focused estimate access/version/chat backend suites pass (`24` tests), including backend-working-directory import, cross-company `404`, worker denial, selected-company writes, and aggregate-mode mutation denial.
- [x] Focused frontend chat/context suites pass (`2` suites / `5` tests), including stale history, stale AI answer, failed clear, successful clear, and company-context reset.
- [x] Full working-tree backend suite passes (`190` tests); full frontend suite passes (`32` suites / `127` tests).
- [x] Production entrypoint/module compile, shell syntax, public proxy smoke, and production build pass.
- [x] Production runtime reports `cf006af7e4f9`; public smoke recognizes both estimate-chat routes, and the authenticated director browser opens `Сметы -> Кисловодск Лицей 4 -> Электрика -> Чат` with the correct estimate and no console warnings/errors. No message was sent and history was not cleared.
- [x] Hardened runtime `80f1e8df72ea` passes health, DB, systemd, startup-log, public smoke, and production build checks. A temporary estimator received `200` for selected/all-company history, `400` for aggregate send/clear, and `403` for an unavailable company; `estimate_chat_messages` stayed at `0` rows with the same SHA-256 before and after.
- [x] The authenticated production browser reopened `Сметы -> Кисловодск Лицей 4 -> Электрика -> Чат`, loaded history with `200`, rendered the empty state with send disabled, and reported `0` console errors/warnings. No send/clear action was used, and the temporary user was disabled afterward.

**Known follow-up:** Estimate changes, `unexpected_works`, project chat, and estimate-version creation remain separate parent-owned slices. A true company-A/company-B negative E2E still requires the isolated multi-company fixture.

**Dependencies:** Tasks M6.1 and M6.4a-M6.4d

**Estimated scope:** M

## Task M6.4f: Estimate Change Ownership Audit

**Description:** Add a read-only production audit for `unexpected_works` before introducing stored tenant ownership or changing estimate-change routes. Classify each row from identifiers only and fail closed on ambiguous or conflicting parents.

**Status:** Released in `6bb10f47`; production read-only audit completed on runtime `80f1e8df`.

**Acceptance criteria:**
- [x] `npm run audit:estimate-changes` opens a read-only transaction and never commits or executes a write statement.
- [x] The report reads only row IDs, project/estimate ownership IDs, and the legacy project name needed for classification; descriptions, notes, photos, prices, totals, and business reasons are not selected.
- [x] Stored `company_id/project_id`, when present, must agree with the project and any explicit estimate parent.
- [x] Missing stored ownership may be proposed from a valid `estimate_id`; name-only fallback is ready only when one project with that name exists globally.
- [x] Broken explicit estimates, partial stored owners, name conflicts, row/parent mismatches, and cross-owner `included_in_estimate_id` links are reported for review rather than silently remapped.
- [x] The report works both before and after owner columns are added and truncates previews without changing summary counts.

**Verification:**
- [x] Focused ownership-report suite passes (`5` tests), including backend-working-directory import, preview truncation, and a connection whose `commit()` raises immediately.
- [x] Full backend regression passes (`189` tests); module compile, M6 registry audit, diff check, and production build pass.
- [x] Production `npm run audit:estimate-changes` returned a consistent read-only report: `4` total/legacy rows, all `4` ready for company `1` and project `1` through a globally unique project name, `0` ambiguous/unresolved/mismatched rows, and `writesAttempted=0`.

**Known follow-up:** The audit is not a migration and does not close runtime reads/writes. Use its exact production counts to design a reversible `project_id/company_id` backfill, leave disputed rows untouched, then scope core CRUD and include/reconcile/AI flows in separate slices.

**Dependencies:** Tasks M6.1 and M6.4d-M6.4e

**Estimated scope:** S

## Task M6.4g: Guarded Unexpected-Works Ownership Migration

**Description:** Add nullable stored `company_id/project_id` ownership to `unexpected_works` and backfill only the four rows already classified as unambiguous by the production audit. Keep all runtime reads/writes unchanged in this migration slice.

**Status:** Deployed in `e8003a1d`; production dry-run, guarded apply, post-audit, public smoke, and read-only API verification passed.

**Acceptance criteria:**
- [x] Dry-run repeated the production gate exactly: `totalRows=4`, `ready=4`, no review rows, and all candidates targeted company `1` / project `1`.
- [x] Apply requires an explicit confirmation token, expected count, and SHA-256 of the complete dry-run plan; it rechecks every ownership source inside one transaction and rolls back on any drift or conflict.
- [x] Columns and supporting indexes are added reversibly; ambiguous rows are never guessed, and no `NOT NULL` or foreign key is added yet.
- [x] Existing estimate-change CRUD, include/reconcile, and AI routes remain behaviorally unchanged until a later tenant-scoping slice.

**Verification:**
- [x] Migration/report tests cover pre-column, dry-run, apply, same-count ownership drift, idempotent rerun, exception/conflict rollback, and post-apply states (`17` focused tests); the clean release backend suite passes (`198` tests), M6 registry audit and production build pass.
- [x] Production before/after stayed at `4` rows with max ID `4`; the business-field SHA-256 stayed `cceaafd9eed744be011a3d3c9aea1eb91a0eb75fff30ce896cbe8a090732893a`, while all four rows received only `company_id=1/project_id=1`.

**Production apply order:** push the migration code and run only `git pull --ff-only` on the server without restarting the service. Run `python3 scripts/migrate-estimate-changes.py --dry-run`, require the same `readyCount=4` and empty review list, copy its `planSha256`, then run `python3 scripts/migrate-estimate-changes.py --apply --confirm APPLY_ESTIMATE_CHANGES --expected-ready-count 4 --expected-plan-sha256 <planSha256>` and repeat the dry-run. Only after the clean post-audit may `bash deploy.sh` restart the runtime. Any count or mapping drift, review row, lock timeout, row-count conflict, or failed post-check rolls the transaction back.

**Production result:** pre-apply dry-run had no owner columns, `readyCount=4`, `reviewCount=0`, and plan SHA-256 `e59a747eec491063b6d8fce460bd90c2a5db57b11113f548d3752d3a35e03ba1`. Apply updated exactly `4` rows with `0` conflicts and passed its in-transaction post-check. Repeated dry-run and the independent ownership audit report `storedRows=4`, `legacyRows=0`, `ready=0`, no review rows, and `complete=true`. Runtime health/DB/systemd/startup logs and public smoke passed; a temporary estimator read the unchanged route and received IDs `1-4`, then the account was disabled.

**Dependencies:** Task M6.4f

**Estimated scope:** S

## Task M6.4h: Estimate Change Create Ownership

**Description:** Before strict list reads are enabled, change only `POST /unexpected-works` to resolve one selected-company actor and exact project parent, then store immutable `company_id/project_id` on every new row. Keep list/update/delete, include/reconcile, limit-check, and AI routes unchanged in this slice.

**Status:** Deployed in `ab9d9bf0` and included in verified runtime `3aa3bba4`.

**Acceptance criteria:**
- [x] Create requires one concrete selected company; `all_companies` and an unavailable company fail before `INSERT`.
- [x] The project is resolved by exact parent inside the selected company, and both `company_id/project_id` are written from server state rather than request claims.
- [x] Explicit `estimateId` and `includedInEstimateId` must belong to the same stored company/project; cross-project or cross-company parents fail before `INSERT`.
- [x] Effective membership role controls project/package access and worker money/status sanitizing; the global account role cannot elevate it.
- [x] Existing request fields and `{id,ok}` response remain compatible; list/update/delete, include/reconcile, limit-check, and AI behavior are unchanged.

**Verification:**
- [x] Focused tests cover stored owner IDs, canonical project identity, aggregate denial, unavailable company, cross-parent estimate denial, package checks, worker sanitizing, and rollback.
- [x] Full backend suite (`211` tests), M6 registry audit, compile, diff check, and production build pass.

**Dependencies:** Task M6.4g

**Estimated scope:** S

## Task M6.4i: Tenant-Scoped Estimate Change List

**Description:** After all new rows receive stored ownership, change only `GET /unexpected-works` to select through `company_id/project_id` and server-resolved tenant context. Keep update/delete, include/reconcile, limit-check, and AI routes unchanged in this slice.

**Status:** Deployed and verified read-only in runtime `3aa3bba4` after a clean production ownership audit.

**Acceptance criteria:**
- [x] Selected-company reads return only rows whose stored company and project are visible to the effective membership role.
- [x] `all_companies` remains read-only and applies each company's effective project/package/status policy without using global role elevation.
- [x] Rows with missing or conflicting stored ownership fail closed; the legacy project name is display data only, never the authorization key.
- [x] Existing response fields, money hiding, customer status filtering, package filtering, and ordering remain unchanged.

**Verification:**
- [x] Focused tests cover two companies, direct selected-company reads, aggregate reads, unavailable company `403`, cross-company invisibility, worker money hiding, and legacy/mismatched owner exclusion.
- [x] Production verification is read-only and confirms no row, owner, or business-field changes.
- [x] Local verification passes: `38` focused tests, `223` full backend tests, compile, M6 registry audit, diff check, and production build.

**Dependencies:** Task M6.4h

**Estimated scope:** S

## Task M6.4j: Tenant-Scoped Direct Estimate Change Mutation

**Description:** Move only direct `PUT/DELETE /unexpected-works/{id}` into the estimate-change module. Resolve one effective selected-company writer, lock the stored change row, verify its exact `company_id/project_id` parent, and constrain the final update by the same owner. Keep include/reconcile, estimate-reconciliation, AI, and limit-check routes unchanged.

**Status:** Implemented locally; release pending.

**Acceptance criteria:**
- [x] `all_companies`, unavailable companies, non-writer effective roles, ownerless rows, and direct IDs from another company fail before any update.
- [x] The global account role cannot elevate the selected-company membership role.
- [x] `includedInEstimateId`, when supplied, must belong to the same stored company/project.
- [x] The final `UPDATE` repeats `id + company_id + project_id` after a locked owner check.
- [x] Approval-created work-journal rows inherit the change `company_id`; best-effort journal failure uses a savepoint and cannot silently roll back the approved change.
- [x] Existing response shapes, approval statuses, soft-delete semantics, and visible business fields remain compatible.

**Verification:**
- [x] Focused tests cover selected-owner mutation, cross-company direct IDs, ownerless rows, aggregate denial, effective-role denial, foreign included estimates, owner-constrained soft delete, inherited journal ownership, and journal-savepoint recovery.
- [x] Local verification passes: `45` focused estimate-change tests, `231` full backend tests, compile, M6 registry audit, diff check, and production build.
- [ ] Production verification uses an existing row for read-only negative checks and a controlled test row only when cleanup is guaranteed.

**Dependencies:** Task M6.4i

**Estimated scope:** S

## Task M6.4k: Tenant-Scoped Include And Reconcile Changes

**Description:** Scope `/estimates/{id}/include-changes` and `/estimates/{id}/reconcile-changes` through one verified estimate/project owner. Every selected unexpected-work ID must match that same owner before an estimate version or status is changed.

**Status:** Deployed and verified in runtime `52ec9af417f4` after Task M6.4j.

**Implementation checklist:**
- [x] Both routes resolve one selected-company effective actor and reject aggregate `all_companies` mutation.
- [x] The target estimate and exact project parent are locked and verified through stored `company_id/project_id`; names remain display data.
- [x] Explicit change IDs are locked as one set and every ID must exist, belong to the target company/project, be approved, and not already be included before any estimate write.
- [x] Automatic include selection is constrained by stored company/project plus the existing estimate-link rule.
- [x] Archiving active estimates is constrained by company, project, estimate type, and work package.
- [x] The generated estimate stores the inherited `company_id/project_id`; no ownerless new version is created.
- [x] Final change updates repeat company/project/status/not-included predicates and require every selected ID in `RETURNING` before commit.
- [x] `approved_by` comes from the server-resolved company actor; client `updatedBy` cannot replace audit identity.
- [x] Legacy response shapes and estimate-section transformation rules remain compatible.
- [x] Focused tests cover owned include, foreign selected IDs, owner-constrained reconcile, server identity, and aggregate-company denial.
- [x] Local verification passes `51` estimate-change tests, `236` full backend tests, compile, route-duplication check, and `git diff --check`.
- [x] Production deploy completed atomically; independent public smoke passed and both new POST routes returned the expected unauthenticated `401` instead of SPA/404.

**Known follow-up:** M6.4l still owns estimate-reconciliation list/detail/create/update/candidate scoping. M6.4m still owns AI estimate and limit aggregation. Do not mark the whole `unexpected_works` domain tenant-complete until those slices and production verification pass.

**Dependencies:** Task M6.4j

**Estimated scope:** M

## Task M6.4l: Tenant-Scoped Estimate Reconciliation

**Description:** Scope estimate-reconciliation list/detail/create/update and unexpected-work candidate reads through verified base/next estimate parents. Project names remain display fields only.

**Status:** Deployed and verified in production runtime `6648dd738d23`. Health, public smoke, route protection, startup logs, and the repeated read-only ownership audit passed.

**Audit checklist:**
- [x] `npm run audit:estimate-reconciliations` uses a read-only transaction and attempts no writes.
- [x] Ownership derives only from `base_estimate_id`, `next_estimate_id`, their stored company/project owners, and the stored project row.
- [x] Missing parents, cross-company/project pairs, and estimate/reconciliation package or type conflicts become `needsReview` rows.
- [x] Output contains only IDs, reasons, and counters; no names, sections, sums, or notes.
- [x] Production returned `readyForStrictRuntime=true`, `totalRows=0`, and empty `needsReview`; no writes were attempted.

**Prepared runtime:** List/detail/create/update and item mutations resolve tenant access through both estimate parents. Candidate `unexpected_works` use exact company/project IDs, aggregate-company and foreign direct-ID writes stop before mutation, final updates repeat parent IDs, reconciliation type/package must match both parents, and package limits remain active for proраб and other limited roles. Local verification passes `16` focused and `248` full backend tests, compile, M6 audit, production build, route-duplication check, and diff check.

**Dependencies:** Task M6.4k

**Estimated scope:** M

## Task M6.4m: Tenant-Scoped Estimate Change AI And Limit Read

**Description:** Scope direct AI pricing and project limit aggregation by stored owner and selected-company read context. The AI receives only a verified visible row, and limit totals aggregate only the exact stored project owner.

**Status:** Deployed and verified in production runtime `26818ea40322`. Direct AI and limit-check routes are present behind authentication; health and full public smoke passed.

**Dependencies:** Task M6.4l

**Estimated scope:** S

## Task M6.5a: Work Journal Ownership Audit

**Description:** Classify every `work_journal` row through a globally unique project and any explicit estimate, unexpected-work, or brigade-contract parent. Do not change rows or expose business content.

**Status:** Production read-only report passed: `8` verified rows, no backfill, unresolved, mismatched, or review rows.

**Safety:** The command opens a read-only transaction, attempts no writes, and reports only journal IDs, owner IDs, reasons, and counters. Ambiguous project names and conflicting parents always require review.

**Dependencies:** Task M6.4m

**Estimated scope:** S

## Task M6.5b: Store Work Journal Owner On Create

**Description:** Change only direct `POST /work-journal` so the server resolves one selected company and exact project parent, then stores the canonical project name and `company_id`.

**Status:** Deployed and verified in production runtime `e74dafc5d0f6`. Health, full public smoke, and unauthenticated route protection passed. Existing-row list/update/delete, AI prefill, batch creation, rooms, acts, and contracts remain unchanged.

**Dependencies:** Task M6.5a

**Estimated scope:** S

## Task M6.5c: Tenant-Scoped Work Journal Read

**Description:** Scope `GET /work-journal` through stored company ownership and one unambiguous project parent while applying project, package, worker, customer-status, search, date, pagination, and money-masking rules per effective company membership.

**Status:** Deployed and verified in production runtime `2a559a9149fe`. Health, full public smoke, and unauthenticated route protection passed. Existing-row mutations, AI prefill, batch creation, rooms, acts, and contracts remain unchanged.

**Dependencies:** Task M6.5b

**Estimated scope:** M

## Task M6.5d: Tenant-Scoped Work Journal Mutation

**Description:** Scope direct `PUT/DELETE /work-journal/{id}` through one selected-company actor, a locked stored journal owner, and the exact project parent. Repeat owner fields in final updates and keep material restoration inside the same company.

**Status:** Deployed and verified in production runtime `0f0575f69aaa`. Health, full public smoke, and unauthenticated PUT/DELETE route protection passed. AI prefill, batch creation, rooms, acts, and contracts remain unchanged.

**Dependencies:** Task M6.5c

**Estimated scope:** M

## Task M6.5e: Tenant-Scoped Work Journal AI Prefill

**Description:** Verify the selected-company actor and exact stored journal owner before sending business data to AI. After the external response, open a new transaction, repeat the owner lock, verify the source snapshot is unchanged, and only then save AI fields.

**Status:** Included in production runtime `8ef743a6`; protected owner smoke remains grouped with the final M6 verification. Batch creation, rooms, acts, and contracts remain unchanged.

**Dependencies:** Task M6.5d

**Estimated scope:** S

**M6 safety gate:** do not backfill ambiguous legacy rows, do not use project names as authorization identifiers, do not allow mutation in `all_companies`, and do not start the two-company production E2E until M6.0-M6.8 and the preceding M4/M5 gaps are closed.

## Task M7: Backfill, Constraints, And Pilot Matrix

**Description:** After all live write paths are tenant-aware, inspect old rows, perform dry-run mapping, backfill only unambiguous records, and add database constraints/indexes in reversible migrations.

**Acceptance criteria:**
- [ ] Dry-run reports unmapped and conflicting rows without changing data.
- [ ] Ambiguous records move to `needs_review`; no guessed tenant links are written.
- [ ] Database indexes and constraints are added only after clean evidence.
- [ ] Pilot matrix covers the owner's company, five or six independent client accounts, and at least one holding with multiple companies/sites.

**Verification:**
- [ ] Read-only cross-account isolation smoke passes before and after backfill.
- [ ] Alembic upgrade and rollback are tested on a database copy.

**Dependencies:** Tasks M2-M6

**Estimated scope:** L, delivered as separate migration slices

## Task M7a: Read-Only Tenant Constraint Readiness

**Description:** Add one fail-closed operator report that combines the M6 tenant registry with technical database ownership facts. The report must identify registry gaps, pending runtime releases, missing owner columns/indexes, null or invalid scopes, orphan companies/projects, and project-company mismatches before any M7 constraint is designed or applied.

**Status:** Initial production report completed read-only: `41` registry entries, `13` stored tables, `35` registry blockers, zero orphan companies/projects or project-company mismatches. The initial two index findings were split into an optional empty `messages.project_id` false positive and one real `work_journal.company_id` gap. Constraints and the pilot remain blocked.

**Acceptance criteria:**
- [x] Report uses a PostgreSQL read-only transaction, performs zero writes, and always rolls back.
- [x] Report reads only schema/index/constraint metadata and ownership counts; it does not output message text, document contents, names, sums, or other business data.
- [x] `missing`, `legacy_default`, `public_surface`, and `pending/local` registry states fail closed.
- [x] Stored tables are checked for `company_id`, relevant indexes, null owners, invalid scopes, orphan parents, and project-company mismatches.
- [x] Constraint candidates are informational only; no `ALTER`, backfill, guessed mapping, or pilot-company creation is included.
- [x] Production report is captured and its blockers are split into independent M7 follow-up slices.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.tenant_readiness.test_report`
- [x] `npm run audit:tenant-readiness` on production: read-only transaction rolled back, no business rows changed.

**Dependencies:** Tasks M4-M6 and the current `docs/m6-tenant-registry.json`

**Estimated scope:** S

## Task M7b: Guarded Work-Journal Tenant Index

**Description:** Correct the generic readiness rule so an optional `project_id` column requires an index only when project-owned rows exist, then add one guarded additive index for the confirmed ЖПР query path: `work_journal(company_id, project)`. Do not add constraints, alter business rows, or touch the 35 unresolved registry/runtime scopes.

**Status:** Complete in production. The guarded plan added the one confirmed index; the post-readiness report shows `work_journal.projectIndex=true` and `schemaBlockers=0`. The separate `runtime_release_pending` registry blocker remains intentionally open.

**Acceptance criteria:**
- [x] Empty optional project scope no longer produces a false `project_index_missing` blocker.
- [x] Project rows without a usable project index still fail closed.
- [x] Dry-run uses a read-only transaction and always rolls back.
- [x] Apply requires exact confirmation, missing-index count and SHA-256 plan.
- [x] Migration creates only `idx_work_journal_company_project` on `(company_id, project)` with short lock/statement timeouts.
- [x] Report exposes exact rollback SQL; no backfill, `NOT NULL`, FK, CHECK or pilot data is included.
- [x] Production index apply and post-readiness audit pass.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.tenant_readiness.test_index_migration backend.features.tenant_readiness.test_report`
- [x] `npm run audit:tenant-indexes` on production.
- [x] `npm run audit:tenant-readiness` after apply: project index present, zero schema blockers.

**Dependencies:** Task M7a production report

**Estimated scope:** S

## Task M7c: Tenant Registry Coverage Audit

**Description:** Compare every PostgreSQL `public` base table with the M6 registry before treating the 41 registered resources as complete. Report unregistered tables and their ownership-signal columns without reading counts or business rows. This closes the discovered blind spot where CRM tables and their project-creation writers were outside the tenant readiness report.

**Status:** Production report completed read-only. After CRM, public-file, supplier-link and core-supply registration slices: `127` schema tables, `49` registered physical tables plus one surface and `78` unregistered tables (`25 critical`, `26 high`, `27 unclassified`). Registered-table drift and duplicate registry entries are zero. Core-supply registration is visible, but its separate row audit remains pending.

**Acceptance criteria:**
- [x] Collector reads only `information_schema` table/column metadata in a read-only transaction and rolls back.
- [x] Registry surfaces are not mistaken for physical tables.
- [x] Missing registered tables and duplicate registry table entries fail closed.
- [x] Every unregistered public table blocks registry freeze.
- [x] Unregistered `company_id/owner_scope` tables are marked critical; project-identity tables are marked high; tables without known owner columns remain unclassified rather than being assumed safe.
- [x] Report does not count, select, output, classify automatically, or modify business rows.
- [x] Production coverage report is captured and split into bounded domain slices; CRM and public-file slices are complete, remaining tables stay fail-closed.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.tenant_readiness.test_coverage_report`
- [x] `npm run audit:tenant-registry-coverage` on production: `78` unregistered, zero missing/duplicate entries.

**Dependencies:** Task M7a; independent of M7b index apply

**Estimated scope:** S

## Task M7d: Read-Only CRM Ownership Audit

**Description:** Register `crm_leads`, `crm_lead_documents` and `crm_lead_tasks` as explicit tenant blockers, then classify current rows through exact stored parents before adding owner columns or changing either CRM project-creation path.

**Status:** Production report completed read-only: one `crm_leads` row exists, has no project owner and remains unresolved; documents and tasks are empty. `writesAttempted=0`, plan SHA `aa8b4a3488506f404a0a037425eb7a99eb0cd9f30fb9a00b2b969a47c8fb4a83`.

**Acceptance criteria:**
- [x] A lead is verified only through `crm_leads.project_id -> projects.id -> projects.company_id -> companies.id`.
- [x] Standalone leads, deleted projects and projects without a valid company remain unresolved; company `1` is never assumed.
- [x] Documents and tasks inherit ownership only from a verified stored lead.
- [x] The report reads only record IDs and owner-parent IDs; it does not read or output names, phones, email, notes, source, document metadata or task titles.
- [x] The command runs in a PostgreSQL read-only transaction, rolls back and reports `writesAttempted=0`.
- [x] All three tables are present in the registry with `companyState=missing`, so readiness remains fail-closed.
- [x] Production report is captured and split into exact migration/review counts.

**Safety:**
- Do not add `company_id` or change CRM reads/writes until the production report identifies verified and standalone lead populations.
- Do not patch only the two project INSERT statements: a project owner must be inherited from the stored owner of the lead, not from a default or current company guess.
- A later guarded migration must update only rows proven by immutable parents; standalone leads require explicit operator mapping or a documented non-company scope.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.crm_ownership.test_ownership_report`
- [x] `npm run audit:crm-ownership` on production.
- [ ] `npm run audit:tenant-registry-coverage` after deploy.

**Dependencies:** Task M7c production report; independent of M7b index apply

**Estimated scope:** S

## Task M7e: Guarded CRM Ownership Migration

**Description:** Add nullable stored owner columns to CRM leads, documents and tasks. Backfill exact project-owned leads automatically, require an explicit operator mapping for every standalone lead, and inherit child ownership only from the verified lead.

**Status:** Implemented locally. Production dry-run explicitly mapped standalone lead `#1` to company `#1` and returned one ready row with no unresolved/mismatched rows; guarded apply and strict post-audit are still pending.

**Acceptance criteria:**
- [x] Default `npm run audit:crm-ownership` is read-only, performs zero writes and rolls back.
- [x] `--lead-owner LEAD_ID:COMPANY_ID` is required for a standalone lead and rejects unknown leads, missing companies, duplicate mappings and conflicts with an existing project owner.
- [x] Leads with an exact stored project derive the company only from `projects.company_id`.
- [x] Documents and tasks inherit the exact company/project pair from a ready or stored lead; missing or conflicting parents block apply.
- [x] Apply adds only nullable owner columns, bounded indexes and project-implies-company checks; it does not change CRM content or assign a project to a standalone lead.
- [x] Apply requires `APPLY_CRM_OWNERSHIP`, exact ready count and exact SHA-256 plan, then locks and rechecks the same plan before writing.
- [x] Every update targets only ownerless rows; any conflict or failed strict post-check rolls back the transaction.
- [x] The director explicitly confirms the company owner of lead `#1` through the production dry-run mapping `1:1`.
- [ ] Production dry-run with the confirmed mapping, guarded apply and strict post-audit pass.

**Safety:**
- Mapping a standalone lead is a business ownership decision, not a technical inference. The migration must not assume company `1` merely because it is the only current tenant.
- Existing `project_id`, lead fields, documents, tasks and user-visible statuses are not changed.
- Runtime reads/writes and both CRM project-creation endpoints remain unchanged until stored ownership is strict-ready.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.crm_ownership.test_ownership_report backend.features.crm_ownership.test_migration`
- [ ] `npm run audit:crm-ownership -- --lead-owner <lead>:<company>` on production.
- [ ] Guarded apply with the exact reported `readyCount` and `planSha256`.
- [ ] `npm run audit:crm-ownership` without manual mapping after apply.

**Dependencies:** Task M7d production report

**Estimated scope:** S

## Task M7f1: Persist CRM Writer Ownership

**Description:** Stop every current CRM creation path from producing ownerless rows after the guarded CRM migration. Authenticated leads use one selected company and effective role; public-site and MAX leads use stored/configured server ownership; documents and tasks inherit the exact lead owner.

**Status:** Complete in production. Authenticated, public-site and MAX writers, cleanup and strict ownership audit are verified.

**Acceptance criteria:**
- [x] Both authenticated lead POST routes resolve one concrete selected company and reject aggregate or unauthorized effective roles.
- [x] Client-supplied `companyId` and `createdBy` do not control stored ownership or actor identity.
- [x] `/site/leads` requires `PUBLIC_SITE_COMPANY_ID` and writes the same company to the lead, uploaded CRM document and projectless CRM follow-up task.
- [x] `/max/marketing-leads` requires a stored company on the exact marketing channel and copies it to the CRM lead.
- [x] CRM documents and tasks copy stored `company_id/project_id` from the parent lead and reject an ownerless legacy lead.
- [x] No CRM writer added by this slice falls back to company `1`.
- [x] Production M7e apply and strict post-audit pass before deploy.
- [x] Protected platform CRM smoke verifies stored owner propagation for authenticated leads, a public client and all four public partner types, then cleans its test rows.
- [x] Self-contained MAX marketing smoke verifies stored channel owner propagation without a user password and proves cleanup of its temporary rows.

**Safety:**
- Deploying this runtime before the M7e columns exist is prohibited.
- Existing CRM rows, reads, update/delete routes and both create-project routes are not changed in this slice.
- Public and messenger ownership comes from server configuration/stored channel rows, never from request payload.

**Verification:**
- [x] Focused CRM/public/MAX ownership tests and Python compilation.
- [x] Full backend suite (`614` tests), frontend production build and M6 registry gate (`44` entries).
- [x] Production `smoke:platform-crm`, `smoke:max-marketing`, strict CRM audit and deploy `smoke:prod`.

**Dependencies:** Task M7e strict production post-audit

**Estimated scope:** S

## Task M7f2: Enforce CRM Read And Mutation Ownership

**Description:** After M7f1 is live, scope list/detail/update/delete/approve/invite/transfer routes and both CRM project-creation writers through stored lead/child ownership. Project creation must persist the lead's exact company instead of relying on a database default or UI context.

**Status:** Complete in production. Reads, mutations, approvals, invitations, document transfer and both project-creation URLs enforce stored CRM ownership.

**Acceptance criteria:**
- [x] Lead summaries use only companies where the effective actor has a CRM role; aggregate mode never broadens access beyond those memberships.
- [x] Lead details return `404` outside the allowed company set and load documents/tasks only when their stored company/project matches the lead exactly.
- [x] Lead counters use the same exact child owner instead of counting rows by `lead_id` alone.
- [x] Production smoke creates a foreign-company lead, proves it is absent from summaries and inaccessible by direct detail URL, then cleans it up.
- [x] Scope lead update/delete and document/task update/delete through stored owner.
- [x] Scope supplier/worker approval, invite and document transfer through stored owner.
- [x] Make both CRM project-creation writers authorize the lead owner and persist its exact company explicitly.

**Verification:**
- [x] Focused CRM tests (`41`) and full backend suite (`642`).
- [x] Production deploy smoke, `smoke:platform-crm` with `foreignLeadHidden=true`, `ownMutationsChecked=true`, six foreign mutation `403` responses, `ownWorkflowOwnershipChecked=true` and four foreign workflow `403` responses, plus strict post-audit with zero legacy/unresolved/mismatched rows.
- [x] Runtime `f8c66354`: `projectCreationOwnershipChecked=true`, both foreign project-creation URLs reject access, six foreign workflows return `403`, and strict CRM audit is clean.

### Task M7f2a-legacy: Scope Compatibility CRM List

**Status:** Complete in production. Совместимый `GET /crm-leads` использует effective CRM company roles; negative production smoke подтвердил изоляцию.

**Acceptance criteria:**
- [x] Legacy-список фильтруется по stored `crm_leads.company_id`.
- [x] Выбранная компания и `Все компании` учитывают effective leadership/CRM-роли, а не глобальную JWT-роль.
- [x] Negative smoke проверяет, что лид чужой компании отсутствует в legacy-списке.
- [x] Production deploy и повторный `smoke:platform-crm` подтверждают legacy isolation.

**Dependencies:** Task M7f1 production verification

**Estimated scope:** M

## Task M7g: Audit Public CRM File Ownership

**Description:** Register `file_ownership` and `public_lead_uploads`, then verify their stored owner chain without reading file metadata, upload tokens, client IPs or CRM content. This is the smallest critical slice remaining after CRM ownership rollout.

**Status:** Complete in production. All `11/11` rows are verified in company `1`; no unresolved/mismatched rows and no writes.

**Acceptance criteria:**
- [x] `file_ownership` is verified only by an existing stored company and, when present, an exact project from the same company.
- [x] `public_lead_uploads` requires the same company as its exact file owner and, when attached, its exact CRM lead.
- [x] Missing parents are unresolved and cross-company parents are mismatched; neither is guessed or repaired.
- [x] Loader reads only IDs and owner relations and never selects upload token, URL/storage key, filename/type, client IP or CRM PII/content.
- [x] Report runs read-only, rolls back and reports `writesAttempted=0`.
- [x] Production dry-run: `verified=11`, `unresolved=0`, `mismatched=0`, `needsReview=[]`, `writesAttempted=0`.
- [x] Registry coverage confirms both tables registered; current unregistered set is `82`.

**Verification:**
- [x] `python3 -m unittest backend.features.public_file_ownership.test_ownership_report` (`7` tests).
- [x] `npm run audit:public-file-ownership` on production.
- [x] `npm run audit:tenant-registry-coverage` on production.

**Dependencies:** Task M7f2 production completion

**Estimated scope:** S

## Task M7h: Audit Company-Supplier Link Ownership

**Description:** Register `company_supplier_links` and classify its exact company, global supplier and optional platform-account parents before changing supplier visibility or link writers.

**Status:** Completed in production read-only. The table currently has zero rows; the report returned `readyForStrictRuntime=true`, `unresolved=0`, `mismatched=0`, `writesAttempted=0`, `needsReview=[]` and rolled back without changing data.

**Acceptance criteria:**
- [x] Every link requires an existing stored company and existing global supplier.
- [x] Optional stored `platform_account_id` must exist and equal the company's platform account; absent optional account does not replace or weaken the company owner.
- [x] Missing parents are unresolved and cross-account links are mismatched; neither is guessed or repaired.
- [x] Loader reads only IDs and owner relations, never contract terms, rating, category, source, status or supplier details.
- [x] Report runs read-only, rolls back and reports `writesAttempted=0`.
- [x] Production dry-run provides exact verified/unresolved/mismatched counts and review reasons.
- [x] Registry coverage confirms `company_supplier_links` leaves the unregistered set.

**Verification:**
- [x] `python3 -m unittest backend.features.supplier_link_ownership.test_ownership_report` (`7` tests).
- [x] `npm run audit:supplier-link-ownership` on production: `0` rows, zero unresolved/mismatched and zero writes.
- [x] `npm run audit:tenant-registry-coverage` on production: `78` unregistered tables and zero registry drift.

**Dependencies:** Task M7g production completion

**Estimated scope:** S

## Task M7i: Audit Core Supply Ownership

**Description:** Register and audit only the first stored procurement chain: `supply_requests -> supply_request_recipients -> supplier_offers`. Prove company and project/request ownership without reading materials, quantities, suppliers, prices, terms, messages or notes.

**Status:** Complete in production. Guarded cleanup removed the exact `25` orphan child rows and strict post-audit verified all `1628/1628` retained core-supply rows with no unresolved, ambiguous or mismatched owners.

**Acceptance criteria:**
- [x] A supply request is verified only by an existing stored company and exactly one same-company project matching its legacy project field.
- [x] A recipient and offer are verified only through their exact stored request parent and an identical stored company.
- [x] Missing parents are unresolved, duplicate same-company project names are ambiguous, and cross-company parents are mismatched.
- [x] Child rows of an unresolved request remain unresolved and are never independently guessed.
- [x] Loader reads only IDs and owner relations; procurement content and supplier/commercial fields are excluded.
- [x] Report runs read-only, rolls back and reports `writesAttempted=0`.
- [x] Production dry-run provides a complete review list: `25` unresolved rows, all caused by a missing request parent; no writes were made.
- [x] Registry coverage confirms the three tables leave the unregistered set.

**Verification:**
- [x] `python3 -m unittest backend.features.supply_ownership.test_ownership_report` (`10` tests).
- [x] `npm run audit:supply-ownership` on production: `17` orphaned recipients and `8` orphaned offers require review.
- [x] `npm run audit:tenant-registry-coverage` on production: all three tables are registered; `78` tables remain outside the registry.

**Dependencies:** Task M7g production completion; independent of M7h supplier-link audit and any future supply backfill or runtime change

**Estimated scope:** S

## Task M7i1: Diagnose Orphaned Core-Supply Children

**Description:** Determine why the `25` production recipients/offers reference missing supply requests and whether downstream invoices, deliveries, messages or other records still depend on them. Produce only IDs, relation types and exact counts; do not expose procurement content.

**Status:** Completed in production read-only. The exact `25`-row source set and SHA matched. `16` rows have no references; `9` rows point only to five terminal legacy MAX outbox rows. No invoices, deliveries, claims, warehouse invoices, supply history or owner mismatches were found. The transaction rolled back without writes.

**Acceptance criteria:**
- [x] The report starts from the exact `17` recipient and `8` offer rows identified by `M7i` and fails closed if the set changes.
- [x] It distinguishes deleted/test request residue from rows that still have downstream business references without guessing a replacement request.
- [x] It reads and outputs only IDs, company ownership and relation types; materials, suppliers, prices, terms, messages and notes remain excluded.
- [x] It runs read-only, rolls back and reports `writesAttempted=0`.
- [x] Future cleanup is separated into Task M7i2 and must preserve terminal legacy MAX history behind exact count/SHA guards.

**Verification:**
- [x] Focused unit tests cover stale request IDs, downstream references, changed-set failure and zero-write rollback (`5` tests; `15` combined supply-audit tests).
- [x] Production dry-run: `16 residueCandidates`, `9 withDownstreamReferences`, `9 referenceLinks`, `0 ownerMismatchLinks`, exact source set matched, `rolledBack=true`.

**Dependencies:** Task M7i production dry-run

**Estimated scope:** S

## Task M7i2: Guarded Core-Supply Orphan Cleanup

**Description:** Prepare an exact cleanup plan for the `17` orphan recipients and `8` orphan offers whose requests no longer exist. Preserve the five already-terminal legacy MAX outbox rows and do not touch valid requests, invoices, deliveries, claims, warehouse documents or supply history.

**Status:** Complete in production. Exact count/SHA guarded apply deleted `17 supply_request_recipients` and `8 supplier_offers`, preserved MAX outbox `30/32/34/36/38`, left zero orphan rows and passed supply/messenger post-audits plus public smoke.

**Acceptance criteria:**
- [x] Dry-run requires source count `25` and SHA `99f5b9b8a3e7d45bbea2042e12dfbadf727447e58996975243f36f5cf0f001e8`; changed input fails closed.
- [x] Plan includes only the exact `17 supply_request_recipients` and `8 supplier_offers` rows whose parent requests are absent.
- [x] Messenger outbox rows `30/32/34/36/38` remain unchanged as terminal legacy history.
- [x] Any newly discovered invoice, delivery, claim, warehouse, history or owner-mismatch reference blocks the whole plan.
- [x] Default command is dry-run with `writesAttempted=0`; apply requires explicit expected count and plan SHA.
- [ ] Post-apply verification must rerun `audit:supply-ownership`, `audit:supply-orphans` and messenger ownership audit before M7i closes.

**Verification:**
- [x] Unit tests cover exact-set success, changed-set failure, newly linked business document failure, preserved terminal-legacy outbox state, rollback and guarded apply (`10` remediation tests; `25` combined core-supply tests).
- [ ] Production dry-run captures the exact delete plan before any apply.

**Dependencies:** Task M7i1 production completion

**Estimated scope:** S

## Task M7j: Audit Supply Invoice And Delivery Ownership

**Description:** Register and audit the next procurement chain slice: `supplier_invoices -> supply_deliveries`. Verify stored company/project ownership and optional or required request/offer parents without reading invoice, supplier, material, quantity, price, file or delivery content.

**Status:** Complete in production read-only. The reciprocal main-warehouse classification verified supplier invoice `#15`; final report is `53/53` with zero unresolved, ambiguous or mismatched rows and `readyForStrictRuntime=true`.

**Acceptance criteria:**
- [x] A direct supplier invoice is verified only by an existing stored company and exactly one same-company project matching its legacy project field.
- [x] When an invoice stores `request_id` or `offer_id`, every stored parent must exist and match the same company/project/request chain.
- [x] A supply delivery requires both exact request and offer parents, and both must match its stored company and exact same-company project.
- [x] Missing parents are unresolved, duplicate same-company project names are ambiguous, and cross-company/project/request links are mismatched.
- [x] Loader reads only record and owner-parent IDs plus the legacy project fields needed for classification; commercial and delivery content is excluded.
- [x] Report runs in a PostgreSQL read-only transaction, rolls back and reports `writesAttempted=0`.
- [x] Production dry-run reported `52 verified`, `1 unresolved`, `0 ambiguous`, `0 mismatched`; the only reason was `project_owner_missing` for supplier invoice `#15`.
- [x] Registry coverage confirms both tables leave the unregistered set.

**Verification:**
- [x] `python3 -m unittest backend.features.supply_execution_ownership.test_ownership_report` (`12` tests).
- [x] `npm run audit:supply-execution-ownership` on production: one exact main-warehouse legacy case requires classifier re-run after the local correction.
- [x] `npm run audit:tenant-registry-coverage` on production: `51` registered physical tables, `76` unregistered and zero registry drift.

**Dependencies:** Task M7i report implementation; independent of M7h production result and later warehouse ownership audit

**Estimated scope:** S

## Task M7k: Audit Warehouse Invoice And History Ownership

**Description:** Register and audit `warehouse_invoices -> warehouse_history`. Verify exact stored company/project or explicit main-warehouse scope and validate optional request, delivery and supplier-invoice parents without reading warehouse or commercial content.

**Status:** Complete in production read-only. The reciprocal document chain verified warehouse invoice `#37`; final report is `404/404`, including all `359` warehouse-history rows, with zero unresolved, ambiguous or mismatched rows and `readyForStrictRuntime=true`.

**Acceptance criteria:**
- [x] An object warehouse invoice is verified only by an existing stored company and exactly one same-company project resolved from its project/location scope.
- [x] A main-warehouse invoice and history row use explicit company scope; an object cannot be hidden behind `warehouse_target=main`.
- [x] Optional request, delivery and supplier-invoice parents must exist, already have a verified exact owner chain and match the warehouse company/project/request.
- [x] A non-null supplier-invoice reverse link cannot point to another warehouse invoice.
- [x] Warehouse history requires either one exact same-company project or explicit `Основной склад`; blank scope remains unresolved.
- [x] Missing parents are unresolved, duplicate same-company projects are ambiguous and cross-company/project/request links are mismatched.
- [x] Loader reads only IDs and owner relations; materials, quantities, units, supplier data, document numbers, totals, items, payments, photos and personal fields are excluded.
- [x] Report runs read-only, rolls back and reports `writesAttempted=0`.
- [x] Production dry-run reported `403 verified`, `1 unresolved`, `0 ambiguous`, `0 mismatched`; the only reason was `supplier_invoice_parent_unresolved` for warehouse invoice `#37`.
- [x] Registry coverage confirms both warehouse tables leave the unregistered set and reports no missing or duplicate registry entries.

**Verification:**
- [x] `python3 -m unittest backend.features.warehouse_ownership.test_ownership_report backend.features.supply_execution_ownership.test_ownership_report` (`30` tests after the exact main-warehouse regression cases).
- [x] `npm run audit:warehouse-ownership` on production: the sole unresolved row is the same `15 <-> 37` main-warehouse legacy chain.
- [x] `npm run audit:tenant-registry-coverage` on production: both warehouse tables are registered with zero registry drift.

**Dependencies:** Task M7j implementation; production classification remains independent of any future warehouse cleanup, backfill or runtime change

**Estimated scope:** S

## Task M7k1: Separate Main Warehouse Receipt From Supplier Payable

**Description:** Allow a director or deputy director to receive material into the main warehouse without a supplier document or payable, while preserving the existing supplier-backed invoice chain.

**Status:** Completed in production runtime `2f5ac37717cb`. Public smoke and protected `smoke:main-warehouse-receipt` passed; initial QA 2FA setup is supported, all temporary receipt rows were removed, and the QA user was disabled after the run.

**Safety:**
- The inventory-only mode is explicit, main-warehouse-only and revalidated on the backend for `директор` or `зам_директора`.
- Supplier identity and `supplier_invoice_id` are forbidden in this mode; the backend never creates or syncs `supplier_invoices`.
- The material and `warehouse_history` receipt remain ordinary stock facts. Only accounting/payable behavior is excluded.
- Legacy supplierless main-warehouse receipts are excluded from warehouse and supplier accounting lists even if an old bad reciprocal link exists.
- Supplier-backed main-warehouse documents retain the existing accounting chain and access roles.

**Verification:**
- [x] Backend policy unit tests.
- [x] Frontend accounting-policy unit tests.
- [x] Python compilation and production frontend build.
- [x] Production deploy.
- [x] Protected `npm run smoke:main-warehouse-receipt` with deputy-director 2FA.
- [x] `npm run smoke:prod` after deploy.
- [x] Both ownership audits after the protected smoke: supplier invoices/deliveries `59/59`, warehouse invoices/history `404/404`, with zero unresolved, ambiguous or mismatched rows.

**Estimated scope:** S

## Task M7l: Isolate Tools And Inventory By Company

**Description:** Add a read-only ownership report for `tools`, `tool_history`, `inventory`, and inventory children, resolve exact company/project parents, then add stored tenant ownership and selected-company runtime filtering in guarded slices.

**Status:** Pending. Runtime `2af7b25bb333` fixes immediate post-save visibility and error handling only. Production currently contains three tool rows, and the tables remain global without `company_id`; do not treat this UI fix as multi-company isolation.

**Progress:** M7l1 adds a read-only report over `tools`, `tool_history`, `inventory`, and `inventory_items`. It accepts only a globally unique project owner or an exact verified parent; names of tools/masters and empty project fields never infer ownership. Production found three empty-project tools in the main warehouse; owner confirmed all three as company-wide for company `1`. M7l2 applied on 2026-08-03 with exact SHA/count guards: all three tools now store company `1` with company-wide scope; `tool_history`, `inventory` and `inventory_items` have the guarded schema but contain no legacy rows.

**M7l3 implementation:** `/tools`, `/tool-history`, `/inventory` and inventory-item mutations now resolve the request company server-side, filter every read by stored `company_id`, require one selected company for writes, and inherit child/history ownership from the verified tool or inventory parent. Payloads cannot select owner columns. Existing operational fields (`status`, `location`, master and project text) are preserved. Production runtime `5ff69f3d` passed the protected self-cleaning smoke and strict post-audit on 2026-08-03.

**Boundary checkpoint:** `smoke:platform-crm` provisions two companies under one SaaS account and a temporary director with memberships in both. It verifies selected-company isolation for tools, inventory and CRM, rejects direct mutations of a record while another company is selected, and rejects writes in `all_companies` mode. Production run passed on 2026-08-03 (`companyAId=5`, `companyBId=6`); cleanup completed.

**Cross-account checkpoint:** The same smoke adds a deliberately invalid membership from a temporary director to an active company belonging to a different `platform_account`. Selected-company reads of tools and CRM are rejected with `403` before data is returned. Production passed on 2026-08-03 (`companyAId=2`, `companyBId=3`, rejected foreign `companyId=1`); cleanup completed.

**Supply lineage checkpoint:** A received supply delivery writes `warehouse_history.source_type=supply_delivery`, the exact delivery ID and generated warehouse-invoice ID in addition to its stored company. `smoke:supply-chain` verifies one company across request, offer, supplier invoice, delivery, warehouse invoice, supply history and the exact linked warehouse-history row. Production runtime `97fc1dd8` passed the protected run on 2026-08-03 (`companyId=1`, `deliveryId=15`, `warehouseInvoiceId=138`); cleanup completed.

## Task M7l4: Audit Remaining Legacy Fallbacks

**Description:** Add one read-only report over the remaining legacy-default critical tables: `projects`, `staff`, `estimates`, `brigade_contracts`, `interim_acts` and `hidden_works_acts`. It checks the stored `company_id` against an existing company and, where an exact parent ID exists, verifies that the parent is in the same company. A row without stored company but with an exact verified parent is reported as an explicit fallback; missing, deleted or mismatched ownership remains review-only.

**Safety:** `npm run audit:legacy-fallback` opens a read-only transaction, returns only IDs and ownership classifications, rolls back, and does not change schema, data, route filtering or legacy visibility.

**Production result:** `npm run audit:legacy-fallback` passed on 2026-08-03 without writes: all `39/39` rows were verified (`projects=4`, `staff=7`, `estimates=21`, `brigade_contracts=4`, `interim_acts=2`, `hidden_works_acts=1`), with `fallback=0`, `unresolved=0` and empty review lists. The legacy-fallback SaaS checkpoint is closed.

## Task P3a: Packaging Stock-Correction Readiness

**Description:** Before adding receipt lots or a stock-changing endpoint, report the exact traceability and schema blockers. `npm run audit:material-stock-correction-readiness` reuses the receipt-to-movement evidence, verifies that `warehouse_receipt_lots` exists, and remains false until both the future lot schema and direct receipt references are clean.

**Safety:** The command is read-only, rolls back, does not create the future tables and never proposes an apply operation for historical aggregate balances.

## Task P3b: Receipt Lots For New Warehouse Receipts

**Description:** Add `warehouse_receipt_lots` only as an additive companion to newly accepted warehouse-invoice lines. Each lot preserves document and normalized quantity, available quantity, exact company, location, invoice ID and line index. Existing invoices, balances, movements and history are not backfilled or rewritten.

**Safety:** The receipt transaction creates the lot together with its existing stock/history writes. Duplicate source lines are ignored by a unique `(company_id, warehouse_invoice_id, invoice_line_index)` index. No movement consumes a lot in this slice; that requires a separate guarded slice.

**Production result:** Runtime `9a90bf19` passed protected `smoke:main-warehouse-receipt` on 2026-08-03. The temporary inventory-only main-warehouse receipt created one exact available receipt lot in company `1`, retained the invoice-line link in history, did not create a supplier invoice or accounting obligation, and cleanup removed the generated rows. `smoke:prod` passed afterwards.

## Task P3c: Consume Exact Receipt Lots On New Movements

**Description:** When a warehouse movement explicitly selects an invoice line and that line has a future receipt lot, lock the exact lot in the same transaction, reject an unavailable balance, reduce only that lot's available quantity, and add an immutable `warehouse_lot_movements` record linked to the warehouse movement. Historical selected invoice lines without a lot retain the existing aggregate movement path and are not backfilled.

**Safety:** The existing aggregate stock update and invoice-line allocation validation remain in force. A race or closed/invalid lot rolls back the whole movement. This slice does not enable packaging stock corrections, reversals, or alteration of historic receipts.

**Verification:** Local unit tests cover the missing-lot compatibility path, available-balance guard and immutable lot event. `npm run smoke:receipt-lot-movement` creates an isolated temporary project and active estimate, receives one object invoice line, moves it to the main warehouse by explicit invoice source, asserts the depleted lot and exact immutable event, then removes every test row. Full backend suite passed locally: `991` tests.

**Production result:** Runtime `821c24f0` passed protected `smoke:receipt-lot-movement` on 2026-08-03. The smoke created a temporary project receipt, then moved it from the object to the main warehouse by the selected invoice line. The exact lot balance became zero and one immutable `warehouse_lot_movements` row referenced the same warehouse movement; cleanup removed all generated rows.

**Safety:**
- Start with a no-write production report and exact parent/reference counts.
- Do not infer company from a tool name, master name, or empty project.
- Keep current tools visible to the pilot company until ownership is proven and migrated.

**Estimated scope:** M

## Task 12: Extract Auth Helpers

**Description:** Move auth/session helper functions from `backend/main.py` into `backend/auth.py` without changing behavior.

**Status:** Complete in production 2026-07-27 (runtime `a82edc9`). 37 pure primitives (password hashing, TOTP/2FA, signed flow tokens, bearer tokens, session records, CSRF, session cookies) moved verbatim into `backend/auth.py`; `main.py` imports them back, so no call site changed. DB-touching user resolution (`get_current_user`, `public_user`, role dependencies) intentionally stays in `main.py` for a later slice. Deploy ran the standard atomic procedure; `smoke:prod` passed after the nginx location sync for the new finance/packaging routes, and `smoke:auth-session` passed fully (login, cookie + CSRF logout, Bearer fallback, every session-revocation scenario).

**Acceptance criteria:**
- [x] Route behavior is unchanged (no call-site edits; full backend suite of 755 tests green; pyflakes undefined-name parity with the pre-change file).
- [x] `backend/main.py` imports auth helpers.
- [x] No schema or business logic changes are mixed into this extraction.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/auth.py`
- [x] `npm run smoke:auth-session` — passed in production 2026-07-27 on runtime `a82edc9`.

**Dependencies:** Task 5

**Files likely touched:**
- `backend/main.py`
- `backend/auth.py`

**Estimated scope:** S

## Task 13: Extract Audit And Client Error Routes

**Description:** Move low-coupling audit/client-error endpoints into a feature module while preserving route paths.

**Status:** Complete in production 2026-07-27 (runtime `b8c0fb5`). Scope note: `/audit-log` routes were already extracted earlier by M6.8a3 into `backend/features/audit_ownership/routes.py`; this slice moved the remaining pair — `POST /client-errors` and `GET /system-status` — verbatim into `backend/features/api_error_ownership/routes.py` (`register_api_errors_module`, deps-injection like the messenger/audit modules) instead of the originally guessed `features/ops`. Deploy smoke passed (`client errors route 422`), `/system-status` answers `401` through nginx, zero new tracebacks. `smoke:activity-log` needs provisioned `SMOKE_EMAIL`/`SMOKE_PASSWORD` and exercises audit routes untouched by this slice — left for a conveyor run with smoke credentials.

**Acceptance criteria:**
- [x] Existing audit/client-error endpoints keep the same URLs.
- [x] Logging still writes the same payload fields (covered by new route tests asserting the exact insert payload and owner scope).
- [x] `backend/main.py` only registers the module.

**Verification:**
- [x] Backend compile passes; full suite `760` tests green (5 new in `test_routes.py`).
- [ ] `npm run smoke:activity-log` (needs SMOKE_EMAIL/SMOKE_PASSWORD; audit routes not part of this slice)

**Dependencies:** Task 12

**Files likely touched:**
- `backend/main.py`
- `backend/features/ops/routes.py`
- `backend/features/ops/__init__.py`

**Estimated scope:** S

## Task 14: Move One Schema Slice To Alembic

**Description:** Move one low-risk `init_db()` table or column group into an Alembic revision while keeping idempotent compatibility during rollout.

**Acceptance criteria:**
- [ ] New migration is small and reviewable.
- [ ] `init_db()` compatibility guard remains until production upgrade is verified.
- [ ] Downgrade or rollback strategy is documented.

**Verification:**
- [ ] `alembic history`
- [ ] `alembic upgrade head` on local initialized database.
- [ ] Backend compile passes.

**Dependencies:** Task 2

**Files likely touched:**
- `backend/main.py`
- `migrations/versions/*.py`
- `migrations/README.md`

**Estimated scope:** M

## Task 15: Minimal CI Quality Gate

**Description:** Add CI for backend compile, frontend tests, and frontend build so regressions are caught before deploy.

**Acceptance criteria:**
- [ ] CI installs backend/frontend dependencies.
- [ ] CI runs backend compile.
- [ ] CI runs frontend tests and build.

**Verification:**
- [ ] Workflow passes on GitHub or equivalent local runner.

**Dependencies:** Task 2

**Files likely touched:**
- `.github/workflows/ci.yml`
- `README_LOCAL_RUN.md`

**Estimated scope:** S

## Task 15.1: Compatible Frontend Dependency Security Refresh

**Description:** Update only vulnerable transitive frontend packages that fit the existing dependency ranges. Do not change React, `react-scripts`, or `xlsx`, and do not use `npm audit fix --force` in this step.

**Status:** Original refresh deployed in `0d95c3d5`. The follow-up compatible override pins transitive `websocket-driver@0.7.5`; production runtime `8c16af0d4d36` passed clean `npm ci`, build and public smoke with audit `critical=0`, `total=28`.

**Acceptance criteria:**
- [x] Direct dependency versions remain unchanged; `package.json` contains only the exact transitive security override `websocket-driver@0.7.5`.
- [x] `package-lock.json` receives only SemVer-compatible updates calculated by `npm audit fix` without `--force`.
- [x] `deploy.sh` installs the exact lock-file tree with `npm ci` before building and restarting the service.
- [x] The critical `shell-quote` advisory is removed; audit totals fall from `40` to `29` and critical findings from `1` to `0`.
- [x] The later `websocket-driver` advisory is removed reproducibly by clean `npm ci`; audit returns to `28` total and `0` critical findings.
- [x] Remaining `react-scripts` and `xlsx` advisories stay visible as separate migration work instead of being hidden by breaking overrides.

**Verification:**
- [x] `npm ls --depth=0` passes.
- [x] Frontend tests and production build pass with the updated installed tree.
- [x] `npm audit --audit-level=critical` exits successfully with zero critical findings.
- [x] `bash -n deploy.sh` passes.
- [x] A clean staged snapshot installs with `npm ci`, then passes frontend tests, build, and static checks.
- [x] GitHub CI, production deploy, and public production smoke pass.

**Dependencies:** Task 15

**Files likely touched:**
- `package-lock.json`
- `deploy.sh`
- `ONBOARDING.md`
- `tasks/plan.md`
- `tasks/todo.md`

**Estimated scope:** S

## Task 15.2: Atomic Frontend Publication

**Description:** Keep the currently served frontend available while the next production bundle is built, and prevent two deploy processes from changing the same checkout at once.

**Status:** Deployed through `3e20b60e`; production verification passed.

**Acceptance criteria:**
- [x] `deploy.sh` acquires `/var/lock/stroyka-deploy.lock` before changing the checkout; a concurrent deploy exits before `git reset`, install, build, restart, or publish.
- [x] React builds into a unique temporary directory instead of nginx's live `build` directory.
- [x] Hashed assets are copied first and older hashes remain available for tabs opened before the deploy; manifests/public files follow, and `index.html` is replaced by one same-directory atomic rename.
- [x] The publisher rejects an incomplete release and any nonempty target that is not already a frontend build.
- [x] Live directory ownership and mode are not inherited from the private `mktemp` directory; `build` remains traversable by nginx with mode `0755`.

**Verification:**
- [x] `npm run test:deploy` passes three regression tests locally and on production Linux, including continuous index reads during delayed rsync and the `0700 -> 0755` permission case.
- [x] `bash -n deploy.sh scripts/publish-frontend.sh`, M6 audit, full frontend suite (`32` suites / `127` tests), and a real `BUILD_PATH` production build pass.
- [x] A deliberate second deploy was rejected with no changes while the first held the lock.
- [x] Final runtime `3e20b60eb8d0` passed public smoke; a 180.5-second monitor made `308` requests each to `/`, `/app`, and `/max-app`, all `924` responses were `200`.
- [x] Production `build` is `0755`, `index.html` is `0644`, the temporary release directory was removed, and all `133` manifest entries exist.

**Known follow-up:** Old hashed assets are intentionally retained for already-open tabs. Add a separate age-based cleanup only after cache lifetime and rollback requirements are explicitly defined.

**Dependencies:** Task 15.1

**Estimated scope:** S

## Task 16: Supply Operator UX Polish

**Description:** Improve the supply UI only after backend contracts are stable, focusing on clear business language and actionable diagnostics.

**Acceptance criteria:**
- [ ] Director/procurement user sees why KP is or is not visible to supplier.
- [ ] Supplier sees only relevant requests and clear linking warnings.
- [ ] Text remains Russian and business-facing.

**Verification:**
- [ ] Browser/manual check on supply page and supplier cabinet.
- [ ] `npm run build`

**Dependencies:** Tasks M3-M7

**Files likely touched:**
- `src/components/SupplyPage.jsx`
- `src/components/supply/SupplyRequestsListParts.jsx`
- `src/features/supply/SupplierCabinetPage.jsx`

**Estimated scope:** M

## Task 17: Browser Smoke For Highest-Risk Role Flow

**Description:** Add a browser smoke for one high-risk authenticated workflow after stable test credentials or TOTP are available.

**Acceptance criteria:**
- [ ] Smoke logs in safely.
- [ ] It checks one complete operator flow.
- [ ] It captures useful error output and screenshot evidence on failure.

**Verification:**
- [ ] `npm run smoke:browser-prod` or new targeted browser smoke passes in the intended environment.

**Dependencies:** Tasks 5 and M7

**Files likely touched:**
- `scripts/smoke-browser-prod.js`
- `TESTING.md`

**Estimated scope:** S

## Task 18: Documentation And Launch Notes

**Description:** Update project guidance after accepted behavior changes so future agents and deploys follow the same rules.

**Acceptance criteria:**
- [ ] `ONBOARDING.md` records accepted product/system rules.
- [ ] `TESTING.md` records new checks.
- [ ] Deploy notes identify required smoke commands and rollback path.

**Verification:**
- [ ] Documentation diff reviewed.
- [ ] Final validation commands are listed in the implementation summary.

**Dependencies:** Tasks 3-17 as applicable

**Files likely touched:**
- `ONBOARDING.md`
- `TESTING.md`
- `README_LOCAL_RUN.md`

**Estimated scope:** S

## Task P1: Protect Material Calculation From False Matches

**Description:** Make the existing project material-control calculation conservative before it can feed new supply requests. Keep warehouse receipt matching and stored business data unchanged.

**Status:** Completed and verified locally on 2026-07-10; production deployment is a separate step.

**Acceptance criteria:**
- [x] Different materials from one broad family are separate procurement rows unless an explicit alias resolves them to one canonical material.
- [x] AI/override norms do not apply from a single generic substring; known false positives (`прокладка`/`кладка`, `по штукатурке`, screed adjustment rows) are rejected.
- [x] An applicable override with `baseNormId` replaces that base rule instead of doubling the requirement.

**Verification:**
- [x] Full frontend suite passes: 61 tests, including 13 new material identity/norm regression tests.
- [x] `npm run check:smeta` passes for all 13 repository estimate files.
- [x] `npm run build` passes.
- [x] `git diff --check` passes.

**Dependencies:** None

**Files likely touched:**
- `src/utils/materialReconciliationUtils.js`
- `src/utils/materialNormUtils.js`
- `src/utils/materialReconciliationUtils.test.js`
- `src/utils/materialNormUtils.test.js`
- `ONBOARDING.md`

**Estimated scope:** M

## Task P2: Add Material Calculation Trace And Review States

**Description:** Expose the full calculation source and move uncertain matches out of operational procurement totals.

**Status:** Released to production on 2026-07-10 in `e1f317ef`.

**Acceptance criteria:**
- [x] Every explicit estimate material can be expanded to its estimate, package, section, work, source quantity, normalized quantity, conversion, and procurement decision.
- [x] Every norm hint can be expanded to its source work, rule, scope, formula, and result.
- [x] Estimate plan and norm hints have separate columns, filters, and totals.
- [x] Invalid estimate rows, unit conflicts, and unconfirmed identities are placed in `Проверить` and excluded from `Докупить`.
- [x] Single and batch supply-request actions enforce the same review guard outside the UI.
- [x] The printed material requirement report contains the same conversion, review reason, and norm formula trace.

**Verification:**
- [x] Focused material trace, review, action-guard, and print tests pass.
- [x] Full frontend test suite: 15 suites / 71 tests passed.
- [x] `npm run check:smeta`
- [x] `npm run build`
- [x] Production deploy, HTTP smoke, and browser smoke for `/` and `/app` passed on version `e1f317ef3397`.

**Dependencies:** Task P1

**Estimated scope:** M

## Task P3: Run Production Material Dry-Run

**Description:** Compare old and corrected projections and prepare review-only cleanup candidates for existing requests.

**Status:** Completed in production on runtime `b672315033c3`. The warehouse material-control overview includes the opened-project comparison, the on-demand summary across active projects and a consolidated item-level list of active requests that require review. Project/request identity is fail-closed, roles without supply-request access see an explicit unavailable state, and no cleanup, apply, delete or business-record mutation action is exposed.

**Verification:**
- [x] Comparator unit tests cover quantity changes, added/removed identities, split aggregates and input immutability.
- [x] UI test covers collapsed/expanded comparison, split quantities, read-only notice and absence of mutation controls.
- [x] Request-review tests cover active/terminal status handling, exact matches, legacy split provenance, missing identities and input immutability.
- [x] All-project tests cover totals, empty projects, risk sorting, input immutability, review-only filtering and absence of mutation controls.
- [x] Item-level tests cover estimate/material-projection provenance, manual-request exclusion, global request deduplication, conflicting duplicates, missing/malformed IDs as distinct review occurrences, inactive/ambiguous/missing project identity, active-before-dedupe status handling and zero-active-project reporting.
- [x] Role tests cover explicit unavailable states in both opened-project and all-project review without false zero/success.
- [x] Pagination tests cover the 50-row boundary, unrelated rerenders, semantic resets, candidate identity changes and A -> B -> A content changes.
- [x] Focused local regression: 3 suites / 28 tests passed.
- [x] Full local frontend regression after adversarial fixes: 60 suites / 237 tests passed.
- [x] Local production build passes after the final review fixes.
- [x] Production frontend build passes.
- [x] Material calculation and adjacent supplier regression suites pass after the build: 7 suites / 46 tests.
- [x] Production deploy and full public smoke pass on runtime `b672315033c3`.

**Dependencies:** Task P2

**Estimated scope:** M

## Task P4: Reconnect Confirmed Material Rows To Supply

**Description:** Restore batch request creation with lineage and idempotency, then verify the complete supplier chain.

**Status:** P4.1 is implemented and fully verified locally; production deployment is pending. P4.2 idempotency and P4.3 end-to-end supplier-chain verification remain separate follow-up slices.

**P4.1 acceptance criteria:**
- [x] Every single or batch request created from material control carries `requestSource=estimate_material_control`.
- [x] Every request item stores versioned project/package lineage and exact estimate/section/item coordinates.
- [x] Backend rechecks company, project, active estimate, estimate type, package, source coordinates, material identity, unit and source quantity before creating the request.
- [x] Confirmed material aliases are accepted through the existing canonical resolver; broad family/name matching is not accepted as lineage.
- [x] A stale cached material-control payload without the new lineage is rejected with an update/refresh instruction instead of falling back to broad estimate control.
- [x] Manual, invoice-control and norm-based request paths remain unchanged.
- [x] Existing estimates and supply requests are not migrated, rewritten or deleted.
- [x] P3 request review recognizes the new nested `estimateLineage` without relying on legacy notes.

**P4.1 verification:**
- [x] Backend lineage unit tests: 11 passed.
- [x] Full backend regression: 748 passed.
- [x] Full frontend regression: 60 suites / 242 tests passed.
- [x] Python compilation and `git diff --check` pass.
- [ ] Production build, deploy, protected material-control smoke and public smoke.

**Dependencies:** Task P3

**Estimated scope:** M

## Task P5: Cache And Cut Over Material Projection

**Description:** Move repeated heavy calculation out of React renders, add package-level loading, shadow verification, and staged rollout.

**Dependencies:** Task P4

**Estimated scope:** M

## Task M6.6a: Five-Table AI Ownership Audit

**Description:** Produce one fail-closed read-only ownership report for `project_ai_summary`, `ai_findings`, `ai_tasks`, `ai_task_reports`, and `ai_task_attachments`. Resolve tenant rows through a globally unique project and verified parent chain; classify `project_name='Система'` as an explicit platform scope. Do not read AI business payloads, write rows, migrate schema, or change runtime routes.

**Status:** Completed in production. The final report classified all `3382` retained rows as verified, including `141` platform-system rows, with `unresolved=0`, `mismatched=0`, `needsReview=[]`, and `writesAttempted=0`. Six orphaned work-assignment smoke tasks were removed by an exact guarded transaction, and the originating smoke cleanup was fixed.

**Runtime slices after a clean report:**
- `M6.6b` project AI summary read/write.
- `M6.6c` finding list/create/update and supported linked-entity verification.
- `M6.6d` task CRUD and assignment actions, including isolated platform system tasks.
- `M6.6e` reports and attachments through matching task/report parents.
- `M6.6f` generate/run/run-all, automatic execution, dedupe and close cascades, then cross-company negative tests.

**Verification:**
- [x] Focused classifier tests cover valid tenant chains, platform system tasks, ambiguous projects, unsupported/mismatched polymorphic entities, orphan reports, and cross-task attachments.
- [x] Database runner requests a PostgreSQL read-only transaction and executes only ownership/linkage `SELECT` statements.
- [x] Production report has `readyForStrictRuntime=true`, `writesAttempted=0`, `unresolved=0`, and `mismatched=0`.

**Estimated scope:** S

## Task M6.6b1: Store Project AI Summary Ownership

**Description:** Add nullable `company_id/project_id` to `project_ai_summary`, revalidate each exact legacy `project_name` against one project, and backfill only a guarded dry-run plan. Keep existing GET/POST and AI-control runtime unchanged.

**Status:** Completed in production. Guarded apply updated the sole legacy row to `company_id=1/project_id=1`; post-audit returned `storedRows=1`, `legacyRows=0`, no review rows, and `readyForStrictRuntime=true`.

**Safety:**
- Dry-run uses a PostgreSQL read-only transaction and never alters schema.
- Apply requires `APPLY_AI_SUMMARY_OWNERSHIP`, expected ready count, and exact plan SHA-256.
- Apply locks projects/summary, updates only null owners, creates the future `(company_id,project_id)` unique index, and commits only after every row is stored and reverified.
- The existing global `project_name` primary key remains until runtime cutover; removing it is the independent M6.6b3 step.

**Estimated scope:** S

## Task M6.6b3: Cut Over Project AI Summary Primary Key

**Description:** After tenant-scoped summary runtime is live, replace the global `project_name` primary key with `(company_id,project_id)` so independent companies can use the same project name. Do not change summary payloads or routes in this slice.

**Status:** Completed in production on runtime `1dbd04db211a`. The primary key is `(company_id,project_id)`, the legacy name key is removed, and both ownership and public smoke audits passed.

**Safety:**
- Dry-run is read-only and validates stored owners, duplicate owner groups, current PK columns, row count, and plan SHA-256.
- Apply locks projects and summaries, requires the exact legacy constraint, sets owner columns `NOT NULL`, replaces only the PK, and performs a post-check before commit.
- The existing partial unique `(company_id,project_id)` index remains during this cutover so the already deployed M6.6b2 upsert contract stays valid.

**Estimated scope:** S

## Task M6.6c1: Store AI Finding Ownership

**Description:** Add nullable `company_id/project_id` to `ai_findings` and guarded-backfill every row through its exact project plus any supported linked entity. Keep findings CRUD, AI-control, dedupe, tasks, and business payloads unchanged.

**Status:** Completed in production. Guarded apply updated `1342/1342` rows without conflicts; the repeated audit is strict-ready with no legacy or review rows.

**Safety:**
- Dry-run uses a PostgreSQL read-only transaction and never selects finding title, description, suggested action, or assignment content.
- Apply locks all supported parent tables and findings, requires `APPLY_AI_FINDINGS_OWNERSHIP`, count and SHA, and updates only rows with both owner columns null.
- The batch update is followed by full project/entity/stored-owner reclassification before commit.

**Estimated scope:** S

## Task M6.6c2: Scope AI Findings Runtime

**Description:** Scope finding list/create/update and internal finding upsert/dedupe/stale-close through stored company/project ownership. Keep AI task/report/attachment ownership and run-all orchestration for their later independent slices.

**Status:** Completed in production on runtime `88fbc832a5b1`. Public/protected smoke and strict owner post-audit passed.

**Safety:**
- Every request resolves one selected company and one effective company role before finding SQL.
- List and direct-ID updates use stored `company_id/project_id`; a foreign finding ID returns `404`.
- New and deduplicated findings always persist the resolved owner; supported linked entities must resolve to the same owner.
- Automatic name-only execution fails closed when the project owner is not globally unique.

**Estimated scope:** M

## Task M6.6d1: Store Explicit AI Task Ownership

**Description:** Add guarded task ownership without changing task routes. Tenant tasks store `owner_scope='company'` with `company_id/project_id`; `Система` tasks store `owner_scope='platform'` with no company/project IDs.

**Status:** Completed in production. `2039/2039` rows migrated without conflicts; repeated audit is strict-ready.

**Safety:**
- A task linked to a finding must inherit exactly the finding's stored owner.
- A task without finding must resolve one exact project owner.
- Platform scope is allowed only for `project_name='Система'` and cannot contain company/project IDs.
- Runtime task CRUD remains unchanged until a clean post-audit.

**Estimated scope:** S

## Task M6.6d2a: Enforce AI Task Owner Writes

**Description:** Persist explicit owner on every task insert and constrain AI/finding dedupe updates by that owner before switching task routes.

**Status:** Completed in production on runtime `337fdba2ffc3`; strict post-audit passed.

**Safety:**
- Finding tasks inherit the finding's stored company/project owner.
- Standalone project tasks require one exact project owner.
- Password-reset tasks use platform scope only.
- Dedupe updates and duplicate closing include the complete stored owner filter.

**Estimated scope:** S

## Task M6.6d2b: Isolate AI Task Routes and Actions

**Description:** Keep the current task API and screens while scoping direct task CRUD, assignment lists and accept/report/close actions through the selected company and stored task owner.

**Status:** Completed in production on runtime `337fdba2ffc3`; public smoke and strict post-audit passed. Protected smoke still requires credentials.

**Safety:**
- `all_companies` is rejected; one company context is required.
- Company tasks use stored `company_id/project_id`; platform tasks are excluded from company requests and require a platform role.
- Cross-company IDs are hidden with `404` before mutation.
- Mutations lock the exact stored project and refetch the task with complete owner.
- Worker visibility keeps both project assignment and role/person assignment filters.
- Reports and attachments remain M6.6e, but current actions reach them only through a verified parent task.

**Estimated scope:** M

## Task M6.6e1: Store AI Task Child Ownership

**Description:** Guarded migration for `ai_task_reports` and `ai_task_attachments` without changing child runtime. Reports inherit stored task owner; attachments require matching report/task parents and owner.

**Status:** Completed in production. Both child tables were empty; schema apply and strict post-audit completed without row writes or conflicts.

**Safety:**
- Dry-run reads IDs and owner columns only, not report text or file URLs.
- Apply requires exact ready count and SHA-256 plan.
- Parent reports are updated before attachments in one serializable transaction.
- Missing parents, report/task mismatch and stored-owner mismatch block the whole apply.
- Runtime switches only in M6.6e2 after strict-ready post-audit.

**Estimated scope:** S

## Task M6.6e2: Isolate AI Task Child Runtime

**Description:** Persist owner on every report and attachment write, and require child owner to match the already authorized task/report parent on reads.

**Status:** Completed in production on runtime `52cf98630067`; live assignment/report/attachment owner smoke passed and cleaned up.

**Safety:**
- Existing API routes and response shape remain unchanged.
- Report list joins the authorized task by exact stored owner.
- Attachment list requires the same report, task and stored owner.
- Report, close-comment and attachment inserts copy owner from the locked parent task.
- Summary counters ignore child rows whose owner does not match their task.
- Fresh installations create the same owner columns and CHECK constraints; existing databases still use guarded migration.

**Estimated scope:** S

## Task M6.6f1: Isolate Single-Project AI Control Runs

**Description:** Keep the existing single-run URLs while resolving one selected company, effective company role and exact stored project owner before AI generation.

**Status:** Deployed on production runtime `c6dfddaa321b`; public smoke passed. Protected single-run is intentionally deferred into the combined final M6.6 smoke.

**Safety:**
- `all_companies` is rejected before project lookup or generation.
- Role checks use the effective role in the selected company, not only the base account role.
- The runner receives exact `companyId/projectId/name` and does not resolve output owner globally by name.
- Standalone task upsert, duplicate cleanup and stale-close reuse that same exact owner.
- Name-only AI sources fail with `409` when the same project name exists more than once.
- `/ai-control/run-all` and automatic event runs remain unchanged until M6.6f2.

**Estimated scope:** S

## Task M6.6f2: Isolate Batch and Event AI Control Runs

**Description:** Scope batch and automatic AI runs without changing the AI findings/tasks business algorithm.

**Status:** Deployed in production runtime `8ef743a6a7d6`; public smoke passed. Combined protected M6 smoke is intentionally deferred.

**Safety:**
- User `run-all` requires one selected company and an effective leadership/engineering role.
- Internal scheduler may enumerate companies, but resolves exact owner for every project.
- Every project in `run-all` uses an independent transaction; one failure does not leave partial writes or stop other projects.
- Event-triggered runs resolve one exact owner and commit or roll back atomically.
- Ambiguous name-only sources fail closed instead of mixing company data.
- Final protected smoke combines deferred single-run, company batch, event run and negative cross-company checks.

**Estimated scope:** M

## Task M6.7a: Audit Messenger File And Outbox Ownership

**Description:** Produce a read-only owner report for `messenger_files` and `messenger_outbox` before adding tenant columns or changing MAX runtime.

**Status:** Production dry-run completed with `writesAttempted=0`: `8` outbox rows are unresolved, including `5` missing supply-request parents and `3` messenger channels without an owner.

**Safety:**
- Database session is forced read-only and reports `writesAttempted=0`.
- Exact project or supported entity parent is stronger than recipient identity.
- Recipient membership may disambiguate duplicate project names but never guesses between several companies.
- Conflicting recipient and parent owners are `mismatched`; missing or multiple candidates remain review rows.
- Message bodies, file bytes, payload JSON and attachment metadata are not read.

**Estimated scope:** S

## Task M6.7a1: Clarify Messenger Ownership Diagnostics

**Description:** Separate supported-but-deleted parents from unknown entity types and show recipient-company candidates without treating them as verified ownership.

**Status:** Production rerun confirmed `5` supported-but-deleted supply parents and `3` channels without owner; every row has an empty recipient-company candidate list.

**Safety:**
- The report remains read-only and does not inspect payload or message content.
- Missing supported parents use `entity_parent_not_found`; unknown types use `entity_parent_unsupported`.
- `recipientCompanyIds` is diagnostic evidence only and cannot make an orphaned entity row migration-ready.

**Estimated scope:** XS

## Task M6.7a2: Audit Messenger Channels And Queue State

**Description:** Treat messenger channels as tenant parents, report their project ownership and expose only operational outbox state needed for a safe migration decision.

**Status:** Production audit completed: four enabled internal channels have no owner; three channel messages are already sent; five failed supply messages point to deleted smoke requests.

**Safety:**
- Channel audit reads only ID, type, project name, enabled state and timestamp; chat IDs, titles and metadata stay unread.
- Outbox diagnostics add only entity ID, status and timestamp; message title/body/payload remain unread.
- `messenger_accounts` is recorded as a shared identity resolved through selected-company memberships, not forced into one company.
- No old outbox row is deleted, retried or linked by this audit.

**Estimated scope:** S

## Task M6.7a3: Stop Supply Smoke Outbox Orphans

**Description:** Make supply-chain cleanup remove MAX outbox rows for every request created by the smoke before deleting the request parents.

**Status:** Released in `9991ee5d`. Production cleanup verification remains grouped with the next supply-chain smoke.

**Safety:**
- Cleanup targets only `provider='max'`, `entity_type='supply_request'` and the exact request IDs created by the current smoke.
- Production business requests and unrelated outbox rows are never selected.
- Existing failed orphan rows remain untouched until the guarded messenger migration defines their legacy status.

**Estimated scope:** XS

## Task M6.7b: Guard Messenger Channel Ownership Migration

**Description:** Add nullable `company_id/project_id` to messenger channels and backfill only exact project owners or explicit operator-provided channel mappings.

**Status:** Production migration completed: all four internal channels store company `1`, no project owner, no legacy/review/mismatch rows; the guarded post-audit is strict-ready.

**Safety:**
- Dry-run is read-only; apply requires exact ready count, SHA-256 plan and `APPLY_MESSENGER_CHANNEL_OWNERSHIP` confirmation.
- Company-level channels without project names are never assigned automatically.
- Every explicit company/project is checked against existing companies and the exact project parent.
- Unknown channel IDs, partial stored owners, mapping conflicts and changed plans block the whole transaction.
- Runtime routes and outbox rows remain unchanged until the stored channel-owner post-check is clean.

**Estimated scope:** M

## Task M6.7c: Consume Stored Channel Ownership In Messenger Audit

**Description:** Make the existing read-only messenger ownership report prefer stored channel company/project ownership and pass it to channel-linked outbox rows.

**Status:** Production verified: four channels and three sent channel messages resolve to company `1`; only five failed deleted-parent supply notifications remain unresolved.

**Safety:**
- Runtime webhook, channel CRUD, outbox writes and dispatch remain unchanged.
- Stored project ownership is revalidated against the exact project company before it is accepted.
- Legacy project-name inference remains available only for channels without stored ownership.
- Five failed outbox rows with deleted supply parents remain unresolved and visible; this slice does not delete, retry or relabel them.

**Estimated scope:** XS

## Task M6.7d1: Guard Messenger File And Outbox Ownership Migration

**Description:** Add nullable `owner_scope/company_id/project_id` to messenger files and outbox, backfill verified company owners, and preserve only explicitly selected failed deleted-parent outbox rows as terminal legacy history.

**Status:** Implemented and tested locally. Production dry-run is pending.

**Safety:**
- Dry-run is read-only; apply requires exact ready count, SHA-256 plan and `APPLY_MESSENGER_ITEM_OWNERSHIP` confirmation.
- A row can become `legacy` only through an explicit `--legacy-outbox ID`, only while `failed/skipped`, only with a supported deleted parent and no recipient-company evidence.
- A database constraint prevents legacy rows from returning to `queued`, so dispatch cannot resend them.
- Verified company rows inherit only the exact project/entity/recipient evidence from the existing audit; conflicting stored owners block the transaction.
- Runtime writes and tenant reads remain unchanged until the post-migration audit is strict-ready.

**Estimated scope:** M

## Task M6.7d2a1: Persist Internal MAX Item Ownership

**Description:** Store owner scope/company/project on internal MAX file and outbox inserts without changing reads or dispatch.

**Status:** Production verified on runtime `e6f4934859bc`; public smoke and strict messenger item ownership audit passed.

**Safety:**
- Stored channel and warehouse-document owners have priority over names or recipient hints.
- Project-based writes resolve one exact project only inside the employee's active company memberships.
- Duplicate project names across employee companies and company-level actions with multiple memberships fail closed.
- Marketing publication and supplier-KP outbox writers remain unchanged for the separately reviewed M6.7d2a2 slice.
- Outbox reads, status changes and dispatch remain unchanged until M6.7d2b.

**Estimated scope:** S

## Task M6.7d2a2: Persist Supplier And Marketing MAX Ownership

**Description:** Store exact company/project ownership on supplier-KP and marketing-publication outbox messages and on authenticated messenger-channel upsert without changing outbox reads or dispatch.

**Status:** Production verified on runtime `2a9c48f18e54`: supply and marketing publication smokes passed, exact outbox owners were confirmed and the strict item-ownership audit remained clean.

**Safety:**
- Supplier notifications inherit only the stored supply-request company/project and require a recipient from the same company.
- Marketing publication outbox inherits the stored marketing-channel owner and a verified project from that company; mixed companies fail closed.
- Authenticated channel creation resolves one selected-company actor and one exact project; an existing channel cannot be moved across companies by upsert.
- Base schema creation includes nullable owner columns for clean installations; guarded production migration and its constraints remain the source of truth for legacy rows.
- Outbox reads, status changes and dispatch remain unchanged until `M6.7d2b`.

**Estimated scope:** S

## Task M6.7d2b1: Scope Authenticated MAX Outbox Reads

**Description:** Restrict the leadership `/messenger-outbox` list to stored `owner_scope=company` rows from the selected tenant context without changing bot-token dispatch or status callbacks.

**Status:** Production runtime `1cc73b4de724`; protected `smoke:messenger-outbox` and public production smoke passed.

**Safety:**
- A selected company is accepted only when its effective membership role is director or deputy director.
- `Все компании` includes only companies where the effective role is leadership; lower-role memberships are excluded.
- Queries require both `owner_scope='company'` and an allowed stored `company_id`, so terminal legacy rows and foreign-company messages are invisible.
- The public response exposes stored owner scope/company/project for support diagnostics.
- Bot-token `/max/outbox`, dispatch and status updates remain unchanged for the separately reviewed `M6.7d2b2` service-scope slice.
- `smoke:messenger-outbox` verifies selected-company rows, rejects an inaccessible company header and checks leadership-only aggregation in `Все компании`.

**Estimated scope:** S

## Task M6.7e1: Audit Shared Messenger Account Ownership

**Description:** Add a read-only ownership/access report for `messenger_accounts` before changing its authenticated list and upsert routes. A messenger identity belongs to one employee identity and may be visible in several companies only through that employee's active memberships.

**Status:** Production verified: the read-only audit returned `totalRows=0`, `unresolved=0`, `ambiguous=0`, `mismatched=0` and `readyForRuntime=true` without writes.

**Safety:**
- `messenger_accounts` does not receive `company_id`: one MAX/Telegram identity may legitimately serve one user in several companies.
- A user-linked account derives company visibility only from active `user_company_roles`; a staff-linked account derives one company from stored `staff.company_id`.
- Exactly one employee target is required. Missing, dual, inactive, deleted and company-less targets remain unresolved.
- Duplicate `(provider, external_user_id)` or `(provider, chat_id)` identities are ambiguous and block runtime tightening until reviewed.
- The report is a read-only transaction with `writesAttempted=0`; it never returns external user ID, chat ID, display name, phone hash or password data.

**Estimated scope:** S

## Task M6.7e2: Scope Messenger Account Runtime

**Description:** Keep one shared MAX/Telegram identity per employee while restricting authenticated account list and upsert to companies where the current user has an effective leadership role.

**Status:** Production verified on runtime `3944b80d39a4`: protected account smoke, exact cleanup, strict ownership post-audit and production smoke passed.

**Safety:**
- A selected company lists only accounts whose target user has an active membership in that company or whose target staff row stores that company.
- `Все компании` is read-only and includes only companies where the effective role is director or deputy director.
- Create/update requires one selected company and one active employee target from that company.
- Existing `(provider, external_user_id/chat_id/user_id/staff_id)` matches cannot be moved to another employee; overlapping matches fail with `409` for manual review.
- No `company_id` is added to `messenger_accounts`; a user shared by several companies remains one messenger identity and gains visibility only through active memberships.
- Protected smoke uses two unique temporary users, verifies selected/foreign/all-company behavior and reassignment blocking, then deletes every generated row.

**Estimated scope:** S

## Task M6.7d2b2: Scope MAX Worker And Prevent Concurrent Dispatch

**Description:** Keep the platform MAX worker global across companies while allowing it to list, dispatch and update only stored company-owned outbox rows.

**Status:** Production verified: `smoke:max-bot-adapter` passed company-owned worker list/status/dispatch, terminal legacy exclusion/requeue denial and CLI dry-run; cleanup completed.

**Safety:**
- The bot token is a platform service credential, so it may process rows from every tenant but cannot read or mutate ownerless/legacy rows.
- Worker list, operational summary, dispatch and every status transition share one `owner_scope='company' AND company_id IS NOT NULL` predicate.
- Real dispatch selects rows with `FOR UPDATE SKIP LOCKED`, preventing two concurrent workers from sending the same queued row at the same time.
- Dry-run does not lock rows and cannot update status.
- The protected smoke creates an explicit company-owned row and a terminal legacy row, proves legacy exclusion/requeue denial, verifies allowed status transitions and cleans both rows.

**Estimated scope:** S

## Task M6.8a1: Audit Legacy Audit Log Ownership

**Description:** Produce a read-only ownership report for `audit_log` before adding tenant columns or changing `/audit-log` runtime behavior.

**Status:** Production read-only audit completed: `910/1037` rows verified (`800` platform, `110` company `1`), `127` unresolved deleted-parent/history rows, no ambiguous or mismatched owners. No rows were changed.

**Safety:**
- The report opens a read-only database transaction and always returns `writesAttempted=0`.
- Exact stored project/entity ownership wins; duplicate project names, missing parents and conflicting evidence remain review rows.
- One active actor company may be used only as a company-level fallback. Multiple memberships are never guessed.
- Login, logout, password-reset and 2FA events are explicit platform scope instead of being copied into every company.
- Output contains only record/entity IDs, ownership status and reason; descriptions, user names, IP addresses and error text are not read.
- `/audit-log`, `log_audit` writers, table schema and production data remain unchanged until the production report is clean and reviewed.

**Estimated scope:** S

## Task M6.8a1b: Stabilize Audit Diagnostics And Smoke Cleanup

**Description:** Stop platform CRM smoke from deleting test parents while leaving their ordinary audit history orphaned, and make the read-only report identify the complete review set with stable counts and SHA.

**Status:** Released. The stable production review set was used unchanged by the guarded ownership migration.

**Safety:**
- Smoke cleanup deletes only rows whose project, actor or description contains the unique `CODEX PLATFORM CRM SMOKE <run id>` prefix from the current run.
- Existing `127` unresolved rows are not deleted, updated or automatically assigned.
- The report adds aggregate reason/entity counts, ID range and SHA-256 over every review row while continuing to omit descriptions, actor names and IP addresses.
- `invite_code` ownership uses its stored company/project columns; deleted invitations remain unresolved.

**Estimated scope:** XS

## Task M6.8a2: Guard Audit Log Ownership Migration

**Description:** Add nullable stored ownership to `audit_log` without changing runtime reads/writes yet. Migrate exact company/platform rows automatically and preserve only the explicitly reviewed deleted-parent set as `legacy`.

**Status:** Production complete. The guarded apply updated `1037/1037` rows with no conflicts: `110` company, `800` platform and `127` explicitly reviewed legacy rows. Post-audit reports `readyForStrictRuntime=true`, zero legacy-ownerless rows and zero unresolved/ambiguous/mismatched rows.

**Safety:**
- Dry-run is the default, opens a read-only transaction and never changes schema or rows.
- `--legacy-review-sha` must exactly match the SHA of every current non-verified row from `audit:audit-log-ownership`; a changed row, parent or classification aborts the plan.
- Only `unresolved` history may enter `legacy`; ambiguous and mismatched ownership always blocks apply even with a matching review SHA.
- Apply additionally requires `APPLY_AUDIT_LOG_OWNERSHIP`, exact ready count and exact full migration-plan SHA from the immediately preceding dry-run.
- The apply path locks `audit_log`, re-runs ownership inside a serializable transaction, updates only completely ownerless rows and rolls back on count/SHA drift, write conflict or failed post-check.
- `legacy` cannot carry company/project IDs; platform rows cannot carry tenant IDs; company rows require a company ID.
- `/audit-log` and `log_audit` remained unchanged during migration; runtime tenant enforcement is the separate `M6.8a3` slice.

**Estimated scope:** S

## Task M6.8a3: Persist And Enforce Audit Runtime Ownership

**Description:** Make every new audit row store an explicit owner scope and restrict the company activity journal to stored company-owned rows visible through the selected company context.

**Status:** Pushed in `e83bf30c`. Production deploy, protected activity-log smoke and post-deploy strict ownership audit remain pending.

**Safety:**
- The central writer resolves ownership only from an exact project, supported stored entity parent or active actor membership. Platform identity actions remain `platform`.
- If ownership evidence is missing, conflicting or ambiguous, the event is preserved as terminal `legacy`; it is never guessed into a company and never appears in `/audit-log`.
- Direct UI audit writes ignore client actor identity, require one selected company and store the server-resolved effective actor and company. A supplied project must exist exactly in that company.
- `/audit-log` always requires `owner_scope='company'` and a stored `company_id`; selected-company and `Все компании` reads include only companies where the effective membership role is director, deputy director or accountant.
- The existing search/date/action filters remain server-side and are applied after the owner boundary.

**Estimated scope:** S

## Task M6.8b1: Audit Legacy API Error Ownership

**Description:** Produce a read-only ownership report for `api_errors` before adding tenant columns or changing middleware, `/client-errors` or `/system-status`.

**Status:** Production report completed: `76/94` rows resolve to company `1`; `18` inactive/missing actor rows require explicit legacy review; ambiguous and mismatched are zero. `writesAttempted=0`.

**Safety:**
- The report opens a read-only transaction and always returns `writesAttempted=0`.
- One active company membership may classify an authenticated company actor; multiple memberships remain ambiguous and are never guessed.
- Verified platform staff roles are platform scope. Client-account roles remain unresolved until an explicit account-level owner model exists; they are not promoted into global platform scope.
- Anonymous, missing and inactive actors remain review rows for a later guarded legacy decision.
- The report does not read or output path, error message or user name. It returns only row IDs, ownership status/reason and aggregate method/count diagnostics.
- Table schema, middleware writers, `/client-errors`, `/system-status` and production rows remain unchanged in this slice.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.api_error_ownership.test_ownership_report`
- [x] `npm run audit:api-error-ownership` on production.

**Estimated scope:** S

## Task M6.8b2: Guard API Error Ownership Migration

**Description:** Add nullable stored ownership to `api_errors` without changing middleware, `/client-errors` or `/system-status`. Migrate verified company rows and preserve only the exact reviewed missing/inactive actor set as terminal `legacy`.

**Status:** Complete in production. All `94` rows migrated into `76 company + 18 explicit legacy`; strict post-audit and public smoke passed on runtime `a1e9541429ef`.

**Safety:**
- Dry-run is the default, opens a read-only transaction and never changes schema or rows.
- The `18` unresolved rows enter legacy only when `--legacy-review-sha` exactly matches production review SHA `9d0cdecb7ab563774626510d67f9a256ab22e2aedc83e7dc64bae09d57a5c7b7`.
- Ambiguous and mismatched rows block apply and can never be hidden as legacy.
- Apply requires `APPLY_API_ERROR_OWNERSHIP`, exact ready count and exact migration-plan SHA from the immediately preceding dry-run.
- Apply locks `api_errors`, re-runs classification in a serializable transaction, updates only ownerless rows and rolls back on drift, conflict or failed strict post-check.
- Runtime writers and `/system-status` remained unchanged until the guarded production migration completed.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.api_error_ownership.test_ownership_report backend.features.api_error_ownership.test_migration`
- [x] Production guarded dry-run, apply and strict post-audit.

**Estimated scope:** S

## Task M6.8b3: Enforce API Error Runtime Ownership

**Description:** Persist exact stored owner on middleware and `/client-errors` writes, then restrict every `api_errors` count and row returned by `/system-status` to the selected authorized scope.

**Status:** Complete in production on runtime `f1842f19`. Nginx proxy, protected ownership smoke, strict migration audit and full production smoke pass.

**Safety:**
- One shared runtime writer stores all owner columns; new rows never remain ownerless and never enter `legacy`.
- Request identity is resolved from either a verified Bearer token or an active server-side cookie session; raw browser identity data is never trusted.
- Authenticated company errors use only the server-validated selected-company context. Missing, platform or ambiguous request context fails closed to platform scope instead of guessing a company.
- Company directors and deputies read only `owner_scope='company'` rows from leadership memberships allowed by the selected company context.
- `system_owner` reads only `owner_scope='platform'`; terminal legacy history is excluded from runtime responses.
- All count and list queries share the same parameterized owner predicate before the time window is applied.
- The protected smoke creates one uniquely marked client error, checks selected-company/all-companies/foreign-company behavior and deletes only its exact smoke row.

**Verification:**
- [x] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m unittest backend.features.api_error_ownership.test_ownership_report backend.features.api_error_ownership.test_migration backend.features.api_error_ownership.test_runtime`
- [x] Python compilation and `git diff --check`.
- [x] Full backend suite and production build.
- [x] Production `npm run smoke:api-error-ownership`, strict migration audit and `npm run smoke:prod`.

**Estimated scope:** S

## Task U1: Show Clear Expired-Session State

**Description:** When a stored token or cookie session is no longer valid, authenticated pages currently render with empty and zeroed data, which users read as total data loss. Intercept authentication failures centrally in the authenticated fetch layer (`installAuthFetch` in `src/api.js`), set an "expired" flag once, and show a blocking plain-language notice with a re-login action. Keep locally stored drafts and the selected-company context untouched. Do not trigger on public-site, login, or register routes, and guard against repeated notices from parallel failed requests.

**Status:** Complete. Found already implemented during the 2026-07-27 review: `expireFrontendSession` in `src/api.js` clears only auth credentials, sets `authExpiredNotice` behind a single-flight guard and reloads to the login screen, where `useAppShellState.js` shows "Сессия истекла, войдите снова". Company-context storage keys are untouched. The review added the previously missing jest test for the double-401 expiry path (`src/api.test.js`).

**Safety:**
- Frontend-only slice; no backend contract changes.
- Both Bearer and cookie sessions keep working; compatible with the Task 5 cookie-first direction.
- A single-flight guard turns any number of parallel `401` responses into one notice.
- No automatic data clearing and no logout side effects beyond showing the notice.

**Verification:**
- [x] Jest test: a `401` on an authenticated route sets the expired state exactly once; public routes stay untouched.
- [x] `CI=true npm test -- --watchAll=false` passes (`src/api.test.js`: 9 tests).
- [ ] Manual smoke: expire the token, open the dashboard, see the notice, re-login and see data return.

**Dependencies:** None.

**Files likely touched:**
- `src/api.js`
- `src/features/app-shell/` shell state
- New test file.

**Estimated scope:** S

## Task U2: Warn On Unparseable Numbers In Estimate Import

**Description:** `toNum()` silently coerces unparseable numeric strings to `0`, so a broken quantity cell imports as zero without a trace. During estimate import, detect source cells whose raw value is non-empty but yields no finite number, and emit warning rows into the existing import validation banner with row and section context. Warning-only: stored values, import flow, and `toNum()` itself stay unchanged.

**Status:** Complete (2026-07-27). Implemented in the deterministic quality engine rather than a separate import-only utility: `estimateUnreadableQuantityText` in `src/utils/estimateReviewUtils.js` upgrades the zero-quantity branch of `estimateQualityRows` to a critical `Нечитаемое количество` row that quotes the original cell text (working value, raw item value and `rawQuantity` are all inspected). The warning therefore appears in the import banner, on every later open of the estimate and in quality review tasks. Import is never blocked and `toNum()` is untouched.

**Safety:**
- `src/utils/measureUtils.js` is not modified; 21 sections depend on its exact behavior.
- Detection never blocks the import; a recovered quantity (non-zero) produces no warning.

**Verification:**
- [x] Unit tests: Russian decimal formats pass silently; non-numeric text yields a warning; empty values stay silent (`src/utils/estimateReviewUtils.test.js`, 6 tests).
- [x] `CI=true npm test -- --watchAll=false` (62 suites, 254 tests) and `npm run build` pass.

**Dependencies:** None.

**Files likely touched:**
- Estimate import validation utilities and `EstimateImportValidationBanner`
- New tests.

**Estimated scope:** S

## Task 13.1: Extract Next Route Groups From Backend Main

**Description:** After Task 13 proves the extraction pattern on the audit/client-error group, continue moving route groups out of `backend/main.py` into `backend/features/<domain>/` one domain per slice, smallest and lowest-risk first. Each slice keeps endpoint paths, auth behavior, and response shapes identical and follows the existing `routes.py`/`service.py` convention. Reality note 2026-07-27: the originally guessed candidates weather/notifications have no backend routes (frontend-only); pick slices from the real route inventory (`grep '@app\.' backend/main.py`).

**Status:** In progress. Released slices:
- 2026-07-27 (runtime `6549357`): `/online` presence pair → `backend/features/online_presence/`, `/document-versions` read pair → `backend/features/document_versions/` (write helper `save_doc_version` stays with its callers in `main.py`).
- 2026-07-28 (runtime `4917758`): `/expenses` pair → `backend/features/expenses/`, demo-request trio → `backend/features/demo_requests/` (platform audit imported from `platform_admin`), `/company-requisites` pair → `backend/features/company_requisites/` (selected-company checks preserved).

- 2026-07-28 (runtime `aabd8f6`): accountable payments/expenses quartet → `backend/features/accountable_payments/` (the unreachable duplicate return with an undefined name was dropped during the move — pyflakes now reports zero undefined names backend-wide), `/project-chat` pair → `backend/features/project_chat/` (access helper injected).
- 2026-07-28 (runtime `d206669`): master-profile trio → `backend/features/master_profiles/` (its pydantic model moved along — sole user), supplier invoice template pair → `backend/features/supplier_invoice_templates/` (recognition helpers and `log_audit` injected; registration placed in the grouped-registrations zone because `log_audit` is defined below the old route location).
- 2026-07-28 (runtime `a922759`): timesheet trio → `backend/features/timesheet/` (model moved along, audit logging injected), salary payments trio → `backend/features/salary_payments/`.
- 2026-07-28 (runtime `a0d3565`): checklist item trio → `backend/features/checklist_items/` (access helpers injected), personal-data consent trio → `backend/features/pd_consents/` (model moved along, self-signing rule preserved). Deliberately skipped for now: `/room-works` (deep in the work-journal + AI-control web — wait for M6.6f), `/telegram` webhooks (belong to the own-expenses cluster, extract together later).

Slices 14-17 released 2026-07-28 (runtimes `2fb525c`, `7ad4e86`, `520003c`): brigade payments trio → `backend/features/brigade_access/payment_routes.py` (act-scan gate, overpayment ceiling and project-payment mirror/reversal covered by six tests), supply request template trio → `backend/features/supply_request_templates/`, material alias trio → `backend/features/material_aliases/` (model + helpers moved along), pricelist item trio → `backend/features/pricelist_items/` (model moved along). Also deliberately skipped: `/piecework` (work-journal web, wait like room-works).

All verified the same way: full backend suite green (827 tests), deploy smoke OK, every moved route answers with an API code through nginx, zero new tracebacks. `main.py` is down to `30,367` lines with `263` routes remaining. Slices 18-20 released 2026-07-28 (runtime `423e65e`): company document trio → `backend/features/company_documents/`, project stage quartet → `backend/features/project_stages/`, project checklist trio → `backend/features/project_checklists/` (cascade delete of items preserved). `main.py` is down to `30,292` lines with `253` routes remaining; suite `832` tests.

Slices 21-23 released 2026-07-28 (runtimes `50addc0`, `23ade54`): contracts trio → `backend/features/contracts/` (worker self-scope, soft-delete, model moved), supply history trio → `backend/features/supply_history/` (role visibility branches and package checks preserved, model moved), project payments trio → `backend/features/project_payment_access/routes.py` (duplicate guard and idempotent storno covered by tests). Deferred like the journal web: `/cable-journal` and `/material-inspection` both carry AI-suggest endpoints — extract after M6.6f; `/interim-acts` (five money routes) queued as its own slice. `main.py` is down to `30021` lines with `244` routes remaining; suite `844` tests.

Slice 24 released 2026-07-28 (runtime `92b70c3`): the five interim-act routes → `backend/features/interim_acts/` (model moved; confirmed-work ceilings, exact ЖПР binding, daily-act protections, project-payment mirror and audit logging covered by seven tests; the daily-act sync helpers stay in `main.py` with their work-journal callers). `main.py` is below the 30k mark: `29739` lines, `239` routes; suite `851` tests. The test-exit-code gate caught bad test stubs twice more before commit (same falsy-empty-list trap — fixed for good).

Slices 25-28 released 2026-07-28 (runtimes `d6ef789`, `9f83cfd`): prescriptions quartet → `backend/features/prescriptions/` (customer identity stamping, worker review-only rule), supervisor acts quartet → `backend/features/supervisor_acts/`, inspection orders quartet → `backend/features/inspection_orders/`, brigade acts pair → `backend/features/brigade_access/act_routes.py` (acted-amount ceiling). All verified on stable prod after an initial transient 502 snapshot taken during the deploy restart window — lesson: verify routes only after the deploy log says finished. `main.py`: `29483` lines, `225` routes; suite `864` tests.

Slice 29 released 2026-07-28 (runtime `4f919ab`): the deferred own-expenses cluster is closed — the quartet plus both Telegram bot webhooks → `backend/features/own_expenses/` with their entire helper family as closures (employee-by-telegram resolution, warehouse-intent guard, invoice payload normalization, finance-expense mirror). Shared services injected; module generated by scripted verbatim move with whole-word renames. Webhooks verified by response code only (405 on GET), no live POSTs. `main.py`: `29014` lines, `219` routes; suite `872` tests.

Slices 30-33 released 2026-07-28 (runtimes `9498f2d`, `27e7390`): expense reports quartet → `backend/features/expense_reports/` (idempotent soft-cancel), invite codes quartet incl. the public code-info endpoint → `backend/features/invite_codes/`, clients quartet → `backend/features/clients/` (model moved, worker price hiding), crm-leads quartet → `backend/features/crm/lead_routes.py` (company-scoped read + create-owner resolution). `main.py`: `28735` lines, `203` routes; suite `882` tests.

Slice 34 released 2026-07-28 (runtime `04f4cf1`): the five brigade contract item routes → `backend/features/brigade_access/item_routes.py` via scripted verbatim move (done-quantity clamping, worker price hiding, contract total recalculation preserved; six tests). The brigade_access family is now complete: contracts scope service, payments, acts and items all live together. `main.py`: `28486` lines, `198` routes; suite `888` tests.

Slice 35 released 2026-07-28 (runtime `d1080b5`): the materials quartet → `backend/features/materials/` (role visibility branches, stock/price hiding, object-stock-only-via-documents rule, disabled delete; eight tests). Plus the series' only deliberate behavior fix, in its own commit: material creation used to write a mislabeled interim_act audit row with an empty description (copy-paste bug) — now logs entity_type material with name/quantity/unit. `main.py`: `28342` lines, `194` routes; suite `896` tests.

Slice 36 released 2026-07-28 (runtime `e17bd8f`): the projects quartet — the first core family — → `backend/features/projects/` (model moved; company-scoped visibility, budget/warranty hiding, archive/close prohibition, disabled delete; five tests). Process note: the pyflakes gate caught a registration placed above log_audit's definition before it could ship — registrations that need late-file helpers always go to the grouped zone. `main.py`: `28191` lines, `190` routes; suite `902` tests.

Slice 37 released 2026-07-28 (runtime `6acd98f`): the measurement domain — rooms quartet plus room-windows and room-doors (12 routes) → `backend/features/rooms/` (model moved; cascade child deletion and the injected AI recalc hook unchanged; six tests). `main.py`: `27990` lines, `178` routes; suite `908` tests.

Slices 38-39 released 2026-07-28 (runtimes `910928d`, `72d9fb8`): supplier directory family (7 routes: dedup-aware create, user/duplicate linking, reference-guarded delete, requisites) → `backend/features/supplier_access/directory_routes.py`; staff family (7 routes: column maps, sanitizer, access provisioning, fire-with-deactivation + session revocation via auth module) → `backend/features/staff/`. Shared alias/scope helpers stay injected. Remaining-block size analysis recorded in chat: ~3-4k lines freely extractable (parse-smeta 910, brigade contracts, warranty, pricelists, offers, tools), ~12-13k locked behind M6.6f/M7l, init_db ~2.7k behind Task 14. `main.py`: `27122` lines, `164` routes; suite `921` tests.

Slices 40-42 released 2026-07-28 (runtimes `d4ad04e`, `f6b1db1`, `07d2283`): POST /parse-smeta — the monolith's largest single route (~920 lines, fully self-contained) → `backend/features/smeta_parser/` (the trailing worker-estimate sanitize helpers stayed in main.py with their estimate callers); warranty defects quartet → `backend/features/warranty_defects/`; supplier documents trio → `backend/features/supplier_documents/` (backfill/dedupe admin ops stay with the dedup domain). All verified: deploy smokes OK, routes answer API codes, zero tracebacks; suite `933` tests.

Slice 43 released by owner request during the pause (runtime `61e8758`): supplier catalog quartet → `backend/features/supplier_catalog/` (per-supplier self-scope; five tests; verified on prod, zero tracebacks). `main.py`: `26023` lines, `152` routes; suite `938` tests.

Slice 44 released by owner request (runtime `f6f4926`): the six supplier-offer routes — heaviest remaining free family (~1,100 lines: list, history, create, update, create-invoice, ship) → `backend/features/supplier_offers/` with the model; ~30 shared helpers injected under original names, registration in the late grouped zone. Verified on prod, zero tracebacks; suite `940` tests. The supplier family is now fully modular (directory, documents, catalog, offers). `main.py`: `24952` lines, `146` routes.

**CAMPAIGN PAUSED 2026-07-28 by owner decision.** Final state: `main.py` `26098` lines / `156` routes (started 2026-07-26 at 31,625 / ~309); 44 domains extracted in 42 slices; suite 755 → 933 tests. To resume: pick candidates from the remaining-block analysis above (free: brigade-contracts, supplier-offers, supplier-catalog, pricelists; locked behind M6.6f/M7l: warehouse, supply core, journals, AI; behind Task 14: init_db). The per-slice conveyor is fully described by the release notes above: scripted verbatim move → exit-code-gated tests → push → CI-success-gated deploy → route verification through nginx → docs.

Process note 2026-07-28: one commit briefly landed with two red tests because the old commit chain gated on grep output instead of the unittest exit code — production was never exposed (the deploy gate requires an explicit CI success), tests were fixed in the next commit, and every commit chain now gates on the exit code. Lessons recorded: do not verify public write endpoints with a real POST (one accidental empty demo request was created and surgically deleted on 2026-07-28) — check an unsupported method instead; after each slice curl the route through the site and treat an `<!doctype` body as a missing nginx proxy entry (a full audit on 2026-07-28 found and fixed seven historically unproxied routes — see ONBOARDING).

**Safety:**
- One domain per slice; no route path or response format changes.
- `py_compile`, the full backend suite, and the route-duplication check run after every slice.
- Releases go through the existing atomic deploy and production smoke.

**Verification:**
- [ ] Full backend unittest suite stays green after each slice.
- [ ] Route inventory diff shows only moved definitions, no added or removed endpoints.
- [ ] `backend/main.py` line count decreases with each slice.

**Dependencies:** Task 13 establishes the pattern.

**Files likely touched:**
- `backend/main.py`
- New `backend/features/<domain>/` packages with tests.

**Estimated scope:** M overall; S per slice.

## Task E1-E2: Estimate Revision Comparison And Activation Guard

**Status:** Implemented locally, pending deployment verification.

- [x] Individual comparison and saved reconciliation documents contain one compact table with only changed, added or removed positions.
- [x] Added one project summary across the previous and active revision of every customer estimate package.
- [x] Empty zero-value technical rows are hidden; a real quantity/price change remains visible even when its monetary impact is zero.
- [x] Existing-draft activation loads full old/new rows and saves a server reconciliation before AI comparison.
- [x] Direct Excel import saves the reconciliation first and loads the full old revision before background comparison.
- [x] Focused Jest coverage passes for pair selection, payload aggregation, compact documents, activation and import ordering.

**Known next risks:** brigade assignment rows do not yet store their source `estimate_id`; imported row keys change between revisions; active-estimate material control still has project-name-only queries that must be made company/project scoped before multi-company pilots.

## Task A0: Tenant-Scope Director Agent Read Tools

**Description:** Keep the existing director assistant read-only while passing the server-resolved selected-company list into every tool. Projects, main/object warehouse, supply requests/deliveries/claims, estimates, finances, staff memberships and AI tasks must fail closed when no company is selected and must never fall back to a global query.

**Status:** Complete in production on 2026-08-05. Runtime `3c0f09fa6396` passed health/public smoke, authenticated protected reads and aggregate-company denial checks. Focused regression tests and the manual no-write dry-run cover two-company tool isolation and the empty-context no-query rule.

**Safety:**
- The model still has no write tools and no direct database access.
- Empty or malformed company IDs produce empty payloads and execute no business queries.
- Supply claims are scoped through their stored request or delivery parent because the legacy claim table has no direct `company_id`.
- Staff role totals come from active `user_company_roles` memberships, not the legacy single `users.company_id` field.
- The route passes the same normalized company list to every registered tool, so future tools cannot rely on a special-case dispatch branch.

**Verification:**
- [x] Regression tests first failed against the unscoped implementation, then passed after the fix (`3` tests).
- [x] Related company-context, AI, supply and warehouse suites pass (`80` tests).
- [x] Full backend discovery passes (`1020` tests) and `backend/main.py` compiles.
- [x] Full frontend Jest command exits successfully and the production build compiles.
- [x] Manual no-write dry-run inspected every generated query with company `4`; empty scope executed `0` queries.
- [x] Production authentication and protected read-only smoke pass; aggregate-company access is denied. Combined with focused two-company tool tests and the empty-context no-query dry-run, no unscoped director-agent read path remains.

**Estimated scope:** S

## Task A1.1-A1.2: Tenant-Scoped Agent Job Kernel

**Description:** Add the durable storage and enqueue boundary for future agent
work without starting a worker or calling an AI model. A job belongs to exactly
one company and optionally one project; repeated requests in different projects
cannot collide.

**Status:** Complete in production on 2026-08-05. The read-only schema audit
reported the complete empty schema, zero invalid rows and
`readyForWorker=true`.

**Safety:**
- `agent_jobs` is separate from MAX delivery outbox and existing business
  tables; this slice does not execute jobs or mutate estimates, warehouse,
  supply, assignments or accounting records.
- Company and project ownership are mandatory and validated before insert.
  Human authors require an active matching `user_company_roles` membership.
- Idempotency is unique per company, project scope, job type and key, so a
  repeated request returns its existing job without resetting attempts/status.
- Payload is JSON-only, limited to 64 KiB and rejects nested password, token,
  secret, cookie, authorization, API-key and private-key fields.
- Queue fields already reserve bounded attempts, run time, lease, heartbeat,
  result, error and correlation data for the next worker slice.

**Verification:**
- [x] Regression tests failed before project-scoped idempotency and actor
  membership validation, then passed after implementation (`15` focused tests).
- [x] Full backend discovery passes (`1035` tests).
- [x] Full frontend Jest passes (`289` tests) and the production build compiles.
- [x] Independent review finding for cross-project idempotency collision is
  fixed; sensitive payload rejection is covered by regression tests.
- [x] The new `agent_jobs` tenant-registry entry passes registry rules; the
  global `audit:m6` remains red only for four pre-existing `M7l` stage entries
  (`tools`, `tool_history`, `inventory`, `inventory_items`).
- [x] Production `npm run audit:agent-jobs` reported `tableExists=true`, empty
  `missingColumns`/`missingIndexes`/`missingConstraints`, `total=0`, zero
  invalid owner/status rows and `readyForWorker=true`.

**Estimated scope:** S

## Task A2.1: Fail-Closed Agent Execution Contract

**Description:** Define the first machine-readable execution policy for
`director.daily_brief` before any runner can call a model. The policy must allow
only existing tenant-scoped read tools, keep tenant selection server-side,
restrict model data and carry fixed execution/cost limits.

**Status:** Complete locally on 2026-08-05. No runner, model call, route or
business-table mutation is part of this step.

**Safety:**
- Unknown job types and tools fail closed.
- SQL, direct database access and write tools are not model capabilities.
- Model payload fields are allowlisted, sensitive keys are rejected and the
  serialized input is capped at 32 KiB.
- Runtime callers cannot enlarge the contract limits.
- Execution is bound to one positive owner company from the claimed queue row;
  aggregate-company mode is not representable in the prepared request.
- Every tool result has an explicit field/type/count schema. Unknown fields,
  including the financial tool's internal `companyId`, are removed before the
  model boundary; incomplete records fail closed.
- The existing tool registry and nested metadata are immutable. Registry tests
  bind every public tool name to its expected function, and the shared query
  adapter allows one `SELECT` in a PostgreSQL read-only session.

**Verification:**
- [x] Contract tests failed before implementation and pass afterwards (`11`).
- [x] Tool policy stays identical to the existing director-agent registry;
  tenant/read-only tests pass (`5`).
- [x] Full backend `1086/1086`, frontend `289/289` and production build pass.
- [x] Manual no-model check accepted one sanitized company-scoped request and
  blocked unknown job, aggregate company, SQL tool and incomplete fact input.
- [x] Independent code/security review found and closed tenant binding,
  mutable registry, raw finance `companyId`, missing result-schema and
  multi-statement SQL risks; final review reported no blockers.

**Specification:** `docs/agent-execution-contract.md`

## Task A2.2: Production Contract Verification

**Status:** Complete on 2026-08-05 for runtime `0d2754bcfe4f`.

**Verification:**
- [x] Atomic frontend/backend deploy completed.
- [x] Public smoke passed every health, site and protected-route boundary check.
- [x] `/health` returned the expected runtime and a healthy database.
- [x] Unauthenticated `/director-agent/tools` returned `401`, not SPA HTML.
- [ ] Authenticated production smoke was not run because `SMOKE_EMAIL` and
  `SMOKE_PASSWORD` were not supplied to the deployment shell.

This gap does not block A2: the step adds no new authenticated route and the
full protected smoke passed on the preceding A1.4 runtime. It must be rerun with
credentials after the next protected API or runner integration.

## Task A3.1: Deterministic Read-Only Director Daily Brief

**Status:** Complete in production on 2026-08-05, runtime `a3ab56bb6f29`.
Permanent worker and bulk scheduling remain disabled.

**Behavior:**
- `director.daily_brief` is now an explicit runner handler beside
  `system.worker_probe`.
- The queue payload contains only an ISO `briefDate`; company scope comes only
  from the claimed row. Project-scoped, aggregate-company and payload-selected
  company requests fail before a business read.
- One company read uses the same immutable seven-tool registry as the HTTP
  director assistant and one rolled-back PostgreSQL read-only transaction.
- The pure aggregator returns six ordered sections: overdue, shortages,
  documents, estimate deviations, payment facts and open/unassigned tasks.
- The result is deterministic, strips internal/unknown fields, caps each
  section at 12 records and stays below the queue's 64 KiB result limit even at
  every tool policy's maximum input size.
- Payment output reports only project budget and net `project_payments` facts;
  it does not infer debt or overspending. Current document/estimate findings
  are explicitly limited to evidence in the existing seven-tool contract.
- A group of companies must fan out into separate company-owned jobs. The
  handler never combines tenants.

**Safety:**
- No model/provider, arbitrary SQL, HTTP route, business-table write, message
  delivery or daemon was added.
- All SQL is server-owned, parameterized and validated as one `SELECT` before
  execution. The read transaction is rolled back on both success and failure.
- HTTP `/director-agent/ask` and the runner now share one read implementation;
  the duplicate block was removed from `backend/main.py`.
- Queue logs still contain metadata only and public job APIs still exclude
  payload/result/worker/lease fields.

**Verification:**
- [x] Service/handler/read-boundary tests were written red before each new
  module or registry connection; focused suite passes (`49` tests).
- [x] Worst-case sanitized input first exceeded 64 KiB, then passed after the
  per-section/text caps were enforced.
- [x] Full backend discovery passes (`1123` tests after the production-import
  regression).
- [x] Full frontend Jest passes (`289` tests) and production build compiles.
- [x] Python compile and `git diff --check` pass.
- [x] Production deploy, readiness audit, protected smoke and one controlled
  test-company brief job completed in Task A3.2.

**A3.2 verification command prepared locally:**
- `SMOKE_EMAIL='<director email>' npm run smoke:director-daily-brief` resolves
  exactly one active leadership membership (or requires `SMOKE_COMPANY_ID`),
  refuses to run alongside an active brief, executes only its own
  max-attempts-one job and deletes the exact queue row in `finally`.
- The smoke reports only company/job metadata and section keys/statuses/counts;
  it does not print the brief body or business values. Focused coverage is
  `55/55`; the final compatibility regression brings full backend coverage to
  `1123/1123`, and the production build passes.
- Production readiness returned `readyForWorker=true`; public and protected
  smoke passed on `a3ab56bb6f29`. The controlled company `1` job returned all
  six sections and cleanup confirmed `persistedAgentJobs=0` with no business
  writes.
- The first backend restart exposed package-only imports that did not work with
  systemd's top-level `uvicorn main:app` launch. Release verification stopped,
  the exact mode was reproduced, a subprocess regression was added and the
  compatibility hotfix restored health before protected or brief verification.

**Specification:** `docs/director-daily-brief.md`

## Task A4.1: Latest Daily Brief In The Director Dashboard

**Status:** Deployed as runtime `7d8c615c09a3` on 2026-08-05. Public smoke
passed; protected director smoke remains pending.

**Behavior:**
- Leadership can read `GET /agent-jobs/director-daily-brief/latest` only for one
  selected company. All-companies and roles outside the leadership allowlist
  fail before the brief query.
- The endpoint selects only the latest successful company-scoped
  `director.daily_brief` row and returns an explicit `{available:false}` when
  none exists.
- A schema-v1 validator rebuilds an allowlisted public projection. Raw queue
  payload/result JSON, correlation, worker identity, lease data and provider
  errors are not exposed.
- The dashboard shows date, critical/warning/info totals, all six section
  counts and at most three bounded subjects per section. Loading, empty,
  selected-company and error states are explicit.

**Safety:**
- This step is read-only. It adds no enqueue button, business-table mutation,
  model/provider call, MAX message, bulk schedule or permanent worker.
- The controlled A3 production smoke deletes its own job, so the production
  dashboard will remain empty until a real persisted brief is deliberately
  scheduled in a later step.

**Verification:**
- [x] Backend query/route and tenant-role tests pass (`35` focused tests).
- [x] Frontend hook/view tests pass (`10` focused tests).
- [x] Production React build compiles and smoke shell syntax passes.
- [x] Mocked Playwright checks pass on desktop and 390 px mobile width with no
  console errors or text overlap.
- [x] Full repository suites pass (`1131` backend tests and `299` frontend
  tests); final correctness, tenant-isolation and field-exposure review passes.
- [x] Production deploy and public endpoint smoke pass on `7d8c615c09a3`.
- [ ] Protected director smoke for the latest-brief endpoint.

**Next:** A4.2.1 implements only the previously selected controlled producer;
scheduling and delivery remain separate decisions.

## Task A4.2.1: Explicit Single-Company Daily Brief Producer

**Status:** Complete in production on runtime `3210bbe905f7` on 2026-08-05.
Not scheduled; permanent worker remains disabled.

**Behavior:**
- `npm run enqueue:director-daily-brief -- --company-id <id> --brief-date
  <YYYY-MM-DD>` performs a read-only plan and rolls back.
- Adding `--apply` enqueues one `director.daily_brief` with the existing queue
  service. The company/date idempotency key returns the existing job on repeat.
- The company must exist and be active. There is no aggregate-company or
  implicit-company mode.

**Safety:**
- The producer uses only server-owned parameterized SQL and the existing
  validated enqueue boundary. Payload is fixed to `briefDate`; the author is
  `system`, project scope is absent and the result exposes only job id/status.
- Dry-run uses a PostgreSQL read-only transaction, attempts zero writes and
  ends in rollback. `--apply` attempts one queue write; it does not call the
  handler or runner.
- No HTTP button, business mutation, scheduler, permanent daemon, model, MAX
  delivery or company fan-out is included.

**Verification:**
- [x] Producer tests were written red before the module existed.
- [x] Focused producer/queue/handler suite passes (`32` tests).
- [x] Full backend discovery passes (`1139` tests).
- [x] Module `--help` works without a database connection; unexpected CLI
  errors expose only their class, not exception text.
- [x] Final diff/security review passes; parameterized SQL, explicit company
  scope, PostgreSQL read-only dry-run and metadata-only errors are confirmed.
- [x] Feature commit `3154f3cf` is pushed to
  `codex/director-brief-producer`.
- [x] Production company `1` dry-run returned `would_enqueue` with
  `writesAttempted=0`; apply created queued job `8`; one runner cycle claimed
  and completed that exact job as `succeeded` in `206 ms`; repeat returned
  `existing` for job `8` with zero writes.

## Task A4.2.2: Exact Agent Job Runner Handoff

**Status:** Complete in production on runtime `ed11051bb8d8` on 2026-08-05.
No scheduler or permanent worker is enabled.

**Behavior:**
- `npm run worker:agent-jobs -- --once --job-id <id>` processes only the
  requested queue row. It never falls back to the next eligible row.
- Exact mode accepts only a positive ID and is rejected unless `--once` is
  present.
- If the row cannot be claimed, the process reports metadata-only
  `not_claimed` and exits with code `2` instead of silently succeeding.

**Safety:**
- The atomic claim requires `queued`, due `run_after`, remaining attempts and
  a job type in the runner's immutable handler registry, with `FOR UPDATE SKIP
  LOCKED` for concurrent workers.
- Exact mode skips global expired-lease recovery, so a targeted run cannot
  mutate or consume a neighboring job or another registered job type.
- No HTTP action, scheduler, daemon, model, MAX delivery or business-table
  mutation is added.

**Verification:**
- [x] Worker and runner tests were written red before implementation.
- [x] Focused agent-job suite passes (`80` tests).
- [x] Full backend discovery passes (`1145` tests).
- [x] Final security and diff review passes: exact ID and every SQL value are
  parameterized, handler allowlist/status/attempt/time guards remain inside the
  atomic claim, logs expose metadata only and ordinary `--once` keeps its
  existing recovery-plus-next-job behavior.
- [x] Runtime `ed11051bb8d8` and the full public production smoke pass.

## Task A4.2.3: Controlled Single-Company Daily Brief Cycle

**Status:** Complete in production on runtime `ed11051bb8d8` on 2026-08-05.
Not scheduled.

**Behavior:**
- `npm run run:director-daily-brief -- --company-id <id> --brief-date
  <YYYY-MM-DD>` is read-only and reports the producer plan.
- Adding `--apply` commits the idempotent producer job and passes only the
  returned `jobId` into exact one-shot runner execution.
- Existing `succeeded` work is returned without rerun. Any other nonqueued or
  unclaimable state returns a nonzero result for operator review.

**Safety:**
- The cycle validates producer company, date and immutable job type before
  runner execution. A mismatched producer result never reaches the runner;
  its dedicated registry contains only `director.daily_brief`.
- A process stop after producer commit leaves a recoverable queued job. There
  is no global recovery or fallback claim in the exact execution step.
- Final stdout is an allowlisted report with `businessWritesAttempted=0`;
  metadata-only runner events use stderr. No schedule, daemon, model, MAX,
  business mutation or multi-company fan-out is added.

**Verification:**
- [x] Cycle and runner-config tests were written red before implementation.
- [x] Focused daily-brief suite passes (`38` tests).
- [x] Focused agent-job suite passes (`81` tests).
- [x] Package command `--help` succeeds without a database connection.
- [x] Full backend discovery passes (`1159` tests).
- [x] Final diff/security review passes: company/date/type and exact processed
  job ID are verified, the dedicated registry exposes one handler, stdout is
  allowlisted and unexpected exception text is suppressed.
- [x] Runtime `ed11051bb8d8` and the full public production smoke pass; no new
  HTTP route required protected smoke.

## Task A4.2.4: One-Company Daily Brief Schedule

**Status:** Complete in production on runtime `2e14a3a2ca3c` on 2026-08-06.

**Behavior:**
- `npm run schedule:director-daily-brief -- --company-id <id>` plans one cycle
  for the current `Europe/Moscow` date and stays read-only.
- Adding `--apply` delegates to the existing controlled producer plus exact
  runner. It does not start the generic worker or process a neighboring job.
- The prepared `systemd` timer targets company `1` once each morning at
  `07:10 Europe/Moscow`; `Persistent=true` performs at most one catch-up run,
  while the company/day idempotency key prevents a duplicate brief.

**Safety:**
- The timezone-aware scheduler rejects a naive clock and verifies the returned
  company, date, immutable job type, dry-run state and zero-business-write
  boundary before emitting an allowlisted report.
- The service is `Type=oneshot`, bounded to ten minutes and hardened with a
  private temporary directory, read-only system paths and no new privileges.
  It has no all-company mode, date override, model or MAX delivery.
- `deploy.sh` intentionally contains no timer install/enable step. A normal
  application deployment therefore cannot activate the schedule.

**Verification:**
- [x] Tests were written red before the scheduler module and unit templates.
- [x] Scheduler/systemd contract tests pass (`13/13`); all daily-brief tests
  pass (`51/51`).
- [x] Full backend discovery passes (`1172/1172`), frontend Jest passes
  (`299/299`) and the production frontend build compiles.
- [x] Module compile, package `--help` and `git diff --check` pass.
- [x] Linux unit verification passed before service start.
- [x] Manual one-shot created company `1` job `9` for Moscow date
  `2026-08-06`; it succeeded in `268 ms` with
  `businessWritesAttempted=0`, and journal output contained operational
  metadata only.
- [x] Runtime `2e14a3a2ca3c` and full public production smoke pass. Protected
  checks were skipped because credentials were not supplied.
- [x] Timer is installed and enabled; `systemctl list-timers` reports the next
  Moscow-morning run. The generic daemon remains disabled.

**Estimated scope:** S

## Task A5.1: Read-Only Director Attention Queue

**Status:** Complete in production on runtime `74344e8692f9` on 2026-08-06.

**Behavior:**
- `GET /agent-jobs/director-daily-brief/latest` keeps the existing validated
  brief and adds one bounded `attentionQueue` projection.
- The queue includes only `critical` and `warning` findings. Critical items
  come first, source order is deterministic, the public list is capped at 12,
  and its count uses the complete brief severity totals even when a section is
  truncated.
- Every row shows priority, category, reason, subject, project, responsible
  state and one next safe review step. The dashboard shows at most six rows on
  desktop and four on mobile before directing the user to the full brief.

**Safety:**
- Reasons, destinations and next steps come only from an immutable server
  policy. Arbitrary `nextAction` or URL-like fields in stored data are ignored;
  an unknown source code receives a fixed manual-review fallback.
- The queue is read-only and adds no button, navigation, enqueue, retry,
  mutation, model request, message delivery, SQL or new database table.
- The existing leadership-role and exact single-company endpoint boundary is
  unchanged. Raw queue payload/result, worker identity and lease data remain
  excluded.

**Verification:**
- [x] Backend projection and query tests were written red before implementation.
- [x] Focused daily-brief tests pass (`58/58`); targeted projection/query tests
  pass (`11/11`).
- [x] Focused frontend hook/panel tests pass (`10/10`).
- [x] Full backend discovery passes (`1179/1179`) and full frontend Jest passes
  (`299/299`).
- [x] Python compile with an isolated cache, `git diff --check` and production
  React build pass.
- [x] Manual Chrome renders from the current component source pass on desktop
  and a 390 px content width. Long subjects wrap, rows do not overlap and the
  block contains no buttons.
- [x] Production deploy and public smoke pass on runtime `74344e8692f9`.
- [x] Protected director smoke passes for one selected company: login and the
  latest daily-brief endpoint return `200`, aggregate-company access is blocked
  with `409`, the shared foreign-company boundary returns `403`, and the
  recursive public-field policy reports no queue payload, worker or lease data.

**Next:** Do not add automatic actions to this completed read-only slice. Any
future resolve/apply flow requires a separate
`preview -> human approval -> apply -> audit` task.

## Task A6.1: Safe Agent Change Dispatch Contract

**Status:** Complete and deployed in production runtime `61187fa63f69`; public
smoke passes. The separate shadow-wiring verification remains tracked in A6.2.

**Behavior:**
- Accept exactly one versioned event shape with explicit company, project,
  source record and immutable source revision.
- The first and only allowlisted route is
  `estimate.version_activated -> director.daily_brief`.
- Build a deterministic company-scoped dispatch plan with a bounded
  idempotency key. The source project remains recorded for traceability while
  the existing daily brief retains its company-level queue scope.

**Safety:**
- Unknown event/source types, aggregate or missing ownership, numeric-like
  strings/floats, invalid revisions, extra fields and invalid business dates
  fail closed.
- A manually constructed event is revalidated before a plan can be built.
- The module has no SQL, queue insert, model/network call, message delivery,
  business mutation or runtime hook. Current imports and estimate activation
  behavior are unchanged.

**Verification:**
- [x] Tests were written red before the contract implementation.
- [x] Focused contract tests pass (`9/9`).
- [x] Full backend discovery passes (`1188/1188`).
- [x] Full frontend Jest passes (`299/299`).
- [x] Python compile with an isolated cache and the production React build
  pass.
- [x] Static safety search finds no database, queue, model, HTTP or process
  execution calls in the new module.
- [x] Deploy the inert contract and run public production smoke.
- [x] Add the separate A6.2 shadow hook after estimate activation; it must
  report the planned dispatch without enqueueing or changing business data.

**Next:** A6.2 was deployed and verified separately as tracked below.

## Task A6.2: Estimate Activation Shadow Wiring

**Status:** Complete and deployed in production runtime `61187fa63f69`; public
smoke and the targeted authenticated manual activation pass. Full protected
smoke remains a separate production-wide check.

**Behavior:**
- Observe all three committed transitions into `Активная`: create an active
  estimate, update a draft into active state, and use the dedicated status
  endpoint.
- Return a bounded `agentDispatchShadow` report. A planned report contains the
  exact company/project/source IDs, target job type and Moscow business date;
  a rejected report contains only a fixed reason code.
- Ignore active-to-active updates, deactivation and draft saves so they do not
  create false activation observations.

**Safety:**
- Observation runs only after the estimate transaction commits. Its own clock,
  validation or logger failure cannot change the completed business action.
- The source revision is calculated from canonical estimate version/sections,
  but source rows, revision, idempotency key, correlation ID and exception text
  are excluded from logs and API output.
- Rejections expose only fixed reason codes. The observer performs no SQL,
  queue insert, runner/model/network call or business mutation and explicitly
  reports zero enqueue/write attempts.

**Verification:**
- [x] Shadow tests were written red before implementation.
- [x] Focused contract/shadow tests pass (`17/17`).
- [x] Import works both from repository root and the production-style
  `backend` working directory.
- [x] Full backend discovery passes (`1196/1196`).
- [x] Full frontend Jest passes (`299/299`).
- [x] Python compile, static side-effect search, `git diff --check` and the
  production React build pass.
- [x] Deploy the stacked A6.1/A6.2 commits and run public smoke.
- [ ] Run the separate production-wide protected smoke for the deployed runtime.
- [x] Manually activate one expendable draft and confirm
  `agentDispatchShadow.state=planned` while no new `agent_jobs` row appears.

Production evidence on 2026-08-06: estimate `84`, company `1`, project `2`
reported `state=planned`, `enqueueAttempted=false`, `writesAttempted=0`; the
`agent_jobs` count remained `2` before and after activation.

**Next:** Keep automatic enqueue disabled. Design A6.3 separately before it may
enqueue exactly one allowlisted job through the existing controlled one-shot
runner.

## Task A6.3.1: Dry-Run-First Change Dispatch Adapter

**Status:** Local implementation complete on branch
`codex/agent-change-dispatch-enqueue`; production deploy and runtime wiring are
not part of this slice.

**Behavior:**
- Revalidate the complete immutable dispatch plan by reconstructing its source
  event and deterministic expected plan before any queue call.
- Default to `apply=False`, return `would_enqueue`, and perform zero queue/write
  attempts.
- With explicit `apply=True`, call the existing idempotent queue service exactly
  once using only the validated company-scoped `director.daily_brief` fields.
- Validate the returned job ID, status, company, queue scope, job type and
  idempotency key before returning bounded metadata.

**Safety:**
- No endpoint, estimate hook, transaction commit, background task, runner,
  model, network call or business-data mutation is added.
- A forged/tampered plan, invalid apply mode, invalid queue dependency or
  mismatched queue result fails closed.
- The source revision and queue idempotency/correlation values remain internal
  and are not returned by the adapter.

**Verification:**
- [x] Tests were written red before implementation.
- [x] Focused package discovery passes (`23/23`).
- [x] Full backend discovery passes (`1202/1202`).
- [x] Imports pass from the repository root and production-style `backend`
  working directory.
- [x] Static usage search confirms the adapter is not imported by runtime code.
- [x] `git diff --check` passes.
- [ ] Deploy or connect the adapter to runtime.

**Next:** A6.3.2 must separately design a disabled-by-default post-commit
handoff. Dispatch failure must never roll back or hide a completed estimate
activation, and runner execution remains disabled.

## Task A6.3.2: Disabled Post-Commit Activation Handoff

**Status:** Complete. Runtime `053bb218987d` is deployed with both activation
controls absent. Public smoke and one manual shadow activation check pass.

**Behavior:**
- Route all three committed activation paths through one handoff after the
  estimate transaction has committed.
- Preserve the exact A6.2 `agentDispatchShadow` response and avoid opening a
  queue connection unless both the exact apply flag and current company ID
  allowlist permit dispatch.
- For an allowed company, rebuild and revalidate the exact source-revision
  plan, then use a separate short transaction for one idempotent queue attempt.
- Return a bounded `agentDispatch` report only when enqueue mode was actually
  entered.

**Safety:**
- `AGENT_CHANGE_DISPATCH_APPLY` must equal the exact string `true`; aliases,
  whitespace and case variants fail closed.
- `AGENT_CHANGE_DISPATCH_COMPANY_IDS` must be a strict comma-separated list of
  canonical positive integer IDs. Empty, aggregate, spaced, zero, negative or
  partially invalid lists disable all companies.
- Queue connection/validation/commit failure rolls back and closes only the
  handoff transaction, returns fixed `dispatch_unavailable`, and never raises
  into the already completed estimate action.
- Exception text, credentials, source revision and queue idempotency/correlation
  values are not exposed. Runner, daemon, model and business writes remain off.

**Verification:**
- [x] Handoff tests were written red before implementation.
- [x] Focused package discovery passes (`30/30`).
- [x] Full backend discovery passes (`1209/1209`).
- [x] Full frontend Jest passes (`299/299`).
- [x] Compile and production React build pass.
- [x] Both import modes pass.
- [x] Static configuration search finds no activation flags outside code/tests.
- [x] Deploy with both controls absent and repeat one shadow activation check.
- [x] Manual activation of test estimate `85` returned `mode=shadow`,
  `state=planned`, `enqueueAttempted=false` and `writesAttempted=0`; the
  `agent_jobs` row count remained `2` and readiness stayed green.

**Next:** The separately approved company `1` enqueue canary is recorded in
A6.3.3. Exact runner execution remains another later step.

## Task A6.3.3: Company 1 Enqueue Canary

**Status:** Complete. The runtime controls were enabled only for the short
manual test window and were removed immediately after verification.

**Verification:**
- [x] Baseline readiness was green with `2` valid persisted jobs.
- [x] Activating empty test estimate `86` created exactly one company `1`
  `director.daily_brief` job `10` with status `queued`.
- [x] The bounded runtime report returned `mode=enqueue`, `state=enqueued`,
  `enqueueAttempted=true`, `writesAttempted=1` and `committed=true`.
- [x] Readiness remained green with `3` total jobs and zero invalid owner,
  status or lease rows.
- [x] The canary drop-in was disabled, systemd reloaded, backend restarted and
  the runtime confirmed no `AGENT_CHANGE_DISPATCH_*` environment values.
- [x] The generic runner, model and business mutations were not started.

**Next:** Execute only exact queued job `10` in a separately approved
`--once --job-id 10` canary, then verify its bounded read-only result. Do not
start the generic runner or daemon.

## Task E3.1: Read-Only Brigade Assignment Lineage Audit

**Status:** Local implementation complete on 2026-08-06. No database schema,
HTTP route or runtime writer is changed in this slice.

**Behavior:**

- `npm run audit:brigade-lineage` opens a read-only transaction, inspects only
  allowlisted schema/data fields, rolls back and closes the connection.
- Pre-migration keys are reported as unproven legacy data. They are never
  promoted from names, codes or fuzzy matches.
- The proposed complete contract verifies contract/project ownership, exact
  estimate version, zero-based row coordinates, canonical full-snapshot hash
  and one exact item key.
- Output is bounded to contract-item IDs and fixed reason codes; descriptions,
  prices and snapshot content are not emitted.
- The report explicitly leaves constraint and writer audits false, so this
  slice cannot claim strict runtime readiness.

**Verification:**

- [x] Focused lineage tests pass (`23/23`), including cross-company,
  pre-migration, hash tampering, ambiguous-key and compatibility-key cases.
- [x] Full backend discovery passes (`1232/1232`).
- [x] Full frontend Jest passes (`299/299`).
- [x] Python compile, `git diff --check`, package-script lookup and the
  production React build pass.
- [x] The local real-PostgreSQL run detected the intentionally older local
  schema as `base_incomplete`, returned `lineageDataReady=false`, reported
  `writesAttempted=0` and confirmed `rolledBack=true`.
- [x] Production pre-migration audit completed on 2026-08-06 with
  `schemaState=pre_migration`, `151` total rows, `151` unproven legacy rows,
  zero invalid rows, `writesAttempted=0` and `rolledBack=true`. The bounded
  preview was truncated at `100` IDs as designed.

**Next:** Design E3.2 as an additive, nullable and rollback-friendly migration.
Do not change assignment writers or enable constraints in the same release.

**Review gates before E3.2:**

- Load and hash each distinct estimate-version snapshot once instead of
  repeating its full `sections_json` for every assignment row.
- Treat excessively nested snapshot JSON as an invalid snapshot with a bounded
  reason code instead of allowing `RecursionError` to abort the complete audit.

## Task E3.2: Nullable Brigade Assignment Lineage Schema

**Status:** Complete in production on 2026-08-06, runtime `857b0b622de9`.
Assignment writers and strict runtime are not enabled in this slice.

**Migration contract:**

- `npm run migrate:brigade-lineage -- --dry-run` is read-only, rolled back and
  emits a deterministic `readyCount + planSha256` guard.
- Apply requires the explicit confirmation token and the exact two guards from
  the immediately preceding production dry-run.
- `estimate_versions.sections_sha256` is added in its own short, idempotent
  phase. The assignment phase then locks only `brigade_contract_items`,
  recomputes the plan before DDL, and updates only the guarded IDs whose full
  lineage tuple is still NULL.
- All six columns remain nullable. E3.2 adds no FK, CHECK, NOT NULL or index and
  does not infer snapshot coordinates or backfill snapshot hashes.
- `source_type='legacy'` is explicit for old rows. A temporary database default
  protects unchanged writers until E3.3; E3.4 must remove it before strict
  enforcement.
- Missing tables, incompatible types/lengths/nullability/defaults, partial
  coordinates, plan drift, update conflicts and post-check failures all stop
  the migration. A committed snapshot-column phase plus a failed assignment
  phase is reported as retry-safe partial schema, never as a full rollback.

**Verification:**

- [x] Production E3.1 baseline contains exactly `151` structurally safe legacy
  candidates and zero invalid rows.
- [x] Audit hardening tests pass (`27/27`): each distinct snapshot is loaded and
  hashed once, pathological nesting fails closed, and both queries share one
  repeatable-read snapshot.
- [x] Guarded migration tests pass (`25/25`); combined lineage tests pass
  (`52/52`). Temporary real-PostgreSQL checks proved first apply, terminal
  report correctness, idempotent repeat, old-writer default behavior and
  conflict rollback.
- [x] Full backend discovery passes (`1261/1261`), frontend Jest passes
  (`299/299`), the production build and both backend import modes pass, and two
  independent reviews found no remaining Critical or Required issue.
- [x] Commits `396bf127` and `857b0b62` were pushed. Production dry-run found
  `151` ready rows and zero review rows with plan
  `193b566eef523a75b74304e6b997507d68a41c0c1ad9c2c93b8a4f72a3009a91`;
  guarded apply updated all `151` rows with zero conflicts. Post-audit reported
  complete schema, `151` explicit legacy rows, zero invalid rows and the full
  public deployment smoke passed on runtime `857b0b622de9`.

**Production apply order:** Pull the migration code without restarting the old
runtime. Run `npm run --silent migrate:brigade-lineage -- --dry-run`, require
`reviewCount=0`, and copy its exact `readyCount` and `planSha256`. Apply only
those guards:

```bash
npm run --silent migrate:brigade-lineage -- --apply \
  --confirm APPLY_BRIGADE_LINEAGE \
  --expected-ready-count <readyCount> \
  --expected-plan-sha256 <planSha256>
```

Then repeat the migration dry-run and `npm run audit:brigade-lineage`. Require
`schemaMigrationComplete=true`, migration `readyCount=0`, audit
`schemaState=complete`, audit invalid `0`, and the expected explicit legacy
count. `lineageDataReady=false`, `writerAuditIncluded=false` and
`constraintAuditIncluded=false` remain expected in E3.2. Only after those
checks pass should `bash deploy.sh` restart and smoke-check the runtime. On any
lock timeout, review row, plan drift, conflict or unknown commit outcome, stop
and rerun dry-run; never reuse stale guards.

## Task E3.3.1: Exact Immutable Assignment Snapshot Resolver

**Status:** Local implementation complete on 2026-08-06. Runtime assignment
writers remain unchanged and continue to receive the temporary E3.2 legacy
default until the atomic E3.3.2 cutover.

**Behavior:**

- `canonical-json-v1` now has one shared implementation for readiness audits
  and the future assignment runtime.
- The batch resolver accepts only server-constructed coordinate records with
  strict non-negative integer indexes and an exact, non-normalized item key.
  It never searches by name, code, generic ID or another descriptive alias.
- One parameterized `FOR UPDATE` binds `estimate_id + company_id + project_id`.
  After validating every requested coordinate, the same transaction creates or
  reuses one `estimate_versions` row whose stored content matches its canonical
  hash. Duplicate or corrupt claimed snapshots fail closed.
- A batch performs one estimate lock and one snapshot lookup regardless of the
  number of assignment rows. Duplicate coordinates and malformed batches are
  rejected before snapshot creation; structurally invalid batches are rejected
  before any database lock.
- The caller owns commit/rollback. The resolver exposes bounded reason codes
  and does not include work descriptions, prices or other business content in
  errors.

**Verification:**

- [x] Tests were written red before the resolver and before the pre-lock batch
  validation.
- [x] Resolver tests pass (`11/11`); the combined brigade-lineage package passes
  (`63/63`).
- [x] Full backend discovery passes (`1272/1272`), frontend Jest passes
  (`299/299`) and the production frontend build compiles.
- [x] Both backend import modes, isolated-cache Python compile and
  `git diff --check` pass.
- [x] Static usage search confirms the new resolver is referenced only by its
  tests; no HTTP writer, background task or application startup path imports it.
- [x] Five-axis correctness, architecture, security and performance review
  found and closed the per-row SQL and invalid-request locking issues; no
  Critical or Required finding remains.

**Next:** E3.3.2 must switch every assignment writer in one deploy: add exact
coordinates to `/distribute`, persist all five estimate-lineage fields, write
explicit `manual`/`pricelist` origins, make exact repeats idempotent and stop
estimate/JPR synchronization from rewriting issued quantity or manual brigade
price. Do not remove the temporary legacy default or enable E3.4 constraints
until the complete writer audit passes.

## Task E3.3.2: Atomic Brigade Assignment Writer Cutover

**Status:** Complete in production on 2026-08-06, runtime `6f5ab8a4430a`.

**Behavior:**

- `POST /estimates/{id}/work-assignment` and
  `POST /estimates/{id}/distribute` resolve one tenant-bound immutable snapshot
  per estimate batch and persist the exact section index, item index and item
  key. A repeat of the same complete lineage reuses the stored assignment and
  never rewrites its issued quantity or brigade price.
- `/distribute` now accepts server-validated exact coordinates instead of
  identifying estimate rows by descriptive fields. Its contract and item
  writes are one transaction, including pricelist autoload.
- Generic brigade item POST creates only `manual` rows, rejects client-owned
  lineage and starts confirmed progress at zero. PUT cannot mutate lineage and
  ignores client-supplied progress while preserving/clamping the stored value
  when an authorized plan edit changes the quantity.
- Pricelist autoload writes explicit `pricelist` lineage with no estimate
  coordinate. It does not infer quantity from an estimate name or work label.
- Estimate saves no longer synchronize assignment quantity or price. Confirmed
  ЖПР remains the only progress source and updates `done_quantity` by the exact
  stored `contract_item_id` rather than a name match.
- The frontend sends exact distribute coordinates and no longer offers the old
  generic "load estimate" path. Assignment status matches the exact
  compatibility key only; names, sections and units are not lineage.
- One shared source-item policy is used by both estimate-derived routes. The
  static writer audit allowlists exactly three assignment INSERT statements
  and three progress/manual-plan UPDATE statements, requires explicit source
  classification and rejects source mutation, descriptive lookup and unsafe
  estimate synchronization.

**Verification:**

- [x] Focused tests were written red before each writer cutover and all
  lineage, route, payload and status tests pass.
- [x] Full backend discovery passes (`1293/1293`); full frontend Jest passes
  (`304/304`, `76` suites).
- [x] Both backend import modes, isolated-cache Python compile,
  `git diff --check`, the production React build and deploy publisher tests
  (`3/3`) pass.
- [x] Desktop and 320 px Playwright checks load the production build and show
  the expected accessible page structure. The only console failures are the
  two expected public API calls because the isolated local browser run did not
  start the backend.
- [x] Final writer audit reports three allowlisted INSERT writers, three
  allowlisted UPDATE writers and no violation in its regression tests.
- [x] Production deploy and `npm run --silent audit:brigade-lineage` confirm
  `writerAuditIncluded=true`, `writersReady=true` and no writer violations.
- [x] The post-deploy report was read-only and rolled back, found complete E3.2
  schema, exactly `151` explicit legacy rows, zero invalid/unclassified rows,
  exactly three INSERT and three UPDATE writers, and an empty violation list.
- [x] The complete public smoke passed on runtime `6f5ab8a4430a`, including
  frontend `/`, `/app`, `/max-app`, health and all expected public/protected
  route status checks.

**Known dependency gate:** `npm audit --audit-level=high` currently reports
`31` inherited dependency findings (`16` high), dominated by the existing
Create React App/Jest toolchain. Its proposed complete fix installs the
breaking `react-scripts@0.0.0`; dependency modernization must be a separate,
tested change and was not mixed into this lineage cutover.

**Next:** Design E3.4 as a separate guarded schema release. Keep the temporary
`source_type='legacy'` default until an E3.4 preflight proves the complete
FK/CHECK/index/immutability/deletion plan against the `151` explicit legacy
rows. `lineageDataReady=false` and `constraintAuditIncluded=false` remain the
expected boundary after E3.3; do not interpret them as writer failure.

## Task E3.4.1: Strict Brigade Lineage Readiness Audit

**Status:** Complete in production on 2026-08-06. This was a diagnostic-only
release; it executed no DDL, route mutation or default removal.

**Objective:** Extend `npm run audit:brigade-lineage` with a bounded,
repeatable-read preflight that proves whether production can safely enter the
later E3.4 enforcement migration. Explicit `legacy` remains an allowed stored
class, but it is never promoted to verified estimate lineage.

**Required gates:**

- Catalog facts structurally verify the intended foreign keys from contract
  items to contracts and immutable estimate versions, and from versions to
  estimates. Matching a constraint name alone is insufficient.
- Catalog facts verify an allowlisted source-type CHECK, the conditional
  estimate/manual/pricelist/legacy shape CHECK, canonical snapshot-hash CHECK,
  removal of the temporary `source_type='legacy'` default, and `source_type`
  NOT NULL readiness.
- Catalog facts verify valid/ready partial indexes for exact estimate-lineage
  uniqueness, estimate-version deletion lookup and immutable snapshot-hash
  uniqueness.
- Catalog facts verify enabled trigger/function pairs for assignment source
  immutability/owner validation and immutable estimate snapshot content.
- Bounded aggregate data checks report NULL source types, invalid row shapes,
  missing snapshot hashes, duplicate estimate lineage and duplicate snapshot
  hashes without emitting business descriptions, prices or snapshot JSON.
- A static delete-policy audit requires the estimate deletion blocker to use
  `source_estimate_version_id -> estimate_versions.estimate_id`; the legacy
  compatibility-key check may remain only as an explicit legacy fallback.
- The runner remains read-only, rolls back, reports zero writes and keeps
  `readyForStrictRuntime=false` until writer, data, deletion and every catalog
  gate are green. Missing enforcement is a readiness result, not an exception.

**Boundaries:**

- Always: target `public` explicitly, use parameterized catalog/data queries,
  bound output to fixed gate names/counts, and preserve the current writer
  audit and lineage classification.
- Ask first: any production DDL, trigger installation, index build, default
  removal or legacy-row rewrite.
- Never: infer lineage from names/codes, modify production rows during audit,
  expose source documents, or weaken deletion protection to make a gate green.

**Verification:**

- [x] RED tests prove missing/wrong/unvalidated catalog objects and the current
  fuzzy delete blocker fail closed.
- [x] Complete synthetic facts produce `constraintsReady=true`; the current
  pre-enforcement schema produces a bounded missing-gate list.
- [x] The database runner uses one read-only repeatable-read transaction,
  attempts zero writes, rolls back and closes resources.
- [x] Focused lineage and estimate-deletion tests, full backend discovery,
  frontend Jest, compile/import modes, build and `git diff --check` pass.

**Dependencies:** E3.3 production writer readiness on `6f5ab8a4430a`.

**Expected files:** `backend/features/brigade_lineage/constraint_audit.py`,
its tests, the existing readiness report/tests, a static delete-policy audit,
this plan and ADR-0001. E3.4.2 migration files are explicitly out of scope.

**Local evidence:** The focused package and deletion-policy set passes, full
backend discovery passes (`1305/1305`), frontend Jest passes (`304/304`, `76`
suites), both readiness import modes and isolated-cache compile pass, the
production React build compiles, and deploy publisher regressions pass (`3/3`).
The static audit reports the current deletion gap only as
`exactEstimateVersionBlockerMissing + legacyFallbackNotScoped`; it executes no
route and changes no deletion behavior. Five-axis review found no remaining
Critical or Required correctness, architecture, security or performance issue.
No dependency changed; the inherited CRA/Jest audit debt recorded in E3.3.2 is
unchanged and remains a separate modernization task.

**Production evidence:** Runtime `4247630c92bb` returned top-level `ok=true`,
`dryRun=true`, `writesAttempted=0`, `rolledBack=true`, a green `3 INSERT / 3
UPDATE` writer audit and no invalid lineage shapes. The first run identified 13
orphaned `estimate_versions` belonging to eight already-deleted estimates.
Their references and hashes were all zero. After an exact-ID transaction backed
up to `/root/stroyka-backups/orphan-estimate-versions-20260806T155256Z.sql`
(`sha256:99ba04e653ff643092077becbe0f4e153be5fda21e8dd766db86d14a9d99f25f`),
the post-audit reports every aggregate integrity count as zero. The backup is
`600 root:root`, the transaction deleted exactly the 13 reviewed IDs, and no
write conflict occurred. Remaining bounded gaps are the expected strict-schema
catalog objects and the estimate-delete policy; therefore
`readyForStrictRuntime=false` remains correct.

## Task E3.4.2a: Exact Estimate Delete Restriction

**Status:** Complete in production on 2026-08-06. This slice changed only delete
preflight queries and contained no DDL or data migration.

**Objective:** Block estimate deletion through the authoritative
`brigade_contract_items.source_estimate_version_id -> estimate_versions.id ->
estimate_id` relationship. Retain compatibility-key matching only for rows
explicitly classified as `source_type='legacy'`.

**Acceptance:**

- Exact version lineage blocks deletion even when its compatibility key does
  not encode the estimate ID.
- Non-legacy rows are never matched through the fuzzy compatibility key.
- Exact and legacy matches expose one stable `договорные позиции` blocker.
- All query values remain parameterized and the existing authorized delete
  route, technical-record cleanup and supply-request checks remain unchanged.
- The static delete audit reports `deleteRestrictionsReady=true`; strict schema
  readiness remains false until the separate E3.4.2b catalog migration.

**Local evidence:** RED produced four expected failures. The minimal policy
change then passed all 14 focused estimate-deletion/static-audit tests, full
backend discovery (`1308/1308`), frontend Jest (`304/304`, 76 suites), isolated
Python compilation, the production React build, publisher regressions (`3/3`)
and `git diff --check`. The static audit reports
`deleteRestrictionsReady=true`, an empty violation list and zero writes.
Five-axis review found no Critical or Required issue: the route still locks and
authorizes the selected-company estimate, every SQL value is parameterized,
the exact writer takes the same estimate row lock, and the two bounded lookups
add no unbounded data path or dependency.

**Production evidence:** Runtime `ce1f568d3cdc` passed the complete public
smoke. The post-deploy report remained read-only and rolled back with
`ok=true`, `writesAttempted=0`, every aggregate integrity count at zero,
`writersReady=true`, `deleteRestrictionsReady=true` and an empty deletion
violation list. The remaining readiness boundary is catalog-only:
`constraintsReady=false` and `readyForStrictRuntime=false` are expected until
E3.4.2b.

## Task E3.4.2b: Guarded Strict Lineage Schema

**Status:** Complete in production on 2026-08-06. Runtime `cb1b59341c5e`
passed public smoke; the separately reviewed guarded schema transaction
committed and its final read-only audit is green.

**Objective:** Add the exact six constraints, three partial indexes, two
trigger/function guards, remove the temporary `source_type='legacy'` default
and set `source_type` NOT NULL. Preserve all 151 explicit legacy rows as a valid
historical class; do not infer estimate lineage or rewrite business data.

**Migration contract:**

- Dry-run uses one read-only transaction, reports a bounded deterministic plan,
  attempts zero schema writes and rolls back.
- Apply requires an explicit confirmation token plus the exact change count and
  SHA-256 from the immediately reviewed dry-run.
- Apply locks only the four lineage owner/source tables with bounded lock and
  statement timeouts, re-runs data, writer and delete-policy gates under lock,
  and rejects plan drift before the first DDL statement.
- Existing invalid same-name constraints, indexes or triggers are blockers;
  the migration never silently replaces an unverified catalog object.
- Every DDL statement is transactional. A failed postcheck rolls the entire
  schema change back; a repeated apply against the complete schema is a no-op.
- The postcheck must produce `constraintsReady=true`; the existing top-level
  audit must then produce `readyForStrictRuntime=true` even though 151 explicit
  legacy rows remain review-visible.

**Rollback boundary:** The code deploy and schema apply are separate operator
steps. Before apply, preserve the reviewed dry-run JSON. If runtime verification
fails after a committed apply, deploy the previous runtime and execute the
generated reverse-order rollback statements only after a fresh data audit.

**Local verification:** RED began with the absent migration module and later
proved that canonical snapshot/content drift must block apply even when all
aggregate SQL counters are zero. The final focused migration set passes
`15/15`; the complete brigade-lineage package passes `103/103`, estimate-delete
tests pass `9/9`, and full backend discovery passes `1323/1323`. Frontend Jest
passes `304/304` across 76 suites, the production build compiles, publisher
regressions pass `3/3`, isolated Python compilation and `git diff --check` pass.

A disposable PostgreSQL 15.17 schema with 151 legacy rows completed a real
dry-run (`13` planned changes, zero writes, rollback), transactional apply (`15`
DDL statements), structural/data postcheck and repeated apply (`0` writes).
The database rejected an unhashed estimate source, cross-owner source, lineage
mutation, snapshot mutation, referenced-version delete and referenced-estimate
delete. The final existing readiness report returned
`constraintsReady=true`, `writersReady=true`,
`deleteRestrictionsReady=true`, `readyForStrictRuntime=true`, empty data issues
and all 151 explicit legacy rows preserved.

**Review result:** No Critical or Required issue remains across correctness,
architecture, security or performance. Apply SQL is a static allowlist; CLI
count/SHA/token inputs are validated and never interpolated into SQL. Existing
same-name functions are not replaced, all locks/timeouts are bounded, writer
and exact-delete audits plus canonical lineage validity are repeated under the
same transaction, and every failure before commit rolls back the complete DDL
set. No dependency changed; inherited CRA/Jest audit debt remains unchanged.

**Production evidence:** Public smoke passed on runtime `cb1b59341c5e`. The
read-only production plan reported `readyForApply=true`, exactly `13` changes
(two column changes, six constraints, three indexes and two triggers), zero
blockers, zero schema writes and plan SHA-256
`a3578a17a4d9a5e086d1f8271a8312a21876dcbe4a269214268e9180ead6093e`.
The guarded apply used that exact count and hash; the chained final audit ran
only after its successful exit. It reports `constraintsReady=true`, empty
missing/invalid catalog lists, every integrity count at zero except the
expected `explicitLegacy=151`, empty `dataIssues`, `writersReady=true` and
`deleteRestrictionsReady=true`. The audit itself remained read-only and rolled
back. Reviewed dry-run and apply outputs are preserved under
`/root/stroyka-backups/brigade-lineage-strict-a3578a17-*.json`.

## Task E4: Reviewed Estimate Row Balance Transfer

**Status:** Complete in production on 2026-08-07 through runtime
`dc0f86558ecf`. The reviewed mapping, assignment receipt and supply-allocation
schemas are installed, the complete public smoke is green, and the final
rolled-back readiness report returns `readyForCutover=true`. Production has no
approved reconciliation, plan or receipt eligible for a manufactured
transfer, so no business data was created for verification.

**Contract:** `docs/estimate-row-transfer-contract.md` is authoritative. The
operation uses an approved exact source/target mapping and explicit quantities.
It may reduce an assignment only above server-recomputed confirmed JPR and may
attribute only an unreceived open-request balance. Existing source lineage,
JPR, acts, supply documents, warehouse history and payments remain unchanged.

**Confirmed decisions:**

- Transfer quantity is explicit, never automatically the full remainder.
- Source assignment quantity may reduce only above confirmed JPR; immutable
  ledger evidence preserves its complete pre-transfer state.
- Target estimate price is current; negotiated brigade price is preserved.
- Supply requests are not split or rewritten; an allocation ledger moves only
  their unreceived balance in material-control projections.
- Estimate writers may draft, but only director/deputy may approve and apply.

### Task E4.1: Read-Only Exact Transfer Impact Audit

**Description:** Inspect one approved estimate reconciliation without trusting
its descriptive row aggregation. Resolve stored owners and exact immutable
assignment sources, validate proposed target coordinates with the canonical
snapshot resolver, calculate assignment/JPR and request/delivery balances, and
emit bounded candidates/blockers without writes.

**Acceptance criteria:**

- [x] Cross-company/project/package/type, stale snapshot, fuzzy mapping,
  malformed request lineage and non-finite/over-completed balances fail closed.
- [x] Output contains IDs, exact coordinates, quantities, counts and fixed
  reason codes only; it excludes descriptions, commercial notes and prices.
- [x] Report proves `writesAttempted=0`, uses a read-only transaction, rolls
  back and includes protected-history counts without loading their content.

**Verification:**

- [x] RED tests cover every trust boundary and protected-history condition.
- [x] Focused and full backend tests pass; Python compilation and
  `git diff --check` pass.
- [x] A real PostgreSQL fixture proves read-only behavior and bounded output.

**Dependencies:** E3.4 production complete; E4 contract approved.

**Files likely touched:**

- `backend/features/estimate_row_transfer/audit.py`
- `backend/features/estimate_row_transfer/test_audit.py`
- `package.json`
- `tasks/todo.md`

**Estimated scope:** M (first independent checkpoint; no runtime mutation).

**Local verification:** RED began with the absent audit module and then caught
closed-request leakage, cross-project supply lineage, duplicate source
coordinates and fractional JSON IDs/indexes. Focused discovery runs `21` tests
with zero failures and one expected opt-in PostgreSQL skip. Full backend
discovery runs `1344` tests with zero failures and the same one expected skip;
isolated Python compilation, npm CLI help and `git diff --check` pass.

A disposable PostgreSQL 15 cluster separately ran the opt-in fixture `1/1`.
The real report resolved one approved reconciliation, recomputed confirmed JPR
quantity `4`, reported transferable assignment quantity `6`, used a read-only
repeatable-read transaction, rolled back and left every fixture table count
unchanged. Both disposable clusters were stopped and removed after testing.

**Review result:** No Critical or Required finding remains across correctness,
security, architecture or performance. Review-fixed regressions exclude closed
requests, bind stored supply project lineage, reject duplicate coordinates and
reject fractional IDs/indexes instead of truncating them. Runtime SQL is static
and parameterized, contains no DML/DDL/row locks, and output omits descriptions,
prices and commercial notes. No dependency, API route, schema or business
writer changed.

**Production evidence:** Runtime `2c816ccb789e` passed the complete public
smoke after atomic frontend publication; backend health and every expected
protected-route status were green. Production contains `13` reconciliation
rows, all in `Черновик`, and zero approved reconciliations, so there is no
legitimate transfer candidate to audit yet. The deployed E4.1 command was run
against latest draft `#15` only to prove the approval boundary: it returned
`ok=false`, fixed reason `reconciliation_not_approved`, empty assignment,
supply and target-mapping lists, `writesAttempted=0`,
`readOnlyTransaction=true` and `rolledBack=true`. No row was approved, created
or changed for testing. The inherited CRA/Jest dependency audit reports zero
critical findings; its existing high build/test-toolchain findings were not
changed or force-fixed in this backend-only release.

### Checkpoint After E4.1

- [x] Human reviews production audit evidence before any E4 schema design.
- [x] No DDL or business row was changed.
- [x] Exact local candidates and the production approval blocker are
  sufficient to design inert E4.2 without
  fuzzy or descriptive inference.

### Task E4.2: Inert Reviewed Mapping Ledger

**Description:** Persist a bounded, immutable review plan for one approved
reconciliation. Resolve exact owners, authoritative source/target snapshots,
current protected/available balances and explicit selected quantities inside
one repeatable-read transaction. Estimate writers may create or review a
draft; only a director or deputy director in the stored company may approve
the unchanged deterministic hash. Approval remains ledger-only and moves no
assignment or supply balance.

**Status:** Complete in production. The separately guarded schema plan applied
successfully with its exact count/SHA-256, and both public and explicitly
authorized authenticated fail-closed API smokes pass.

**Acceptance criteria:**

- [x] Strict payload allowlists accept 1–100 exact entries and reject unknown
  fields, duplicate sources, fractional IDs/indexes, non-canonical keys,
  non-finite quantities and quantities with more than six decimal places.
- [x] The server recomputes company/project/package/type, reconciliation,
  source/target snapshots, exact coordinates and current balances; fuzzy,
  ambiguous, stale, cross-owner and truncated inputs fail closed.
- [x] A minimal stored owner preflight authorizes company, project and package
  before any full assignment/supply impact scan; foreign reconciliation IDs
  return not-found without scanning their snapshots or dependent rows.
- [x] `planSha256` covers the exact owner/snapshot/coordinate/balance/quantity
  plan in deterministic source order and excludes actor metadata, descriptions,
  notes and prices.
- [x] Draft/read routes are tenant-bound to estimate writers; approval is
  leadership-only, locks and recomputes the plan, and repeated approval of the
  same hash is a read-only idempotent result.
- [x] Database constraints, partial uniqueness and triggers make entries
  immutable and permit only one `draft -> approved` transition and one
  approved plan per reconciliation.
- [x] Runtime DML is limited to inserting ledger plans/entries and updating
  plan approval metadata. Assignment, request, delivery, warehouse,
  accounting, JPR, act and payment rows have no E4.2 mutation path.
- [x] Schema DDL is absent from `init_db()` and `deploy.sh`; same-name objects
  with incompatible constraint/index/function/trigger definitions block the
  guarded migration.

**API:**

- `POST /estimate-row-transfer-plans`
- `GET /estimate-row-transfer-plans/{id}`
- `POST /estimate-row-transfer-plans/{id}/approval`

**Operator commands:**

```bash
npm run audit:estimate-row-transfer-schema
npm run migrate:estimate-row-transfer-schema -- \
  --expected-change-count <count> \
  --expected-plan-sha256 <sha256>
```

The first command is rolled back and reports zero writes. The second command
must use the exact count and hash from the reviewed dry-run; any catalog drift
or mismatched guard aborts before DDL.

**Local verification:** RED tests began with the absent plan/schema/API and
later proved that a same-name but weakened guard function must block schema
readiness. Focused discovery passes `59/59` with two expected opt-in
PostgreSQL skips; full backend discovery passes `1382/1382` with the same two
expected skips. A disposable PostgreSQL cluster passes the opt-in `2/2` suite:
guarded schema apply reaches strict readiness; one real draft and leadership
approval leave every measured business-table count unchanged; the database
rejects entry mutation. Temporary clusters were stopped and removed.

The local frontend production build, Python compilation, smoke-script syntax
and rate-limit regressions passed during the implementation review. The
inherited CRA/Jest dependency audit remains unchanged at zero critical
findings; E4.2 adds no dependency.

**Implementation commits:** `6cfe4bbc`, `c906208d`, `f7872fb7`, `7ed33f11`,
`349d411c`, `919cd023`, `ad1a4dcc`, `b237a28b`, `a5935b5d`, `c700e043`.

**Production evidence:** The first restart exposed a production-only import
path gap and left nginx returning `502`; hotfix `a5935b5d` converted the new
package to relative imports and added a pre-restart production-import gate.
The healthy backend then exposed the separately missing nginx allowlist;
hotfix `c700e043` added exact collection/detail proxy routes through an
idempotent updater that backs up the active config. Final public smoke is fully
green on runtime `c700e043`, including all three transfer-plan routes at `401`.

The reviewed production schema dry-run reported exactly `11` additive changes,
zero blockers/writes, rollback and plan SHA-256
`683b69acd90e196a1310b008acc7d6c43efb43ecaf520c43496ba937a9fba85e`.
Guarded apply committed those exact `11/11` changes. The repeated read-only
audit reports `schemaReady=true`, `changeCount=0`, `changes=[]`,
`writesAttempted=0`, rollback and empty-plan SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
No assignment, request, delivery, warehouse, accounting, JPR, act or payment
balance was changed.

The separately authorized authenticated smoke used only deliberately missing
or invalid resources. `GET /estimate-row-transfer-plans/2147483647` returned
`404 transfer_plan_not_found`; a draft for reconciliation `#15` with missing
assignment source `2147483647` returned `409
target_snapshot_context_invalid` before ledger insertion; and approval of
missing plan `2147483647` with a syntactically valid placeholder hash returned
`404 transfer_plan_not_found`. The failure paths rolled back, and no approved
reconciliation, plan or business row was manufactured for testing.

### Checkpoint Before E4.2 Production Apply

- [x] No production DDL or E4 business balance write was executed locally.
- [x] Disposable PostgreSQL proves the guarded schema and inert API storage.
- [x] Production dry-run count, changes and SHA-256 were reviewed.
- [x] The exact plan applied; runtime, nginx routing, public smoke and repeated
  read-only schema audit are green.
- [x] The separately authorized authenticated fail-closed GET/draft/approve
  smoke returned `404 / 409 / 404` without manufacturing an approved
  reconciliation or business data.

### Task E4.3: Transactional Assignment Balance Apply

**Description:** Apply only the assignment entries of one approved E4.2 plan
after leadership repeats its exact `planSha256`. Lock the immutable plan,
contracts, source assignment rows and their JPR rows in deterministic order;
recompute every owner, source lineage, target snapshot, confirmed quantity and
contract total inside one serializable transaction. Reduce only the selected
unconfirmed quantity, insert an exact target-lineage row with the target
estimate price and source brigade price, and store immutable before/after
evidence. Supply entries remain untouched for E4.4.

**Status:** Complete in production on 2026-08-07 for runtime `b1ff981db5be`.
The guarded schema applied with its exact reviewed count/SHA-256, public and
authenticated fail-closed smokes pass, and no assignment balance was changed.

**Acceptance criteria:**

- [x] A separately guarded additive schema creates an immutable assignment
  transfer receipt linked to the exact plan/entry/company/project. Partial,
  mismatched or manually mutated evidence fails at the database boundary.
- [x] Only stored-company leadership may call the exact-hash apply endpoint;
  draft, stale, cross-owner, mixed-state, over-balance, existing-target and
  target-snapshot conflicts fail before business mutation.
- [x] Source quantity never falls below recomputed confirmed JPR; JPR links,
  source progress/lineage, acts, payments and all supply/warehouse/accounting
  rows remain unchanged. Target quantity equals the transfer, target estimate
  price is current and negotiated brigade price is preserved.
- [x] Contract brigade total is unchanged within the existing numeric
  tolerance, the first apply is atomic and a repeated exact apply is a
  read-only idempotent response.

**Verification:**

- [x] RED unit/route/schema tests fail before each new behavior exists, then
  focused E4 and brigade-writer suites pass.
- [x] Opt-in real PostgreSQL proves rollback, concurrent double-apply, exact
  receipt evidence and unchanged protected-table rows.
- [x] Full backend regression, Python compilation, static writer audit,
  frontend tests/build and `git diff --check` pass before release review.

**Boundaries:** No automatic schema apply, background worker, UI or supply
allocation was added. Production DDL was applied only through the separately
reviewed guarded command. No production assignment mutation was executed
because there is no approved reconciliation or transfer plan.

**API:** `POST /estimate-row-transfer-plans/{plan_id}/assignment-apply` accepts
only `{"planSha256":"<approved-lowercase-sha256>"}`. The route requires one
selected company and a director/deputy director, locks the exact approved plan
in a `SERIALIZABLE` transaction and returns a bounded receipt with only plan,
entry, source/target item IDs, transferred quantity, timestamp and idempotency
state. It never returns work descriptions or prices.

**Local verification:** Two independent disposable PostgreSQL clusters each
passed the complete opt-in `5/5` suite and were stopped and removed. The real
database proof split assignment quantity `10 -> 7 + 3`, kept confirmed JPR and
source progress at `4`, used target estimate price `900`, preserved negotiated
brigade price `700`, and left contract total `7000` unchanged. The exact
receipt is immutable; a sequential repeat writes nothing, two concurrent
calls leave one target and one receipt, and JPR drift rolls every apply write
back. Row snapshots for work journal, hidden acts, brigade acts/payments,
supply requests/offers/invoices/deliveries/history/claims and warehouse
invoice/history remained byte-for-byte unchanged.

Focused E4 discovery passes `81` tests with five expected opt-in PostgreSQL
skips outside the fixture. The neighboring writer/assignment route suites pass
`32` tests. Full backend discovery passes `1406/1406` with the same five
skips; frontend Jest passes `304/304`; Python compilation, smoke shell/rate
limit checks, production frontend build and `git diff --check` pass. No new
dependency was added.

**Review result:** Code review found and fixed two required money/progress
boundaries before completion: stored contract totals must match the locked
item sum using PostgreSQL-compatible positive rounding, and preserved source
progress may not exceed the post-transfer quantity. The database guard now
also binds receipt before/protected quantities, package, compatibility keys
and source status to the exact approved plan and live rows. No Critical or
Required finding remains.

**Implementation commits:** `f2b84e57`, `ec482f7b`, `75d8cad9`, `63ca9371`.

**Production evidence:** Runtime `b1ff981db5be` deployed atomically and passed
the complete public smoke, including unauthenticated `401` for the new
assignment-apply route. The production schema dry-run reported exactly five
additive changes, no blockers, rollback, zero writes and plan SHA-256
`43e220bbe2a9352863717e68fb0c7467ac73bb3bc4fc376aa473a6b55631fb44`.
Guarded apply committed those exact `5/5` changes. The repeated audit reports
`schemaReady=true`, `changeCount=0`, `writesAttempted=0`, rollback and the
empty-plan SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.

A separate read-only production snapshot returned `plansByStatus=[]`,
`assignmentReceipts=0` and `approvedReconciliations=0`. After leadership login,
`POST /estimate-row-transfer-plans/2147483647/assignment-apply` with a valid
placeholder hash returned bounded `404 transfer_plan_not_found`. Thus the
authenticated route reached the installed schema without creating a plan,
receipt, reconciliation or business balance change. QA password, 2FA and token
were not stored in the repository; the operator was instructed to clear the
temporary shell variables immediately after the smoke.

### Task E4.4: Immutable Supply Balance Allocation And Projection

**Description:** Apply only the supply entries of one approved E4.2 plan after
leadership repeats its exact `planSha256`. The operation records an immutable
allocation for the reviewed finite unreceived balance; it never rewrites the
request item, status, delivery chain, supplier documents, warehouse history or
accounting. Material control consumes the tenant-bound allocation metadata and
attributes only the allocated open quantity to the exact target estimate row.

**Status:** Completed and production-verified on runtime `bf078924852b`. The
guarded additive schema is installed; no production plan or allocation was
created for verification.

**Acceptance criteria:**

- [x] A separately guarded additive schema stores one immutable receipt per
  supply plan entry, binds it to the exact plan/company/project/request/item,
  source and target snapshot coordinates, request-item snapshot hash,
  requested/received/prior/allocated/remaining quantities and leadership
  actor. Update/delete and inconsistent inserts fail at the database boundary.
- [x] The exact-hash supply apply action locks the approved plan, request,
  deliveries and prior allocations in deterministic order, revalidates the
  canonical open-status allowlist, owner/project/package, exact validated
  source lineage, target snapshot and finite quantities, and prevents the
  cumulative allocation from exceeding the current unreceived balance.
- [x] First apply writes only immutable allocation receipts. An exact repeat is
  read-only and idempotent; partial receipts, changed deliveries/request JSON,
  mixed owners, ambiguous delivery allocation, stale target snapshots and
  concurrent conflicts roll back the whole transaction.
- [x] `/supply-requests` attaches allocation metadata only to already visible
  tenant-owned requests. Material control resolves each allocation against one
  exact target `estimateId + sectionIndex + itemIndex`; unresolved, malformed
  or over-quantity metadata fails closed to the original request attribution
  and raises review state rather than guessing a material row.
- [x] For a request item `requested = received + unallocated open + allocated
  open`, the original row keeps `received + unallocated open` and the target
  row receives exactly `allocated open`. Delivery, invoice, warehouse and
  accounting calculations remain unchanged because only the request
  `requested` projection consumes the ledger.

**Verification plan:**

- [x] RED unit/route/schema/frontend tests precede each behavior; focused E4
  suites pass after implementation.
- [x] Opt-in real PostgreSQL proves rollback, concurrent double-apply,
  cumulative allocation bounds, immutable evidence and byte-for-byte unchanged
  protected request/delivery/supplier/warehouse/accounting tables.
- [x] Full backend regression, Python compilation, frontend tests/build,
  static writer checks and `git diff --check` pass before release review.

**Boundaries:** No automatic schema apply, background worker or historical
request cleanup. No production DDL, plan creation or supply allocation occurs
until the local implementation, reviews and guarded dry-run are separately
approved.

**Local evidence (2026-08-07):** focused E4 discovery passes `106` tests with
`8` opt-in skips; a fresh disposable PostgreSQL cluster passes all `8` real
transaction/concurrency tests and was removed afterward. The full backend
suite passes `1430` tests with `8` skips, the frontend passes `307` tests in
`76` suites, Python compilation, production build, atomic-publish tests and
`git diff --check` pass. Review additionally made projection metadata internal
only, restricted apply to statuses actually counted as open requests, required
an explicitly typed material target at audit/apply/database boundaries, bound
duplicate project identity fail-closed and corrected original projection to
use the stored unallocated remainder rather than double-count received supply.

**Implementation commits:** `fbb8bc6e`, `911d7e2f`, `690155cc`, `ce0f09df`,
`9b0e259c`, `669dd3e9`.

`npm audit` reports the repository's existing Create React App dependency
chain (17 high, 5 moderate and 10 low findings); this feature adds no package
and `npm audit fix --force` proposes a breaking `react-scripts@0.0.0` change,
so dependency modernization remains a separate release item rather than an
unreviewed mutation in E4.4.

**Production evidence:** The complete public smoke passed on runtime
`bf078924852b`, including unauthenticated `401` for the new supply-apply route.
The rolled-back schema dry-run reported exactly five additive changes, no
blockers, zero writes and plan SHA-256
`5598b4490e89b751fc1776172cf6c5443f7f406a198a18f4c4d24cecb2359916`.
Guarded apply committed those exact `5/5` changes. The repeated audit reports
`schemaReady=true`, `changeCount=0`, `writesAttempted=0`, rollback and the empty
plan SHA-256
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The service remained active and the repeated full public smoke passed. A
separate read-only production snapshot returned `plansByStatus=[]`,
`assignmentReceipts=0`, `supplyAllocations=0` and
`approvedReconciliations=0`; no reconciliation, plan, receipt, allocation or
business balance was manufactured for testing.

### Task E4.5: Cutover Readiness And Reviewed Production Sequence

**Description:** Close E4 with one operator-facing, rolled-back readiness
report. It must combine the already guarded schema catalog, deterministic
stored-plan integrity, all-or-none assignment/supply receipt state, exact
entry/receipt quantities, the complete E4 writer inventory and the required
real PostgreSQL rollback/idempotency/concurrency cases. An optional exact
`plan_id + plan_sha256` filter is the production pre-apply gate. It remains
read-only and cannot approve or apply a plan.

**Status:** Complete in production on 2026-08-07 for runtime `dc0f86558ecf`.
There was no E4.5 schema change or business apply during deployment.

**Acceptance criteria:**

- [x] The report uses one read-only `REPEATABLE READ` transaction, attempts
  zero writes, always rolls back and fails closed when any required E4 schema
  object is missing or definition-invalid.
- [x] Every stored plan hash is recomputed from its exact canonical owner,
  snapshots, coordinates, balances and quantities. Draft approval residue,
  owner mismatch, missing entries, duplicate/foreign receipts, receipt/hash or
  quantity mismatch and per-kind partial apply are fixed-code blockers.
- [x] A mixed assignment+supply plan may be pending, assignment-applied,
  supply-allocated or complete, but each individual kind is all-or-none.
  Pending approved work is reported as state, not mistaken for corruption.
- [x] Issue output is bounded and contains only plan/entry IDs and fixed reason
  codes. It never emits descriptions, notes, prices, request JSON, actor names
  or snapshot content.
- [x] The static writer audit scans the repository without importing runtime
  code. Only the exact reviewed ledger DML and assignment split statements are
  allowlisted; any new E4 mutation of JPR, acts, payments, supply documents,
  deliveries, warehouse or accounting is a blocker.
- [x] The integration inventory requires the opt-in real PostgreSQL tests for
  assignment and supply rollback, sequential idempotency, concurrent
  double-apply and unchanged protected-history snapshots. The inventory does
  not substitute for executing that suite before release.
- [x] `--plan-id` requires the exact lowercase `--expected-plan-sha256`, fails
  on missing/wrong/draft/corrupt plans and reports readiness separately for
  assignment and supply. The command remains read-only.
- [x] Production apply remains exclusively through the authenticated
  leadership-only assignment/supply endpoints. No root-only SQL apply command,
  automatic migration, background worker or synthetic production plan is
  introduced.

**Operator sequence:**

1. Run the global readiness command and review `readyForCutover=true`.
2. For a real approved plan, run the exact plan/hash readiness command and
   archive its JSON before any apply call.
3. Apply one pending kind through its existing leadership API with the same
   hash; re-run and review exact readiness before applying the other kind.
4. Re-run exact and global readiness, schema audit, service health and public
   smoke. A failed/partial/corrupt state stops the sequence; it is never
   repaired automatically.

**Commands:**

```bash
# Always safe after deploy: global read-only cutover audit.
npm run audit:estimate-row-transfer-readiness

# Only for a real approved plan after separately reviewing its exact ID/hash.
npm run audit:estimate-row-transfer-readiness -- \
  --plan-id "$PLAN_ID" \
  --expected-plan-sha256 "$PLAN_SHA256"
```

The second command does not apply anything. If its exact gate is green, the
operator uses the existing authenticated leadership endpoints, one at a time:
`POST /estimate-row-transfer-plans/{id}/assignment-apply`, re-audit, then
`POST /estimate-row-transfer-plans/{id}/supply-apply`, followed by exact and
global audits. With no real approved plan, those apply calls are skipped.

**Verification plan:**

- [x] RED unit tests cover schema-not-ready, plan-hash drift, all receipt
  mismatch/partial cases, bounded output, optional exact-plan guards and
  writer/test inventory drift.
- [x] A fresh disposable PostgreSQL cluster executes the complete E4 suite and
  the final readiness report against empty, pending, applied and concurrent
  fixture states.
- [x] Focused/full backend tests, Python compilation, static lineage writer
  audit, frontend tests/build, smoke syntax and `git diff --check` pass before
  release review.

**Local evidence (2026-08-07):** RED began with absent readiness/inventory
modules and then caught indirect SQL-literal inventory evasion, unbounded
global scans and incomplete receipt evidence. Focused E4 discovery passes
`120` tests with `9` expected opt-in skips. Two fresh disposable PostgreSQL 15
clusters independently passed the complete `9/9` suite, including assignment
and supply sequential idempotency, both concurrent double-apply cases, both
drift rollbacks, unchanged protected history and global/exact readiness over
pending and applied plans; both clusters were stopped and deleted.

Full backend discovery passes `1445` tests with `9` skips. Frontend Jest passes
`307/307` tests in `76/76` suites. Python compilation, the brigade-lineage
writer audit, readiness CLI help, deploy/smoke shell syntax, atomic-publish
tests, the production frontend build and `git diff --check` all pass. The
readiness report caps a global scan at `1000` plans and `100000` ledger rows,
caps an exact plan at the contractual `100` entries and fails closed instead
of silently truncating.

**Review result:** Five-axis review found and fixed three required boundaries:
the static writer audit now sees SQL literals even when assigned before
`execute`, every global/exact read is bounded, and receipts are matched to the
exact source/target coordinates plus assignment before/after and supply
quantity equations. Output contains no descriptions, prices, request JSON or
actor names. No dependency, schema, API route or business writer changed.

**Production evidence:** Runtime `dc0f86558ecf` deployed atomically, the
service remained active and the complete public smoke passed. The global
readiness command returned `ok=true`, `dryRun=true`,
`readOnlyTransaction=true`, `writesAttempted=0` and `rolledBack=true`. Its
schema audit found zero changes, blockers or missing columns. The bounded
ledger audit found zero plans, entries, assignment receipts, supply
allocations and issues. The static inventory found the expected `8` DML
statements and all `6` required integration checks with no violations, so the
top-level result is `readyForCutover=true`. No exact-plan apply was attempted
because production has no real approved plan.

**Implementation commits:** `6bf59973`, `8a3529a5`, `9ff09364`, `295998cf`,
`61b7cad7`, `89a00704`; production smoke rate-limit hardening is `dc0f8655`.

## Task E5: Exact Active-Estimate Material-Control Ownership

**Description:** Replace project-name ownership in the complete active-estimate
material-control path with the stored `company_id + project_id` tuple. The
authoritative accepted contract is
`docs/active-estimate-material-control-ownership.md`.

**Status:** Complete in production on 2026-08-07. Runtime `ded68df1ad00` passed
atomic deploy, service health, two public smoke runs and the final read-only
audit. All `6/6` runtime boundaries are owner-scoped; the writer/test inventory
is the exact reviewed `5/5`; all violations and data issues are zero; and
`readyForCutover=true`. E5 required no schema or business-row apply.

**Original observed risk:** The estimate query read `company_id` but its public
payload omitted `companyId`; frontend active selection accepted either a
matching name or project ID. The E5.1 inventory found that selector plus five
backend name-scoped boundaries: supply material control, linked-work control,
project AI control, estimate activation and material-norm suggestions. Before
E5.4, an all-companies view could therefore mix identically named projects
across companies.

### Task E5.1: Read-Only Owner Readiness

**Acceptance criteria:**

- [x] One read-only repeatable-read report audits active project/estimate owner
  tuples, duplicate active owner/kind/package groups and name-collision groups.
- [x] Missing, invalid, mismatched and ambiguous rows use fixed reason codes;
  previews are bounded and contain IDs only.
- [x] A static inventory identifies every frontend active-estimate selector and
  backend material-control active-estimate query still using project name.
- [x] The command attempts zero writes, always rolls back and performs no DDL.

**Verification:** `13` focused tests pass with the guarded dedicated-PostgreSQL
fixture skipped until an explicitly approved `e5_*` database is supplied;
`1458` backend tests pass (`10` guarded skips), all `76` frontend suites / `307`
tests pass, Python compilation and the production build pass. The local command
returned a bounded `schema_not_ready` report against the available older
developer schema instead of raising or writing.

**Production evidence (2026-08-07):** Runtime `1bfae554aa47` deployed
atomically, remained active and passed the complete public smoke. The read-only
audit returned `ok=true`, `dataReady=true`, `schemaReady=true`,
`scanComplete=true`, `readOnlyTransaction=true`, `writesAttempted=0` and
`rolledBack=true`. It verified `4` active projects and `15` valid active
estimates, with zero duplicate active scopes, name-collision groups or data
issues. Static inventory found exactly the accepted `6` name-scoped boundaries;
therefore `runtimeInventoryReady=false` and `readyForCutover=false` were the
expected pre-cutover result.

**Estimated scope:** M, diagnostic-only.

### Task E5.2: Estimate API And Strict Discovery

**Acceptance criteria:**

- [x] Estimate list, summary and detail responses include the stored
  `companyId` while preserving authorization and all existing fields.
- [x] Material-control discovery requires exact positive company/project IDs;
  missing or mismatched owners fail closed without a name fallback.
- [x] Frontend tests use two same-name projects in different companies and
  prove that each sees only its own active customer/material estimate.

**Local evidence (2026-08-07):** TDD reproduced the cross-company collision,
ownerless/malformed acceptance and duplicate-active selection before the fix.
The shared estimate response mapper now exposes stored `companyId`; all three
API surfaces are statically bound to that mapper and continue to use the
existing visibility filters. The pure frontend matcher accepts only canonical
positive decimal integer IDs, requires exact company/project ownership, rejects
a conflicting supplied name and omits duplicate active kind/package groups.

Focused E5 discovery passes `15` tests with one guarded PostgreSQL skip; the
three focused frontend suites pass `22/22`. Full backend discovery passes `1461`
tests with `10` guarded skips, full frontend Jest passes `313/313` in `77/77`
suites, Python compilation and the production build pass. Static inventory now
reports the deliberate intermediate state `6` candidates, `1` owner-scoped
frontend selector and the remaining `5` name-scoped backend boundaries. No
schema, business row, auth rule, SQL predicate or dependency changed.

**Production evidence (2026-08-07):** Runtime `9c8ba525932f` deployed
atomically, the service remained active and the complete public smoke passed.
The post-deploy read-only audit returned `ok=true`, `dataReady=true`,
`writesAttempted=0` and `rolledBack=true`. It verified `15/15` valid active
estimates, no duplicate scopes or name-collision groups, and the exact
intermediate static state: `candidateCount=6`, `ownerScopedCount=1`,
`nameScopedCount=5`, with only the five accepted backend violations. Protected
checks were skipped because credentials were not supplied; auth behavior was
unchanged and all protected public routes remained fail-closed.

**Estimated scope:** M, no schema or business writes.

### Task E5.3: Runtime Owner Propagation

**Acceptance criteria:**

- [x] Material plan, reconciliation and summary functions receive an exact
  project owner object instead of a name-only scope.
- [x] Cache keys include company ID, project ID and package; same-name projects
  cannot share cached rows or summaries.
- [x] UI consumers pass the stored project object and retain unchanged labels,
  totals and single-company behavior.

**Local evidence (2026-08-07):** The runtime canonicalizes stored projects into
an immutable `{companyId, projectId, projectName}` owner and rejects malformed,
incomplete and name-only scopes. Material plan, norm requirement,
reconciliation, summary, hints and alias candidates use that owner. Cache keys
contain company ID, project ID and package, and regression tests prove that two
same-name projects in different companies do not share rows or summaries.

Warehouse, project, dashboard, economy, AI, supply-planning, master and print
consumers now pass a stored project object. Remaining legacy-name boundaries
resolve only one valid stored owner and fail closed on a collision. Display
labels and historical name-based operational records are unchanged. The focused
frontend suites pass `33/33`; full frontend verification passes `318/318` tests
in `77/77` suites; the focused E5
backend package passes `16` tests with one guarded PostgreSQL skip, and the
production build succeeds. The local audit returned the bounded expected
schema-not-ready report against the older developer database with zero writes
and rollback; static inventory remained `1` owner-scoped frontend selector and
the `5` accepted backend violations.

**Production evidence (2026-08-07):** Runtime `fbc6374cc221` deployed
atomically, the service remained active and the complete public smoke passed.
The post-deploy read-only audit returned `ok=true`, `dataReady=true`,
`schemaReady=true`, `scanComplete=true`, `readOnlyTransaction=true`,
`writesAttempted=0` and `rolledBack=true`. It verified `4/4` active projects,
`15/15` valid active estimates and zero duplicate scopes, name collisions or
data issues. Static inventory remained exactly `6` candidates, `1`
owner-scoped frontend selector and the `5` accepted backend violations, so
`runtimeInventoryReady=false` and `readyForCutover=false` are the expected
pre-E5.4 state. Protected checks were skipped because credentials were not
supplied; authentication behavior was unchanged and protected public routes
remained fail-closed. No schema or business-row apply was required.

**Estimated scope:** Split into S/M consumer slices, each independently tested.

### Task E5.4: Server Lineage And Refresh Cutover

**Acceptance criteria:**

- [x] Versioned material-control lineage includes company/project IDs and exact
  estimate row coordinates; the server resolves and validates every owner.
- [x] Active-estimate material-control SQL filters by stored company/project IDs
  and never grants scope from project-name equality.
- [x] Tampered, stale, ownerless and cross-company payloads fail before writes;
  repeated valid requests retain existing idempotency behavior.

**Local evidence (2026-08-07):** Material-control request lineage is version
`2`, carries the exact owner and source row coordinates, and is re-resolved
against the selected company, stored project and active estimate before any
business insert. Malformed, legacy, stale and foreign payload tests pass. The
lineage advisory lock, conflict scan and request insert now share one explicit
transaction; a source coordinate remains the idempotency key.

All five backend active-estimate boundaries and the frontend selector now use
stored owner IDs. Supply refresh propagates both IDs, AI control and estimate
activation use parameterized `company_id + project_id`, and material-norm
generation/derived estimates resolve exact server-side owners. The static
inventory reports `candidateCount=6`, `ownerScopedCount=6`,
`nameScopedCount=0` and zero violations.

The full backend suite passes `1470` tests with `10` guarded PostgreSQL skips;
the full frontend suite passes `325/325` tests in `78/78` suites; Python
compilation and the production build pass. The local read-only audit attempted
zero writes and rolled back. Its runtime inventory is ready, while its overall
`readyForCutover=false` is the expected result from the deliberately old local
schema (`dataReady=false`); production already passed that data/schema portion
under E5.3 and must be audited again after deployment.

**Production evidence (2026-08-07):** Runtime `d0f52ad81832` deployed
atomically and the service remained active. The deploy smoke and a separate
repeat of the complete public smoke both passed; rate-limited `429` responses
in the repeat were accepted by the route contract. The read-only audit returned
`ok=true`, `dataReady=true`, `schemaReady=true`, `runtimeInventoryReady=true`,
`readOnlyTransaction=true`, `writesAttempted=0` and `rolledBack=true`. It
verified `4/4` active projects, `15/15` valid active estimates, zero duplicate
scopes, name collisions or data issues, and exactly `6/6` owner-scoped runtime
boundaries with `nameScopedCount=0` and `violationCount=0`; therefore the
top-level result is `readyForCutover=true`. Authenticated protected checks were
skipped because credentials were not supplied, while the unauthenticated route
contract remained fail-closed. No schema or business-row apply was performed.

**Implementation commits:** `2be1e1bf`, `c9bd2c92`.

**Estimated scope:** M per backend slice; any schema/data apply is separately
planned and requires explicit review.

### Task E5.5: Cutover Readiness And Production Evidence

**Acceptance criteria:**

- [x] Real PostgreSQL tests prove same-name cross-company isolation, rollback
  and unchanged protected history.
- [x] The final bounded report is read-only and returns
  `readyForCutover=true` only when data and writer inventories are exact.
- [x] Deployment, public smoke and the production audit pass before E5 closes;
  no synthetic production business data is created.

**Local evidence (2026-08-07):** The final static gate inventories exactly five
reviewed E5 DML statements and requires five named real-PostgreSQL integration
checks. It rejects writer drift, protected-history mutation, missing integration
coverage and writers placed in nested E5 modules. The readiness command combines
this exact writer gate with the existing data and runtime inventories while
remaining bounded, read-only, repeatable-read, zero-write and always rolled
back.

A dedicated PostgreSQL 15 `e5_*` database ran all `5/5` integration cases. Two
companies with the same project name selected only their own active estimates;
a foreign lineage failed before insert; two concurrent identical valid requests
serialized to exactly one created row and one `409`; and SHA-256 snapshots of
work journal, acts, warehouse, delivery, supplier, invoice and payment history
remained unchanged. The final report returned all three gates ready without
including the collision name or business payload.

After the recursive-inventory review, the focused E5 package passes `26` tests
with only the five opt-in PostgreSQL cases skipped in the ordinary environment.
Full backend discovery passes `1479` tests with `14` guarded skips; frontend
passes `325/325` tests in `78/78` suites; Python compilation and the production
build pass. The local audit reports the exact `5/5` writer/test inventory and
zero violations; its overall data gate remains false only because the local
developer database intentionally has the older schema. No dependency file,
schema or business row changed. The existing CRA dependency tree still reports
`17` high npm advisories and requires a separately planned breaking toolchain
migration; E5.5 introduces none of them.

**Implementation commits:** `fe3b77e3`, `4dd2fa7f`, `8973fd45`.

**Production evidence (2026-08-07):** Runtime `ded68df1ad00` published the
frontend atomically, the `stroyka` service remained `active`, and both the
deploy smoke and its post-audit repeat returned `Smoke-check OK`. Contractually
accepted `429` responses in the repeat were rate limiting, not route failures.
The audit was read-only and rolled back with `writesAttempted=0`; it verified
`4/4` active projects, `15/15` valid active estimates, zero duplicate scopes,
name collisions or issues, all `6/6` runtime boundaries owner-scoped, and the
exact five allowed DML statements plus all five required PostgreSQL checks with
no missing checks or violations. The automated assertion printed
`OK: E5.5 cutover gate`, and the final result was `readyForCutover=true`.
Protected credentialed checks were not supplied; the unauthenticated route
contract remained fail-closed. No schema, remediation or synthetic business
row was created. This closes E5.

**Estimated scope:** M, read-only release gate.

## Task E6: Approved Project-Budget Adjustment Event

**Description:** Apply an approved customer-estimate revision delta to the
stored project contract budget through one immutable, tenant-bound financial
event, without rewriting any accounting or operational history. Draft contract:
`docs/approved-budget-adjustment-event.md`.

**Status:** The human owner accepted all three business decisions on
2026-08-07: delta semantics, director/deputy approval and retention of manual
initial-budget editing, then approved the detailed implementation slices.
E6.1 is complete in production and remains inert. E6.2.1 exact planning and
E6.2.2 guarded schema tooling are complete locally; routes, production schema,
production data and project-budget runtime behavior remain unchanged.

**Proposed acceptance criteria:**

- [ ] An approved reconciliation produces a read-only, deterministic adjustment
  preview containing exact owner/source IDs, before/delta/after amounts and a
  plan SHA-256.
- [ ] Only a server-resolved director/deputy may approve the exact plan; project
  budget and immutable event commit atomically and repeat idempotently.
- [ ] Source drift, stale hash, wrong owner/role, inactive next revision,
  concurrent conflict and negative after-budget all fail with zero writes.
- [ ] Payments, expenses, JPR, acts, supply, invoices, warehouse and estimate
  contents remain byte-for-byte unchanged.
- [ ] A guarded schema/readiness/writer inventory and dedicated PostgreSQL proof
  pass before production apply or UI enablement.

**Next action:** Deploy the inert E6.2.2 schema command and run only its
production dry-run. Review the exact production change count, names, conversion
counts and SHA-256 separately before authorizing E6.2.3 apply.

**Estimated scope:** L, split into audit/schema/runtime/UI/cutover slices.

### Task E6.1: Read-Only Budget And Source Baseline

**Description:** Establish whether exact financial events can be introduced
without coercing current data. The current `projects.budget` is floating point,
while reconciliation totals are `NUMERIC(14,2)`; this phase measures that gap
and the present writer surface without changing either one.

**Acceptance criteria:**

- [x] A pure bounded classifier rejects non-finite, negative, out-of-range or
  more-than-two-decimal project budgets and reports fixed codes plus IDs only.
- [x] Approved reconciliation candidates are checked for exact company/project,
  customer type, work package, active next revision and stored-total readiness.
- [x] The database runner is repeatable-read, read-only, hard-capped, always
  rolled back and reports `writesAttempted=0`; the static inventory finds only
  the accepted existing create/manual-edit budget writers.

**Verification:** Focused RED/GREEN unit tests, CLI output allowlist,
`git diff --check`, full backend discovery and Python compilation. A later
production run is diagnostic only and cannot execute DDL or business writes.

**Dependencies:** Accepted E6 contract.

**Files likely touched:** `backend/features/project_budget_adjustments/audit.py`,
`test_audit.py`, `readiness_report.py`, `test_readiness_report.py`,
`writer_inventory.py`, `test_writer_inventory.py`, and `package.json`, split
across three atomic commits so no increment exceeds one concern.

**Estimated scope:** Three S increments.

**Local evidence (2026-08-07):** TDD began with missing classifier,
readiness-runner and writer-inventory modules. The focused package now passes
`21/21` tests covering finite two-decimal bounds, owner/type/package/active
source checks, fixed ID-only bounded output, catalog gaps, both scan limits,
repeatable-read rollback, exact existing writers, unexpected/missing writers,
baseline E6 DML and split-static-SQL evasion. Full backend discovery passes
`1500` tests with `14` guarded skips; focused Python compilation and
`git diff --check` pass.

The local CLI returned `ok=true`, `readOnlyTransaction=true`,
`writesAttempted=0`, `rolledBack=true`, the exact `3/3` existing manual/create
budget writers, zero E6 DML and zero writer violations. Its data/schema gate
correctly remains false because the local developer database has the older
pre-tenant schema. No schema, route, dependency, runtime writer or business row
changed.

**Implementation commits:** `7c925ed3`, `cd47a45d`, `e3546f1d`.

**Production checkpoint E6.1.4:** Deploy this inert command, pass public smoke
and run `npm run audit:project-budget-adjustments` on production. E6.2 remains
blocked until that report proves bounded exact budget data and source readiness
with rollback and zero writes.

**Production evidence (2026-08-07):** Runtime `e08eddea662f` published the
frontend atomically, the `stroyka` service remained `active` and the complete
public smoke passed. The read-only production audit returned `ok=true`,
`readOnlyTransaction=true`, `writesAttempted=0`, `rolledBack=true` and
`readyForSchemaPlan=true`. It scanned all `4` projects and found all `4/4`
stored budgets safe for an exact two-decimal conversion; the current catalog is
the expected `float8` (`numericPrecision=53`), so `budgetColumnExact=false`.

All `13` stored reconciliations were scanned. None is approved, so there is no
real business candidate to preview or apply and no synthetic candidate was
created. Source readiness is green with zero issues. The static boundary found
the exact reviewed `3/3` existing create/manual budget writers, zero E6 DML and
zero violations. No schema, route, event, project budget or protected-history
row changed. This closes E6.1 and authorizes code-only E6.2 planning; it does
not authorize production DDL.

### Task E6.2: Exact Money Kernel And Guarded Schema

**Description:** Introduce deterministic decimal planning and an additive,
idempotent schema tool. The schema plan converts `projects.budget` to
`NUMERIC(14,2)` only after E6.1 proves a lossless conversion, then adds one
immutable receipt per reconciliation with restrictive ownership/source links.

**Acceptance criteria:**

- [x] Canonical plan logic derives delta and after-budget server-side, rejects
  negative after values, treats zero delta as no-op and hashes a stable payload.
- [x] Dry-run reports exact changes/count/hash; apply requires those exact
  expectations, performs no startup DDL and is repeatably zero-change afterward.
- [x] Database constraints enforce owner/source IDs, monetary equations, actor
  evidence, one receipt per reconciliation and immutable update/delete guards.

**Verification:** Pure unit tests, schema catalog/signature tests, dedicated
disposable PostgreSQL apply/repeat/rollback tests and explicit production
dry-run review before any schema apply.

**Dependencies:** E6.1 production diagnostic is data-ready.

**Estimated scope:** Two M code increments plus one separately approved
production operation.

#### Task E6.2.1: Exact Decimal Plan Kernel

**Status:** Complete locally on 2026-08-07. The pure module validates only the
exact authoritative ID/money field set, rejects silent rounding and invalid
range, derives delta and after-budget server-side, canonicalizes signed zero,
returns zero delta as a hashed non-approvable no-op and binds every ID/amount to
a stable SHA-256. Monetary JSON values are two-decimal strings to preserve the
hash through browsers.

**Verification:** Focused plan tests pass `12/12`; the complete E6 package
passes `33/33`; full backend discovery passes `1512` tests with `14` guarded
skips; compilation and `git diff --check` pass. Review found no DB, SQL,
network, dependency or runtime mutation boundary in this slice.

**Implementation commit:** `543a777b`.

**Follow-up:** E6.2.2 added only the guarded dry-run/apply schema tool. It does
not run from startup or deploy, and production apply remains blocked until its
production-specific count/hash and DDL signatures are separately reviewed.

#### Task E6.2.2: Guarded Exact-Money Schema

**Status:** Complete locally on 2026-08-07. The new operator-only command
converts `projects.budget` from `float8` to `NUMERIC(14,2)` only when a bounded
aggregate audit proves every stored value lossless. It creates one immutable
receipt table with restrictive project/reconciliation/estimate/user foreign
keys, exact monetary equations, actor evidence, one reconciliation receipt,
unique plan hash, owner/history index, a source/ownership insert guard and an
update/delete rejection trigger.

Apply requires the exact dry-run change count and SHA-256. After the guards
match, it takes an exclusive project-table lock and repeats both the data audit
and deterministic plan under that lock, closing the concurrent manual-budget
write window. Catalog or data drift rolls back before DDL. Startup and
`deploy.sh` contain no reference to the schema module.

**Verification:** The focused E6 package passes `46` tests with one explicit
dedicated-PostgreSQL skip. Full backend discovery passes `1525` tests with `15`
guarded skips. A local read-only run reported 2/2 conversion-safe project rows,
7 changes, `writesAttempted=0`, rollback and plan SHA-256
`6ee2d241f6c4b4c7e90ffda92e0542bad4ca000a2e3c42b5fb122485cf57f3d0`.
Executing all seven DDL statements plus the catalog post-check inside one local
transaction produced `schemaReadyInsideTransaction=true`, zero blockers and
zero remaining changes, then rolled the entire transaction back. Compilation,
writer inventory and `git diff --check` pass.

**Production evidence (E6.2.3):** Runtime `fecbe019380b` passed atomic deploy,
service health and complete public smoke. The production dry-run matched the
reviewed 7-change plan and SHA
`6ee2d241f6c4b4c7e90ffda92e0542bad4ca000a2e3c42b5fb122485cf57f3d0`.
The separately authorized guarded apply re-audited all four safe budgets under
the project-table lock and committed exactly seven DDL statements.

The immediate repeat reported `changeCount=0`, `schemaReady=true`, no blockers,
zero writes and rollback. The baseline audit confirmed `projects.budget` is
exact `NUMERIC(14,2)`, all `4/4` project budgets and all `13` reconciliations
remain data-ready, there are no approved reconciliation candidates, and writer
inventory remains exact `3/3` with zero E6 runtime DML. The service stayed
active and final public smoke passed. No project budget or other business row
was changed. E6.2 is closed in production.

**Next action:** Continue with E6.4.3: add the exact route/integration-test
inventory and rolled-back ledger readiness gate before any production deploy of
the approval route.

### Task E6.3: Tenant-Bound Read-Only Preview

**Description:** Expose the approved plan without enabling a writer. The server
resolves selected-company leadership context, validates the approved customer
reconciliation and recomputes exact current evidence before returning the
bounded before/delta/after contract and SHA-256.

**Acceptance criteria:**

- [x] Foreign, aggregate-company, wrong-package/type, inactive, unapproved and
  drifted sources fail closed with fixed codes and zero writes.
- [x] A valid preview contains only allowlisted owner/source IDs, monetary
  values, readiness blockers and plan hash; it never returns estimate sections.
- [x] The endpoint is authenticated and public smoke expects fail-closed auth;
  no approval route is registered in this slice.

**Verification:** Service/storage/route tests, full backend regression, public
route smoke and production read-only preview only when a genuine approved
reconciliation exists.

**Local implementation evidence:** The pure bounded total calculator, one-row
tenant storage boundary, fail-closed preview service and authenticated GET route
pass `70` focused tests with one expected dedicated-PostgreSQL skip. Full
backend discovery passes `1551` tests with `15` guarded skips. The route opens a
`REPEATABLE READ` read-only transaction, sets bounded timeouts and always rolls
back; its response is a 13-field allowlist and the slice contains no approval
route or E6 DML. Static material-control inventory now explicitly reviews all
`7/7` active-estimate boundaries and requires correlated company/project
predicates to use the same distinct alias pair.

**Production evidence:** Runtime `39af888a3ee5` deployed atomically, remained
active and passed both public smoke runs. The unauthenticated preview returned
the expected `401` backend response. Material-control readiness reported clean
`15/15` active-estimate data, exact `7/7` owner-scoped runtime boundaries,
exact `5/5` writer/integration inventory, zero violations/writes, rollback and
`readyForCutover=true`. E6 readiness confirmed exact `NUMERIC(14,2)`, safe
`4/4` project budgets, all `13` reconciliations data-ready, exact `3/3`
pre-existing project-budget writers, zero E6 DML, zero writes and rollback.
Production contains no approved reconciliation candidate, so the authenticated
success path was correctly not exercised and no fixture was created. E6.3 is
closed in production; E6.4 remains disabled.

**Dependencies:** E6.2 schema ready.

**Estimated scope:** Two M increments.

### Task E6.4: Atomic Approval Receipt And History

**Description:** Allow a selected-company director or deputy to approve exactly
the previewed hash. One transaction locks in deterministic order, revalidates
everything, inserts the immutable receipt and applies only its delta once.

**Acceptance criteria:**

- [x] Event insert and project-budget update commit or roll back together;
  duplicate approval is idempotent and conflicting/stale evidence is `409`.
- [x] Dedicated PostgreSQL tests prove concurrent double-click safety and
  byte-for-byte unchanged payment, work, act, supply, invoice and warehouse
  history.
- [x] Tenant-bound history is bounded/newest-first, and the exact static writer
  inventory permits only the receipt insert and guarded budget update added by
  E6.

**Verification:** RED/GREEN kernel and route tests, dedicated PostgreSQL
concurrency/rollback suite, writer inventory, readiness report and authenticated
missing-ID fail-closed smoke.

**Local implementation evidence (E6.4.1):** The approval input, orchestration
and storage boundaries were implemented test-first. The kernel requires a
caller-owned `SERIALIZABLE` transaction, resolves director/deputy membership
from the database, locks the tenant project, ordered project estimates and
approved reconciliation, recomputes exact current totals/hash, and fails closed
on source or stored-total drift. Its only DML is the reviewed immutable receipt
insert followed by a company/before-value-guarded project budget update;
idempotent replay returns the existing receipt and does not write again.

A fresh dedicated PostgreSQL cluster passed all `6/6` scenarios: exact apply,
idempotent repeat, stale hash/source drift, post-insert update conflict rollback,
manual budget drift, and concurrent double approval. Concurrency persisted one
receipt and one delta only. SHA-256 snapshots across 21 protected accounting and
operational tables remained unchanged. The exact static inventory now requires
`4/4` project-budget writers and exactly two E6 DML statements. Focused E6 tests
pass `85` tests with six guarded PostgreSQL skips when no DSN is supplied; full
backend discovery passes `1566` tests with `20` expected guarded skips. No API
route is registered, so this kernel is not reachable in production and no
production schema or business row was changed in E6.4.1.

**Local implementation evidence (E6.4.2):** The authenticated POST at
`/estimate-reconciliations/{id}/budget-adjustment-approval` accepts exactly one
lowercase SHA-256 field and derives company, actor and every amount server-side.
It resolves one selected-company director/deputy, then the E6.4.1 kernel
revalidates that active membership in PostgreSQL. The route owns a bounded
`SERIALIZABLE` transaction, commits only a new event/budget pair, rolls back an
idempotent repeat, and maps missing, forbidden, stale, schema and write-conflict
paths to fixed public codes.

The leadership-only GET at `/projects/{id}/budget-adjustments` runs in a
rolled-back `REPEATABLE READ` read-only transaction. It verifies the project
through `project_id + company_id`, returns an exact 17-field event allowlist,
orders by descending immutable ID and supports `beforeId` cursor pagination
with `limit <= 100`. Foreign and missing projects share the same `404`.
Unauthenticated production smoke contracts cover both routes. A five-axis
review found and fixed two FastAPI pre-handler validation leaks so missing body
and out-of-range history queries preserve fixed error codes.

Focused E6 discovery passes `98` tests with six guarded PostgreSQL skips; full
backend discovery passes `1579` tests with `20` expected guarded skips. The
static gate reports exact `4/4` project-budget writers, exactly two reviewed E6
DML statements and zero violations, and the optimized production build
compiles successfully. Ordinary manual initial budget editing and all automatic
estimate/reconciliation flows remain unchanged. Nothing was deployed and no
production schema or business row was changed in E6.4.2.

**Local implementation evidence (E6.4.3):** The final backend enablement gate
now combines the strict E6 schema, baseline owner/source data, immutable receipt
ledger, exact writer surface, route/registration/smoke inventory and required
integration proofs in one operator-facing report. Its database work runs in one
`REPEATABLE READ`, read-only transaction and always rolls back. Receipt scanning
is capped at `100000` rows and diagnostics at `100` fixed ID-only issues; the
classifier recomputes each deterministic plan hash and monetary equation,
rejects invalid identities/actors/timestamps, duplicate reconciliation/hash
evidence and current project/reconciliation/estimate/user link drift without
returning amounts, hashes or names.

The static cutover boundary requires exactly `3` E6 routes, `2` main-module
registrations, `3` unauthenticated production smoke checks, one invocation of
the approval kernel and `13` named PostgreSQL/HTTP integration scenarios.
Missing, duplicated, renamed or additional entrypoints fail closed. A fresh
dedicated UTF-8 PostgreSQL cluster passed all `7/7` tests, including concurrency,
idempotency, rollback, protected-history and a final green read-only gate whose
receipt count was unchanged. Focused E6 discovery passes `115` tests with `7`
expected no-DSN skips; full backend discovery passes `1596` tests with `21`
guarded skips; all `78` frontend suites / `325` tests and the optimized
production build pass. Compilation and `git diff --check` are clean.

**Implementation commits:** `910fb9ce`, `aff86523`, `9965cf6e`, `0efb6f29`.

**Next action:** Push the reviewed E6.4.3 commits, then use a separate production
deploy checkpoint. After deployment run the public smoke and
`npm run audit:project-budget-adjustments`; require exact schema/data/ledger/
writer/route/test readiness, zero writes, rollback and
`readyForCutover=true`. Do not manufacture an approved reconciliation or
financial receipt for smoke.

**Dependencies:** E6.3 preview contract production-green.

**Estimated scope:** Three M increments.

### Task E6.5: Explicit Leader UI

**Description:** Add a visible preview, exact confirmation and immutable history
for directors/deputies. Reconciliation approval and estimate activation remain
separate and never auto-apply a budget change.

**Acceptance criteria:**

- [x] Only authorized leaders see the action; all users may see only history
  already allowed by their project access and financial visibility.
- [x] Confirmation displays before, delta and after, submits the exact hash once
  and handles stale/conflict/idempotent responses without optimistic mutation.
- [x] Component/action tests cover role visibility, loading, error, refresh and
  no automatic approval path.

**Implementation evidence (2026-08-07):** The selected-company role now controls
both reconciliation and budget actions. The bounded client allowlists canonical
IDs/money/hash/receipt fields, verifies both exact-cent equations, sends only
`{"planSha256":...}` and maps fixed public errors. The responsive panel keeps
preview, explicit confirmation and immutable cursor history separate from
reconciliation approval. Focused frontend coverage passed `31/31`; the full
frontend suite passed `342/342`, and isolated Chromium checks at `1280x800` and
`390x844` confirmed accessible controls, exact before/delta/after values,
history, live success status, zero API traffic in the harness and zero console
errors.

**Dependencies:** E6.4 backend production-green.

**Estimated scope:** Two M increments.

### Task E6.6: Final Cutover Evidence

**Description:** Combine exact schema/data/ledger/writer/integration gates into
one bounded read-only production report and close E6 only after all release
evidence is green.

**Acceptance criteria:**

- [ ] Focused/full backend and frontend suites, compilation, build and smoke
  pass from a clean tree.
- [x] Real PostgreSQL proves same-name cross-company isolation, rollback,
  concurrency/idempotency and unchanged protected history.
- [ ] Production audit is read-only, rolled back, zero-write and ready; no
  synthetic reconciliation or financial event is created for smoke testing.

**Local release evidence (2026-08-07):** The E6 package passed `117` tests, the
full backend passed `1598` (`21` expected skips), the full frontend passed
`342/342`, the optimized build
compiled, and the dedicated `e6_codex_20260807` PostgreSQL fixture passed all
`7/7` rollback/concurrency/protected-history scenarios before the temporary
database was removed. The final cutover inventory now also requires exact
frontend wiring `11/11` and named UI/action proofs `17/17`; either drift makes
`readyForCutover=false`. The remaining checkpoint is a clean push followed by
production deploy, public smoke and the rolled-back zero-write production
audit. No production reconciliation or receipt will be manufactured.

**Dependencies:** E6.1-E6.5 complete.

**Estimated scope:** M, release gate only.
