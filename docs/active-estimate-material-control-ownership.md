# E5 Active-Estimate Material-Control Ownership

## Status

Accepted on 2026-08-07. E5.1 and E5.2 are complete in production. E5.3 runtime
owner propagation is implemented and locally verified; its production release
is pending, and the later backend-query cutover remains disabled.

## Objective

Make every active-estimate decision in material control use the stored
`company_id + project_id` owner tuple. Two companies may have projects with the
same display name without sharing an estimate, cache entry, material-plan row
or supply-request lineage.

`project_name` remains a display and legacy compatibility field. It never
selects an active estimate or grants ownership after E5 cutover.

## Assumptions

1. A material-control project is usable only when both its positive stored
   company ID and project ID are known.
2. Active estimates already have nullable stored `company_id` and `project_id`;
   E5 audits existing rows before deciding whether any data remediation is
   required.
3. Existing operational and accounting history is immutable. E5 changes
   selection, validation and cache identity; it does not rewrite receipts,
   deliveries, warehouse movements, JPR, acts or payments.
4. Missing, malformed or conflicting owner IDs fail closed and appear through
   bounded fixed-code diagnostics. A matching name is never an automatic
   fallback.
5. Production contains no synthetic reconciliation or transfer plan for E5.
   Any schema or data apply discovered by the audit is a separate guarded step.

## Current Risk

The estimate API reads `estimates.company_id` but omits it from the response.
The frontend active-estimate selector currently accepts an estimate when
either its project name matches or its project ID matches. The E5.1 static
inventory also found five backend active-estimate boundaries that still use
`project_name`: supply material control, linked-work control, project AI
control, estimate activation and material-norm suggestions.

In an all-companies view, two projects called `Школа` can therefore select or
recalculate against the wrong company's active estimate even though both
stored owner IDs are available. This is a tenant-isolation bug, not a display
ambiguity.

## Ownership Contract

The canonical owner is:

```text
project_owner = (positive company_id, positive project_id)
```

- The project row supplies the canonical tuple.
- An estimate is in scope only when both stored IDs exactly equal that tuple.
- A supplied project name, when present, must also equal the resolved project's
  current name, but name equality never substitutes for either ID.
- Global templates and ownerless legacy estimates are excluded from active
  material control.
- Exactly one active estimate is selected per owner, estimate kind and work
  package. Duplicate active rows fail closed instead of choosing the newest.
- Material-control cache keys include company ID, project ID and work package;
  they never use project name alone.
- Material plan details retain estimate ID and exact row coordinates and also
  carry the resolved company/project owner.
- Material-control supply requests send the owner tuple as a claim only. The
  server resolves the selected-company actor and stored project/estimate rows,
  then rejects a missing, foreign, stale or name-conflicting tuple.
- Every SQL query that selects an active estimate for material control filters
  by both `e.company_id` and `e.project_id`. User values remain parameterized.

## Threat Model

- **Cross-company collision:** same project name exists in two companies.
  Mitigation: exact tuple matching at API, runtime, cache and SQL boundaries.
- **Tampered client IDs:** a client combines one company's `companyId` with
  another project's `projectId`. Mitigation: server-side project resolution in
  the selected company and exact child-owner checks.
- **Legacy ownerless data:** an active estimate lacks one stored ID.
  Mitigation: read-only audit and fail-closed exclusion; no guessed backfill.
- **Stale name:** project renamed while cached payload still has its old name.
  Mitigation: stored IDs resolve ownership; a conflicting supplied name stops a
  write and forces refresh.
- **Cache bleed:** two projects share a name in an all-companies session.
  Mitigation: tuple-based cache keys and collision regression tests.

## API And Runtime Contract

- `GET /estimates`, `GET /estimates-summary` and `GET /estimates/{id}` expose
  the stored `companyId` together with the existing `projectId`.
- Frontend project/estimate identity parsing accepts only positive decimal
  integer IDs and rejects booleans, fractions, arrays and empty values.
- Material-control functions take a project object or an immutable owner object;
  name-only calls are removed from the active-estimate path.
- A versioned material-control lineage payload contains `companyId`,
  `projectId`, `projectName`, work package and exact estimate row sources.
- Public response bodies remain bounded and do not expose snapshot content,
  prices or cross-tenant identifiers outside already authorized resources.

## Phased Plan

1. **E5.1 — Read-only readiness audit.** Audit active projects/estimates and
   the static active-estimate query/selector inventory. Report missing,
   mismatched, ambiguous and duplicate owner states with fixed reason codes.
   No schema, runtime selection or business write changes.
2. **E5.2 — API and strict selector.** Expose stored estimate `companyId`, add
   the pure owner matcher and make material-control estimate discovery fail
   closed on missing/mismatched IDs. Prove same-name cross-company isolation.
3. **E5.3 — Runtime identity propagation.** Pass the owner object through
   material plan/reconciliation/summary functions, tuple-key caches and their
   UI consumers. Keep display names unchanged.
4. **E5.4 — Server lineage and refresh cutover.** Version the request lineage,
   resolve the project inside the selected company, validate every source
   estimate against the exact tuple and replace name-only active-estimate SQL.
5. **E5.5 — Final readiness and production sequence.** Run real PostgreSQL
   collision/rollback tests, full regressions, deploy inert changes first, run
   the global read-only audit, and apply any separately reviewed remediation
   only with exact count/hash guards.

### E5.1 Evidence And Expected Production Result

`npm run audit:material-control-ownership` first verifies the required table
columns, then reads bounded owner metadata in one read-only repeatable-read
transaction and always rolls it back. It performs no DDL and never returns
project names, estimate contents, prices or totals.

The accepted static inventory contains one frontend selector and five backend
boundaries. Until E5.2-E5.4 replace their name predicates, a successful E5.1
production audit is expected to report `ok=true`, `nameScopedCount=6`,
`runtimeInventoryReady=false`, `readyForCutover=false`,
`writesAttempted=0` and `rolledBack=true`. `dataReady` is determined only by
the production rows; any fixed-code issue IDs require review before later
cutover work.

Production runtime `1bfae554aa47` completed this gate on 2026-08-07. The audit
reported `dataReady=true`, `schemaReady=true`, `scanComplete=true`, no duplicate
active scopes, no project-name collision groups and no data issues across `4`
active projects and `15` active estimates. It found exactly the accepted six
name-scoped boundaries and returned `readOnlyTransaction=true`,
`writesAttempted=0` and `rolledBack=true`. `runtimeInventoryReady=false` and
`readyForCutover=false` were the expected pre-E5.2 state, not audit failures.

### E5.2 Local Evidence And Expected Production Result

The shared list/summary/detail estimate mapper now exposes its already-selected
stored `companyId`. Frontend discovery uses one pure positive-ID owner matcher,
requires the exact company/project tuple and rejects conflicting names,
malformed IDs and duplicate active estimates within one kind/package group.

The focused E5 package passes `15` tests with one guarded PostgreSQL skip; the
focused frontend ownership/material consumers pass `22/22`. Full backend
discovery passes `1461` tests with `10` guarded skips, full frontend Jest passes
`313/313` in `77/77` suites, and the production build succeeds. Static inventory
now reports the expected intermediate state: `candidateCount=6`,
`ownerScopedCount=1`, `nameScopedCount=5` and only the five accepted backend
violations. Therefore `runtimeInventoryReady=false` remains expected until the
E5.4 backend-query cutover.

Production runtime `9c8ba525932f` deployed atomically on 2026-08-07, remained
active and passed the complete public smoke. The post-deploy audit verified the
same `4` active projects and `15/15` valid active estimates with no duplicates,
collisions or data issues. Static inventory reported `candidateCount=6`,
`ownerScopedCount=1`, `nameScopedCount=5` and only the five accepted backend
violations. The report attempted zero writes and rolled back. Protected smoke
was not run because credentials were not supplied; this slice did not alter
authentication or authorization rules.

### E5.3 Local Evidence And Expected Production Result

Material plan, work-norm projection, reconciliation and summary functions now
accept a stored project or immutable `{companyId, projectId, projectName}`
owner. The boundary rejects malformed, incomplete and name-only scopes. Legacy
document/invoice entry points resolve a name only when exactly one stored
project with a valid owner exists; collisions fail closed.

Reconciliation caches use `companyId + projectId + workPackage`; summary caches
use the same tuple with an empty package. Project materials, warehouse control,
all-project review, finance/economy, dashboard, AI review, master hints, supply
planning and print consumers pass the stored project object while continuing to
display the existing project name and totals.

TDD reproduced the same-name cache bleed before the change. The focused owner,
runtime, reconciliation, norm and all-project suites pass `33/33`; full
frontend Jest passes `318/318` in `77/77` suites, the `16` focused backend tests
pass with one guarded PostgreSQL skip, and the production build succeeds. The local read-only
audit used the older developer schema, returned the bounded expected
`material_control_owner_schema_not_ready` issue, attempted zero writes and
rolled back; its static inventory remained exactly `6` candidates, `1`
owner-scoped frontend selector and the `5` accepted backend violations.

Production acceptance requires an atomic deploy, active service, complete
public smoke and the production read-only audit confirming the same clean
`4`-project / `15`-estimate owner data. No schema or business-row apply belongs
to E5.3.

## Commands

```bash
# Focused frontend tests
CI=true npm test -- --watchAll=false --runTestsByPath \
  src/features/estimates/projectEstimateRuntime.test.jsx \
  src/features/material-control/materialRuntime.test.js \
  src/utils/materialReconciliationUtils.test.js \
  src/utils/materialNormSelectors.test.js \
  src/components/AllProjectsMaterialProjectionReview.test.jsx

# Focused backend tests; the E5 package is added in E5.1
python3 -m unittest discover -s backend/features/material_control_ownership -t . -p 'test_*.py'

# Read-only environment audit
npm run audit:material-control-ownership

# Optional real PostgreSQL fixture; the database name must start with e5_
E5_RUN_POSTGRES_INTEGRATION=1 \
E5_TEST_DATABASE_URL='<dedicated e5_* database DSN>' \
python3 -m unittest \
  backend.features.material_control_ownership.test_postgres_readiness

# Full verification
python3 -m unittest discover -s backend -t . -p 'test_*.py'
CI=true npm test -- --watchAll=false
npm run build
```

## Project Structure

- `backend/features/material_control_ownership/` — read-only owner audit and
  exact backend selection helpers.
- `backend/main.py` — existing estimate response and supply-control integration
  points, kept narrow until their route family is extracted.
- `src/features/estimates/projectEstimateRuntime.jsx` — active-estimate
  selection boundary.
- `src/features/material-control/` — runtime, cache and request lineage.
- `src/utils/materialReconciliationUtils.js` — exact material-plan projection.
- `tasks/plan.md` and `tasks/todo.md` — implementation and production evidence.

## Code Style

Identity checks are small, pure and fail closed:

```javascript
const sameStoredProjectOwner = (project, estimate) => (
  positiveId(project?.companyId) !== null
  && positiveId(project?.id) !== null
  && positiveId(estimate?.companyId) === positiveId(project.companyId)
  && positiveId(estimate?.projectId) === positiveId(project.id)
);
```

Database orchestration stays separate. SQL uses static statements,
parameterized values and explicit `company_id + project_id` predicates.

## Testing Strategy

- Pure unit tests cover strict ID parsing, missing/mismatched owners, duplicate
  active estimates and tuple cache keys.
- API tests prove estimate responses expose `companyId` without weakening
  existing visibility rules.
- Real PostgreSQL tests create two companies with identically named projects
  and prove each material-control query sees only its own active estimate.
- Route tests tamper every combination of company/project/name and require a
  fail-closed response with zero writes.
- Full backend/frontend suites and the production build remain release gates.

## Boundaries

### Always

- Resolve authorization and project ownership server-side.
- Treat client IDs and names as untrusted claims.
- Keep diagnostics bounded, read-only and free of material descriptions.
- Preserve historical operational and accounting rows byte-for-byte.

### Ask First

- Any production schema or data migration discovered by E5.1.
- Applying against a real material-control supply request.
- Removing a legacy compatibility field or changing a public route shape
  beyond adding `companyId`.

### Never

- Guess an owner from a globally matching project name.
- Manufacture production business data to exercise the path.
- Auto-apply DDL during startup or deployment.
- Repair a mismatch inside a readiness report.

## Success Criteria

- Two companies with the same project name never share an active estimate,
  material-plan row, request lineage or cache entry.
- All active-estimate SQL and frontend selection use exact stored owner tuples.
- Missing or conflicting ownership produces a fixed, bounded review state and
  zero writes.
- Existing single-company behavior, displayed names and historical records are
  unchanged.
- The final production read-only report returns `readyForCutover=true` before
  E5 is marked complete.

## Open Questions

None blocking. If E5.1 finds ownerless or mismatched production rows, their
exact IDs and plan hash will be reviewed before a separate remediation step.
