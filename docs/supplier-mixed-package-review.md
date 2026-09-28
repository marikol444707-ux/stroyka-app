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
