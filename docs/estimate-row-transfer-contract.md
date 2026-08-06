# Spec: Reviewed Estimate Row Balance Transfer (E4)

## Status

Approved by the user on 2026-08-06. This approval authorizes the read-only E4.1
implementation only; it does not authorize schema changes or production
writes.

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

Read-only audit command planned for E4.1:

```bash
npm run audit:estimate-row-transfer -- --reconciliation-id <id>
```

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
