# E6 Approved Project-Budget Adjustment Event

## Status

The three business decisions were accepted by the human owner on 2026-08-07.
This authorizes implementation through separately reviewed, reversible slices;
it does not authorize an unreviewed production schema or business-data apply.

## Objective

Allow an approved customer-estimate revision to change the stored project
contract budget without rewriting payments, work history, acts, invoices,
warehouse history or any other accounting fact.

The project card currently stores the contract budget in `projects.budget`.
Operational customer plan/done values are calculated separately from all active
customer estimates across work packages. E6 therefore applies only the exact
approved revision delta, not the complete total of one package estimate:

```text
adjustment = approved_reconciliation.next_total
           - approved_reconciliation.base_total

project_budget_after = project_budget_before + adjustment
```

This preserves the budget contribution of every other work package and any
contract amount outside the revised estimate.

The current `projects.budget` column is floating point while reconciliation
totals are already `NUMERIC(14,2)`. Exact financial events therefore require a
bounded, read-only value audit followed by a separately reviewed, lossless
conversion of the project budget to `NUMERIC(14,2)`. The conversion is blocked
if any stored value is non-finite, negative, outside range or has more than two
material decimal places. Startup initialization must not perform this change.

## Proposed User Flow

1. A same-owner, same-package customer-estimate reconciliation is created and
   reviewed through the existing workflow.
2. The reconciliation reaches `Утверждена`. This does not change the project
   budget by itself.
3. An authorized leader requests a read-only adjustment preview. The server
   locks nothing permanently, recomputes source totals and returns only IDs,
   before/delta/after amounts and a deterministic plan hash.
4. The leader explicitly approves that exact hash.
5. In one transaction the server locks the reconciliation, both estimates and
   project; revalidates owner, status, totals, active revision and current
   project budget; inserts one immutable approved event; and changes only
   `projects.budget`.
6. A repeated request for the same reconciliation returns the existing event.
   A stale or conflicting hash fails with `409` and performs zero writes.

## Proposed API Contract

### Read-only preview

```http
GET /estimate-reconciliations/{id}/budget-adjustment-preview
```

Successful response:

```json
{
  "reconciliationId": 15,
  "companyId": 4,
  "projectId": 14,
  "baseEstimateId": 100,
  "nextEstimateId": 101,
  "projectBudgetBefore": "1000000.00",
  "estimateBaseTotal": "250000.00",
  "estimateNextTotal": "275000.00",
  "adjustmentAmount": "25000.00",
  "projectBudgetAfter": "1025000.00",
  "planSha256": "<64 lowercase hex characters>",
  "readyForApproval": true,
  "blockers": []
}
```

The preview is bounded, contains no estimate sections or accounting rows, and
attempts zero writes. Monetary JSON fields are canonical two-decimal strings so
browser number conversion cannot alter the approved hash.

### Explicit approval

```http
POST /estimate-reconciliations/{id}/budget-adjustment-approval
Content-Type: application/json

{"planSha256":"<exact preview hash>"}
```

Only a director or deputy director of the selected company may approve. The
response returns the immutable event ID, exact amounts, source IDs, approver and
timestamp. It never returns estimate contents or historical accounting data.

### Project history

```http
GET /projects/{id}/budget-adjustments
```

The list is tenant-bound, newest first and capped. It exposes approved events
only. A later UI slice may also project them into the existing project-events
timeline without changing any source history table.

## Proposed Data Contract

Add one guarded table owned outside startup initialization:

```text
project_budget_adjustments
  id
  company_id
  project_id
  reconciliation_id            UNIQUE
  base_estimate_id
  next_estimate_id
  project_budget_before
  estimate_base_total
  estimate_next_total
  adjustment_amount
  project_budget_after
  plan_sha256                   UNIQUE, 64 lowercase hex
  approved_by_user_id
  approved_by_name
  approved_by_role
  approved_at
  created_at
```

Database checks require positive owner/source IDs, finite non-negative monetary
amounts, `adjustment_amount = estimate_next_total - estimate_base_total`, and
`project_budget_after = project_budget_before + adjustment_amount`. The after
budget may not be negative. Foreign keys use restrictive deletion. An
immutability trigger rejects `UPDATE` and `DELETE`.

The event is a receipt, not a mutable workflow row. Draft state remains in the
existing reconciliation; no second draft lifecycle is introduced.

## Invariants And Failure Codes

- Reconciliation, both estimates and project have the same stored
  `company_id + project_id` owner.
- Reconciliation type is `Заказчик`, status is `Утверждена`, and its next
  estimate is the active revision for that exact work package.
- Locked estimate totals equal the stored reconciliation totals. Drift returns
  `409 budget_adjustment_source_drift`.
- The approval hash includes IDs, owner, before budget, both totals, delta and
  after budget. A stale hash returns `409 budget_adjustment_plan_stale`.
- One reconciliation can create at most one event. A valid repeat is
  idempotent; conflicting evidence returns `409`.
- A zero delta returns a read-only no-op preview and cannot create an event.
- Owner or role mismatch fails before any mutation with `403` or `404` as
  appropriate; ambiguous aggregate-company context returns `409`.
- `projects.budget` and the event insert commit or roll back together.

## Protected History

E6 never inserts, updates or deletes rows in:

- `project_payments`, expenses or accountable payments;
- `work_journal`, hidden-work acts or brigade acts/payments;
- supply requests, deliveries, offers or invoices;
- warehouse balances, movements, invoices or history;
- estimate sections, estimate versions or reconciliation items;
- signed project documents.

The existing reconciliation document status may already change during its own
approval flow; the separate budget approval does not rewrite that document.

## Threat Model

- **Cross-company direct ID:** resolve the reconciliation through both estimate
  parents and the selected company before returning a preview or locking rows.
- **Privilege escalation:** financial approval requires a server-resolved
  director/deputy actor; the client cannot supply approver identity.
- **Replay/double click:** unique reconciliation receipt plus row locks make the
  approval idempotent.
- **Concurrent manual budget edit:** the hash and locked before value make the
  stale approval fail rather than overwrite the newer budget.
- **Estimate drift:** recompute locked totals and active status immediately
  before the transaction writes.
- **Tampered amount:** the client submits only a plan hash; every monetary value
  is server-derived and parameterized.
- **Information disclosure:** responses contain only authorized IDs, bounded
  amounts, fixed blockers and receipt metadata.

## Commands

```bash
# Focused backend package
python3 -m unittest discover \
  -s backend/features/project_budget_adjustments -t . -p 'test_*.py'

# Optional dedicated PostgreSQL integration fixture
E6_RUN_POSTGRES_INTEGRATION=1 \
E6_TEST_DATABASE_URL='<dedicated e6_* database DSN>' \
python3 -m unittest \
  backend.features.project_budget_adjustments.test_postgres_integration

# Read-only production readiness audit
npm run audit:project-budget-adjustments

# Guarded schema dry-run (zero writes, always rolled back)
npm run audit:project-budget-adjustment-schema

# Apply only after separate review of the exact dry-run count and SHA-256
npm run migrate:project-budget-adjustment-schema -- \
  --expected-change-count '<exact dry-run count>' \
  --expected-plan-sha256 '<exact dry-run SHA-256>'

# Full regression and build gates
python3 -m unittest discover -s backend -t . -p 'test_*.py'
CI=true npm test -- --watchAll=false
npm run build
npm run smoke:prod
```

The final readiness command opens one `REPEATABLE READ`, read-only transaction,
checks the strict schema and bounded baseline, scans at most `100000` immutable
receipts, then rolls back before evaluating the static writer/route/test
inventory. It reports only fixed reason codes and owner/source IDs, caps the
issue preview at `100`, attempts zero writes and exits successfully only when
`readyForCutover=true`.

The receipt audit recomputes every stored plan hash and monetary equation and
verifies immutable actor evidence, uniqueness and current owner/source links.
It intentionally does not require the current project budget to equal the most
recent receipt's after-value: the accepted contract retains ordinary manual
budget editing for initial and non-estimate setup. A later estimate-driven
approval still hashes and locks the then-current before-value, so stale manual
changes cannot be overwritten.

The schema apply takes an exclusive lock on `projects`, repeats the conversion
audit and rebuilds the plan under that lock before running DDL. Any changed
value, catalog drift, count mismatch or hash mismatch rolls the transaction
back. Neither startup initialization nor `deploy.sh` invokes this command.

## Project Structure

- `backend/features/project_budget_adjustments/` — pure plan/hash logic,
  guarded schema/readiness tools, storage and tenant-bound routes.
- `backend/features/estimate_reconciliations/routes.py` — existing approved
  reconciliation parent; only narrow dependency injection/registration changes.
- `backend/features/projects/routes.py` — existing project budget owner; no
  broad refactor and no history rewrite.
- `src/components/ProjectBudgetAdjustmentPanel.jsx` and
  `src/components/ProjectBudgetAdjustmentHistory.jsx` — explicit responsive
  preview/confirm/immutable-history UI for a leader of the selected company.
- `src/features/estimates/projectBudgetAdjustmentActions.js` — bounded client
  allowlist, exact-cent evidence validation, fixed-error mapping and the three
  E6 HTTP calls; approval submits only the preview SHA-256.
- `src/components/EstimateReconciliationsPanel.jsx` and
  `src/features/estimates/projectEstimateRuntime.jsx` — keep reconciliation
  approval separate, resolve the effective selected-company role and wire E6
  actions without automatic apply.
- `tasks/plan.md` and `tasks/todo.md` — phased implementation and evidence.

## Code Style

Financial arithmetic is decimal, deterministic and server-owned:

```python
def adjustment_amount(base_total, next_total):
    return money(next_total) - money(base_total)

def project_budget_after(before, adjustment):
    result = money(before) + money(adjustment)
    if result < 0:
        raise BudgetAdjustmentBlocked("budget_adjustment_negative_after")
    return result
```

SQL statements are static and values are parameterized. Public diagnostics use
fixed reason codes and bounded ID-only previews.

## Testing Strategy

- Pure unit tests cover decimal normalization, deterministic hashes, negative
  after-budget rejection and zero-delta no-op behavior.
- Route tests cover selected-company ownership, director/deputy authorization,
  stale hashes, source drift, active-revision checks and response allowlists.
- Dedicated PostgreSQL tests prove atomic project/event writes, rollback on
  every blocker, concurrent double approval, idempotent repeat and immutable
  receipts.
- Protected-history SHA-256 snapshots prove all accounting, work, supply and
  warehouse tables are byte-for-byte unchanged.
- A static writer inventory permits only the reviewed event insert and guarded
  project budget update.
- A static cutover inventory requires exactly three E6 routes, two
  registrations, three public smoke checks, one approval-kernel entrypoint and
  the complete named PostgreSQL/HTTP proof set.
- The final receipt-ledger gate is hard-capped, ID-only, read-only and always
  rolled back; schema, data, ledger, writer, route and test evidence must all be
  green together.
- Full backend/frontend suites, production build and public smoke remain release
  gates.

## Boundaries

### Always

- Resolve company/project ownership and financial approval role server-side.
- Preview first, approve only an exact server hash, and lock/revalidate before
  writing.
- Keep one adjustment event and project budget update in one transaction.
- Deploy audit/schema/runtime/UI as independently reversible slices.

### Ask First

- Applying schema in production after exact dry-run count/hash review.
- Enabling the approval UI or applying against a real reconciliation.
- Changing who may approve financial adjustments.
- Removing or restricting the existing manual project-budget field.

### Never

- Derive owner, amount or approver from client claims.
- Set the whole project budget to one package estimate total.
- Auto-apply a budget change during estimate activation or reconciliation
  approval.
- Rewrite or delete historical financial/operational records.
- Manufacture production reconciliation or payment data for smoke testing.

## Success Criteria

- An approved revision can change `projects.budget` only through one explicit,
  exact-hash, authorized and immutable event.
- Multi-package projects preserve unaffected package budget amounts by applying
  only the approved delta.
- Concurrent/repeated approval creates one receipt and changes the budget once.
- Every stale, tampered, foreign, ownerless or drifted input fails with zero
  writes.
- Protected accounting and operational history remains byte-for-byte unchanged.
- Final production read-only audit reports exact schema/data/writer readiness,
  zero writes, rollback and `readyForCutover=true` before E6 closes.

## Resolved Decisions

The human owner accepted all three decisions on 2026-08-07:

1. Apply the reconciliation delta rather than replace the project budget with
   the next estimate total.
2. Restrict financial approval to director and deputy director.
3. Keep ordinary manual project-budget editing for initial/non-estimate setup;
   estimate-driven changes use only the event.
