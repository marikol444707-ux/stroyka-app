# Allocation persistence: local verification checkpoint

Historical storage checkpoint. Subsequent current-authority and unmounted API
verification: `supplier-payment-allocation-api-check-2026-09-18.md`.

Implemented locally: additive 0021 schema, strict command normalizer, caller-owned
replace/read workers, and transaction-owning save wrapper. No mounted HTTP/UI,
production migration, original-worktree edits, real notification or payment.
Decision and limitations: `docs/decisions/0006-explicit-receipt-allocation-revisions.md`.

## Contract

`replace_allocations(get_db, authorize_and_lock, actor_id, company_id, body)` owns
commit/rollback. Its `replace_allocations_in_transaction(cur, ...)` counterpart
neither commits nor closes the caller transaction. Both require current authority
before UUID replay or expected-version comparison.

Body: `{requestId, groupId, expectedVersion, reason, rows}`. Each row contains
`{paymentId, receiptId, amount}`; **receiptId is the receipt-relation ID**, not the
warehouse invoice ID. This distinction is covered with deliberately offset IDs.
Rows are the complete replacement map, at most 2000 per invoice; empty is valid.
Duplicate pairs, unknown/server-owned fields, float amounts and sub-kopecks fail.
Canonical ordering makes equivalent maps produce the same fingerprint.

Saved response: `{revisionId, groupId, version, requestId}`. Replay retains that
response even after subsequent revisions/reversal. Current read is separate:
balances/version plus active `allocations` and historical `reversedAllocations`.
It creates no allocations and no baselines. Deadline adapter is not connected:
receipt dates are explicitly unknown in this storage reader, not invented.

## Independent main-agent verification

All databases were new synthetic `supply_chain_test_*` databases on the private
Unix-only PostgreSQL at `/tmp/stroyka-private-rehearsal.geQFDWCn`, port 55442.
Run each fixture class against its own empty database; do not run all classes
against one database. Main independently observed:

| Suite | Passed | Database suffix |
|---|---:|---|
| `test_allocation_storage_postgres.AllocationStorageTests` | 19 | `alloc_storage_main_20260918a` |
| `test_allocation_storage_postgres.AllocationCommittedTests` | 4 | `alloc_committed_main_20260918a` |
| `test_allocation_store_postgres.AllocationStorePostgresTests` | 14 | `alloc_store_main_20260918a` |
| `test_allocation_compatibility_postgres.AllocationCompatibilityTests` | 10 | `allocation_compat_20260918c` |

Total for these explicitly named PG runs: **47 passed**. Separately **44 unit/
contract tests passed**: allocation projection/commands/read shape/signatures and
existing payment commands/policy/attachment commands. No browser/full-project
test or real authorization adapter completion is inferred from these results.

Covered: immutable correction/empty-map release, exact UUID replay and conflict,
current synthetic membership revocation before replay, competing CAS, concurrent
same UUID, allocation vs actual payment reversal in both lock orders, stale map
rejection, historical coverage invalidation, per-source/receipt capacity, caller
transaction preservation, deferred failure rollback, sealed rows, forged XID,
cross-company legacy link race, mode/namespace exclusion, frozen provenance,
exact SQL monetary precision and nonempty downgrade refusal. No new financial/
stock writes from allocation save are asserted by before/after table snapshots.

RED/GREEN: missing new modules, absent editable read map, SQL sub-kopeck rounding,
contract-binding mutation and cross-company admission defects were tested/fixed.
Independent schema/service reviewers accepted the bounded internal scope after
fixes. Early compatibility runs failed on old synthetic fixtures lacking current
provenance columns and explicit item package; only the fixture was updated. The
production package validator was not weakened. Final 10 compatibility cases pass.

## Remaining gates

1. Authoritative partial-receipt registration with immutable invoice-line quantity
   accounting; production owner/payer/project/package authorization adapter.
2. Default-off API/editor confirmation, real due dates, reminder semantics and
   supplier/company cabinet integration. Current reader is not a deadline service.
3. Safe writer lock ordering across all legacy paths and metadata correction
   policy for frozen receipts; full browser→API→PG and broader regressions.
4. Copied-data migration rehearsal with writers stopped, separately authorized
   production migration/activation. Historical full-value mirrors are not imported.

Work saved locally; no GitHub push or production operation is part of this slice.
