# QA preparation diagnostics (local implementation, not runtime acceptance)

This change follows published `d73c03cea97cd2a285f191a59394d3ea9adb6c5e`.
It neither explains nor reconstructs the earlier server's generic RuntimeError.
No server run, database connection, npm build, migration or deployment was performed
while developing it. Publishing this change requires a separate instruction.

## Recorded evidence

Only an explicitly selected interactive execution creates a private
`/opt/stroyka-qa-diagnostics-*/events.jsonl` (directory mode 0700, file 0600).
The path is printed immediately, before preparation. Each record is flushed and
fsynced. Dry-run creates neither this directory nor the journal or a driver.

Records contain fixed driver stage names, start/success/failure/cleanup events,
child sequence number, an allowlisted operation family, exit code, fixed error
category, and an allowlisted SQLSTATE from the database child's structured envelope.
No commands, stderr, environment values, connection strings, SQL, exception text,
application records or configuration contents are persisted. Unknown errors remain
`unexpected_error`; missing libraries are distinguished in the DB child. The normal
CLI preserves these safe diagnostic fields. There is no credential fallback or retry.

Allocated frontend host/container staging, maintenance, publication and configuration
backup paths are recorded only against fixed QA path patterns. No directory contents
are recorded. A failure to record a stage/child start stops work before that operation.
A journal write or cleanup failure does not replace the original safe error. There
can be a gap if the process dies between allocating a directory and recording it;
the journal is evidence, not proof that every resource is known.

A subprocess failure may leave partial work. Timeout/interruption/nonzero child
exit conservatively marks the outcome uncertain; unaccepted frontend staging is
retained for inspection, including when its local cleanup flag was previously safe.
No automatic rerun, reconnect, resume or rollback is added. A durable intent journal
for confirmed database maintenance remains separate and unchanged in purpose.

## Bounded protocol before any future approved retry

1. Preserve this attempt's diagnostic journal and, if present, maintenance journal.
   Share only sanitized events, never raw service logs or environment/configuration.
2. Locate the last stage and child sequence and distinguish start without success
   from completed work. The old d73 failure has no such evidence; do not retroactively
   mark its database checks or build completed or unexecuted.
3. For the exact recorded owned paths, check that the resources still belong to this
   attempt and whether a builder/child is still active. A timed-out Docker client
   does not prove its process in the container stopped. Do not retry or delete while
   this remains unknown. Do not infer ownership from a similar directory name.
4. Review the exact tooling SHA, manifest hash and current candidate/routing state.
   Retain unknown paths. Cleanup only individually verified, no-longer-used owned
   resources under the existing cleanup authorization; no wildcard deletion.
5. Authorize one bounded next attempt only after the previous outcome is understood.
   Preparation consent does not authorize the later connection gate, session
   termination, schema replacement, container stops or routing changes. The fresh
   interactive confirmation remains mandatory. The production hold is unchanged.

These steps are a review protocol, not runnable commands or a route around a denied
audit. Failure before confirmation excludes the post-confirmation actions in this
executor, but does not establish absence of Git object delivery, readonly database
connections, package downloads or isolated frontend build activity.

## Verification and remaining limits

127 tests passed, 0 failed, 0 skipped in the final combined local unittest run:
`test_qa_diagnostics`, `test_qa_routing`, `test_qa_frontend_stage`,
`test_qa_maintenance`, `test_qa_install`, `test_qa_host_runtime`, `test_qa_topology`,
`test_qa_server_adapter`, `test_qa_release_internal`, `test_qa_bootstrap_plan`,
`test_qa_sql_inventory`, `test_qa_recovery_model`, `test_qa_startup_inventory`
(all under `scripts`). Counts include 11 new diagnostics tests, not sums of reruns.
Tests use local temporary files, fake connections and mocked transports only.

Tests cover failure classification/redaction, structured SQLSTATE, single-call auth
failure, stage order, journal-before-subprocess, cleanup/journal failures preserving
the primary error, timeout retention, inert dry-run and CLI rendering. Actual server
permissions, database authentication, PostgreSQL compatibility, package build and
runtime installation remain unverified. No claim of complete audit or release
readiness follows from these tests. SIGKILL/power loss cannot be handled by finally.
