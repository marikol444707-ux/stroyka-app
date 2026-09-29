# Supplier finance release preflight — 2026-09-28

## Live observations (read-only)

- Production application HEAD: `780798ab`; backend service active.
- Alembic current: `0051_supplier_offer_item_scopes`.
- Root filesystem: 77 GB total, 24 GB used, 53 GB available (31%).
- Existing production smoke script passed. Protected authenticated checks were
  explicitly skipped because no test login was supplied; this is not an
  end-to-end financial workflow verification.
- Supplier payment, allocation, settlement, opening, partial/unpaid receipt,
  VAT, invoice-line specification and allocated-refund switches are unset.
  Owned delivery sources and quality switches are 1.
- Tracked server tree is clean. Untracked historical directories and files
  exist; they were not removed or treated as disposable release artefacts.
- No deployment, migrations, feature activation or business-data writes made.

## Corrected release configuration

`resolve-frontend-build-env.sh` now exports the four supplier UI switches from
the explicitly allowlisted backend settings. Defaults are explicit false.
Systemd values override the file; duplicate file settings use the first value,
matching backend.config. Secrets are never exported.

Openings require payments. Mixed openings additionally require opening confirmations
and mixed review. Allocated refunds require payments, allocations and
settlements. Invalid values or missing dependencies stop the build. All flag
output is withheld until the complete configuration, including the existing
A10 allowlist, validates. This also fixes pre-existing partial output from the
warehouse flag resolver on A10 validation errors.

Verification: 19 tests passed across supplier/warehouse configuration and deploy
migration/build ordering. New tests first reproduced the missing supplier flags.
No frontend component or financial posting code changed in this increment.

## Remaining release gates

The earlier UI/API evidence is recorded in supplier-refund-form-2026-09-28.md.
It does not replace these remaining checks:

1. Completed on a populated synthetic database: actual Alembic 0051 → 0061,
   downgrade to 0051 before any new-feature writes, and upgrade again. Exact
   JSON snapshots of invoices, receipts, deliveries, stock, cash, payment
   documents/operations/impacts and allocation history were unchanged. Old
   payment UUID replay returned the same operation without writes; a subsequent
   payment succeeded. This is not a rehearsal on a production-data clone.
2. Inspect current legacy invoice/receipt readiness using a read-only report.
   Correction to the initial preflight: invoice-line specification tables were
   introduced in 0050, so their presence is compatible with 0051. Migration 0052
   introduces receipt proofs, not invoice specifications. Verify the audit's
   full dependencies before running it. Production read-only audit is now
   complete: see supplier-legacy-live-audit-2026-09-28.md. Of 49 invoices, 25 are
   review candidates (17 matching mixed, 7 matching single, 1 standalone) and
   24 have blocking evidence issues;
   no opening confirmations or repairs were performed.
3. Verify financial report projections and the complete current invoice →
   partial receipt → allocation → refund flow in the integrated app, not only
   the isolated payment dialog. Determine the release switches as a set.
4. Deploy with a bounded rollback stage; verify backend, database, published
   frontend and authenticated browser workflow before enabling and finalizing.
   Follow deployment-retention.md; do not create multiple full repository copies.

Current status: release preparation advanced; production activation not ready.

Latest local schema head is 0061 (atomic mixed opening bindings).
The populated Alembic upgrade/empty-review rollback/re-upgrade rehearsal was
extended through 0061 and passed. See supplier-mixed-package-review.md. Production
remains unmodified; review evidence alone does not enable financial transfer.

## Migration rehearsal finding and fix

The real Alembic runner failed at 0057 because its original revision identifier
`0057_supplier_opening_confirmations` exceeded `alembic_version.version_num`
VARCHAR(32). Individual migration-body tests did not exercise that metadata.
Changed the unreleased revision ID to `0057_supplier_openings` and updated the
0058 parent. The filename stays unchanged. Production was confirmed at 0051;
no deployed revision was renamed or stamped.

Added a regression for the whole Alembic graph (single head, now 0061, every ID fits
32 characters) and a disposable PostgreSQL upgrade/rollback/replay regression.
Both passed. The integration fixture includes the actual pre-existing 0027 and
0033 dependency migrations rather than omitting their tables. Live read-only
checks confirmed work_material_operations, supply_claim_events, invoice line
specifications/lines, payment operations, allocation groups and receipt relations
exist on production 0051. No production files or records were changed.

The test initializes version metadata only in its guarded socket-only synthetic
database after applying the baseline fixture. That operation must never be used
as a production substitute for running migrations. A rollback after writing
new opening/refund evidence is a separate guarded case, not covered by this
pre-activation rollback rehearsal.


## Combined browser checkpoint

The real browser → real authenticated API → disposable PostgreSQL mixed opening,
payment and reversal rehearsal passed, including reload/retry after a lost
post-commit confirmation response. It uncovered and fixed a dialog dependency
that disabled review before the mixed document could be registered. Frontend
regression: 122 tests passed. See supplier-mixed-package-review.md for exact SQL
balances and the scope of this evidence. Gate 3 above still requires integrated
receipt/allocation/refund verification; this checkpoint does not close it.

Latest read-only production recheck: HEAD 780798ab, service active, 53 GB free,
tracked tree clean; pre-existing untracked files retained. No production changes.


## Receipt → allocation → refund → accounting checkpoint

Added an authenticated full-app HTTP regression to RefundVatHTTPTests. Its fixture
creates current invoice lines, ships and receives two partial VAT deliveries, and
records payment 120. The test calls the application's allocation route (80 + 20),
replays the same allocation UUID, reads the refund context, then refunds 25
(release 20 from the first receipt plus 5 free). Public invoice, allocation and
legacy accounting reads agree: total 200, paid/net expense 95, debt 105,
allocated 80, free 15. Two cash rows carry authoritative payment/refund kinds.
Exact material and receipt-tax-proof snapshots do not change with the refund.

Verification on disposable PostgreSQL: partial-receipt runtime 14 tests passed;
updated refund/VAT HTTP class 12 tests passed. Accounting summary/payment panels
and cash classification: 24 frontend tests passed, including a new 120 minus 25
summary check with invoice paidAmount 95. Expense is counted once; refund is not
customer income. Fixture logs still contain missing-owner background-task and
old api_errors schema warnings; these runs do not verify those background paths.

### User-flow gap found before the allocation editor (resolved below)

Source inspection found no browser caller of POST supplier-payments/allocations
or an allocation editor. The refund panel can release existing allocations, but
the earlier browser fixture seeded those allocations through server code. Thus
its success does not prove an accountant can complete the whole flow in the UI.
This gap must be closed before declaring the block complete.

Required next increment: add an explicit payment-to-receipt allocation editor
reachable from the invoice payment dialog. Show each physical receipt, current
assignment and available payment/receipt amounts; never assign automatically.
Submit the complete replacement revision with expectedVersion and stable UUID,
persist uncertain submissions for exact retry, preserve company/user/invoice
scope and prevent concurrent payment/refund edits. Enforce capacities and access
on the server; stale revisions must require refreshed review. Reuse the existing
allocation API and financial permission checks. This is monetary attribution to
receipts, distinct from moving materials between warehouses/objects.

Then use the real browser to perform receipt → allocation → refund and inspect
accounting projections without pre-seeding allocations. Only after that finish
the release flag set, deployment and authenticated production checks. No release
or production business-data change was made in this checkpoint.


## Allocation editor implemented and exercised

SupplierAllocationPanel is now mounted in the invoice payment dialog under the
existing default-off REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED switch. That
release switch already requires backend payments, allocations and settlements.
It reuses the authorized refund-context projection (all active payments and
physical receipt IDs), and POST allocations for the complete replacement map.
The user selects a payment and enters receipt amounts; existing assignments for
other payments are preserved. Zero removes a designation. Reason and explicit
confirmation are required. No payment or stock movement is created by allocation.

The client checks payment and receipt capacities in exact kopecks, persists the
complete scope/context/UUID/body before sending and reads it back, uses Web Locks,
restores pending intent after reload and verifies the response company, group,
UUID, revision and version before clearing it. Pending/open editing blocks
payment, reversal and refund actions in the dialog. Company/user/invoice changes
remount the panel and abort old requests. Storage failures block sends.

After current authorization and UUID replay lookup, the allocation transaction
now emits a scoped allocation_not_saved 409 for stale-version or rejected
projection checks before any INSERT. Only this matching company/group/UUID
rejection lets the client discard that failed attempt and require a fresh review.
Generic conflicts, saved-UUID fingerprint conflicts and uncertain connection or
commit failures retain the command. An old successful UUID still replays normally.

Validation:
- 136 frontend tests in 12 supplier-payment suites passed.
- 13 real PostgreSQL refund/VAT HTTP tests passed, including the new scoped
  non-save/replay/fingerprint regression (which failed before the server change).
- 15 allocation store/route unit tests passed.
- Optimized production build with payment/opening/refund/mixed UI flags compiled.
- Headed Chromium with the actual dialog and authenticated real FastAPI/isolated
  PostgreSQL: fixture created two genuine partial VAT receipts and payment 120;
  no allocation was pre-seeded. Browser assigned 80 + 20, HTTP bridge discarded
  the response after commit, reload restored pending intent, retry returned
  revision 1 without a duplicate. Browser then refunded 25 (release 20 + free 5).
  Database and UI agreed: paid 95, debt 105, allocated 80, free 15, cash net 95;
  stock remained 2 units and receipt VAT 34. Mobile viewport 390×844 was inspected.
- A separate authenticated test request advanced the revision while the browser
  held an old draft. Browser save returned the explicit stale rejection, retained
  no uncertain pending command, and required reloading rather than overwriting.
  Only expected injected empty-response and stale 409 console errors occurred.

The browser and disposable database were stopped and cleaned. This closes the
missing allocation-editor gap. These are isolated dialog/full API checks, not an
authenticated deployed full-application receipt workflow. Production is unchanged;
release configuration, deployment and live authenticated verification remain.


## Production release completed — 2026-09-28

Installed runtime: `6225f667d1b8f0492a7ddf58398cae89307a762d`.
Frontend: allocation editor build from `f91c9d82`; subsequent change was backend/test only.

- Migrated to `0061_supplier_mixed_bindings`. Fingerprints of original columns in
  15 business tables remained unchanged. Enabled the staged supplier finance gates.
- Verified 146 frontend files and 3 public manifest/entrypoint checks against the
  production build. Read-only production smoke check passed.
- Backend health reports the installed SHA and healthy database; app and job worker
  are active. Initial deployment stopped on missing remote `rg`; rollback restored
  the previous app before DB changes. Resume reused the same stage and build.
- Authenticated production browser, company 1: invoice 24 payment history reads
  correctly; opening preview shows linked warehouse 46, paid 989398, remaining 0.
  Allocation context correctly reports no receipt group for this historical invoice.
  No financial confirmation, payment, allocation or refund was written in production.
- Browser verification exposed native JSONB warehouse item adaptation failure.
  Fixed serialization before the existing strict SQL package validator. Regression
  reproduced the failure first; all 7 real PostgreSQL package tests then passed,
  including malformed/mixed-package rejection and transaction recovery.
- VIST invoice 161 remains blocked for document ownership/link/requisite review.
  Historical financial discrepancies were not inferred or repaired.
- After backend, database, frontend and browser evidence passed, finalized only
  `/root/stroyka-supplier-finance-20260928-f91c9d82`. Backup and staging were removed;
  small receipt retained in `/var/log/stroyka-release-receipts/`. Free disk: 53 GB.

The technical release is complete. Historical balance confirmations and disputed
source-document links remain business review work; this release does not certify
those amounts. Financial writes were exercised only in the isolated test workflow
recorded above.
