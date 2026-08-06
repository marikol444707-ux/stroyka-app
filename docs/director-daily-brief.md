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

## In-app read model

`GET /agent-jobs/director-daily-brief/latest` exposes the latest succeeded
company-scoped result to leadership for one selected company. Aggregate-company
mode and roles outside the leadership allowlist fail before the query. A
missing completed brief returns `{ "available": false }`.

The endpoint does not reuse the generic job detail projection and does not
return raw queue internals. It validates the stored schema-v1 result and builds
a new allowlisted copy containing only `jobId`, `completedAt` and the bounded
brief fields. Malformed stored data fails closed and must be regenerated.

The director dashboard renders this read model as a compact block with the
brief date, severity totals, all six section counts and up to three subjects per
section. It has explicit loading, empty, selected-company and error states and
contains no start/retry/mutation command. The company switch reloads the block
and clears the previous company's result before the next response arrives.

### Read-only attention queue

The same latest-brief response also contains `attentionQueue`. This is a
bounded projection of the already validated brief, not a separate query or
business workflow. It includes only `critical` and `warning` findings, sorts
critical items first and returns at most 12 visible rows. The count comes from
the full brief severity totals, so a truncated source section cannot silently
reduce it.

Each queue row contains a fixed priority, category, reason, subject, project,
responsible state and next safe review step. Reason, destination and next step
come from an immutable server policy keyed by the allowlisted finding code.
Unknown codes receive a fixed manual-review fallback. Fields such as an
arbitrary action, URL or command from stored result data are never copied into
the public queue.

The dashboard shows this queue before the six existing detail sections. It is
read-only and has no button or navigation side effect. Missing responsible data
is shown truthfully as `Не указан`; `task.unassigned` is shown as
`Не назначен`. Enriching responsible names requires a separately reviewed read
contract and is not inferred from unrelated fields.

## Operations

The production registry contains `system.worker_probe` and
`director.daily_brief`. Runtime `a3ab56bb6f29` passed readiness,
public/protected smoke and one controlled company brief with exact queue
cleanup. The permanent worker and bulk scheduling remain disabled. A4 will add
human-facing explanation/delivery and still must not mutate business records.

A4.1 adds only the in-app read surface. The controlled production smoke removes
its own queue row, so this screen can legitimately stay empty until a later,
explicitly approved producer persists real daily briefs. A model, MAX delivery,
bulk scheduling and a permanent daemon are still disabled.

The A4.2.1 producer keeps that boundary explicit. It requires one active
`company_id` and one ISO `brief_date`, checks the existing company/day job and
uses the queue's unique idempotency constraint. Without `--apply` it only reads
inside a PostgreSQL read-only transaction and rolls back. With `--apply` it
writes at most one system-owned queued job:

```bash
npm run enqueue:director-daily-brief -- \
  --company-id 1 --brief-date 2026-08-05

npm run enqueue:director-daily-brief -- \
  --company-id 1 --brief-date 2026-08-05 --apply
```

The command does not execute the job. Processing remains a separate explicit
operation. A4.2.2 added an exact `--once --job-id <id>` runner hand-off;
repeating the same company/date reports the existing job instead of creating a
duplicate. There is no all-companies option.

Runtime `3210bbe905f7` verified this boundary with company `1`: dry-run returned
`would_enqueue` with zero write attempts, explicit apply created job `8`, one
runner cycle completed that exact job as `succeeded`, and the repeat returned
the same existing job. The permanent worker remained disabled.

A4.2.3 combines those two reviewed boundaries into one controlled command:

```bash
npm run run:director-daily-brief -- \
  --company-id 1 --brief-date 2026-08-05

npm run run:director-daily-brief -- \
  --company-id 1 --brief-date 2026-08-05 --apply
```

The default remains read-only. Explicit apply commits the idempotent producer
transaction first, then opens the exact runner cycle only for the returned job
ID. The cycle validates that the producer result still belongs to the requested
company/date and expected job type. It never recovers or falls through to
another queue row, and its registry contains only `director.daily_brief`. An
existing successful job is not rerun; running, failed,
cancelled, delayed, locked or otherwise unclaimable work fails closed for
operator review. Runner metadata events go to stderr and the final allowlisted
report goes to stdout. The report always states `businessWritesAttempted: 0`;
only queue lifecycle metadata may change. This command is not a schedule and
does not enable a daemon, model call, MAX delivery or company fan-out.

A4.2.4 prepares a narrow scheduler adapter around that same controlled cycle:

```bash
npm run schedule:director-daily-brief -- --company-id 1
npm run schedule:director-daily-brief -- --company-id 1 --apply
```

The adapter does not accept a date from `systemd`. It derives the current
business date from the timezone-aware clock and converts it to
`Europe/Moscow`, so the VPS UTC date cannot create the previous or next day's
brief around midnight. The default command is still read-only. Explicit apply
validates that the controlled result belongs to the same company, Moscow date
and immutable job type, requires zero business writes and emits only an
allowlisted operational report.

The repository contains a one-shot service and timer template for company `1`
at `07:10 Europe/Moscow`. The service does not run the generic worker and the
normal `deploy.sh` does not copy, install or enable either unit. Runtime
`2e14a3a2ca3c` passed Linux unit validation and public smoke; a manual one-shot
completed job `9` for company `1` and Moscow date `2026-08-06` with zero
business writes. The production timer is now installed and enabled. The
permanent worker, model, MAX delivery and multi-company fan-out remain off.

Repeat production verification for exactly one leadership company with the
controlled smoke (set `SMOKE_COMPANY_ID` too when the account leads more than
one company):

```bash
SMOKE_EMAIL='director@example.com' npm run smoke:director-daily-brief
```

The smoke refuses to run when that company already has a queued/running daily
brief. It enqueues one unique max-attempts-one job, runs a registry containing
only `director.daily_brief`, validates the fixed result contract and removes
its exact queue row in `finally`. It prints section keys/statuses/counts only;
business subjects, financial values and the result body are not logged. The
permanent daemon remains off.
