# Work-owner fixture schema correction — 2026-10-31

Base: 5900362c8e18862d0afbac083d8dcd4d0962fc84. Local-only followup on
fix/audit-stabilization-20261031. No product handlers or migrations changed.

## Observed CI evidence

Run 41195621137, job 124521079702:
https://github.com/marikol444707-ux/stroyka-app/actions/runs/41195621137/job/124521079702

Backend: 6179 counted, OK (skipped=2329), therefore 3850 passed and 2329 skipped.
Company-context PostgreSQL: 10 passed. Acceptance: 13 failures, all at
work_acceptance/test_postgres.py:74 in setUp creating the initial journal.
No acceptance test body was reached. Contractor-contract class was not run:
the launcher returns on the preceding class's nonzero exit. Supplier/frontend
were skipped. These are historical CI observations, not new execution results.

POST /work-journal reached _sync_room_work_from_journal and the name-based
_room_work_duplicate query against room_works.company_id. The legacy fixture
omitted migration 0107. The request contained an owned journal; this was not a
missing HTTP companyId. Logging the failure also failed because api_errors lacked
owner_scope; legacy init_db does not prepare its current ownership schema.

## Limited correction

The shared helper now has an opt-in work_owners profile, selected by transfer/work
fixture ancestry and the contractor-contract class. Other fixture profiles keep
their existing migration ownership/order.

The profile reuses the exact projects(id,company_id) unique-index statement from
0023, then complete existing upgrades 0103, 0104, 0106 and 0107. It reuses
api_error_ownership.migration._ensure_schema for the logger. No owner backfill,
company fallback, weakened guards, modified constraints or copied business rules.

This is a PARTIAL fixture schema, not a full Alembic upgrade. It does not stamp
head or mark any migration applied. Only the composite-key prerequisite is taken
from 0023; its unrelated quality journal triggers/tables are not provisioned by
this profile. Payment migration 0105 and command migration 0108 are outside this
work-owner profile and are not represented as applied. It is unsuitable as a
production migration procedure or proof of full upgrade compatibility.

0104 was inspected: all six legacy tables already have CREATE declarations in
init_db, including interim_acts; its full upgrade supplies owner columns, paired
CHECKs and composite FKs. 0106 supplies the same exact-owner boundary for
existing document_versions. Both upgrades are included, not just room_works.

Before seed and importing the HTTP application, readiness queries check owner
columns, the composite unique index, named validated CHECK/FK constraints and
exact composite FK definitions. A missing dependency raises a schema preparation
error before HTTP setup. CHECK expressions themselves come unchanged from the
existing complete upgrades; readiness checks their presence/type/validation,
not semantic equivalence of arbitrary pre-existing CHECK expressions.

## Verification performed

Command (no database, app startup, HTTP or network):

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest -v backend.features.supplier_access.test_work_owner_fixture_static

Final run: 7 passed, 0 failed, 0 skipped. Uses recorded SQL/catalog mocks only.
Covers reuse of full DDL, changed prerequisite rejection, missing columns,
incorrect FK/nonunique project key/unvalidated CHECK rejection, transaction
exception propagation/connection closing, opt-in caller wiring and preparation
ordering and explicit RealDictCursor selection for catalog rows. Manual review
against backend/db.py caught the need for that explicit cursor; it is covered
in the final run. Mock context handling does not prove PostgreSQL rollback behavior.

git diff --check passed.

Initial attempt with the generic python interpreter: 6 passed, 1 import error
resolving the logger migration (dependency environment); existing project .venv
resolved it. During manual diff review the owner preparation call was found
before schema_runtime initialization, moved after _initialize_schema, and the
ordering assertion strengthened before the final successful run. These runs
are not added together as independent coverage.

## Remaining limits

No PostgreSQL/HTTP/CI runs, stand restoration, production access, push, merge,
deployment or migration application. The prior prohibited global audit was not
repeated. SQL execution, catalog formatting on actual PG, subsequent acceptance
logic, real rollback and migration compatibility still require separately
permitted runtime verification. This change does not claim the CI chain is green
or the audit complete. No new databases, containers or temporary checkouts were
created; report, patch and tests are retained deliverables.
