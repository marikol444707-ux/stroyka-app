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

The production registry currently contains only `system.worker_probe`. This is
a deterministic operational handler that does not read business tables, call a
model or change business data. `director.daily_brief` deliberately remains
unregistered until Task A3 provides its deterministic read-only implementation
and tests.

Do not enable a permanent production worker service before the A3 handler is
registered and its production verification step is approved. The safe current
check is a single cycle:

```bash
npm run worker:agent-jobs -- --once
```

That command recovers expired `system.worker_probe` leases and processes at
most one due probe. Other job types are not claimed.

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
