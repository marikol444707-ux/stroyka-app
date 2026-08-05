# Director Daily Brief

## Purpose

`director.daily_brief` builds one deterministic read-only brief for one
company. It does not call a model, send a message, create documents or change
projects, estimates, supply, warehouse, assignments or accounting data.

The handler accepts only this queue payload:

```json
{"briefDate":"2026-08-05"}
```

The company comes only from the claimed `agent_jobs.company_id`. A payload
cannot select another company, and project-scoped or aggregate-company jobs are
rejected before any business read. A holding/group must be processed as
separate company-owned jobs; cross-company facts are never merged inside one
handler result.

## Read boundary

The handler calls the same immutable seven-tool registry as the existing HTTP
director assistant: `projects`, `warehouse`, `supply`, `estimates`, `finances`,
`staff` and `ai_tasks`.

All queries are server-owned parameterized `SELECT` statements. One company
read uses one PostgreSQL session with `readonly=True`, no model or job payload
can provide SQL, and the transaction is rolled back after the facts are read.
Each tool result then passes the A2 field/type/count policy before aggregation;
internal fields such as financial `companyId` and unknown raw fields are
removed.

## Result

The result has a fixed version, date, summary, source counts and six ordered
sections:

1. `overdue`: project deadlines and open AI-task deadlines.
2. `shortages`: main-warehouse balance below its minimum and open shortage
   claims.
3. `documents`: estimate drafts/check states and non-terminal supply-request
   states visible through the current read contract.
4. `estimateDeviations`: informational candidate total differences between the
   two newest rows with the same project/type/package in the bounded estimate
   feed. This is not presented as a proven version-chain change.
5. `payments`: budget and net `project_payments` facts only. The deterministic
   layer does not infer debt, overspending or payment purpose from them.
6. `tasks`: open-status counts and unassigned open AI tasks.

Every section is capped at 12 ordered items and reports whether more findings
were truncated. Text fields are re-bounded for the brief, and a regression test
proves the maximum sanitized input still fits the queue's 64 KiB result limit.

The estimate and document sections intentionally report only what the current
seven-tool contract can prove. Signed acts, supplier invoices, contracts and
line-level estimate reconciliation need separately reviewed read contracts;
the brief must not guess those states.

## Operations

The local registry contains `system.worker_probe` and
`director.daily_brief`. Do not start a permanent production worker or enqueue a
production brief until the A3 production verification step is explicitly
approved. A4 will add human-facing explanation/delivery and still must not
mutate business records.
