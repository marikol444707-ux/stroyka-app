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
