# Atomic allocated refunds (local, not released)

The internal `refund_store.refund` service now saves the complete replacement
allocation revision, the cash refund and its original-payment link in one
transaction. `engine.execute_in_transaction` reuses the existing payment engine
without committing independently. Existing public payment routes still call the
transaction-owning `execute` wrapper.

Current allocation authority runs before UUID replay or version checks. An
identical authorized retry returns the original operation and revision; a changed
body conflicts. The company advisory lock serializes payments and allocations;
expectedVersion rejects stale maps. Allocation revisions use a deterministic
internal UUID in the existing guarded namespace. New refunds are default-off via
SUPPLIER_ALLOCATED_REFUNDS_ENABLED, in addition to the existing settlements flag.
Replay remains available with that feature flag off, after authority/schema checks.

Migration 0059 adds immutable source links and deferred net-capacity checks.
It verifies the same invoice/company/payer/supplier, original payment impact, and
same-transaction refund and revision. Cash refunds cannot exceed their source
payment; the source cannot be reversed while a linked refund remains active.
Latest receipt coverage cannot exceed payment minus active refunds. A refund
reversal restores free money and leaves the released coverage unchanged.

Old unlinked refunds and credits retain conservative guards. They cannot be mixed
with linked-refund history while active. Historical balances are not backfilled,
opening money is not assigned a fabricated payment, and receipt amounts/stock
never change. Downgrade restores exact prior guards only if no refund links exist.
Disabled prerequisite guards cause a 503 before new writes or replay.

## Verification

- 12 PostgreSQL service tests: save/replay, reversal, competing UUIDs and versions,
  revoked membership, real financial authority, complete rollback on deferred
  failure, direct-SQL net caps, planner-bypass capacity rejection, immutable
  evidence, downgrade refusal, disabled flag/trigger, and no unlinked bypass.
- 10 existing HTTP settlement tests pass after migration chain 0055–0059.
- 14 existing allocation service PostgreSQL tests pass on the prior schema.
- Unit discovery: 146 tests passed; PostgreSQL opt-in cases are skipped there and
  are executed separately as above. Updated one stale read-test mock to include
  the settlement-schema readiness column; no production read logic was changed.

The integration fixture emits existing synthetic auto-control owner warnings;
those background workflows are not covered by these financial assertions.

## Remaining release work

No new HTTP refund endpoint is mounted, no UI is connected, and no server was
updated. The real allocation authority tested here accepts the conservative
0049 zero-VAT receipt proof. Before runtime activation, adapt and test authority
for current sealed invoice-line receipts (0052/0056), including VAT and current
scope denial. Then add the API boundary, lost-response recovery UI, full browser
workflow, deployment and production verification. Credits/VAT corrections remain
separate from cash refunds; this increment does not enable them for allocations.
