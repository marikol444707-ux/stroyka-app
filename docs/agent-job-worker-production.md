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
  start or enable it. Production activation is a separate canary step.

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
