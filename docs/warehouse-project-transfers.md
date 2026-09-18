# Two-stage project transfers

Current integration and release status: [2026-09-18 release](warehouse-release-2026-09-18.md).
Earlier milestones below describe the development branch, not the deployed state.

## Accepted workflow (2026-09-16)

The user chose separate physical dispatch and acceptance, not immediate posting
to both projects. One verified company owns the source and destination projects.
No supplier cabinet is required. A transfer creates neither a purchase nor a
supplier liability; payment dates, payer and deferral remain unchanged.

1. An authorized warehouse employee selects an existing allocation, a different
   destination project, quantity and reason, and confirms dispatch. Debit source
   stock only. The unaccepted quantity becomes in-transit inventory.
2. Any authorized employee in that company may confirm actual destination receipt;
   the workflow is not hard-bound to one named foreman. Initially the warehouse
   write roles are director, deputy, storekeeper and supply. Accountant reads.
3. Each receipt records expected and accepted quantities and the employee/reason.
   Accepted quantity alone enters destination stock and its quality journal.
   Partial receipt is allowed. Expected minus accepted is a discrepancy event,
   not automatic write-off. Outstanding goods remain in transit and can be
   received later. A zero-accepted discrepancy creates no stock or quality row.
4. Destination acceptance retains the root receipt/lot and original source
   allocation. Original acceptance is immutable. An accepted destination
   allocation can subsequently be returned or dispatched by the same rules.

## Accounting invariants

- Source entitlement = allocated minus returned minus dispatched quantity.
- Shipment outstanding = dispatched minus accepted quantity.
- A discrepancy report does not itself decrease outstanding or create loss.
- Dispatch/receipt leave root main-warehouse lot availability and main stock
  unchanged. Only a real return to main replenishes the original lot.
- Check both allocation entitlement and physical aggregate stock under locks.
  Source selection is an employee attestation, as with current physical returns;
  it does not prove physical lot identity within historically mixed stock.
- Every command is atomic, company-authorized and idempotent; a replay must not
  create a second stock delta, receipt or quality entry.
- Keep immutable lineage and identity guards even when the feature is disabled.
- Never represent a direct transfer as a fictitious main-warehouse return/reissue.
- Do not infer historical provenance, silently convert packages or round drifted
  legacy balances.
- Preserve source price/category in the dispatch snapshot and preserve its work
  package on receipt. Reject a protected dispatch whose quantity cannot be
  represented by the destination quality journal before debiting stock.
- Validate physical ancestry even for unowned/flag-off records. The destination
  allocation must retain the parent's company, lot, receipt, invoice line,
  material, unit and package; migration triggers enforce these root keys too.
- Protect the original invoice while any descendant allocation has remaining
  entitlement or any shipment remains in transit. A fully returned chain must
  not leave a false outstanding-distribution block on invoice cancellation.
- Reserve `В пути` as a movement label, never a project stock bucket. Protect
  destination identity before the first acceptance as well as afterwards.

## Additive HTTP contract

Behind `WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=1` and existing distribution gate:

- `GET /warehouse-distributions/transfers`: literal `q`, exclusive `beforeId`,
  `limit` 1..200 (default 100); `{items,truncated,nextCursor}`.
- `POST /warehouse-distributions/transfers`: `{companyId,requestId,reason,
  allocationId,toProjectId,quantity}`.
- `POST /warehouse-distributions/transfers/{id}/receipts`:
  `{companyId,requestId,reason,quantity,expectedQuantity}`;
  `0 <= quantity <= expectedQuantity <= inTransitQuantity`, expected > 0.
- Commands return `{ok:true,requestId,item}`. An unknown outcome preserves the
  same request UUID and payload until confirmed; new writes stay blocked.

Transfer fields: `id`, `companyId`, `sourceAllocationId`, `fromProjectId`,
`fromProjectName`, `toProjectId`, `toProjectName`, `warehouseInvoiceId`,
`invoiceNumber`, `lotId`, `materialName`, `unit`, `quantity`, `receivedQuantity`,
`inTransitQuantity`, `status`, `reason`, `createdAt`, `createdBy`, `receipts`.
Status: `in_transit`, `partial`, `received`, or `discrepancy` while unresolved.
Receipt fields include `quantity`, `expectedQuantity`, `discrepancyQuantity`,
destination `allocationId` (null for zero acceptance), employee/time/reason.

Frontend gate: `REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=true`.
The existing warehouse and accounting workspace host the transfer list; accounting
has no mutation controls. No new supplier-facing debt or payment UI.
When both distribution and transfer frontend flags are enabled, the warehouse
movement tab hides the legacy immediate-movement form. Tools/inventory and
either-flag-off behavior are unchanged. Deploy the compatible backend/schema
before enabling this UI mode.

## Verification / release gates

Tests must prove conservation across A, transit and B; repeat dispatch/receipt;
partial receipt; discrepancy then later receipt; source return versus dispatch;
destination return/redispatch; insufficient stock; wrong company/membership;
rollback after intermediate changes; quality entries only for accepted quantity;
unchanged supplier documents; and migration refusal to drop business records.
UI must reject stale scope responses and preserve uncertain command state.

Development uses synthetic isolated databases. An authorized local copied-data
rehearsal is recorded below; historical reconciliation and production activation
remain separate release steps.

Apply additive migration `0015_distribution_transfers` after `0014` before
enabling the backend/frontend flags. Keep the flags off until the existing
distribution/quality prerequisites and historical reconciliation are verified.
For rollback, disable commands but keep the provenance-aware backend and schema;
do not roll back to software that ignores transferred quantities. Downgrade
refuses to remove transfer business records. Empty downgrade restores the prior
identity guard. This is not a production deployment instruction or authorization.

The initial local browser preview was synthetic and had no real authorization, database,
quality journals or supplier ledger. It verifies interactions, not backend
accounting. PostgreSQL regressions separately exercise persisted stock and
evidence. Production load capacity has not been established by these checks.

## Local verification (2026-09-16)

- Combined backend regression: 115 passed (unit, membership, registry,
  distributions, transfers and quality contracts; PostgreSQL opt-in enabled on
  an isolated fresh Unix-socket database). Includes concurrent writes, rollback,
  zero/partial receipts, descendant return/redispatch and migration safeguards.
- Full frontend: 167 suites / 1051 tests passed; production build succeeded.
  Existing bundle-size and Node `fs.F_OK` deprecation warnings remain.
- ESLint for changed frontend files, Python compilation and `git diff --check`
  passed; synthetic preview self-test passed.
- Browser: dispatch 6, accept 4 of expected 6, then accept remaining 2; final
  received quantity 6, transit 0, discrepancy retained in receipt history.
  Accountant has no mutation controls; 320px viewport has no horizontal overflow.
  Browser console: no errors/warnings (React DevTools informational message only).
- Existing real-runtime distribution-quality regression: 27 passed on a separate
  fresh database. Its fixture emits two diagnostic logging errors because
  `api_errors.owner_scope` is absent; business assertions pass. This does not
  establish production diagnostic-schema compatibility.
- Independent source review closed unowned lineage, receipt root-key enforcement,
  full-return cancellation and cancelled-root replay findings. Replay returns the
  committed result without new stock mutations; new writes still require an
  active source. No production activation or real-data reconciliation performed.

## Copied-data rehearsal and legacy fixes (2026-09-16)

These later checks supersede the initial synthetic-only verification limitation;
they do not authorize or constitute production activation.

- Restored the authorized production snapshot into private local PostgreSQL
  16.15, Unix socket only, and applied Alembic 0008–0015. Original-column row
  fingerprints remained unchanged across all 142 existing tables. The local
  macOS build is not full production Linux/locale parity.
- Actual browser, authentication and backend on a separate copy: dispatch 6,
  another employee accepts 4 then 2, transit reaches zero and discrepancy history
  remains. Accountant sees the chain without mutation controls; HTTP mutation
  and foreign-company access return 403. Original supplier/warehouse invoice and
  delivery fingerprints stay unchanged. External calls were blocked.
- Legacy quality recovery had a pre-existing psycopg2 `IndexError`: the literal
  receipt-prefix `%` was interpreted as parameter syntax. Both journal history
  queries now bind the LIKE pattern as a parameter.
- Copied-data replay exposed another pre-existing defect: custom units containing
  spaces (such as `уп 100м`) compared differently in Python and SQL, repeatedly
  inserting stock-derived inspections. Normalize comparison values only in the
  two affected inspection checks; stored units, quantities and source keys stay
  unchanged. This is not a redesign of global unit normalization.
- Six real PostgreSQL regression tests first reproduced these failures, then
  passed: both journals with/without project filters, history exclusions and
  replay, plus independent custom-unit ensure/precheck coverage.
- All 27 existing distribution-quality runtime tests passed again after both
  fixes. Their previously documented fixture-only logging diagnostics remain.
  Independent source review found no blockers; Python syntax and diff checks pass.
- On a fresh clone of the migrated snapshot, filtered and unfiltered recovery
  each add zero inspections and one cable entry; the second call adds nothing.
  Existing journal rows, stock and upstream documents retain their fingerprints.
  No company/project ownership is inferred. Rehearsal transactions are rolled back.
- Legacy ownership reconciliation remains open: 358 old journal records lack
  exact company/project owners. Do not enable owned-only journal reads as a
  workaround or silently adopt those records. Production and its flags are unchanged.
