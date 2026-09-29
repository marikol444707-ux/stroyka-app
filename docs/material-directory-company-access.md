# Material directory company access

Current integration and release status: [2026-09-18 release](warehouse-release-2026-09-18.md).
Earlier milestones below describe the development branch, not the deployed state.

Approved and implemented locally, 2026-09-16. No production rollout.

## Contract and reason

Previously `/materials` read across companies, POST omitted `company_id`, and
PUT selected/updated by material ID alone. This bypassed tenant boundaries even
when company context headers were sent by the existing frontend API wrapper.

- GET, POST and PUT resolve the existing `X-Company-Id` / `X-Company-Mode`
  contract through the shared company resolver, then require an active real
  membership in an active company. Legacy profile and account-only fallback
  contexts do not grant material access. No shared resolver behavior changed.
- GET supports `all_companies`: SQL combines separately authorized company,
  project and package predicates, then performs one global sort and pagination.
  Stock and price masking uses each row's company role, never the global role.
  Customer/supervisor exclusion and existing warehouse-role branches remain.
- POST/PUT accept optional strictly positive integer `companyId`. A header/body
  mismatch returns 409; aggregate-mode writes return 400. Omitted context uses
  the shared resolver's default membership, not a database default company.
- Creation persists explicit company ownership and returns `companyId`.
  Creation audit includes authenticated user ID and explicit company ownership.
- PUT authorizes the selected company before the shared stock lock; both the
  row lock and UPDATE include `id AND company_id`. Foreign IDs return 404.
  No material/project read is inserted ahead of the shared stock lock.
- Object quantities cannot be edited directly; document workflows remain
  mandatory. Metadata-only updates never assign object quantity. Physical
  DELETE stays disabled. No migration or stock adjustment is performed.

## Verification

Three unit reproductions failed on the old implementation (unscoped read,
implicit creation owner, unscoped ID update) and pass after the fix.

85 unit tests: materials routes, company context, stock guards/lock boundary,
material transfer access, project access and audit ownership runtime.

10 full authenticated HTTP/PostgreSQL cases in `test_company_postgres.py`:
same-name isolation/search; non-default company create/update/audit; foreign-ID
invariance; claim mismatch/aggregate write/strict ID rejection; effective-role
write denial and per-row masking/global pagination; revoked membership;
inactive company; missing membership; selected and aggregate project/package
restrictions; document-only object quantity. No authentication or SQL mocks.

31 PostgreSQL regressions: metadata commit/rollback, transfer shared locks and
warehouse distribution. The metadata transaction fixture injects an authorized
company actor; the full HTTP suite separately verifies real authorization.

8 integrated authenticated stock-chain PostgreSQL cases also passed, including
receipt/distribution/executor races and late persistence rollback. Two deliberate
fault injections reproduce the already documented missing `api_errors.owner_scope`
logging column in the synthetic bootstrap; stock assertions passed. This is not
a new production logging readiness claim. Total: 134 distinct passing tests.

All databases were fresh isolated UTF8 databases on the local Unix-only test
cluster, with outbound network blocked by the fixture. Final material test DB:
`supply_chain_test_material_company_20260916_c`; metadata/distribution:
`supply_chain_test_material_regression_20260916_a`; stock chain:
`supply_chain_test_material_stock_chain_20260916_a`.

Independent read-only review found no actionable regressions; its missing
mixed-company project/package denial coverage was added. Frontend code was not
changed; no new browser/build result is claimed.

## Release limits and remaining work

Existing installations must verify actual active memberships before rollout:
legacy-profile-only users will now receive 403. This is intentional, not a
reason to silently recreate revoked memberships. No automatic backfill ran.

The existing audit writer remains postcommit/best-effort. Same-name project
resolution in other legacy commands, global material aliases, personal-stock
identity, atomic multi-row issue and release/load/backup gates remain separate
work. This block does not certify all SaaS endpoints or the supplier billing
and document workflows. Supplier cabinet access is unchanged.
