# Company/project material mappings

Release base: deployed `1cd73516c809`, schema `0023_quality_journal_owners`.
This integrates the already implemented owned directory from the supplier-catalog
development branch without its warehouse distribution or supplier payment work.

## User behavior and access

Projects → Materials now contains “Соответствия материалов”. A mapping relates
a supplier name to an estimate name within either one exact object or its
company. The object mapping takes precedence. Original invoice names remain in
the document, and units are not converted by name matching.

The editor supports create, replace and deactivate. Replacement preserves the
previous version and author/time, requires the version the operator actually
read and returns a conflict instead of silently overwriting another edit.
Deactivation preserves history. A conflict keeps the draft for review.

The separate `/company-material-aliases` API requires a real active company
membership and its effective role. User, company and membership locks serialize
revocation with saves. Legacy profile assignments cannot restore removed project
access. Cross-company IDs, aggregate company mode, ambiguous assignments and
old numeric alias IDs are rejected. Responses use `private, no-store`.

Document transactions hold a shared company alias lock so concurrent editor
changes cannot split one receipt/control calculation across directory versions.
Business consumers explicitly pass the authorized company and, where already
resolved, exact project ID. Enabled readers never fall back to unowned aliases.

Browser snapshots include all visible scopes with a consistent revision.
Company, membership, assignment or role changes, permission refresh/errors,
in-flight writes and incomplete reads invalidate reconciliation and dependent
actions. The interface never presents a failed load as a successful empty result.

## Historical data and migration

The live read-only inventory contains 14 legacy mappings, all inactive. None is
imported, assigned an inferred owner or reactivated. New company storage starts
empty. Migration `0024_company_material_aliases` follows deployed 0023 directly;
do not run the unreleased branch's original 0013 migration or future finance
migrations. A later branch merge must reconcile the equivalent table migration.

A full database-copy rehearsal upgraded through Alembic with the repository's
pinned versions. All original columns in 143 existing application tables stayed
unchanged. Legacy mappings remain 14/0 active; new storage has zero rows. The
same inventory and original-data hashes are checked again during deployment.

## Validation and review

- PostgreSQL exercises active membership, revocation while saving, assignment
  removal, foreign IDs, company and project precedence, concurrent replacement,
  rollback, immutable history, downgrade protection and receipt/journal lineage.
- New regressions first reproduced both authorization gaps and mixed-version
  document reads, then passed with the fixes.
- Browser fixture: create, replace, deactivate, conflict/draft retention,
  switching companies with identical project names and read-only role.
  The 390px view has no page overflow; wide tables scroll within their panel.
- Frontend: 147 suites / 753 tests passed; production build compiled successfully.
- Backend fingerprints were updated only after reviewing the owned-reader and
  transaction changes; the unrelated warehouse preview handlers are unchanged.
- Dependencies and lockfile are unchanged. The existing tooling dependency audit
  reports 39 advisories (19 high, 0 critical), primarily the react-scripts build
  chain. Resolving that baseline is separate from this directory release.
- Minimal PostgreSQL fixtures log missing `api_errors.owner_scope` on deliberate
  negative requests, and receipt auto-AI cannot infer a synthetic task owner.
  These fixture limitations do not represent successful checks of those services.

## Publication and recovery

Enable together `COMPANY_MATERIAL_ALIASES_ENABLED=1` on the API and
`REACT_APP_COMPANY_MATERIAL_ALIASES_ENABLED=1` in the browser build. Keep all five
owned journal flags and the existing company-1 accounting exception, technical
comparison and assignment draft flags. Material capability UI stays disabled.
The new API prefix must be added to the existing nginx API proxy route.

Deploy only a pinned descendant of the previous release under the shared
deployment lock. Back up PostgreSQL, code, frontend, backend environment and
nginx config; stop application writers; recheck the inactive legacy inventory;
apply 0024; verify unchanged existing data; publish assets while preserving old
hashes; restart previously active units and verify health and authenticated UI.

Do not drop the owned table or turn legacy matching back on after users create
owned mappings. The downgrade refuses nonempty history. Before any new mapping
has been saved, failed publication can restore the previous runtime/config and
frontend while retaining the harmless additive schema. After new rows exist,
preserve them and fix forward with company isolation enabled.

Supplier invoices/payments remain with the other workstream. Historical journal
duplicates, units and factual inspection details are unchanged.
