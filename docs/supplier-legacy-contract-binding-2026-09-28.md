# First contract binding for an unused legacy invoice

## Scope and status

Implemented locally; migration 0062 and the new UI/API are NOT deployed. Both
runtime and frontend switches default off. Production remains 6225f667 / 0061.
This is a first-binding transition, not a contract replacement or historical
balance correction. The original invoice ID and every non-contract field remain
unchanged. Existing reviewed contract snapshots are required.

GET/POST `/supplier-invoices/{id}/legacy-contract-binding` reuse live company,
project, package and offer authorization. Supplier accounts cannot bind invoices.
POST requires a UUID, exact expected amount, explicit reviewed contract ID,
trimmed reason and human confirmation. The current version and parties must
match. The invoice must be on approval, have an explicit zero paid value, no
warehouse link (including reverse links), no delivery for that offer, no ledger
registration and no sealed line specification. Buyer/payer authority and frozen
snapshot hash/scope are checked before commit.

A narrowly guarded null-to-contract transition is backed by an append-only
` supplier_legacy_contract_bindings ` record. The database rejects ordinary
contract changes, audit mutation and orphan audit commits. The transition writes
only the reference and its evidence in one transaction; it creates no money,
stock, approvals or contract versions. Downstream documents are not backfilled.
The migration never changes historical invoice rows and is intentionally not
silently reversible after evidence has been recorded.

The one-time legacy action uses short NOWAIT table locks to exclude old writers,
then a nonblocking company advisory lock. It rejects busy documents instead of
waiting in an inconsistent lock order. Same-UUID retries recheck authorization
and return the original binding; mismatched payload/actor/UUID cannot replace it.
Scoped `legacy_binding_not_saved` rejections are issued only after authorization,
UUID lookup and rollback of a new attempt; uncertain failures retain the intent.

The dialog shows the reviewed version, number/date and buyer/payer/supplier
identities. A reason and checkbox are required. Pending intent survives reload;
Web Locks exclude simultaneous submissions from tabs. A validated scoped
non-save response releases the failed intent for a fresh review; a lost response
retries the same UUID. Other financial actions in the dialog are blocked while
the binding form or pending command is active.

## Validation

- 140 existing/new payment UI tests passed; the additional scoped-rejection test
  passed with all 5 binding panel tests after its final change.
- Policy and build configuration tests cover current version, exact scope,
  inactive/paid/used documents, missing evidence and required switches.
- 8 actual PostgreSQL/HTTP tests: real contract review and company authorization,
  binding/replay, paid/registered denial, foreign and supplier denial, expected
  amount/confirmation, fingerprint conflict, raw SQL denial and immutable audit.
- Headed Chromium completed the real component against authenticated FastAPI and
  a disposable PostgreSQL fixture: one binding, amount 200 and paid 0 unchanged.
  This is a binding test, NOT the entire post-binding receipt/payment workflow.
- Actual Alembic rehearsal on populated accounting data upgraded through 0062:
  financial/allocation snapshots preserved, binding audit empty, old payment
  command replay unchanged. Existing 0051/0061 rollback rehearsal also passed.
- Optimized production build compiled successfully. No real financial writes.

## Production configuration correction

Read-only inspection found SUPPLIER_INVOICE_LINE_SPECS_ENABLED=1 while all three
contract dependencies were absent (default off). The create-invoice implementation
explicitly rejects that combination with 503. The previous release's read-only
checks did not catch this creation-path gap.

After verifying the existing isolated supply-chain test, restored this flag to 0
on production, restarted the app and verified matching backend version/DB health.
No schema, invoice, payment, stock or frontend files were changed by this correction.
Receipt: /var/log/stroyka-release-receipts/supplier-line-spec-config-20260928.json.
The frontend configuration resolver now rejects this unsupported combination and
requires all contract dependencies for the new binding feature too.

## Customer contract form (local, 2026-09-28)

The binding panel now opens a customer-side form for selecting accessible buyer
and payer companies, uploading an original and manually reviewing a contract.
Company choices come from `/users/company-context`, not the global company list.
Names/INNs come from authorized review context; signer and bank details remain
blank until explicitly entered. Saving a reviewed version neither binds the
invoice nor records signatures, money or stock. Binding remains a separate action.
The form is behind the same disabled-by-default legacy binding build switch.

Versioned commands are persisted before sending and protected by Web Locks.
Lost responses retry the same payload and reconcile the exact immutable revision.
A conflicting scoped revision releases the unsuccessful command and refreshes
parties. A first-attempt schema rejection permits field correction. Network,
foreign-response and uncertain retry failures retain the command for reconciliation.
No uncertain payload can be overwritten by edits.

Validation: 152 UI tests in 15 suites passed; optimized build compiled successfully.
Headed Chromium + real authenticated FastAPI + disposable PostgreSQL completed
party version saving, original upload, manual contract review and separate invoice
binding. DB assertions confirmed one binding and unchanged amount 200 / paid 0.
The fixture console had development React notices and an absent favicon; no form
API error occurred. This is a local test, not a production release.

## Post-binding chain evidence and remaining release gate

Two persistent PostgreSQL/HTTP regression tests cover old invoices without sealed
line specifications (`test_legacy_contract_chain_postgres.py`):

- Postpayment works after full receipt, original waybill upload and accountant
  approval of the linked warehouse invoice. Payment then records 200 against the
  invoice; no line specification is invented. Trying to pay before that review
  correctly fails eligibility; approval without a waybill correctly fails too.
- Prepayment records against the bound invoice, but subsequent shipment is still
  blocked because the ledger document has no sealed material lines. The regression
  verifies the safe rejection and unchanged shipment count; it does NOT claim this
  user journey is complete.

The unused-invoice line-review implementation is now available locally in
[the 0063 increment](supplier-legacy-line-review-2026-09-28.md). It resolves the
prepayment path when original-document review is completed before approval and
payment. The blocking regression above still applies when that review is omitted.
Production activation remains gated on the complete new-invoice contract workflow
and the deployment checks documented in the 0063 increment.

VIST invoice 161 still needs the user's actual contract and item evidence; tests
never modified it. Production remains 6225f667 / 0061 with contract prerequisites,
legacy binding and invoice-line creation disabled as described above.
