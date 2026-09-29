# Supplier allocated-refund form — 2026-09-28

Local implementation; not deployed or enabled in production.

The invoice payment dialog now offers an explicitly selected source payment,
free cash amount and amounts released from individual receipt allocations.
The total is calculated from those parts. Date, reason and confirmation that
the money was actually received are required. No automatic receipt selection.

The authenticated `refund-context/{invoice_id}` read returns complete source
capacities and physical warehouse receipt identifiers. Existing document and
allocation permissions apply before data is returned. Reads roll back.

The client validates scope, exact money and allocation conservation. Before
sending, it persists the exact UUID, command and source snapshot under an
API/user/company/invoice key. Web Locks prevent simultaneous tab submissions.
Failures, including conflicts, retain the command. Reload restores it; retry
uses the same UUID. Cancellation persists its intent and uses the existing
server cancellation tombstone protocol. A committed refund is confirmed, never
automatically reversed. Storage failures block submission.

## Verification

- Supplier payments frontend: 118 tests in 10 suites pass.
- Supplier payments Python discovery: 146 passed; 717 PostgreSQL opt-in tests
  skipped in this invocation (not counted as passed).
- Real PostgreSQL refund/VAT HTTP class: 11 tests pass, including source context
  permissions/capacities and cancellation before/after commit.
- Production frontend build with payments, opening confirmations and allocated
  refunds enabled: compiled successfully.
- Headed Chromium at 390×844 against actual React dialog and real HTTP backend
  in a disposable PostgreSQL database: source payment 120, allocations 80+20,
  free 20. Submitted refund 25 (receipt release 20, free 5). Proxy deliberately
  discarded the first successful response after commit. Reload restored the
  pending command; retry confirmed the original operation. UI debt became 105.
  Database assertions passed: exactly one refund of 25, paid 95, allocated 80,
  free 15, unchanged stock and receipt VAT total 34. One expected browser
  ERR_EMPTY_RESPONSE; no application exception. Test server and browser closed.

## Release requirements

Requires the preceding allocated-refund API and migrations through 0059, all
existing payment/allocation/settlement backend gates, and the explicit backend
`SUPPLIER_ALLOCATED_REFUNDS_ENABLED` gate. Frontend requires
`REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED=true` in addition to the payment
feature flag. Defaults remain off. Production migration/readiness verification
and deployment remain separate work; this local browser run is not evidence
that the production feature is enabled.
