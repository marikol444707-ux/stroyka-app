# Atomic receipt-lot distribution

Current integration and release status: [2026-09-18 release](warehouse-release-2026-09-18.md).
Earlier milestones below describe the development branch, not the deployed state.

## Scope and contract

Opt-in local implementation (`WAREHOUSE_DISTRIBUTION_ENABLED=1`, frontend
`REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true`). Allocate existing, active main
warehouse receipt lots to explicit same-company project IDs. A request contains
1..50 rows and commits all stock, movement, lot and allocation records together.
Any invalid row rolls back the whole request. No automatic FIFO or old-data repair.

Director/deputy/storekeeper/supply memberships write; finance roles and those
operational roles read. Select one company for
both this report and commands; all-company mode does not fetch data. Company ID comes from verified context;
caller IDs are assertions, never authorization. Existing aggregate stock uses
project names, so ambiguous names within a company and renamed allocation targets
must be rejected rather than guessed. Same-name projects across companies are
resolved by company and ID.

GET `/warehouse-distributions/sources`: pages of scoped available lots.
GET `/warehouse-distributions`: allocation pages with issued/returned/net quantities
and source documents. Both accept `beforeId` (exclusive positive ID), `limit`
(1..200; history defaults 100, sources 200), and literal case-insensitive `q`
(up to 200 characters, NUL rejected). History searches project/material/receipt/ID;
sources search receipt/material. History also accepts `projectId`, `dateFrom`,
`dateTo` (inclusive UTC calendar days; reversed ranges fail 422).
`nextCursor` is the last returned ID when more matches exist, otherwise null;
`items`, `truncated`, and source `max` remain compatible. Use the same filters
when continuing a page. Each request is authorized independently. History has one
repeatable-read snapshot per page, not a frozen snapshot across all pages; refresh
to see new operations or newer return totals. Reads have a 15-second SQL timeout.
POST `/warehouse-distributions`:
companyId, requestId UUID, reason, rows of lotId/projectId/quantity. POST
`/warehouse-distributions/{id}/returns`: companyId, requestId, reason, quantity.
Command IDs plus canonical payload hashes make replay safe; reused IDs with
different data conflict. Decimal quantities are positive and bounded to six places.

Returns explicitly reference one original allocation, cannot exceed its remaining
issued quantity, and must have physical aggregate stock available at the project.
They append a compensating event and replenish the original lot atomically. This
records the employee's explicit source selection; it does not prove that other
legacy consumption retained a per-lot destination balance. Net issued is not
current on-hand or work consumption. Existing legacy movements cannot be returned
through this interface by inventing an allocation.

No supplier invoice creation, supplier payment writes, payer changes or resetting
deferral. Accounting shows source receipt + object allocation, not a new liability.
Cost allocation, intercompany transfers, object-to-object provenance, unsupported
packaging conversions and automatic allocation of legacy receipts remain outside
this feature. Cancellation/mutation of an actively distributed original receipt
must fail closed; production rollout requires auditing every legacy writer.

## Implementation and verification

The existing movement body is transaction-owned and reused by both entry points.
The new command validates exact source evidence and projects exact decimal stock
deltas back onto legacy FLOAT columns, verifying the stored result with RETURNING.
Already drifted, negative, non-finite, over-six-place or >=1e8 aggregate balances
are rejected, not silently rounded or repaired. This is not a migration of all
legacy arithmetic to NUMERIC. Quantities in new lot/allocation journals are NUMERIC.

Migration 0012 creates missing shared receipt-lot prerequisites and additive
operation/allocation/return tables. Downgrade refuses business records and leaves
shared lot tables intact. Identity/immutability triggers remain active when the
API flag is off. Existing project names cannot be changed or duplicated once
referenced; source receipt identity is protected while an allocation is outstanding.

Commands acquire company advisory locks and coarse locks on materials,
warehouse_main and projects before receipt/lot/project row locks. This serializes
different companies too: a deliberate correctness-first development constraint,
not a validated production scaling solution. Legacy movement/cancellation and
metadata edits have compatible lock order; preliminary cancellation authorization
releases its read transaction before legacy DDL and repeats authorization after
locking the receipt. Other legacy writer paths still require release audit.

The warehouse move tab contains the gated editing panel. Accounting incoming
documents contain the same history in read-only mode. Applied server filters search
the full scoped registry; history and sources have independent load-more controls.
Changing source search preserves selected lots. Invalid pages and access denials
clear affected data; stale requests cannot restore an older company/filter result.
Legacy truncated responses without cursors display a warning, not a fake full list.
Returns require a physical
return attestation; batch commands support up to 50 rows.

## Completion follow-up: registry and operational roles (2026-09-16)

Confirmed before/after failures: operational roles received 403; filter parameters
were ignored; history beyond 100 and sources beyond 200 had no continuation.
These are now covered with real PostgreSQL tests, including returning the oldest
allocation after 105 issues and finding a source beyond 200 lots. Company boundaries,
membership revocation and immutable project/source guards are retained.

The earlier audit overstated the rename failure: migration 0012 already prevents
renaming a referenced project. Do not remove that guard while legacy balances are
keyed by project names. User-friendly renaming requires a coordinated ID migration,
not deleting the return identity check.

Direct object-to-object transfer remains gated pending the receiving workflow:
immediate destination acceptance versus separate dispatch/acceptance. Under the
immediate option, a safe implementation requires immutable source/destination
allocation lineage; quantity minus returns minus transferred-out entitlement;
direct A/B stock changes without changing main stock or root lot availability;
and destination-owned quality proof without changing the original acceptance.
Reuse the explicit source attestation semantics of existing returns. Do not model
an object transfer as a fictitious return to main and reissue. Package-changing
transfers require per-leg representation or must fail closed.

Historical reconciliation still requires complete authorized source inventories
and reviewed remaining quantities. Existing read-only tools in
`material_traceability/report.py`, `stock_correction_readiness.py` and
`quality_journals/ownership.py` can classify evidence; they cannot invent missing
receipt/lot ownership. No automatic repair or production connection was made.

Verification for this follow-up:

- 20 distribution contract/membership unit tests passed.
- PostgreSQL: 22 existing distribution cases, 5 registry/operational-role cases,
  11 membership cases and 27 quality-distribution cases passed. Dedicated empty
  UTF-8 database, Unix socket, synthetic users and data; not production E2E.
  The quality fixture emitted two diagnostic log errors because its synthetic
  `api_errors` table lacks `owner_scope`; business assertions passed. This does
  not verify production error-log migration readiness.
- Full frontend: 165 suites / 1007 tests passed. Feature-enabled optimized build,
  changed-source ESLint, preview self-test and diff whitespace check passed.
  Existing bundle-size and Node deprecation notices remain.
- Browser on the isolated fixture: server search requests return 200, selected
  source survives a different search, filtered empty-state is accurate, accounting
  shows no issue/return controls; 320px has no horizontal overflow. Screenshots:
  `output/playwright/warehouse-registry-mobile.png` and
  `output/playwright/warehouse-registry-accounting.png`. Console: no errors or
  warnings. Pagination completeness itself is covered by DB/component tests.
- Independent read-only backend review found no blockers; frontend review found
  no critical stale-response/pagination/access-clearing issue. Historical source
  reconciliation, receiving-workflow decision and authorized staging remain open.

Preview accepts `WAREHOUSE_PREVIEW_PORT` (default 4410) to avoid stopping another
local preview; only binds 127.0.0.1 and keeps synthetic stock in memory.

Unanswered UI commands retain payload and UUID in sessionStorage, scoped by company
and accessible only in an authorized editing view. No credentials are stored.
Navigation and reload in that tab retain the pending command; a new browser session
does not. New writes are blocked while the result is unknown; retry sends the same
command. Response shape and request ID must confirm success. Explicit access denial
clears displayed records and disables writes. Never clear a pending command merely
because a later authorization/feature-state check cannot replay it.

Closing the browser session, clearing site storage or using another tab removes
that UI protection; check the authoritative history before manually re-entering
an uncertain operation. Server idempotency applies to the UUID, not to guessed
similar-looking business payloads. Pending payloads are business drafts, so shared
devices need the same session hygiene as other authenticated application screens.

Tests: `CI=true node node_modules/react-scripts/bin/react-scripts.js test --watch=false --runInBand`;
backend: `python -m unittest discover -s backend/features/warehouse_distribution -t .`.
Build: `REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true node node_modules/react-scripts/bin/react-scripts.js build`.
Real DB tests require a new explicit `supply_chain_test_*` database over a local
Unix socket as chain_test, never an ambient production connection.

No production migrations, feature activation, actual company documents, real
email or deployment in this work. All external-model CLI reviews require approval.

## Production release gates (including applying migration with API disabled)

- Audit other legacy writers, especially material transfers, corrections and
  receipt creation, for company authorization, lock order and receipt-lot deltas.
- Existing name-based legacy material authorization is not replaced by the new
  explicit-ID API. Original receipt-line projection/selection is repaired in the
  [integrated follow-up](stock-chain-integration.md); this is not proof that every
  old workflow is tenant-safe or source-preserving.
- Validate migration on a representative baseline, backup/restore, actual company
  membership and estimate dependencies, and startup schema behavior.
- Load-test the cross-company table locks, bounded waits and rollback/retry behavior;
  replace coarse serialization before high-concurrency rollout.
- Audit existing source/aggregate precision and availability without automatic
  historical backfill. Some receipts do not yet have usable lot evidence.

The PostgreSQL feature fixture executes real movement/unit helpers and migration
SQL against legacy FLOAT stock. Authentication and estimate annotations are
synthetic dependency boundaries, not a full production end-to-end authorization
proof. Browser preview is synthetic in-memory data, not the PostgreSQL fixture.

## Verification record — 2026-09-16

- New backend: 30 passed (8 contract/unit + 22 real PostgreSQL tests); no skips.
  Includes same-key replay, competing issues/returns, full rollback, source/tenant
  validation, FLOAT fractional cycle, precision read-back rejection, immutable
  records, downgrade guards and prerequisites. Actual legacy source helper and
  new command compete under the compatibility lock. Two cancellation sessions
  test the preauth-rollback/DDL lock protocol, not the complete HTTP route.
- Related backend: 28 material-traceability + 94 materials/receipts/movement/
  source-binding/company-context tests passed. Metadata HTTP interleavings and
  full cancellation-vs-distribution remain part of rollout integration checks.
- New frontend: 19 passed, including multi-row command, partial return attestation,
  company switch, role denial, malformed responses, persistent unanswered command,
  same-ID retry and late completion not deleting a newer pending command.
- Optimized feature-enabled build and changed-source ESLint passed. Existing
  bundle-size and Node deprecation warnings are not addressed by this feature.
- Full frontend run was **not green**: 148 suites passed / one failed, 755 tests
  passed / two timed out in `PublicSitePage.actions.test.jsx`. A separate rerun
  passed 20/21; the project-sharing test still exceeded its 15-second limit,
  including when run alone. Its source was not modified; cause is not established.
- A final broad rerun excluding that public-site file ran 149 suites / 743 tests:
  147 suites and 741 tests passed; `SupplierContractRecognition.test.jsx` and
  `App.test.js` each timed out. Both passed in the earlier full run. This does not
  establish a cause or justify calling the general suite green; no unrelated
  timeouts were increased or assertions removed.
- A subsequent isolated run of App and contract recognition passed all 22 tests
  without code or timeout changes. The individually reproducible public-site
  project-sharing timeout remains unresolved.
- Local browser: one batch issues 10 + 5 from a 100-unit lot (85 remaining), then
  returns 3 against the first allocation (88 in source, 7 net issued there).
  Accounting read-only view shows the same event history and no mutation buttons;
  search works. No horizontal overflow at 320/768/1024/1440; no console errors or
  warnings in the tested fixture. Screenshots: `output/playwright/warehouse-distribution-*`.

Preview: `node scripts/preview-warehouse-distribution.cjs`, localhost port 4410;
`?readOnly=1` opens the accounting-style read view. Fixture self-test:
`node scripts/preview-warehouse-distribution.cjs --self-test`. All fixture data is
synthetic and in memory. This is not a supplier/production account.

## Legacy writer audit follow-up (2026-09-16)

### Metadata transaction regression

`backend.db.get_db` returns an autocommit connection. The material and main-stock
metadata handlers acquired transaction-only table locks without disabling it.
Both success cases were reproduced on isolated PostgreSQL with SQLSTATE `25P01`
(`NoActiveSqlTransaction`), before fixing either handler. They now explicitly set
`autocommit=False` before their first query. Their existing commit, rollback,
cleanup, quantity validation and authorization policy are otherwise unchanged.

The new `material_traceability.test_metadata_transactions` suite invokes the real
material handler and the unchanged AST-extracted main-stock handler body, with a
real PostgreSQL connection initially in autocommit mode. It checks committed
metadata without quantity/history changes, rejected stock/identity edits,
rollback after an actual UPDATE followed by an injected failure, and closure.
Only the guards' two exact `public` schema probes are redirected to the synthetic
fixture schema. Role dependencies are synthetic. This is not authenticated HTTP,
production bootstrap, baseline migration, or concurrency verification. The older
test doubles and default non-autocommit PostgreSQL fixture did not cover this
production connection-mode boundary.

Verification for this repair: 5 new metadata PostgreSQL tests, 22 existing
distribution PostgreSQL tests, 109 related unit tests and 28 traceability tests
passed (164 distinct tests). Python syntax checks and `git diff --check` passed;
independent review found no blocking issue in this narrowly scoped repair.
An initial distribution run failed all 22 cases during setup because its empty
database inherited SQL_ASCII. `SHOW server_encoding` confirmed the cause; the
same suite passed in a new empty UTF-8 database created from `template0`. No
business assertion was disabled or timeout raised. Provision UTF-8 explicitly
for both PostgreSQL suites. Frontend code/build and the previously failing
general frontend suite were not rerun for this backend-only change.

### Remaining release work, in priority order

| Area | Source evidence / current conclusion | Required next verification |
| --- | --- | --- |
| Legacy material company access | `materials/routes.py`: list has no company predicate; update selects by ID and checks project names. No policy fix in this follow-up. | Confirm company-membership/role rule, then test read/create/update with two companies, duplicate project names and denied membership. |
| Transfer creation and return | Common stock lock precedes parent access. Integrated HTTP tests cover issue/personal return against distribution return, quantity conservation and journals. | Broader work-journal/consumption interleavings, legacy provenance and load remain open. See `stock-chain-integration.md`. |
| Transfer cancellation | Common stock lock precedes transfer/project row locks. Integrated unsigned cancellation versus distribution return passes; the prior full transfer cycle covers signed/package denials. | Representative baseline, legacy writers and contention/load remain open. |
| Receipt creation and delivery acceptance | Integrated follow-up reproduces both receipt/distribution deadlocks and aligns entry transaction lock order, with full-handler rollback/replay tests. Runtime DDL remains. | Baseline migration and other legacy interleavings/load; see `stock-chain-integration.md`. |
| Duplicate project names | `_project_company_id` uses a global name lookup; manual receipt creation uses that candidate before later company checks. | Test explicit selected company with same-name projects. Possible legitimate-request rejection, not established unauthorized access. |
| Source line identity | Integrated follow-up adds authoritative original indices before filtering and updates display/selectors; stored historical references are not rewritten. | Audit historical links and remaining legacy command-side source validation; see `stock-chain-integration.md`. |
| Baseline and load | Synthetic fixtures do not represent historical production schema/data or realistic contention. | Migration rehearsal, backup/restore, precision/source audit and bounded-wait load tests remain mandatory. |

The original audit described source-supported possible deadlocks. The integrated
follow-up subsequently reproduced both receipt cases. Transfer signing changes signature fields only; it
was not identified as a stock writer. Packaging correction review records review
evidence, not stock changes; this audit does not authorize enabling stock apply.
Company-scoped stock queries and receiver-membership checks already exist in
transfer creation/cancellation; do not conflate their locking issue with the
separate legacy material directory authorization gap.

General frontend timeout investigations and the other release gates above remain
open. No production deployment, migration, feature activation, historical data
repair, supplier documents, payments or notifications were performed.

## Transfer lock-boundary follow-up (2026-09-16)

Three legacy handlers now use the existing `lock_distribution_compatible_stock`
after selected-company role authorization and before parent/receipt/balance
access: `create_material_transfer`, `return_material_from_master`, and
`delete_material_transfer`. The existing schema-presence guard retains this
ordering when the distribution API is disabled but its tables still exist.
Without that schema the guard does not add a table lock or runtime DDL. No role,
package, recipient, quantity, signature or company-policy check was changed.
Transfer signing is not a stock writer and was not modified.

Boundary unit tests execute the extracted handler bodies and real role/lock
helpers with synthetic connections. Before the fix, all three paths missed the
early lock; ordering and lock-failure expectations failed in six subcases.
They also check denial before global locking, rollback/cleanup and no extra
table lock before the distribution schema exists.

The new PostgreSQL tests explicitly distinguish protocol evidence from full
business-workflow evidence: the historical SELECT FOR UPDATE then UPDATE
protocol can upgrade a RowShare table lock after a concurrent distribution has
taken ShareRowExclusive. RowShare itself is compatible; the later RowExclusive
upgrade creates the cycle. This protocol reproduction concerns create/return's
stock access, not a claim that transfer cancellation has the identical cycle.

The three handler concurrency tests stop at substituted parent callbacks, inspect
real granted table locks, then apply synthetic stock deltas while a real
distribution API request waits. They verify that the early lock serializes those
deltas and distribution. They do not execute transfer journals, personal balances,
successful handler commit logic, real membership auth, or HTTP transfer endpoints.
Do not treat these tests as complete transfer conservation or production readiness.

The coarse lock still serializes different companies, and existing non-idempotent
transfer commands must not be blindly retried. Receipt runtime DDL and other
legacy writers remain outside this patch. Load tests, bounded waits, full HTTP
interleavings, company-isolation approval and rollout rehearsal remain open.

Verification: 4 boundary unit tests, 148 related unit tests, 4 new PostgreSQL
protocol/boundary tests and 27 existing distribution/metadata PostgreSQL tests
passed (183 distinct tests, 31 on PostgreSQL). The old protocol produced actual
SQLSTATE `40P01`; disabling the compatibility helper in-memory caused all three
PG handler-boundary cases to fail. Syntax and diff checks passed. Independent
source review found no required changes in the bounded patch. Frontend was not
changed or rebuilt; its previously recorded general-suite timeouts remain open.
All DB tests used dedicated empty UTF-8 databases over the local Unix socket.

Subsequent full authenticated transfer lifecycle coverage and quantity validation
repair are recorded in [material-transfer-workflow.md](material-transfer-workflow.md).
Those whole-handler tests supplement, rather than change the evidence limits of,
the earlier synthetic boundary tests. Transfer-versus-distribution HTTP races
remain a separate open gate.
