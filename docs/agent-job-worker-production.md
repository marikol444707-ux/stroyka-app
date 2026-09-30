# A13: production agent-job worker

## Goal

Run the existing durable agent-job runner as a separate, single-process
service on the current server. HTTP requests stay independent from long work,
while operators can see queue depth, expired leases, failures and duration.

## Approved boundary

- One worker process; it processes one job at a time.
- It may claim only the immutable registry types:
  `system.worker_probe`, `director.daily_brief` and
  `estimate.revision_impact`.
- It never creates or schedules jobs by itself.
- It does not make payments, move warehouse stock or edit estimates.
- Current handlers do not call an AI model, so their model cost is not
  applicable. Adding a model-backed handler requires a separate review and
  cost instrumentation before it enters the registry.
- The repository service is disabled by default. `deploy.sh` must not install,
  start or enable it. Production activation is a separate canary step. After
  activation, deploy may restart the service only when it is already active so
  the worker and HTTP backend load the same release.

## Operator questions

The read-only report must answer:

1. How many jobs are due now, delayed, running or failed?
2. Is a running job stuck behind an expired lease?
3. How old is the oldest due job?
4. How many jobs succeeded or failed in the last 24 hours, and what is the
   recent p95 completion duration?
5. Are due jobs present whose types are outside the worker allowlist?

The report must not expose payloads, results, exception text, correlation
values, credentials or lease tokens.

## Safety and recovery

- Database monitoring runs in a read-only repeatable-read transaction and
  rolls back after the report.
- The worker uses the existing short claim, heartbeat, completion, retry and
  expired-lease recovery transactions.
- `SIGTERM` stops polling and lets the current handler finish within the
  systemd stop timeout.
- systemd restarts only failed processes and limits restart bursts.
- A canary rollback is simply stopping/disabling the worker unit. Queued jobs
  remain durable; a running job becomes recoverable after its lease expires.

## Production activation gate

Before a later canary, all of these must be true:

- the read-only report says `readyForWorker: true`;
- no expired running leases exist;
- no due disallowed job types exist;
- the service unit passes `systemd-analyze verify` on Linux;
- public and protected smoke checks remain green;
- rollback commands have been prepared and tested without deleting queue data.

## Production acceptance — 2026-10-01

The separate worker is installed and enabled on the current server. The active
unit is byte-identical to `ops/systemd/stroyka-agent-job-worker.service`, passes
`systemd-analyze verify`, runs one Python process and has no restart failures.
The normal deployment path has repeatedly stopped it with `SIGTERM`, waited for
the clean `runner_stopped` event and started the released code with a new
`runner_started` event. The HTTP service remained independent and healthy.

The read-only production report on runtime `f5e82539313c` returned:

- `63` total jobs: `63` succeeded, `0` due, delayed, running, failed or
  cancelled;
- `0` expired leases and `0` due job types outside the immutable registry;
- one success and no failures in the last 24 hours, with `150 ms` recent p95;
- complete schema readiness and `readyForWorker=true`;
- `modelCost.state=notApplicable`, because all three registered handlers are
  deterministic and model-free.

The report used a rolled-back read-only `REPEATABLE READ` transaction and
printed no payload, result, error text, correlation value, credential or lease
token. Queue data was not modified. Stopping and disabling the unit remains the
tested rollback boundary; queued rows would stay durable and recoverable.
