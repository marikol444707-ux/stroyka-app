# Explicit original review of unused legacy invoice lines

## Local status and scope

Implemented locally, not deployed or enabled in production. Migration 0063 is
additive and performs no historical backfill. The reviewed invoice keeps its ID,
amount, VAT, status, paid amount and original birth metadata unchanged.

Eligible invoices have a checked bound contract, explicit VAT (including zero),
status «На утверждении», exactly zero paid, no payment-ledger registration, no
warehouse link in either direction, no shipment for their offer and no sealed
specification. Already used/approved/paid invoices are deliberately rejected.
This is admission before future prepayment, not repair of prior cash or receipts.

The buyer/accountant selects the original file and confirms every position and
its explicit tax. Names, units, work package, quantities, prices, line totals and
source positions must match the locked approved KP/request and invoice total.
VAT is checked per line against the stored invoice VAT. Missing VAT is not zero;
no tax rate, exemption, quantity, price or allocation is inferred.

## Evidence and concurrency

GET/POST `/supplier-invoices/{id}/legacy-line-review` require current company,
project/package, buyer and payer authority. Suppliers cannot attest this review.
POST requires a UUID, exact contract/amount, original file, complete reviewed
lines, total VAT, reason and explicit confirmation. The protected file must belong
to the invoice company and, if project-scoped, the same project. It is retained.

The transition uses NOWAIT table locks to exclude legacy writers, then the common
company lock. It reauthorizes after locking. A single transaction appends an audit
record and immutable specification/lines, without touching money or stock. Replay
requires the same authorized actor and exact command and rechecks current access.
Scoped definitive non-save errors release editable intent; unknown outcomes retain
it for exact replay. Frontend Web Locks and persisted commands prevent competing
same-invoice submissions. Other financial actions are disabled while review is open.

`supplier_legacy_line_reviews` retains original file, actor/reason, exact request,
canonical reviewed payload and frozen invoice identity. `legacy_review_id` marks
this distinct provenance on the specification. The old birth-only insert function
is unchanged; its trigger still runs for every ordinary new-invoice specification.
An alternative header guard accepts only a matching same-transaction review.
Deferred constraints prohibit orphan review records, altered lines and incomplete
specifications. Existing VAT/identity/immutability constraints remain active.
Automatic downgrade refuses removal of evidence.

## Verification

- Eight pure review tests plus existing exact line/tax validation passed; build
  flag tests require the contract prerequisites and keep this feature default off.
- Ten real PostgreSQL/HTTP cases passed (nine together, new-birth compatibility
  separately): full prepayment followed by two partial VAT receipts and replay;
  foreign actor/supplier/file denial; incorrect amount/tax/confirmation;
  approved/paid rejection; exact replay; immutable audit/invoice identity;
  original birth writer still rejecting old invoices; orphan-review rejection;
  original new-invoice creation still working after 0063.
- Populated actual Alembic upgrade through 0063 passed: accounting/allocation
  snapshots and existing payment replay unchanged, no historical reviews created.
- 157 payment UI tests passed across the unchanged suites and the corrected new
  panel suite. Optimized frontend build compiled with both new features enabled.
- Headed Chromium used the actual component and authenticated FastAPI against
  disposable PostgreSQL: uploaded original, entered explicit VAT, confirmed and
  saved exactly one review. Amount 200 / VAT 34 / paid 0 remained unchanged.
  The fixture then approved and prepaid that invoice and accepted two partial
  deliveries, including receipt retries, without extra cash entries.
- Browser fixture used synthetic accounts/documents and development styling;
  production browser rollout and full application appearance are still release
  checks. No live invoice, payment or stock data were written.

## Release boundary

Backend switch: `SUPPLIER_LEGACY_LINE_REVIEW_ENABLED=1`; frontend switch:
`REACT_APP_SUPPLIER_LEGACY_LINE_REVIEW_ENABLED=true`. Both default off. Backend
registration is nested under the existing deal-party, contract snapshot and
contract-binding gates. The build resolver enforces those dependencies and payments.
Migration 0063 must precede enabling the feature; runtime rejects missing guards.

Do not independently switch on all contract prerequisites in production merely to
expose this panel. They also change new supplier invoice creation. The release must
verify customer access to contract review before a *new* invoice exists, as well as
the existing-invoice entry, then exercise supplier creation with those flags.
The current customer form is reached from a legacy invoice's payment dialog; that
alone does not prove the new-invoice path. After that gate, follow the repository's
backend/database/frontend/authenticated-browser verification and backup cleanup.

Real VIST invoice 161 requires its actual original contract and invoice. No test
attests those documents, edits VAT or imports historical paid balances.
