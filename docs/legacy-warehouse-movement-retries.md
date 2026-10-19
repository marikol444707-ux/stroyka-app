# Legacy warehouse movement retry safety

Prepared on main `c30b5c7a`; not deployed and migration not applied.

- Every line gets a UUID and frozen business date before its first POST. The draft
  retains those fields through failed requests, rerenders and partial-batch retries.
  Same-render/concurrent clicks share an in-flight guard. Confirmed lines are removed
  on partial failure; an uncertain line retains its original key.
- POST `/warehouse-movements` requires `commandId`. Malformed/missing IDs fail with
  422 and an instruction to refresh the stale client. Editing a previously committed
  command's payload returns 409, rather than treating it as a new movement.
- Company membership, project/package/warehouse permissions and the existing
  owned-distribution feature flag are checked before replay. The company + UUID key
  is serialized with a PostgreSQL transaction advisory lock. The full payload hash
  and JSON response are persisted in the same transaction as stock/history/documents.
  An identical committed retry returns that response without reapplying stock.
- Postcommit review-task creation and project AI control still run for the initial
  execution only. Transient `estimateReviewTaskId`/`estimateReviewTaskCreated` response
  decorations are no longer added: the replayable response is the core movement
  result saved before commit. Estimate-review status remains in that response.
  The UI can say review is required, but cannot count newly-created tasks from it.
- If the process dies after stock commit but before postcommit work, those existing
  best-effort review/AI side effects can be missing. This patch does not introduce an
  outbox or claim reliable delivery of ancillary tasks.
- Command IDs live in the open form, not browser storage. A discarded form/reload
  loses its retry intent; check movement history before manually creating a new one.
  Network/5xx alerts explicitly warn that the movement may have committed, to retry
  from the same form without closing/reloading, and to check history if it is lost.
  The command ledger intentionally has no expiry/cleanup that could permit old
  commands to execute twice.

## Coordinated rollout (requires separate authorization)

1. Integrate/review the prepared `0102_movement_commands` migration. The combined
   branch follows `0101_receipt_originals`, which follows
   `0100_packaging_history_guard`; this preserves one Alembic head.
2. Apply the additive migration before exposing the backend path. Runtime code never
   creates schema. Missing schema fails before stock writes.
3. Release backend and frontend together. Old open tabs without a command ID receive
   422 and need refresh. No fallback to non-idempotent movement writes is provided.
4. Validate on an isolated test database: concurrent identical requests commit one
   movement; lost-response replay leaves stock unchanged; changed payload conflicts;
   revoked access cannot replay; company keys remain isolated; partial batches resume.

## Verification

Unit/route extraction tests do not import application startup or use live DB config.
Optional real PostgreSQL tests require explicit `SUPPLY_CHAIN_RUN_POSTGRES=1` and a
validated disposable Unix-socket `SUPPLY_CHAIN_TEST_DB_*` configuration. They execute
real transaction/ledger SQL with synthetic stock mutations, not the whole business
worker. An absent fixture is an explicit skip, not proof of concurrency correctness.

## Durable follow-up

The form-only reload limitation above is superseded by the server-owned draft
protocol in [durable-movement-recovery.md](durable-movement-recovery.md). Coordinated
frontend/backend rollout and prepared migration 0103 are required; do not enable
new client code against an older server.
