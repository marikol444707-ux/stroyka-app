# Supplier payment and contractor settlement check

Supplier payment now separates ordinary bank payment recording from legacy
document reconciliation, opening balances, receipt allocation and refunds.
The correction panels stay mounted so saved requests and blocked states are
detected even while collapsed. Errors or unfinished correction operations open
the section automatically. Server eligibility and confirmation gates remain.
No bank transfer is initiated by this interface.

The warehouse-package error originates in the database-backed validation of
persisted receipt items. This change explains it without bypassing validation;
it does not repair invoice 159 or infer missing work packages.

Local disposable PostgreSQL checks: 35 material settlement tests and 18 tool
settlement tests passed. These cover confirmed work, financial acts, registered
signature files, partial payment, retries, concurrent requests, deductions and
cross-company access. Tool settlement fixtures now include frozen contract
parties, as required by the existing financial act guard.

Supplier payment UI: 21 suites / 185 tests passed. Production build passed.
All settlement records are synthetic and removed with the disposable database.
No real payment, act or contractor record was changed. Authenticated production
workflow and the exact data problem in invoice 159 are not verified here.

## Compact payment form follow-up

The ordinary payment form precedes legacy document correction panels. The
recipient and saved account remain visible; other requisites and the contract
expand on demand. Payment history is collapsed until opened. On phones the
amount and date share a row when space permits; the close header remains sticky.
The remaining-debt shortcut fills only the draft amount from the authorized
snapshot and never confirms or records a payment. It is unavailable when blocked
and does not apply to refunds or credits.

Verification: 187 supplier-payment tests, 18 focused dialog tests, ESLint and
production build passed. Local real-browser checks at 320, 390 and 1280 px
verified no horizontal overflow, amount filling, confirmation gating, the form
before corrections and expandable requisites/history. The preview uses synthetic
records and disables writes. Invoice 159 remains a separate data-reconciliation
issue; this UI change does not bypass or repair its warehouse-package validation.

## Invoice 159 diagnosis and reconciliation guidance

A read-only production audit found invoice 159 linked reciprocally to receipt 26
in company 1. Receipt items span three work packages; the paid amounts disagree
between the two documents. Neither document has a registered ledger baseline.
The canonical audit reports receiptBalanceMismatch and missing original line
evidence. These are existing-data blockers, not proof of a bank payment. No
production document, balance, registration or financial operation was changed.

The mixed-package review now explains a balance mismatch after authorization of
every involved package. Denied package access still returns 403 before exposing
financial diagnostics. Payment errors offer a button that scrolls/focuses the
existing reconciliation section without submitting a command. Opening copy now
explains that sums are reviewed from source documents; it does not suggest an
unavailable manual amount input. Confirmation and payment gates remain intact.

Checks: four disposable PostgreSQL review tests, 188 supplier-payment UI tests,
ESLint and production build; local browser review navigation at 390/1280 px.
The factual bank-payment status remains required before correcting live data.
