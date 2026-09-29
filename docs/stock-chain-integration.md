# Integrated receipt / distribution / executor block

Current integration and release status: [2026-09-18 release](warehouse-release-2026-09-18.md).
Earlier milestones below describe the development branch, not the deployed state.

Local development, 2026-09-16. No production rollout, migrations on a customer
database, feature activation, historical repair, actual payments or email sends.
Related: [distribution](warehouse-distribution.md) and
[executor workflow](material-transfer-workflow.md).

## Receipt transaction ordering

The authenticated PostgreSQL rehearsal reproduced deadlocks for both manual
receipt creation and supplier-delivery acceptance against a paused distribution.
Distribution acquired stock locks before receipt access; receipt handlers took
runtime schema locks before stock writes. This could make each wait for the other.

Both receipt entry points now acquire the existing distribution-compatible stock
lock before schema preparation or parent reads. Acceptance no longer commits
between runtime schema preparation and delivery access: the lock is retained
through receipt, stock, history, document linking and acceptance/replay. Failures
roll back that complete transaction. The guard also supports the manual receipt
handler's tuple cursor, as well as dictionary cursors.

The lock remains **schema-gated**, not feature-flag-gated. Existing allocation
integrity is required even with the distribution API/UI switched off. Role and
membership rules are unchanged. Receipt authorization remains inside the guarded
transaction, after runtime schema preparation as in the legacy implementation;
the early global lock is not a new authorization decision.

This is a bounded lock-order repair, not removal of all request-time DDL or proof
that every legacy writer is compatible. Coarse locks serialize companies too.
Migration/bootstrap cleanup, contention testing and bounded waits remain release
gates. Do not automatically retry non-idempotent legacy commands after an unknown
result; distribution retries retain their original request ID.

## Original receipt-line identity

`GET /warehouse-invoices` adds `invoiceLineIndex` to every returned item. It is a
zero-based integer derived from the **original stored JSON array**, before package
filtering. It overrides any similarly named field in stored/uploaded item data
without modifying that data. Existing fields, package filtering and filtered
totals remain unchanged; hidden items are not returned.

Example: if stored lines 0 and 1 are hidden, the first visible item may have
`invoiceLineIndex: 2`. Its displayed line number is 3, and commands must send 2,
not its new visible position 0. Duplicate material names do not identify a line.

History display and source selectors use only explicit, unique nonnegative safe
integer indices. Missing, duplicate or invalid indices are not reconstructed from
array position. Such old/stale responses require refresh or source review. A
source-less legacy movement remains possible, but is not falsely linked. UI and
API should be deployed together; a new UI against an old API cannot safely invent
the missing indices. No historical movement references are rewritten.

Packaging-review previews and saved reviews also send the original index. A
visible warning replaces actionable review rows when their identity is missing or
ambiguous. This changes which source is reviewed, not authorization or permission
to apply a stock correction.

Invoice-to-executor preparation keeps same-name source lines separate. The editor
uses invoice + original line as its row identity, so editing/removing one does not
change its sibling. Ordinary source-less rows remain independently selectable and
cannot inherit a parent form's stale invoice link. Suggested quantities share the
same physical stock budget; the editor checks the aggregate before issuing any
HTTP request. Invoice cards calculate issued quantities by company + receipt +
original line, not material-name keys. Potentially related legacy transfers without
adequate identity show `не подтверждено` instead of a falsely verified zero.

## Full-runtime rehearsal

`backend/features/material_traceability/test_stock_chain_postgres.py` uses the
existing guarded full application fixture, real signed authentication tokens,
company memberships, estimate checks and complete registered HTTP handlers.
Whole migration 0012 is applied only to a new empty UTF-8 Unix-socket test DB.
No ambient `.env`/database settings or outbound TCP are allowed. The only business
integration disabled is the external post-commit AI hook.

Eight scenarios cover:

1. An executor issue and a distribution return compete for the same two units.
   Only one can spend them; object stock + main stock + issued quantity is conserved.
2. A manual main-warehouse receipt overlaps distribution of an existing lot.
   Both finish, correct stock remains, distribution replay does not move it twice.
3. The real request → approval → addressed supplier offer → invoice → shipment
   workflow leads to acceptance concurrent with distribution. Replay is stable.
4. A foreman sees original indices `[1, 2]`, not hidden item 0 or spoofed indices.
   A movement selecting the wrong material line is rejected; selecting original
   line 2 persists that exact source in the movement and changes stock once.
5. A late receipt-lot persistence failure rolls back the manual receipt, stock,
   histories and lots. An explicit retry succeeds once; a duplicate is rejected.
6. A late stock persistence failure rolls back acceptance, receipt and invoice
   linkage. Retry accepts once; later replay preserves every business row.
7. Unsigned executor-transfer cancellation overlaps a distribution return.
8. A signed executor's personal return overlaps a distribution return.

The last two cases start with two distributed units and one issued unit. Both
concurrent actions must succeed, leaving one unit at the main warehouse and one
at the object, with the expected transfer/personal balance and allocation journal.

Concurrency is coordinated with a test-only advisory-lock trigger and observed
PostgreSQL lock waits, not a timing-only race. The fixture uses 15-second statement
and 5-second lock timeouts. Foreign-company stock and financial document sentinels
are unchanged. Financial snapshots allow only the verified one-time
`supplier_invoices.warehouse_invoice_id` link established by acceptance; no new
supplier liability or payment is created by internal distribution.

Fault injections also expose the previously documented missing
`api_errors.owner_scope` column in the synthetic full-schema bootstrap. The
business rollback is independently asserted; error logging readiness is not fixed
or implied by these passing tests.

## Limits and remaining work

- This does not prove a physical destination lot ledger through every consumption
  path, FIFO, or provenance of material already mixed at an object.
- Legacy material-directory authorization, same-name project resolution, material
  aliases and name-based personal return history remain separate work.
- Package filtering in the response is not proof that all legacy command-side
  package/source validation is strict. In particular, existing foreman package
  policy and source/material matching across old commands need a separate audit.
- Multi-row executor issuance still uses separate HTTP transactions. Client-side
  aggregate validation is not an atomic batch API or protection against another
  user's later stock change. A partial/unknown submission needs reconciliation.
- Production baseline migration/backup/restore, load, actual SMTP scheduling,
  post-commit integrations and the general frontend timeout remain open gates.

## Verification record

- 188 related backend unit tests: 162 materials/receipts/movements/company/
  transfer/project/distribution/traceability tests, plus 26 estimate-ownership
  tests. The tuple-cursor change exposed an unrealistic unconstrained Mock result
  in the old movement test; its probe now returns the actual dictionary shape.
- 31 PostgreSQL distribution/metadata/transfer-lock regressions, seven full
  authenticated executor workflow tests, and eight integrated full-runtime tests:
  **46 PostgreSQL tests**. The final integrated run completed in 14.539 seconds.
- 101 frontend tests across ten suites; optimized frontend build succeeded with
  distribution enabled. Build tooling reports the existing Node `fs.F_OK`
  deprecation and large-bundle advisory. This is not a clean full-project suite
  result: the unrelated general frontend timeout remains unresolved.
- **335 distinct automated tests passed**; repeated reproduction/review runs are
  not counted again. Python syntax and `git diff --check` passed.
- Independent source review required editor row identity, shared stock caps and
  receipt fault-injection evidence. All three were addressed; no required findings
  remained before local commit. Reviewer did not independently rerun the suites.

The guarded PostgreSQL environment is explicitly supplied on every invocation:

```sh
SUPPLY_CHAIN_RUN_POSTGRES=1 \
SUPPLY_CHAIN_TEST_DB_HOST=/tmp/stroyka-distribution-pg.U659QZ \
SUPPLY_CHAIN_TEST_DB_PORT=55439 \
SUPPLY_CHAIN_TEST_DB_NAME=supply_chain_test_new_empty_utf8 \
python -B -m unittest backend.features.material_traceability.test_stock_chain_postgres -v
```

Provision a **new empty UTF8 database for every full-runtime run** (`template0`,
encoding UTF8, local role `chain_test`, same socket); cleanup does not erase the
full fixture's evidence. Do not reuse the example name if already populated and
never substitute an ambient/production database. Final main-run databases were
`supply_chain_test_stock_regression_20260916_a` (31),
`supply_chain_test_transfer_stock_followup_20260916_a` (7), and
`supply_chain_test_stock_main_final_20260916_b` (8).

Frontend regression command:

```sh
CI=true node node_modules/react-scripts/bin/react-scripts.js test --watchAll=false --runInBand --runTestsByPath \
  src/components/WarehouseMovementSource.test.jsx \
  src/components/WarehouseOperationsPanel.sources.test.jsx \
  src/components/WarehouseInvoicesPanel.sources.test.jsx \
  src/components/WarehouseObjectsPanel.sources.test.jsx \
  src/components/warehouse/WarehouseInvoicesParts.sources.test.jsx \
  src/features/warehouse/warehouseCrudActions.test.js \
  src/features/warehouse/distributionCommands.test.js \
  src/features/warehouse/WarehouseDistributionPanel.test.jsx \
  src/components/WarehousePage.humanApprovedActions.test.jsx \
  src/utils/materialReconciliationUtils.test.js
REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true node node_modules/react-scripts/bin/react-scripts.js build
```

The browser fixture `node scripts/preview-warehouse-source-lines.cjs` serves only
synthetic data on `127.0.0.1:4411`. It imports the real components, has no backend
or persistence, blocks network connections in CSP and captures synthetic commands
in visible page output. It is a UI rehearsal, not a browser-to-PostgreSQL E2E test.

Chromium checks confirmed: original line 2 resolves while hidden line 0, duplicate
indices and a different company do not; packaging preview sends item index 5;
two source lines suggest quantities 2 + 1 against stock 3; editing the second to 2
blocks submission without sending an issue request; removing the first leaves
only line 5; the subsequent synthetic issue sends line 5, not the stale parent
form's line 2. Per-line issued quantities remain 1 and 0.5 rather than a combined
total; adding an ambiguous legacy issue changes them to `не подтверждено`.

The mobile editor was inspected at 390px; page-width checks at 320, 768, 1024 and
1440px found no horizontal overflow in this fixture. Keyboard Tab reached the
next named button. Console: zero errors/warnings (React development info only).
Screenshots under ignored `output/playwright/`: `source-lines-aggregate-block.png`
and `source-lines-editor-mobile.png`. This is not a full accessibility audit or
production browser session. The owned browser and preview server were stopped
after verification; test databases remain retained with the cluster stopped.
