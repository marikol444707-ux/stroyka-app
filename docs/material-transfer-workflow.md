# Material transfer business-cycle rehearsal

Current integration and release status: [2026-09-18 release](warehouse-release-2026-09-18.md).
Earlier milestones below describe the development branch, not the deployed state.

Local follow-up to `warehouse-distribution.md`. No production deployment,
real user documents, supplier payments or notification sends.

The subsequent [integrated stock-chain block](stock-chain-integration.md) covers
receipt/distribution interleavings, executor issue versus allocation return,
receipt rollback/replay and original source-line projection/selection.

## Quantity validation repair

Create/return previously converted `quantity` with `float(...)` and compared it
only with zero. `NaN`, positive infinity and overflowing numeric strings passed
that check; invalid text raised an uncaught conversion error; JSON `true` became
one unit. Regression tests reproduced eight failing subcases and two uncaught
exceptions before the fix. Both handlers now reject boolean, unconvertible,
non-finite and nonpositive quantities with HTTP 400. Positive numeric strings,
including fractional/scientific notation, remain supported.

This rejection precedes the handler's `get_db`, not authentication dependencies,
which may already query the database. No role or authorization rule changed.
This patch does not migrate legacy FLOAT quantities to exact decimal arithmetic,
repair previously corrupted stock, or impose a new business quantity cap.

## Company-scoped estimate aggregates

The first five full-cycle cases passed with one company's stock. Adding company
3's seven units with the same project/material/unit/package names made company
2's legitimate issue fail: the estimate remainder became -5. The sentinel was
retained rather than renamed or removed. `_supply_material_estimate_control`
resolved an explicit company/project owner but omitted company predicates on
several downstream aggregate reads.

Stock, return history, work-journal consumption, open requests and deliveries now
use the already-resolved owner's `company_id`. Delivery reads additionally keep
their request ID, and request exclusion parameters retain their original order
after the company parameter. Role/membership authorization is unchanged. This
repair isolates arithmetic inputs; it does not close the separate legacy
material-directory access gap or company scope of name-based material aliases.

## Full handler coverage

`backend/features/material_traceability/test_transfer_workflow_postgres.py`
reuses the guarded `supplier_access.test_postgres_chain_support.build_fixture`.
It executes the complete registered HTTP endpoints with real signed tokens,
authentication dependencies, company membership, project/transfer ownership,
recipient/package checks, estimate control, stock writes and personal-balance
queries. Unlike the earlier boundary tests, no parent callback or synthetic
replacement stock mutation stops the handler early.

Covered business states:

- Issue from object stock to an active assigned recipient: stock decreases, the
  transfer and expense history point to the issued quantity and transfer ID.
- Unsigned issue has no available personal balance. The intended recipient signs;
  replaying the signature changes neither stock nor history.
- Partial then full return restores object stock and decreases available personal
  balance. Returning more than available is rejected without business writes.
- Cancelling an unsigned transfer restores stock once; repeated cancellation is
  stable. Signed transfers cannot be cancelled; cancelled transfers cannot sign.
- Foreign company, wrong role, wrong package and another recipient are denied.
  A worker cannot return another worker's balance by supplying their ID/name.
- A database trigger injects failure while inserting history. Create, return and
  cancellation must roll back their preceding stock/transfer writes together.
- Authenticated NaN/text quantity requests return 400 with unchanged business data.
- Two authenticated full-return requests are held at the real PostgreSQL stock
  lock concurrently, then released. Exactly one may credit stock and history;
  the other must see the updated balance and reject over-return.
- Same-name foreign stock stays unchanged through each lifecycle case. A separate
  projection case seeds foreign return history, consumption and requests, plus a
  deliberately inconsistent foreign delivery pointing to an own-company request;
  these must not change the selected company's calculation.
- Own-company delivery of 0.5 reduces a one-unit open request to 0.5; excluding
  that own request reduces its requested contribution to zero. This positive
  counterpart guards against accidentally filtering out every delivery/request.

## Isolation and limits

Every full-workflow run needs a NEW, empty UTF-8 `supply_chain_test_*` database,
owned by the local test user, over an explicit Unix socket. The fixture rejects
ambient production connection settings, suppresses `.env` loading and blocks
outbound network access. It leaves the synthetic schema/data for inspection;
do not reuse that nonempty database for another run. Other distribution fixtures
have a different cleanup contract and must not share this database concurrently.

The fixture bootstraps existing schema with documented prerequisites and applies
migration 0012, so the real schema-gated compatibility lock is active. It does
not prove migration from a representative production baseline. Only postcommit
AI control is patched out; login and 2FA challenge flows, external integrations
and browser interaction are not exercised by issuing pre-signed test tokens.

Injected-error requests reveal the already-known bootstrap logging gap:
`api_errors.owner_scope` is absent. Business rollback is checked directly; full
error-log ownership must be verified against the complete migration schema.
Do not hide that limitation behind passing transaction assertions.

Remaining: full authenticated transfer/distribution interleavings, receipt DDL
lock order, work-journal consumption versus returns, same-name/renamed-person
history identity, source-row ambiguity and legacy FLOAT precision, load/bounded
waits, and the separate legacy material-directory company-policy decision.
This is not a blanket statement that all stock writers or the SaaS are ready.

## Running

With a newly provisioned empty UTF-8 test database:

```sh
SUPPLY_CHAIN_RUN_POSTGRES=1 \
SUPPLY_CHAIN_TEST_DB_HOST=/absolute/path/to/test/socket \
SUPPLY_CHAIN_TEST_DB_PORT=55439 \
SUPPLY_CHAIN_TEST_DB_NAME=supply_chain_test_unique_run \
python -B -m unittest backend.features.material_traceability.test_transfer_workflow_postgres -v
```

Small quantity regression: `python -B -m unittest
backend.features.material_traceability.test_transfer_quantity -v`.

## Verification checkpoint

Final full-workflow suite: seven tests passed on a new UTF-8 database in both the
worker run and an independent main-agent run. The cases include a real forced
overlap of two return handlers at the PostgreSQL lock and unchanged foreign
sentinels. Related unit suites passed 180 tests. Three expected injected-error
requests emitted the known `api_errors.owner_scope` warning; no assertion was
removed to conceal it. Syntax and diff checks passed. Independent source review
found no outstanding critical/required changes in this bounded patch.

The final existing PostgreSQL regression run also passed all 31 metadata,
lock-protocol and distribution tests on a separate empty UTF-8 database. Total:
218 distinct tests, including 38 PostgreSQL tests (7 authenticated workflow +
31 regression). Repeated runs are not counted twice.

No frontend changes or new dependencies; the previous general frontend timeouts
remain unresolved. These tests do not authorize enabling production flags.
