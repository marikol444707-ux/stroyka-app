# Material inspection and cable journal isolation

Release starts from deployed `51990a0a`. Only journal access, receipt lineage,
historical ownership and their browser consumers are included. Supplier invoice
and payment workflows remain outside this release.

## Behavior

Journal reads, edits and AI writes resolve and lock the current company
membership. Rows join projects by both company and project IDs. Foreign IDs,
revoked memberships, wrong company headers, ambiguous project assignments and
unauthorized estimate packages are rejected. AI saves recheck the original row
and permissions after the provider returns. GET no longer reconstructs journals
when exact ownership is enabled.

Object receipts create inspection/cable rows within their stock transaction.
Invoice line ordinals identify repeated lines. Automatic delivery retries verify
the existing receipt and journal; conflicts fail without rebuilding history.
Partial receipts, concurrent retries and late failure rollback have real
PostgreSQL regression coverage.

The interface loads a complete company-scoped snapshot and filters by project
ID for views and exports. Changing company, an incomplete load, an in-flight
save or an unconfirmed save result invalidates printing and stale previews.

## Confirmed history

The owner explicitly answered “Да, все относятся к моей компании и этому
объекту” to the inventory of **340 inspection + 19 cable records**, company 1,
project 1, **Кисловодск Лицей 4**. That confirmation authorizes ownership only.
It does not assert that legacy duplicates, package assignments or cable units
have been checked or corrected.

The operator-only `quality_journals.bootstrap` pins every selected row, its
45 referenced warehouse invoices and the target owner. It rejects changed
snapshots and contradictory references. It updates only `company_id` and
`project_id`, records the exact confirmation and hashes in append-only
`quality_owner_bootstraps`, and supports idempotent replay. It never assigns
ownership from a name, a default tenant or inferred document correctness.
There is no public bootstrap endpoint and no impersonated authenticated actor.

The existing proposed review workflow in the unreleased supplier-catalog branch
is not a dependency. Its content matching holds 17 rows and has no primary
document for the stock-only cable row. The owner's explicit inventory
confirmation covers ownership of those records while preserving their contents.

## Schema and release

Migration `0023_quality_journal_owners` follows the deployed
`0022_supplier_company_catalog` directly. It adds exact owner columns, composite
foreign keys, indexes, immutable owner triggers and bootstrap audit storage.
It performs no historical assignment itself. It does **not** apply migrations
0012–0021 from the other development branch. A later integration of that branch
must reconcile its overlapping 0014 owner migration instead of running it twice.

Activate together:

- `OWNED_QUALITY_ACCESS_ENABLED=1`
- `OWNED_QUALITY_AI_ENABLED=1`
- `OWNED_INVOICE_QUALITY_ENABLED=1`
- `OWNED_DELIVERY_SOURCES_ENABLED=1`
- `OWNED_DELIVERY_QUALITY_ENABLED=1`

Do not enable warehouse distribution, financial migrations or new unrelated UI
flags. Preserve older frontend asset hashes when publishing the new build.

After binding historical owners, do not revert to legacy unrestricted reads or
drop ownership columns. The migration refuses a destructive downgrade. Restore
an entire pre-release backup only as an explicit recovery operation while
writers are stopped; otherwise fix forward with company isolation retained.

## Validation

- Full production-copy rehearsal: 143 tables; every original column unchanged
  after schema upgrade, 359 journal assignments, 45 document assignments and
  idempotent replay.
- PostgreSQL: access, revocation interleavings, guarded AI, receipt lineage,
  partial/concurrent retry, full rollback, bootstrap integrity and prior legacy
  backfill/performance regressions.
- Frontend: 143 suites / 733 tests passed; production build compiled successfully.
- Full backend regression: 3152 tests, 154 opt-in skips, no failures or errors.
- 87 real PostgreSQL checks passed across the journal and supplier regression
  suites; guarded AI was rerun after switching to the existing model gateway.
- Frontend publishing script: 11 checks passed.

## Production result — 18 September 2026

Ownership release `0f7a55e5d7e526bea2fd1f62c5a7cbab8d30f08d` completed at
21:57:35 MSK. Final frontend correction
`1cd73516c80949f9fff74079feb06340b6092e7e` completed at 22:11:41 MSK.
The latter changes only project-page context wiring and its regression test;
it requires no database changes or API restart. Public and local health report
`1cd73516c809`, database healthy, schema `0023_quality_journal_owners`.

The live migration preserved all original columns across 142 application tables
(the Alembic version table changes by design). The confirmed batch assigned
340 inspections, 19 cables and exactly 45 referenced warehouse invoices to
company 1 / project 1. One append-only ownership audit records plan digest
`0a246e2e3ad2d97fc47d14d702907222782ddb532a65fa24e833e523a2e05cbe`.
All 26 company supplier cards remain present.

The first browser check caught missing company and user context in the project
page assembly: the loader had a valid snapshot, but the page correctly refused
to display it without a confirmed scope. A regression test reproduced the
failure through `buildAppRenderContext`; explicit context forwarding fixes it
without weakening foreign-company or aggregate-mode rejection. All frontend
tests and the production build passed again after the correction.

The final build keeps the previously enabled company-1 accounting exception
checks, supply technical comparison and assignment daily draft preview flags.
Material capability UI remains disabled. All 243 published files were verified
by SHA-256; the public asset manifest matches the artifact. The browser loads
`/static/js/main.9c89df4a.js`. Previous static asset hashes remain available.

Authenticated browser evidence, using the session the owner signed into:

- Inspection API: HTTP 200, 340 rows, every owner `1:1`, `owned-v1` marker,
  590 ms in the recorded request. Cable API: HTTP 200, 19 rows, owner `1:1`,
  same marker, 173 ms.
- Native same-origin requests with company 2: HTTP 403 for both journals,
  no rows exposed. This probe uses a separate `/health` page in the same browser
  context because the app's fetch wrapper replaces explicit company headers.
  No cookies or tokens were extracted.
- Final UI: 340 inspection rows and 19 cable rows; both previews display the
  selected project and contain exactly those row counts. Print buttons are
  enabled. The operating-system print dialog was not opened.
- The cable editor opens successfully, shows source identity and received length
  as text, and offers editable inspection/installation details. It was closed
  without saving; the live check did not change journal business data.
- No JavaScript page errors during journal navigation or preview generation.
  App startup separately returned HTTP 429 for `/piecework` and the selected
  project's AI summary. These are outside the journal endpoints; the console
  also contains an unused public-site image preload warning.
- Post-release API logs contain no Traceback, journal BACKFILL ERROR, delivery
  quality recovery error, UndefinedColumn or ForeignKeyViolation.

Evidence lives in ignored `output/journal-isolation/`; screenshots are in
`output/playwright/journal-*-production.png`. Full pre-migration backup:
`/root/stroyka-journal-isolation-x_m8rlcd/backup`. The frontend correction's
additional backup is the sibling `ui-wiring-backup` directory. Deployment used
the shared deployment lock and a pinned previous Git revision. Temporary local
production SQL and restore logs were removed after validation; the server
backup remains available for recovery.

Historical duplicates, cable quantities/units and missing inspection details
are preserved. This release confirms ownership and access, not the factual
quality of those historical entries. Supplier invoice/payment business changes
remain with the parallel workstream.
