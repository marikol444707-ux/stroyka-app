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

## Remaining release gates

Do not enable the new production feature independently of the contract workflow.
VIST invoice 161 has no reviewed contract version. A usable customer-side form for
selecting parties and reviewing the original contract is still required; showing
an explanation in the binding panel does not provide that missing workflow.
Also rehearse the complete post-binding invoice approval, payment, shipment,
receipt and accounting path, including historical invoices without sealed lines.
Binding is not proof of historical VAT/line quantities and must not fabricate them.
The actual VIST invoice and its amount remain unchanged.
