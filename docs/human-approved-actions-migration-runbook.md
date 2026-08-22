# A12 human-approved action ledger migration runbook

Status: reviewed local procedure only. Production execution requires separate explicit approval
for the exact commit, database, operator, maintenance window, backup and
12-change plan. This document does not authorize a deploy,
migration, feature flag, nginx reload, canary or business-data change.

## Safety boundary

The migration may create only `human_action_proposals`,
`human_action_events`, their reviewed indexes, sequences and append-only
triggers/function. It must not modify warehouse, stock, movement, estimate,
payment, salary, accountable, project, user, session or existing audit rows.
The reviewed plan SHA-256 is
`6d570c93eb504ade2a97f88ed1d12c0ea807d218049bf0db8dcf986cc2d34951`.

## Preconditions

- [ ] A new approval names the commit, database, operator and window.
- [ ] The worktree is clean and the reviewed commit is checked out.
- [ ] Backend/frontend A12 flags are absent and the route is unavailable.
- [ ] PostgreSQL health, disk capacity and backup storage are green.
- [ ] Focused/full tests, disposable PostgreSQL, build, audit and static
      inventory are green on the exact commit.
- [ ] A rollback/incident owner is present for the whole window.

## Backup and before-state

Take the normal provider snapshot and a restorable custom-format `pg_dump`.
Record its size, SHA-256 and `pg_restore --list` result in a root-owned `0700`
evidence directory outside the repository. Record ID-only counts for
`human_action_proposals`, `human_action_events` and the scoped `audit_log`
action when the tables exist. Never record credentials, cookies, session
hashes, raw preview/job JSON or business text.

Also record byte-stable row-count/checksum evidence for the protected tables
named by the A12 writer inventory. Any unexpected pre-existing A12 table,
function, trigger, index, row or catalog drift is a stop condition.

## Dry run

Use the application connection mechanism without putting credentials in shell
history. Run `run_human_action_schema_migration(connection)` with no apply
arguments. Require:

```text
dryRun = true
writesAttempted = 0
changeCount = 12
planSha256 = 6d570c93eb504ade2a97f88ed1d12c0ea807d218049bf0db8dcf986cc2d34951
readyForApply = true
```

The function must roll back. A different count/hash, nonempty blocker, missing
protected table or dependency error requires a new review; never substitute a
new expected value during the same window.

## Guarded apply

Only after the dry result receives its own approval may the operator run:

```python
from backend.features.human_approved_actions.schema_contract import (
    APPLY_CONFIRMATION as HUMAN_ACTION_SCHEMA_CONFIRMATION,
    run_human_action_schema_migration,
)

result = run_human_action_schema_migration(
    connection,
    apply=True,
    confirm=HUMAN_ACTION_SCHEMA_CONFIRMATION,
    expected_change_count=12,
    expected_plan_sha256=(
        "6d570c93eb504ade2a97f88ed1d12c0ea807d218049bf0db8dcf986cc2d34951"
    ),
)
```

Require one commit, `writesAttempted=12`, exact catalog postcheck and matching
applied SHA. Immediately rerun dry mode and require `changeCount=0`, complete
catalog state, zero writes and rollback.

## Postchecks and stop conditions

Require exact columns, constraints, indexes, restrictive foreign keys,
one-decision/one-apply uniqueness and UPDATE/DELETE/TRUNCATE rejection on both
ledger tables. Recompute all protected row counts/checksums and require exact
equality. Keep both A12 feature flags disabled.

Stop without retry on catalog/count/SHA drift, timeout, serialization or lock
failure, unexpected DML target, partial ledger object, protected-table change,
failed append-only probe, uncertain commit or private error disclosure.
Preserve the evidence and investigate from a new preflight.

## Rollback boundary

Feature disablement never requires dropping the ledger. If any proposal/event
row exists, the ledger is immutable evidence and must not be dropped. A schema
rollback is allowed only under a new approval when both ledger tables and the
scoped A12 audit count are exactly zero, the application flags are absent and
the backup is verified. Use only the reverse `rollbackSql` emitted by the exact
dry plan, then repeat catalog and protected-table checks. Database restoration
is an incident action, not a normal canary rollback.
