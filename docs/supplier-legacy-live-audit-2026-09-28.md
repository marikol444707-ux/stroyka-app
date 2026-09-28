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

## Detailed follow-up: causes, not automatic corrections

Additional read-only examination clarified the primary blockers:

- All 28 package failures are `Warehouse contains mixed packages`. Package
  fields exist: real combinations include Основная/Отопление, Отделка/Электрика,
  and Вентиляция/Отделка. They must not be described as missing packages or
  normalized into one arbitrary package. The one-package opening model lacks
  support for these historical documents. Preserve document identity, line
  packages, permissions and one cash balance when designing that support.
- For the 10 balance mismatches, invoice and warehouse TOTALS are numerically
  equal (compare Decimal, not text such as 45000.00 versus 45000.0). Every invoice
  has paid=0 while its linked warehouse is fully paid. Invoice IDs are
  82,145,146,147,148,149,150,151,152,157; warehouse IDs are respectively
  2,3,4,5,6,7,8,9,10,15. Verify original payment evidence before recognizing an
  opening; copying warehouse paid into invoice paid without evidence is not an
  authorized repair. Additional balance issues may exist within mixed packages.
- Invoice 15 has no supplier, empty invoice project, and warehouse 37 is labelled
  Основной склад. Numeric totals agree. This needs explicit general-warehouse
  context and supplier evidence, not a fabricated construction project.
- Ambiguous IDs 144 and 160 have explicit test labels. Invoice 144 (200) points
  forward to warehouse 167, whose reverse link points to invoice 160 (100).
  Warehouse 166 (100) points back to 144. Invoice 160 also points to 167. This
  explains the ambiguity; labels alone do not authorize deletion or prove which
  correction is intended. No test documents or links were modified.

Priority: design historical multi-package review without weakening package
access, then reconcile paid-balance evidence and general-warehouse identity.
Handle the two test links as a separate, explicitly reviewed repair. None of
these findings warrants automatic production balance changes.

Detailed read-only evidence is local, mode 0600:
`/tmp/stroyka-legacy-details-20260928.json`. Raw document values are not committed.

## Post-release follow-up — 2026-09-28

Refreshed operator audit on deployed 6225f667, read-only with rollback: 49
invoices; 17 mixed-package pairs, 7 matched pairs, 1 standalone, 24 blocked.
Blocked breakdown: 20 balance mismatches, 2 identity mismatches (15,83),
2 ambiguous links (144,160). Candidate classification is not runtime admission.

Direct scoped read established the additional blocker for VIST invoice 161:
company 1, supplier 159, offer 71, request 880; amount 263000, paid 0,
status На утверждении, project Кисловодск Лицей 4, package Отделка.
Offer 71 is Утверждено. Invoice contract_version_id and warehouse_invoice_id
are null; no supplier_contract_versions exist for offer 71.
The payment resolver intentionally rejects an offer-backed invoice without a
bound contract. This is not evidence of a paid-balance mismatch.

Code inspection: reissuing the invoice with a contract would reject the existing
invoice's different/null binding; it does not retrofit the old invoice. Therefore
simply approving the invoice or retrying invoice creation is not a demonstrated
repair. A reviewed legacy contract-binding workflow needs explicit design and
validation, preserving invoice identity and verifying absent payments/receipts
and current company/offer/party authority. Do not silently attach the latest
contract, erase offer_id, annul/recreate, or change financial values.
No production records were changed in this follow-up.
