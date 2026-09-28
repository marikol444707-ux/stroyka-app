# Linked-refund API and current receipt authority (local)

The application now registers allocation read/write routes and
`POST /companies/{company_id}/supplier-payments/allocated-refunds` behind the
existing payment and allocation feature flags. New refunds additionally require
SUPPLIER_ALLOCATED_REFUNDS_ENABLED=1 and SUPPLIER_SETTLEMENTS_ENABLED=1. Default
activation is unchanged: none of these flags is enabled by this change.

The strict refund command is defined in refund_commands.py. Company headers must
match the path; actor identity comes from the authenticated session. The endpoint
returns the immutable operation and revision receipt plus companyId, requestId
and paymentId. Current financial authority precedes replay, schema checks and
version comparisons. Confirmed PostgreSQL constraint rejection returns 409;
connection/commit uncertainty returns 503/refund_unconfirmed and requires the
same UUID and command. Responses are no-store, including subscription middleware
rejections that occur before routing.

## Current receipt evidence

Allocation authority now supports sealed invoice-line receipts, including VAT.
It verifies the exact invoice specification identity, active immutable-evidence
triggers, all receipt proofs, company and line identities, quantity, price,
material/unit/package, gross and tax amounts, and cumulative line capacity/tax.
The frozen physical warehouse/delivery provenance still must match. Missing or
corrupt evidence fails closed. Legacy groups without specifications retain their
zero-VAT checks. Tax rates and exemptions are not inferred.

A cash refund reduces paid amount and selected receipt coverage. It does not
change accepted quantities, warehouse stock, the original invoice amount, or VAT
evidence. Mixed taxed/zero-tax lines retain their own saved tax amounts.

## Verified

- 9 disposable PostgreSQL tests through the actual application and current invoice
  -> shipment -> receipt chain: VAT allocation/refund, unchanged stock/tax,
  actual HTTP replay, stale version, refund reversal, current membership denial,
  strict body/company/flags, missing/altered evidence, disabled proof guard,
  mixed tax lines, response loss AFTER commit, deferred rejection/full rollback.
- 20 prior allocation authority PostgreSQL regressions passed, including distinct
  payer and omitted-receipt scopes; 6 prior allocation HTTP regressions passed.
- 146 supplier-payment unit tests and 15 subscription-access tests passed.
  Database opt-in tests were run separately, not counted as passed unit tests.
- Existing synthetic background owner/API-error-log fixture warnings remain;
  those background subsystems are not part of this financial validation.

## Not yet released

No server deployment, browser verification or user-facing refund form was done
in this increment. Next: expose the current group/source-payment balances to the
refund form, persist pending UUID/body across reloads and company changes, test
lost-response recovery in the browser, then deploy and verify. Noncash credits
and VAT corrections remain distinct, not enabled by this cash-refund API.
