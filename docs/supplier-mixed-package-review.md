# Historical mixed-package review

Objective: represent historical receipt line packages accurately while keeping
one invoice/receipt cash balance. Never rewrite packages, invent per-package
paid amounts or reconstruct historic invoice/VAT lines.

First increment: operator-only read-only audit. Strictly parse original JSON
text preserving duplicate keys. Require nonempty object rows and explicit,
canonical string workPackage/work_package; aliases must agree. Preserve empty
literal package as distinct from Основная. Return package groups and original
1-based row positions. Invalid rows block the entire review.

For a reciprocal, same-company/supplier/project pair with equal exact amounts
and paid balances, expose a mixed-package review candidate with one opening
paid balance and newCashAmount=0. Never grant admission. The invoice header
package and every receipt package form the future authorization scope. Existing
single-package confirmations, document resolvers and database guards stay strict.

Acceptance: mixed packages retain row mapping; duplicate keys, malformed JSON,
missing/non-string/whitespace/conflicting aliases fail closed; foreign identity,
ambiguous links and balance mismatch expose no opening; mirrored paid counted
once. Existing text and JSONB audit contracts continue passing.

Next increment requires immutable evidence for the whole package scope, current
read/write permission for every package before preview/replay/confirmation, and
database constraints preserving single cash ownership. No write endpoint or UI
activation is authorized by the read-only candidate alone.

Files: backend/features/supplier_payments/legacy_package_review.py,
legacy_reconciliation.py; scripts/audit_supplier_legacy_invoices.py.
Tests: python -m unittest backend.features.supplier_payments.test_legacy_package_review
and opt-in LegacyAuditTests / LegacyJsonAuditTests through
scripts/run_supplier_catalog_postgres_tests.py with PostgreSQL bin on PATH.

## Implemented read-only increment

The operator audit now recognizes valid mixed packages separately from malformed
item data. It uses the same money/link checks as single-package review, with a
separate strict package evidence parser. It returns requiredPackages including
the invoice header scope, grouping original positions without allocating money
to them. This is not a runtime permission check or confirmation endpoint.

Read-only live refresh (company 1, 49 historical invoices): 17 mixed-package
candidates, 7 single-package pairs, 1 standalone invoice, 20 balance mismatches,
2 identity mismatches and 2 ambiguous links. The 17 mixed candidates are invoice
IDs 6,7,13,14,16,17,18,19,20,21,22,23,70,71,74,84,143. Eleven other mixed documents
have independent identity/balance blockers. These categories supersede the
initial primary-blocker counts, not the underlying data. All admissionGranted
values remain false; no cash or opening records were written. Source amounts
remain in local mode-0600 /tmp/stroyka-mixed-review-20260928.json, not version control.

Validation: 9 pure preview/parser tests; PostgreSQL audit suites cover both
text and JSONB storage, mixed balance conservation, no registration/mutation,
company isolation, malformed packages and prior single-package scenarios.

## Authenticated review increment

Added GET `/companies/{company_id}/supplier-opening-confirmations/package-review/{invoice_id}`.
It requires payment and opening flags plus the new default-off
`SUPPLIER_MIXED_OPENING_REVIEW_ENABLED=1`. No UI flag or production activation.

The existing financial read transaction validates schema, holds the company
advisory lock and always rolls back. Root owner/project/header-package authority
is checked before detailed link discovery. Both documents are locked and links
rechecked. Cross-company and ambiguous links fail closed. Contract payer scope
is resolved server-side; current authority is then checked for each receipt
package on its actual project, including the payer company, before returning
any balances or package list. Existing-ledger or sealed-line documents are
excluded from this legacy preview.

Response explicitly has `readOnly=true`, `confirmationAvailable=false`, and
`admissionGranted=false`. It deliberately contains no `reviewedHash` accepted by
the existing single-package confirmation writer. That writer, payment resolver,
and database package guards have not been weakened.

Still required: immutable multi-package baseline evidence and database guards,
current all-package authority on every later read/payment/reversal/replay, then
confirmation UI and an integrated end-to-end test. Enabling a mixed opening
before those consumers understand its complete scope would be unsafe.

Verified: 14 boundary/parser tests and 4 real PostgreSQL tests (actual HTTP,
no-write snapshots, real financial authority with one denied package, revoked
membership/roles/default-off, mismatched balances and nonreciprocal links).
No production code, flags, schema or financial records changed in this increment.

## Immutable evidence storage (0060)

Migration `0060_supplier_mixed_scopes` adds an append-only
`supplier_mixed_scope_reviews` table and exact SQL package-scope derivation. It
stores the original invoice and warehouse snapshots, required packages and the
package of every original line, actor, request UUID and review reason. The SQL
parser delegates each singleton original JSON row to the existing strict package
validator; missing/conflicting/repeated package aliases are not normalized away.

Insert guards lock the company and physical documents and require matching
company/supplier/project, reciprocal nonambiguous links, equal amounts and paid
balances, no existing ledger baseline or sealed invoice lines, exact source
snapshots and exact complete package scope. Updates, deletes and truncation are
rejected; downgrade refuses to discard any review evidence. Empty-table rollback
is supported. No backfill or production migration was performed.

This is evidence of a review at insertion time, NOT a financial opening or an
authorization grant. There is deliberately no public writer yet. Subsequent
confirmation must revalidate current source snapshots and every package's live
authority; physical documents may have changed since review. No change was made
to the existing single-package payment/attachment/opening admission guards, and
the new evidence cannot bypass them. No per-package cash amount is invented.

Four disposable PostgreSQL tests passed: exact scope/no new cash or baseline;
tampered scope, foreign company and mismatched balances rejected; immutable
history/nonempty downgrade and cash-admission protection; malformed packages.
The Alembic graph has a single 0060 head with IDs fitting its version column.
Actual Alembic 0051 → 0060 → 0051 → 0060 also passed on a populated synthetic
database: complete financial snapshots unchanged, old payment UUID replay did
not duplicate cash, and a new payment remained valid. This tests pre-activation
rollback with empty review storage; evidence-bearing downgrade remains blocked.

## Internal atomic review save

`mixed_scope_evidence.save_review` saves one immutable review under the company
lock, with current financial WRITE authority for the header and all receipt
packages. The command accepts only UUID, invoice ID, evidence hash and reason;
company and actor are server arguments. The preview now exposes `evidenceHash`
over PostgreSQL's exact JSON text snapshots (not Python float reserialization).
It still does not expose the old opening writer's `reviewedHash`.

Any source change requires a new review before saving. UUID reuse checks actor,
document identities, reason and exact stored snapshots/scope. Concurrent retries
serialize and return the same review ID. Revoked package access or missing
immutable guards blocks retries as well as new saves. A late commit failure
rolls the review back. No ledger baseline, cash, opening or application of paid
balance occurs; response explicitly returns `openingConfirmed=false`.

The worker is exposed through the default-off POST route described below; there
is no UI button yet. It is a prerequisite for financial admission, not
implementation of that admission.
The existing guards still reject mixed-package cash baselines. Future transfer
must bind review evidence to the baseline and ensure every financial consumer
uses the complete package scope, including legacy reports and reversal/replay.

Verified: 2 command-validation tests, 5 isolated PostgreSQL save/retry/concurrency/
rollback tests, and 4 existing authenticated mixed-review PostgreSQL regressions.
No production migration, deployment, review save or financial write was performed.


## Authenticated save endpoint

POST /companies/{company_id}/supplier-opening-confirmations/package-review
accepts the strict save command above. It requires the payments, opening
confirmations and mixed review flags, selected-company headers and a server
injected financial update authorizer. It never falls back to read authority.
The application supplies this authorizer from the existing payment access policy.
All package checks, stale evidence checks and UUID retry handling run inside the
same database transaction as the immutable evidence insert. Responses are
no-store. This endpoint only saves evidence: it does not confirm an opening.

Local validation covers HTTP company/flag/write-authority boundaries and an
HTTP → real PostgreSQL save/retry/revoked-package scenario, in addition to the
existing transactional rollback/concurrency checks. Production remains unchanged.


## Revalidating saved evidence

GET /companies/{company_id}/supplier-opening-confirmations/package-review/{invoice_id}/saved/{review_id}
restores a saved review only after authorizing all current document scopes and
locking the source pair. Company, invoice and receipt identity must match.
Stored exact JSON snapshots and the complete SQL-derived package scope must
still match the current sources; otherwise the endpoint returns 409 and requires
a new review. Missing or foreign evidence returns 404 after document authority
checks. Read responses are no-store and the transaction always rolls back.

The same load_current_review helper can be called from a future opening writer
with its financial WRITE authorizer while retaining the transaction locks.
A successful read is not financial admission: confirmationAvailable and
openingConfirmed remain false. Binding evidence to both ledger records and
updating every payment/history/reversal scope consumer is still outstanding.


## History authority prerequisite

The history reader previously checked only the operation target. A PostgreSQL
HTTP regression reproduced an invoice-target payment returning 200 after its
impacted warehouse document became malformed. History now expands the bounded
operation set to all impacted ledger documents and attached receipt mirrors,
then applies recorded and current financial authority before returning results.
UUID lookup (including attachment UUIDs) and pagination lookahead use the same
checks. Warehouse items are selected as original text for the SQL validator,
including installations storing items as JSONB.

Regression coverage includes malformed paired receipts, revoked current receipt
package access, and malformed attached mirrors through both operation and
attachment UUID lookup. This is a history safety fix; mixed opening admission
remains disabled and the old single-package baseline guard is unchanged.

## Database binding to a paired opening (0061)

Migration 0061 adds immutable supplier_mixed_opening_bindings connecting one
0060 review to the invoice ledger record, receipt ledger record and opening
confirmation. Their IDs are reserved before insertion; deferred foreign keys
and a deferred completeness trigger require the complete chain in one commit.
The insert guard locks the company and sources, requires exact current evidence,
and rejects already registered documents, sealed invoice lines and foreign
companies. The existing paired-opening guard still validates reciprocal links,
equal identity/balances, same-transaction baseline creation and exact snapshots.

The warehouse baseline guard accepts the invoice header as its accounting anchor
only through this same-transaction binding. It retains strict single-package
validation without a binding. Full original package scope remains in the review;
it is never replaced by the header or split into invented monetary subtotals.
Completion checks exact current snapshots again and rejects any payment impacts.
An incomplete transaction rolls back both baselines. Bindings cannot be changed,
deleted, truncated or discarded by downgrade. Empty-schema downgrade restores
the exact previous baseline guard.

The database admission was first tested with synthetic direct SQL. The internal
application writer described below now calls it. Runtime resolver, new-payment policy and history still reject
mixed receipt packages; financial WRITE authorization over all packages and
idempotent confirmation must be integrated before exposing an opening action.
No production migration or historical-data mutation was performed.

The populated release rehearsal now covers actual Alembic 0051 → 0061 → 0051 →
0061, unchanged financial snapshots, replay of an old payment and a new payment.


## Internal application confirmation worker

mixed_openings.confirm accepts only requestId, invoiceId, reviewId and reason;
actor/company and financial update authority come from the server. It locks and
authorizes both current sources and every package before retry lookup. New
confirmation requires eligible accounting statuses and a still-current saved
review, then inserts the binding, both numeric baselines and opening evidence
in one transaction. A deferred commit failure rolls the entire operation back.
No cash operation is inserted.

The UUID fingerprint includes actor, company, review and reason. Retry requires
the same persisted binding and current access to both current and recorded
package scopes, including the recorded payer. It returns the original opening
amount without another baseline or payment. Missing evidence guards fail closed.

The common source-locking/authorization stage was extracted from the read-only
preview; its unregistered-source checks remain in the preview. This internal
writer has no HTTP route or UI activation yet. Payment, reversal, document
projection and legacy report consumers still require bound mixed-scope support
before exposing it. Production remains unchanged.


## Internal payment and reversal adapter

mixed_payments.build_resolver and validate_new now connect a confirmed mixed
opening to the existing cash engine. They are internal and not selected by HTTP
routes yet. Only invoice-target payment and reversal commands are accepted.
Current scopes and recorded scopes/payer are authorized before UUID replay.
The exact original source snapshots must still match apart from the explicit
payment/status fields the engine updates. Changed items, identities or links
require review; original full package scope is preserved.

The warehouse snapshot uses the invoice header as the accounting anchor only
after the binding and original scope have been validated. The shared policy
accepts a server-only snapshot adapter, while ordinary routes retain their
strict single-package snapshot by default. Status, remaining-debt bounds,
paired impacts, single cash row, immutable UUID and reversal conservation stay
in the existing engine/policy. Ledger, opening, review and binding guards must
be present and enabled.

A synthetic chain proves opening 50 → payment 20 → paid 70 → reversal → paid 50
on both physical documents. Retry creates no extra cash; revoked package scope
blocks retry/reversal, overpayment is rejected, and reversal preserves cancelled
statuses. Public document/history/legacy report integration and UI remain
outstanding; no production changes or real financial writes were made.
