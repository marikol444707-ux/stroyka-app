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

## New-deal entry points — local continuation

Added customer contract review entry directly to approved offers (no invoice
required), scoped to the selected editable company. Supplier invoice form loads
latest reviewed contract and current deal parties, requires explicit selection,
and submits contractVersionId only for the matching offer. Missing, foreign,
unreviewed and stale-party versions cannot be selected. Reload clears selection.
The build resolver now exports DOCUMENT_CONTRACT_BINDINGS and requires both
DEAL_PARTIES and CONTRACT_SNAPSHOTS for it.

Local checks: 27 frontend tests across five suites passed (contract choice,
preparation, invoice contract payload, existing invoice tax payload and cabinet
offers); 11 build resolver tests passed. Production build with document contract
bindings enabled compiled successfully. No deployment in this continuation.
Remaining release gate: real API/database and browser verification of customer
contract preparation before a new supplier invoice, then controlled release of
migrations 0062/0063 and flags. Frontend unit checks do not close that gate.

Additional verification: all 14 isolated PostgreSQL invoice creation tests passed.
Headed Chromium exercised the real SupplierInvoiceContractChoice and
createSupplyActions against real local API/database: invoice disabled before
explicit selection; reviewed contract selected; invoice created successfully.
Database assertions confirmed amount 200, paid amount 0, exact selected contract
and one immutable specification. No production data touched. Final browser run
had no console errors (development JSX transform warning only). Initial harness
missed a build-time environment definition; corrected harness and reran before
recording success. Disposable database/server/bundle stopped and removed.
Customer preparation entry still needs browser verification before release.

Customer-side local browser gate passed: real preparation entry opened from an
approved synthetic offer without an invoice; accessible buyer/payer saved; a
synthetic original uploaded; number/date/terms and explicit review confirmation
saved through real API. Database asserted exactly one contract version and zero
invoices for this offer. Browser had zero console errors (development transform
warning only). This was an isolated component page, not production UI. Temporary
PostgreSQL instance and browser bundle removed after assertions passed.

## Production release 2026-09-28

Installed 7bd914d849d6ab38bd59562fff9e068a5c3ca6fa; schema upgraded from
0061 to 0063. Enabled deal parties, contract snapshots/document bindings,
legacy binding/review and new invoice line specifications; frontend flags resolved
with the same backend configuration, VAT UI enabled. Public/backend health passed;
251 installed frontend files matched the build. Read-only hashes for supplier
invoices, payment operations, project payments, warehouse invoices and materials
matched before/after; new review tables empty. No historical records backfilled.

Authenticated production browser: approved VIST offer71 exposes preparation and
loads accessible buyer/payer. Invoice161 payment history opens with expected409
for missing checked contract; legacy-binding read explicitly reports no checked
version and offers preparation. No production contract/payment/stock writes.
Console network409 is the displayed business guard, not a failed migration.
Existing public-page unused-preload warnings remain. Customer save and supplier
invoice creation were exercised against isolated real API/PostgreSQL, not live
financial records. Release receipt records verification scope and cleanup.
