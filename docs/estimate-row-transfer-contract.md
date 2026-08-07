# Spec: Reviewed Estimate Row Balance Transfer (E4)

## Status

Approved by the user on 2026-08-06. E4.1 is production-complete. On the same
date the user authorized the next E4.2 implementation block: an additive,
inert reviewed-mapping ledger and its tenant-bound draft/review/approve API.
This does not authorize production DDL or any assignment, request, delivery,
warehouse, accounting or payment mutation.

The E4.2 runtime and reviewed 11-change additive schema are live in production
at `c700e043`. Guarded apply and the repeated read-only schema audit are green,
and public smoke reaches all three API routes. The separately authorized
authenticated fail-closed smoke is also complete: missing-plan read returned
`404`, an invalid draft against reconciliation `#15` returned `409` before
ledger insertion, and missing-plan approval returned `404`. No approved
reconciliation or business data was manufactured for the check.

## Confirmed Decisions

1. Every transfer stores an explicit positive quantity. The server never
   assumes that the complete remaining balance should move.
2. An assignment source row may reduce only by the reviewed transfer quantity
   and never below its server-recomputed confirmed JPR quantity. Its original
   values remain in an immutable transfer ledger.
3. A target assignment uses the target estimate row price while preserving the
   source assignment's negotiated brigade price.
4. Existing supply requests, supplier workflow, deliveries, invoices,
   warehouse history and payments remain unchanged. Only the unreceived open
   request balance is attributed to the target estimate row in a separate
   ledger.
5. Estimate writers may prepare a draft mapping, but only a director or deputy
   director in the stored company context may approve and apply it.

## Objective

Provide a reviewed, exact `old estimate row -> new estimate row` operation for
one approved estimate reconciliation. It may move only:

- an explicitly reviewed part of an assignment's uncompleted plan quantity;
- an explicitly reviewed part of an open supply-request item's unreceived
  quantity.

The operation must preserve all historical evidence. Confirmed work journal
rows, signed acts, supplier history, deliveries, invoices, warehouse history,
project/brigade payments and closed requests retain their existing IDs,
parents, quantities and content.

Success means a reviewer can see a bounded impact plan containing only IDs,
exact immutable coordinates, quantities and fixed reason codes; apply can
commit only that exact plan and a repeated apply is a no-op.

## Existing System Constraints

- Brigade estimate sources are immutable
  `estimate_versions.id + section_index + item_index + item_key` coordinates.
- The strict trigger forbids mutating an existing assignment's source tuple.
- Current estimate reconciliation rows are descriptive aggregates. They group
  by normalized section/name/unit and do not preserve authoritative row
  coordinates, so `old_row_json/new_row_json` is evidence for review only.
- Material-control request lineage currently stores an estimate parent ID and
  row indexes inside `items_json`; it does not store an immutable estimate
  version or a per-source fulfilled balance.
- Confirmed JPR quantity is authoritative only when recomputed from
  `work_journal.contract_item_id` with status `Подтверждено`.
- Supply execution and warehouse history remain attached to the request and
  delivery IDs, not to a replacement estimate row.

## Authoritative Mapping

A mapping is never inferred from a name, unit, normalized reconciliation key,
generic ID or fuzzy match. A reviewed mapping contains:

- stored company ID, project ID, work package and approved reconciliation ID;
- exact source estimate-version ID, source parent estimate ID, zero-based
  section/item indexes, exact canonical item key and snapshot SHA-256;
- exact target estimate ID, zero-based section/item indexes and exact canonical
  item key;
- the canonical target snapshot ID and SHA-256 resolved inside the apply
  transaction;
- explicit assignment and/or supply quantities selected for transfer;
- creator, approver, timestamps, deterministic plan SHA-256 and terminal
  status.

The source and target estimates must have the same stored company, project,
package and estimate type as the reconciliation. The reconciliation must be
`Утверждена`. The source snapshot and current target content are parsed with
the existing canonical lineage helpers. Any drift makes the mapping stale.

## Assignment Balance Rules

For each selected `brigade_contract_items.id`, apply locks the source item,
contract, source/target estimates, target snapshot, relevant JPR rows and the
transfer ledger. It then recomputes:

```text
confirmed_quantity = SUM(work_journal.quantity)
  WHERE contract_item_id = source_item_id
    AND status = 'Подтверждено'

transferable_quantity = source_item.quantity - confirmed_quantity
```

The reviewed transfer quantity must be finite, positive and no greater than
`transferable_quantity`. The source must be an exact `source_type='estimate'`
row owned by the reconciliation's company/project/package. Invalid or
over-completed progress blocks the complete transfer.

Apply does all of the following atomically:

1. records the source item's original quantity, prices, progress and source
   tuple in an immutable ledger entry;
2. reduces only `source_item.quantity` by the reviewed transfer quantity,
   never below confirmed JPR quantity;
3. inserts one target item in the same brigade contract with the target
   immutable source tuple, transferred quantity, target estimate price,
   source brigade price and zero completed quantity;
4. recalculates the contract total and requires the brigade-price total to be
   unchanged within the existing numeric tolerance;
5. records the created target item ID and terminal applied state.

An independently existing target item is a review conflict; balances are not
silently merged. Confirmed JPR rows stay linked to the source item. Acts and
payments are not queried as mutation targets and are never updated.

## Supply Request Balance Rules

Only requests in the canonical open-status allowlist may participate. For one
exact request item index, the server computes requested and received quantity
from the stored request/delivery chain. The request item must have one
unambiguous validated old estimate source and exact material/unit/package
identity. Multiple indistinguishable request items, malformed JSON, ambiguous
delivery allocation, non-finite quantities or lineage drift are review
blockers.

The transferable supply quantity is the finite positive unreceived balance.
E4 does not edit `supply_requests.items_json`, request quantity/status,
suppliers, offers, deliveries, invoices, warehouse rows or accounting rows.
Instead it stores an immutable balance-allocation entry from the old source to
the target source. Material-control projections consume this ledger so only
the open balance follows the target row; fulfilled history remains attributed
to the original request chain.

Closed, cancelled, rejected and fully delivered requests are never transfer
candidates. A repeated allocation cannot exceed the remaining unallocated
balance.

## Workflow

1. **Impact audit (E4.1, read-only):** Inspect one reconciliation and emit
   exact candidates, blockers and bounded dependent-history counts. No schema
   or business writes.
2. **Reviewed mapping (E4.2, additive):** Add the transfer/mapping ledger and a
   tenant-bound draft/approve API. Approval stores the exact deterministic
   plan hash; no balances move yet.
3. **Assignment apply (E4.3):** Apply only approved assignment entries under
   row locks and post-check the immutable history boundary.
4. **Supply balance apply (E4.4):** Add unreceived-balance allocations and make
   the material-control projection consume them without rewriting requests.
5. **Cutover audit (E4.5):** Prove ledger consistency, idempotency, writer
   inventory and zero mutation of protected history before production apply.

Every apply phase is independently guarded and rollback-friendly. Production
dry-run and apply remain separate operator actions.

## E4.5 Cutover Readiness Contract

The cutover command is an audit, not another writer. It opens a read-only
repeatable-read transaction, checks the complete guarded E4 schema and scans
only bounded ledger identities and quantities. It recomputes every canonical
plan hash and requires assignment-transfer and supply-allocation receipts to
be all-or-none for their respective entry kind. A plan may legitimately be
pending or have only one kind applied; a partial receipt set within one kind is
always a blocker.

The report also performs a static repository inventory. It allowlists only the
reviewed E4 plan/entry/approval writes, assignment split/receipt writes and
supply-allocation inserts, and it requires the disposable PostgreSQL tests for
rollback, sequential repeat and concurrent double-apply to remain present.
This inventory complements but never replaces executing those tests.

An optional exact plan gate accepts only a positive plan ID together with its
lowercase approved SHA-256. It reports whether assignment and supply are
pending, applied or absent, but it cannot approve or apply anything. The only
production mutation path remains the authenticated director/deputy-director
API. Operators archive the exact readiness JSON, apply one kind, re-audit, then
apply the other kind and run the final global audit and smoke checks. No
synthetic production reconciliation or plan is created to exercise the path.

## E4.2 API Contract

E4.2 exposes one immutable resource collection. It has no update or delete
operation and does not expose descriptions, notes or prices:

- `POST /estimate-row-transfer-plans` creates an inert draft from one approved
  reconciliation and one to one hundred exact entries;
- `GET /estimate-row-transfer-plans/{id}` returns one tenant-bound plan for
  review;
- `POST /estimate-row-transfer-plans/{id}/approval` changes only an unchanged
  draft to `approved` after the caller repeats its exact `planSha256`.

The draft request contains `reconciliationId` and `entries`. Every entry has
`sourceKind`, positive `sourceId`, positive finite decimal `quantity`, and the
exact target `targetSectionIndex`, `targetItemIndex` and `targetItemKey`.
Supply entries additionally require `requestItemIndex` and an exact
`sourceEstimateVersionId`; assignment entries must not send either field.
Unknown fields, duplicate sources, non-canonical keys, fractional IDs/indexes,
quantities with more than six decimal places, truncated impact previews and
quantities above the server-recomputed transferable balance fail closed.

The server resolves all owners and snapshot content from PostgreSQL in one
repeatable-read transaction. A supply snapshot must belong to the base
estimate, have a canonical stored SHA-256 equal to its actual content and
match the current base snapshot. The stored plan includes company, project,
package, estimate type, reconciliation and estimate IDs; exact source/target
coordinates and snapshot hashes; source total/protected/available quantities;
and the explicitly selected transfer quantity. Those values, sorted by source
identity and serialized canonically, form `planSha256`. Actor names and
timestamps are audit metadata and are not part of the hash.

Before the full impact scan, the create route loads only the reconciliation's
stored base-estimate company, project and package. It authorizes that minimal
scope against the selected actor first, so a foreign reconciliation cannot be
used to scan snapshots, assignments or supply rows in another scope.

Estimate writers may create drafts. Only a stored-company `director` or
`deputy director` may approve. Approval locks the plan, recomputes the exact
plan from current authoritative rows, and requires the request hash, stored
hash and recomputed hash to agree. Repeated approval of the same hash is an
idempotent read; drift, a second approved plan for the reconciliation, or any
cross-tenant access fails before an update. Approval writes only plan status
and approver metadata. It never applies a balance transfer.

The schema is installed only through a separate guarded operator migration.
It is deliberately absent from `init_db()` and `deploy.sh`. Database checks,
partial uniqueness and mutation-rejection triggers enforce one approved plan
per reconciliation, immutable entries and a single `draft -> approved`
transition.

## E4.3 Assignment Apply API Contract

E4.3 adds one explicit action to an already approved E4.2 plan:

- `POST /estimate-row-transfer-plans/{id}/assignment-apply`

The body must contain exactly one field with the approved lowercase digest:

```json
{"planSha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
```

Only a director or deputy director acting in one selected stored company may
call the action. The route locks the immutable plan and runs at
`SERIALIZABLE` isolation with bounded lock and statement timeouts. The request
hash, approved hash and recomputed canonical hash must agree before any
business row can change.

For assignment entries only, the transaction locks contracts, all their item
rows, source JPR rows and the exact target estimate snapshot in deterministic
ID order. It recomputes owner/package/lineage, current source quantity,
confirmed JPR, stored contract total and target price. Any drift, cross-owner
row, existing target lineage, protected-balance violation or partial receipt
fails the whole transaction. Supply entries remain untouched for E4.4.

The source row keeps its ID, immutable lineage, progress, status and prices;
only its quantity is reduced. The new target row receives the selected
quantity, exact target snapshot lineage and current target estimate price,
while preserving the source's negotiated brigade price. Source quantity must
remain at or above both confirmed JPR and stored progress. The rounded brigade
contract total must remain unchanged.

Success returns no descriptions or prices:

```json
{
  "planId": 5,
  "planSha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "state": "assignment_applied",
  "assignmentCount": 1,
  "transfers": [
    {"entryId": 8, "sourceItemId": 41, "targetItemId": 101, "quantity": "3"}
  ],
  "appliedAt": "2026-08-07 12:00:00+03:00",
  "idempotent": false
}
```

The first call stores one immutable receipt per assignment entry. A later
exact call reads those receipts and rolls back its transaction without
business writes, returning the same transfers with `idempotent=true`.
Malformed bodies return `422`; missing plans return `404`; authorization,
stale-state, integrity, lock and serialization failures use bounded `403` or
`409` details. Unexpected database errors remain server errors and never
commit a partial split.

The receipt table and guard are part of the existing separately reviewed
schema command. The database rejects update/delete, duplicate entry receipts,
and inserts that do not match the exact approved plan, owner, quantities,
lineage, package, prices, status, contract total and current confirmed JPR.
Neither deploy nor application initialization applies this DDL automatically.

Production checkpoint `2026-08-07`: runtime `b1ff981db5be` passed public smoke;
the exact reviewed five-change E4.3 schema applied successfully and its repeat
audit is schema-ready with zero changes. Production contains zero transfer
plans, assignment receipts and approved reconciliations. An authenticated
leadership request for a deliberately missing plan returned bounded `404`, so
no reconciliation, plan or business transfer was manufactured for testing.

## E4.4 API Contract

`POST /estimate-row-transfer-plans/{id}/supply-apply` accepts only:

```json
{"planSha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
```

Only a director or deputy director acting in the selected stored company can
apply the supply entries of an approved plan. The action runs under
`SERIALIZABLE`, locks the request, delivery rows, prior allocation receipts and
immutable estimate versions, and rechecks the exact approved hash. A target
must be an exact current estimate coordinate explicitly stored as a material
row; heuristic work/material inference is not accepted at this mutation
boundary.

The operation accepts only request statuses that material control currently
counts as open `requested` quantity: `Новая`, `Подтверждена прорабом`,
`Утверждена` and `КП запрошены`. It stores one immutable receipt per reviewed
supply entry with the equation `requested = received + previously allocated +
allocated + remaining`. It never updates request, delivery, supplier,
warehouse or accounting rows.

Success is bounded and contains no material descriptions, notes or prices:

```json
{
  "planId": 5,
  "planSha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "state": "supply_allocated",
  "supplyCount": 1,
  "allocations": [
    {"entryId": 8, "requestId": 61, "requestItemIndex": 0, "quantity": "3"}
  ],
  "appliedAt": "2026-08-07 18:00:00+03:00",
  "idempotent": false
}
```

An exact repeat is read-only and returns `idempotent=true`. The internal
material-control projection receives only tenant-visible receipt metadata. It
keeps fulfilled quantity and the stored unallocated remainder on the original
identity, moves exactly the allocated open quantity to one target material
coordinate, and raises review state if snapshot, quantity or target resolution
no longer matches. Supplier-facing request responses never receive estimate
coordinates.

Production checkpoint `2026-08-07`: runtime `bf078924852b` passed the complete
public smoke, including unauthenticated `401` for supply apply. The reviewed
five-change schema plan SHA-256
`5598b4490e89b751fc1776172cf6c5443f7f406a198a18f4c4d24cecb2359916`
applied exactly `5/5`; the repeated rolled-back audit reports
`schemaReady=true`, zero changes and zero writes. A separate read-only snapshot
returned zero transfer plans, assignment receipts, supply allocations and
approved reconciliations, so production verification manufactured no business
state.

## Threat Model And Abuse Cases

### Trust boundaries

- Client mapping payloads are untrusted coordinate requests.
- Reconciliation JSON is descriptive evidence, not authority.
- Stored request JSON may be legacy, malformed or stale.
- Company/project/package ownership must come from stored parent chains.

### Assets

- confirmed production quantities and signed evidence;
- negotiated brigade price and contract value;
- procurement, warehouse and accounting history;
- tenant isolation and the ability to explain every transferred balance.

### Required controls

- Server-resolved actor and stored company context on every read/write.
- Positive integer IDs and indexes; finite decimal quantities; exact keys.
- Parameterized SQL only; no client text interpolated into statements.
- Deterministic plan hash, explicit confirmation and optimistic drift guards.
- Fixed lock order and bounded transaction/statement timeouts.
- Bounded output containing no work descriptions, commercial notes or prices.
- Immutable audit entries and idempotency uniqueness constraints.

### Abuse cases that must fail

- cross-company, cross-project, cross-package or cross-estimate-type mapping;
- fuzzy/name-only mapping or client-supplied snapshot identity;
- moving more than the current uncompleted/unreceived balance;
- moving confirmed JPR, signed acts, received stock or paid amounts;
- applying an unapproved/stale plan or applying the same plan twice;
- merging into an unrelated existing target assignment;
- partial commit when any entry fails its post-check.

## Tech Stack And Project Structure

- Python 3 / FastAPI modules under `backend/features/`;
- PostgreSQL transactions through the existing `backend.db.get_db`;
- `unittest` focused tests beside each feature module;
- existing brigade snapshot, ownership, writer-audit and supply-lineage helpers;
- task contract in `tasks/plan.md` and `tasks/todo.md`.

Likely packages are `backend/features/estimate_row_transfer/` for the audit,
plan and routes, plus narrowly scoped integrations with brigade writer audit
and material-control projection. No new dependency is planned.

## Code Style

Classification stays pure and emits bounded reason codes:

```python
def classify_assignment_balance(source_quantity, confirmed_quantity):
    if confirmed_quantity < 0 or confirmed_quantity > source_quantity:
        return {"state": "blocked", "reason": "confirmed_quantity_invalid"}
    remaining = source_quantity - confirmed_quantity
    return {"state": "ready", "transferableQuantity": remaining}
```

Database orchestration is separate from pure classification. SQL explicitly
targets `public`, uses static statements and parameterized values, and leaves
commit/rollback ownership with one top-level transaction.

## Commands

Focused tests:

```bash
python3 -m unittest discover -s backend/features/estimate_row_transfer -t . -p 'test_*.py'
```

Full backend regression:

```bash
python3 -m unittest discover -s backend -t . -p 'test_*.py'
```

Frontend and build when a UI slice is added:

```bash
npm test -- --watchAll=false
npm run build
```

E4.1 read-only impact audit:

```bash
npm run audit:estimate-row-transfer -- --reconciliation-id <id>
```

E4.2/E4.3 schema dry-run and separately guarded apply:

```bash
npm run audit:estimate-row-transfer-schema
npm run migrate:estimate-row-transfer-schema -- \
  --expected-change-count <count> \
  --expected-plan-sha256 <sha256>
```

The audit verifies not only catalog names but the expected definitions of
constraints, indexes, guard functions and triggers. The apply refuses a
changed catalog or mismatched count/hash before executing DDL.

## Testing Strategy

- Small pure tests for quantity arithmetic, exact coordinate validation,
  reason codes, deterministic hashes and bounded output.
- Route/service tests for tenant, role, package and approval enforcement.
- Real PostgreSQL integration for locks, constraints, rollback, idempotency,
  concurrent apply and protected-table non-mutation.
- Static writer audit updated before any new assignment mutation is allowed.
- Production flow is deploy inert code, public smoke, read-only audit, human
  review, guarded apply, independent post-audit.

## Boundaries

### Always

- Recompute owners, snapshots and balances inside the apply transaction.
- Preserve existing IDs and content of historical operational documents.
- Record exact before/after evidence and keep outputs bounded.
- Test every abuse case before implementing the corresponding success path.

### Ask first

- Any change to the five assumptions at the top of this document.
- Any schema apply, production balance write or expansion of approval roles.
- Any decision to split or rewrite an existing supply request.

### Never

- Infer row identity from description/name/unit alone.
- Update source lineage on an existing assignment.
- Reparent JPR, acts, deliveries, warehouse history, invoices or payments.
- Auto-apply from reconciliation approval or from background AI.
- Execute E4 DDL from `init_db()` or `deploy.sh`.

## Success Criteria

- Every applied entry cites one approved exact mapping and deterministic plan.
- Assignment source quantity never falls below confirmed JPR quantity.
- Target assignment has exact immutable lineage and preserved brigade price.
- Contract brigade total is unchanged by the transfer.
- Only unreceived open-request balance affects the target projection.
- Protected history tables have zero writes and unchanged parent IDs/content.
- Repeated apply is a no-op; plan/data drift fails before business mutation.
- Cross-tenant and ambiguous mappings fail closed with bounded reason codes.

## Open Questions

No open design question blocks the read-only E4.1 impact-audit slice. Later
write-capable slices still require their own reviewed checkpoints.
