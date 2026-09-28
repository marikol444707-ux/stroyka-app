# Refund allocation calculation

Implemented a pure planner in refund_allocation_plan.py, not mounted in runtime.
The caller must provide a complete authorized and consistent invoice snapshot.
Each refund names its original payment. The caller explicitly selects receipt
coverage to release and the amount to take from that payment's free balance.
Opening paid and other payments cannot fund that refund. Refund reversal restores
free money without implicitly restoring receipt assignments. Original payment
amounts remain immutable; net amounts exist only in the projection.

Validation covers exact monetary amounts, scoped identities, unique refund IDs,
source capacity after prior refunds, reversed payments, duplicate designations,
and release conservation. Historical assignments of reversed payments are
validated before being omitted from the proposed active revision.

Validation: 34 unit tests passed across test_refund_allocation_plan and
 test_allocation_projection, including 100 cent-level conservation scenarios.
No production data, runtime routes, SQL guards, or migrations were changed.

Next: persist the original-payment relation and allocation revision atomically;
prove concurrency, idempotency, rollback, authorization and reversal constraints
with PostgreSQL tests before changing existing refund/allocation guards. Then
connect API and UI. Credits and VAT corrections require separate treatment.

## Strict command contract

`refund_commands.normalize_refund_command` accepts exactly requestId, groupId,
expectedVersion, paymentId, amount, unallocatedAmount, paidAt, reason, releases.
Release rows contain receiptId and amount; duplicate receipts fail. Amounts are
strings or integers, never JSON floats or booleans. Normalized rows are sorted so
row order does not change the idempotency fingerprint. Release total plus free
amount must exactly equal the refund. Company and actor come from trusted request
context, never the body. The expectedVersion is syntax-checked here; comparing it
with the locked current revision remains the transaction service's responsibility.

Validation: 49 tests passed (refund commands, refund planner, allocation projection,
allocation commands). This is command validation only, not saved-UUID replay,
rollback, concurrent write, database authorization or end-to-end verification.
The atomic database integration and runtime activation remain outstanding.
