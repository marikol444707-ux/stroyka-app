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
