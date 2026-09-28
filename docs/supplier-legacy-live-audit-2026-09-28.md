# Legacy supplier invoice readiness — live read-only audit

Production remained at code `780798ab`, Alembic 0051. Scope: company 1, 49
invoices. Audited with an explicit REPEATABLE READ, READ ONLY transaction and
rollback, using a 30-second statement timeout. No invoices, cash, stock, links,
feature flags or application files were changed. Three reviewed report modules
were streamed into a transient Python process in memory; no server copies were
created. The existing package-validation helper is unchanged from deployed code.

## Report compatibility fix

The first attempt stopped because JSONB warehouse items arrive as Python
lists/dicts and the package validator expects SQL text. Read the column as
`w.items::text AS items`. This supports text and JSONB without modifying stored
content or relaxing package validation. Real PostgreSQL tests reproduced the
adapter error before the fix. All 8 JSONB and 8 text audit tests pass afterward,
including read-only preservation, company isolation and invalid receipt handling.

## Results

All 49 invoices lack the newer sealed original line evidence. This is expected
for historical records; it does not itself prove they are wrong. Fifteen contain
historical paid amounts without new-ledger registration. No admission or opening
confirmation was granted by this report.

| Primary review outcome | Count | Invoice IDs |
| --- | ---: | --- |
| Matching legacy invoice/receipt pair | 7 | 24, 72, 73, 75, 76, 77, 153 |
| Standalone legacy invoice | 1 | 161 |
| Receipt package cannot be validated | 28 | 6, 7, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 53, 70, 71, 74, 78, 79, 80, 81, 83, 84, 143, 154, 155, 156, 158, 159 |
| Receipt identity mismatch | 1 | 15 |
| Invoice/receipt amounts or paid balances disagree | 10 | 82, 145, 146, 147, 148, 149, 150, 151, 152, 157 |
| Ambiguous receipt links | 2 | 144, 160 |

These are primary classifications, not an exhaustive list of all issues per
invoice. For example a package failure can mask an additional balance mismatch.
The 8 matching/standalone candidates still require authorized opening review;
they must not be treated as newly received cash or as proven line VAT.

## Remaining work

Prepare explicit per-document reconciliation evidence for the 41 blocked
invoices: original documents, intended package/project/supplier, correct links,
and bank-confirmed paid balances. Do not infer missing package assignments or
overwrite balances merely to make invoice and receipt match. Historical line
specifications must not be fabricated. Keep new-ledger activation off until
legacy handling and integrated accounting projections are verified.

Full monetary audit output was saved locally with mode 0600 at
`/tmp/stroyka-legacy-audit-20260928.json`; it is not committed. This document keeps
only classifications and IDs. Audit results are a point-in-time observation and
must be refreshed before executing any later confirmed reconciliation.
