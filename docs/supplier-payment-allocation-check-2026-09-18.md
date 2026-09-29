# Optional receipt allocation: internal calculation checkpoint

Later persistence checkpoint: `supplier-payment-allocation-storage-check-2026-09-18.md`.
The following records the earlier pure-calculation slice, not current full scope.

Status: local pure projection only. No migration, mounted route, financial write,
production activation, historical reassignment, email, or real bank transfer.

## Implemented

`backend/features/supplier_payments/allocation_projection.py` takes a complete
server-authorized snapshot for one invoice and returns exact decimal strings:

- Invoice remaining = invoice amount − opening paid − active new payments.
- Allocated coverage belongs to a specific payment and receipt. Its sum cannot
  exceed either source payment or target receipt. Cross-invoice/company/payer/
  supplier snapshots and duplicate/dangling IDs are rejected.
- Reversed payment designations remain in supplied history but give no effective
  receipt coverage. Other payment designations do not move.
- Unallocated new payments and opening paid are separate. Opening paid affects
  invoice debt but is not fabricated into a new payment or automatic suggestion.
- Earliest due receipt suggestions are separate from confirmed balances. Undated
  receipts follow dated receipts; stable IDs settle ties. Suggestions cannot
  exceed receipt capacity, including when payment precedes receipt.

The projection deliberately does not create/validate an audit event stream.
The future transaction adapter must provide current confirmed allocation rows,
excluding superseded corrections, plus authentic reversal state. A caller cannot
use this calculation as an authorization or historical integrity certificate.
Per-object/package permissions remain the responsibility of that adapter; scope
equality in a pure function is not a permission grant.

## Verification

- Initial test run failed because the new module did not exist (RED).
- 17 initial tests passed after implementation.
- Further RED tests exposed boolean scope identity, undated/date.max ordering,
  and invalid historical reversed allocation capacity; fixes pass all 22 tests.
- Combined with existing commands, policy and attachment command suites:
  **34 tests passed**. No PostgreSQL/browser verification is claimed for this slice.
- Independent read-only review reproduced scope/date defects; they were fixed.
- Money uses the existing exact-money validator and Decimal; float, nonfinite,
  sub-kopeck, nonpositive operation and inconsistent totals are rejected.

Reproduce:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/stroyka-pdf-check.hCRQnw/venv/bin/python -m unittest \
  backend.features.supplier_payments.test_allocation_projection \
  backend.features.supplier_payments.test_commands \
  backend.features.supplier_payments.test_policy \
  backend.features.supplier_payments.test_attachment_commands -q
```

## Compatibility and next gates

0018 is a full-value single-receipt mirror: unique pair, equal amounts and paid
balances. It is NOT an explicit allocation and must not be converted by relaxing
one constraint. Existing records and baselines remain unchanged.

Before real usage, introduce mutually exclusive explicit-allocation and legacy
mirror groups, proven partial receipt relationships, append-only allocation audit,
current permissions, transaction serialization and idempotent confirmation/
correction. Full payment reversal must release its own coverage in the same
transaction without changing stock or creating another expense.

Test true PostgreSQL concurrent allocation/reversal/replay and late rollback,
then default-off API/UI confirmation and browser→API→DB. A list of uncovered
receipt amounts is not extra debt on top of invoice debt. Reminders must expose
unallocated money rather than assert a final receipt debt before reconciliation.
Copied-data migration rehearsal and separately authorized activation remain open.
