# Supplier documents in accounting

User-approved navigation: Accounting -> Supplier documents contains supplier
contract originals, changes and addenda. A supplier can be selected before any
invoice exists. Reuse the existing company/supplier registry and stored originals;
do not create another archive or fabricate an offer for a contract.

Procurement offer cards retain prices, terms, line items, original quotations,
comparison and explicit supplier choice. Contract preparation and standalone
technical document checks are removed from these cards. The supplier contact card
also no longer embeds contract editing.

Standalone technical checks remain under the selected supplier's proposals in
accounting for authorized leadership and the configured companies only. Exact
request company, supplier, scoped project and protected file identities are kept.
Existing backend authorization and automatic contract reuse are unchanged.

Verification: focused component tests cover own-company supplier selection,
company changes, all-companies mode and exact document check selectors. Actual
components were viewed in an isolated browser at 390 and 1280 px: no contract or
technical controls in procurement, contract management available in accounting,
no horizontal overflow. Separate disposable PostgreSQL checks cover comparison,
quotation -> invoice -> warehouse lifecycle and deferred-payment receipt (12 tests).
No production business records or payments were created during these checks.
