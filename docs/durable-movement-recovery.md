# Durable legacy movement recovery

Migration `0103_movement_pending_drafts` follows `0102_movement_commands` and is
prepared, not applied. Deploy backend, migration and frontend together after
review. Stale clients without draft/actor identity fail closed. Owned distribution
feature flags and source/stock guards are unchanged.

## Protocol

A verified single-company session prepares an immutable draft before stock writes.
Every request uses explicit `X-Company-Mode: company`, `X-Company-Id`, and authenticated
`expectedActorUserId`. Server authorization uses the selected company's effective
membership role, project and package assignments, including on every replay.

- POST `/warehouse-movement-drafts`: `{draftId, expectedActorUserId, commands}`.
- GET `/warehouse-movement-drafts?expectedActorUserId=...`: current pending queue.
- POST `/warehouse-movements`: saved command plus `draftId` and `expectedActorUserId`.
- POST `/warehouse-movement-drafts/{draftId}/cancel`: `{expectedActorUserId}`.

Command UUIDs and normalized payloads are immutable. One unresolved draft is
allowed per actor/company, bounded to 100 commands and 256 KiB. Command bindings
prevent another actor from adopting a prior command ID. The existing company-scoped
transactional command ledger remains authoritative for committed stock and exact
replay results. No stock is posted by prepare or by uploading a document.

Reload retrieves pending work from the server. Reconciliation runs before retry,
and confirmed commands are skipped. The browser stores no credentials or movement
payload in local/session storage. Account/company/logout generations fence stale
callbacks, state updates, requests, post-refresh results and move-and-print previews.
New form submissions remain blocked while recovery is loading, failed or pending.

## Safe resolution

Business-invalid drafts can be safely resolved without blocking unrelated work
forever. Cancellation takes the same actor transaction lock as execution, reconciles
the command ledger, and permanently tombstones only commands proven uncommitted.
Already committed movements and responses stay intact. A delayed old POST cannot
execute a tombstoned command. Partial cancellation is not a stock rollback.

If source projects or packages become inaccessible, recovery and cancellation
return metadata only (`restricted: true`, IDs, completion, empty commands). They
still require current company membership and warehouse role. Prepare and execution
continue to require full current access. No unauthorized material, location,
quantity or response is returned through this lane.

Pending drafts do not expire into silently reusable commands: an uncertain outcome
must be reconciled or explicitly safely cancelled. Completed/cancelled history is
retained for audit and is not part of the active queue. Retention automation is not
introduced by this patch.

## Verification and limits

Regression tests cover lost committed responses, reload, partial business failure,
payload mismatch, company membership overlays, account switching/logout, safe
cancel, restricted recovery, and post-refresh/late-print fencing. PostgreSQL tests
are opt-in against an explicitly disposable local fixture only; skips do not prove
real concurrent transaction behavior. No live database is used as a fallback.

Postcommit ancillary AI/review task creation remains best-effort; this change does
not introduce a task outbox or claim to repair a crash after stock commit. Stable
stock/document responses deliberately exclude transient task-created decorations.
