# Exact material return and cancellation sources

This follow-up preserves the stock row debited by each new issue in nullable
`material_transfers.source_stock_id`. Migration 0104 follows 0103 pending movement
drafts. No historical backfill, stock merge, live migration or deployment is included.

Stock selection requires exact trimmed/case-insensitive name, normalized unit,
company, project and package. Similarity and cross-package fallback never authorize
mutations. An optional `sourceStockId` selects an exact duplicate stock row, still
subject to all scope checks. Estimate processing cannot change the selected package.

Cancellation locks the transfer and source, restores only that source once, and
commits stock/history/status together. Repeated cancellation leaves stock unchanged.
Returns lock signed issues before checking available personal balance and keep the
original issued identity in return history; a newer similar stock name cannot replace it.

Missing/changed original stock, ambiguous legacy source rows, multiple issued source
IDs or alias-merged original names require reconciliation (409). No automatic allocation
or replacement row is invented. Existing incorrectly credited history is not repaired.
The shared selector also protects legacy work-writeoff restoration.

Verification includes actual AST-extracted create/return/cancel helpers and statements
on a labelled SQLite adapter. Auth/project/estimate/document boundaries are mocked;
SQLite strips FOR UPDATE and does not prove PostgreSQL locking. Dedicated opt-in real
PostgreSQL tests use isolated schemas on explicitly configured disposable Unix sockets,
including concurrent duplicate returns/cancellations and rollback after history failure.
They do not load main/config/.env and are not authenticated HTTP end-to-end tests.
PostgreSQL tests are skipped locally unless explicitly provisioned; run them in CI.

Schema deployment must include preceding 0103 and additive 0104 before changed handlers.
Fresh-install bootstrap includes the same column. Downgrade will not erase source evidence.

Personal returns from historical issues directly from the main warehouse are blocked
for reconciliation: they must not silently credit the project warehouse instead.
Unsigned historical main-warehouse cancellations remain supported only for the exact
saved source ID or a uniquely resolved historical row in the same company.
