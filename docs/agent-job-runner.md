# Agent Job Runner

## Purpose

`npm run worker:agent-jobs` starts a process that is separate from the HTTP
application. The API may enqueue or read a job, but it never waits for a
handler or model call inside a user request.

The runner processes one job at a time. It claims only job types present in the
immutable handler registry, commits that claim, closes the database connection
and only then calls the handler. Heartbeat, success, retry and stale recovery
each use a new short transaction.

## Current scope

The production registry contains `system.worker_probe` and the A3
`director.daily_brief` handler. The brief reads one company through the shared
tenant-scoped read-tool registry, deterministically aggregates bounded facts
and does not call a model or change business data. Its detailed boundary is in
`docs/director-daily-brief.md`.

Runtime `a3ab56bb6f29` passed readiness, public/protected smoke and one
controlled company brief with exact queue cleanup. The permanent production
worker and bulk scheduling remain disabled until a separately reviewed delivery
or scheduling step. The safe manual diagnostic remains a single cycle:

```bash
npm run worker:agent-jobs -- --once
```

That command recovers leases for registered types and processes at most one due
job. Inspect the queue first: after A3 is deployed, `--once` may claim a queued
daily brief as well as a probe.

For controlled producer or scheduler hand-off, use the exact queued job ID:

```bash
npm run worker:agent-jobs -- --once --job-id <job-id>
```

Exact mode does not run global expired-lease recovery and never falls through
to another queue row. It atomically claims only that ID when it is queued, due,
below its attempt limit and present in the immutable handler allowlist. A
missing, locked, delayed, completed or disallowed target exits with code `2`
and metadata-only status `not_claimed`. `--job-id` is rejected without
`--once` so it cannot accidentally start a permanent process.

## Handler boundary

A handler receives an immutable `AgentJobContext` with one positive company
owner, optional project, request metadata, job type, attempt counters and a
validated immutable payload. It never receives a database connection, cursor,
worker ID or lease token.

Handlers must be idempotent. A process can stop after external work but before
the success transaction commits; in that case lease recovery may execute the
same job again. Unknown handlers fail closed because their job types are not
included in the claim query.

## Configuration

All values have bounded defaults and invalid values stop startup:

| Variable | Default | Meaning |
| --- | ---: | --- |
| `AGENT_JOB_WORKER_ID` | host and PID | Explicit worker identity |
| `AGENT_JOB_LEASE_SECONDS` | `120` | Claim lease duration |
| `AGENT_JOB_HEARTBEAT_SECONDS` | `30` | Lease heartbeat interval |
| `AGENT_JOB_POLL_SECONDS` | `2` | Idle polling interval |
| `AGENT_JOB_RETRY_SECONDS` | `60` | Base retry delay |
| `AGENT_JOB_RECOVERY_SECONDS` | `60` | Expired-lease recovery interval |
| `AGENT_JOB_RECOVERY_LIMIT` | `100` | Maximum rows per recovery batch |

`SIGTERM` and `SIGINT` stop polling. A running handler is allowed to finish so
the runner does not abandon a successful operation midway.

## Observability

The process writes one JSON object per event. Logs contain only operational
metadata such as job/company/project IDs, type, attempt, status, duration and
error class. Payloads, handler results, correlation values, exception text,
credentials and lease tokens are never logged.

Normal business API work is independent from this process. Database or handler
failure is logged, the job is retried within its configured attempt limit, and
expired leases are recovered in bounded batches.
