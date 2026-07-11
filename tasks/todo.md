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

**Status:** Implementation complete locally; production dry-run/apply/post-audit pending.

**Acceptance criteria:**
- [ ] Dry-run repeats the current production gate exactly: `totalRows=4`, `ready=4`, no review rows, and all candidates target company `1` / project `1`.
- [x] Apply requires an explicit confirmation token, expected count, and SHA-256 of the complete dry-run plan; it rechecks every ownership source inside one transaction and rolls back on any drift or conflict.
- [x] Columns and supporting indexes are added reversibly; ambiguous rows are never guessed, and no `NOT NULL` or foreign key is added yet.
- [x] Existing estimate-change CRUD, include/reconcile, and AI routes remain behaviorally unchanged until a later tenant-scoping slice.

**Verification:**
- [x] Migration/report tests cover pre-column, dry-run, apply, same-count ownership drift, idempotent rerun, exception/conflict rollback, and post-apply states (`17` focused tests); the clean release backend suite passes (`198` tests), M6 registry audit and production build pass.
- [ ] Production before/after counts and ownership audit are identical except for the four guarded owner assignments.

**Production apply order:** push the migration code and run only `git pull --ff-only` on the server without restarting the service. Run `python3 scripts/migrate-estimate-changes.py --dry-run`, require the same `readyCount=4` and empty review list, copy its `planSha256`, then run `python3 scripts/migrate-estimate-changes.py --apply --confirm APPLY_ESTIMATE_CHANGES --expected-ready-count 4 --expected-plan-sha256 <planSha256>` and repeat the dry-run. Only after the clean post-audit may `bash deploy.sh` restart the runtime. Any count or mapping drift, review row, lock timeout, row-count conflict, or failed post-check rolls the transaction back.

**Dependencies:** Task M6.4f

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

## Task 12: Extract Auth Helpers

**Description:** Move auth/session helper functions from `backend/main.py` into `backend/auth.py` without changing behavior.

**Acceptance criteria:**
- [ ] Route behavior is unchanged.
- [ ] `backend/main.py` imports auth helpers.
- [ ] No schema or business logic changes are mixed into this extraction.

**Verification:**
- [ ] `PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py backend/auth.py`
- [ ] `npm run smoke:auth-session`

**Dependencies:** Task 5

**Files likely touched:**
- `backend/main.py`
- `backend/auth.py`

**Estimated scope:** S

## Task 13: Extract Audit And Client Error Routes

**Description:** Move low-coupling audit/client-error endpoints into a feature module while preserving route paths.

**Acceptance criteria:**
- [ ] Existing audit/client-error endpoints keep the same URLs.
- [ ] Logging still writes the same payload fields.
- [ ] `backend/main.py` only registers the module.

**Verification:**
- [ ] Backend compile passes.
- [ ] `npm run smoke:activity-log`

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

**Status:** Deployed in `0d95c3d5`; public production smoke passed.

**Acceptance criteria:**
- [x] `package.json` and direct dependency versions remain unchanged.
- [x] `package-lock.json` receives only SemVer-compatible updates calculated by `npm audit fix` without `--force`.
- [x] `deploy.sh` installs the exact lock-file tree with `npm ci` before building and restarting the service.
- [x] The critical `shell-quote` advisory is removed; audit totals fall from `40` to `29` and critical findings from `1` to `0`.
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

**Dependencies:** Task P2

**Estimated scope:** M

## Task P4: Reconnect Confirmed Material Rows To Supply

**Description:** Restore batch request creation with lineage and idempotency, then verify the complete supplier chain.

**Dependencies:** Task P3

**Estimated scope:** M

## Task P5: Cache And Cut Over Material Projection

**Description:** Move repeated heavy calculation out of React renders, add package-level loading, shadow verification, and staged rollout.

**Dependencies:** Task P4

**Estimated scope:** M
