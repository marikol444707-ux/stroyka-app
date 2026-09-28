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

### Open user-flow gap (release blocker)

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
