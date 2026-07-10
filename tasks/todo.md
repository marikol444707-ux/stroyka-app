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

**Status:** Implemented locally; release pending.

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
