# A12: Human-approved actions

## Status

Accepted for the pure A12.1 contract, local A12.2 schema proof and private
A12.3 audit-only kernel on 2026-08-23. This document is a design boundary, not
approval to add a route, migrate the production schema, change business data,
deploy, or enable a feature flag. A12.4 and every later slice retain their own
approval boundary.

## Why this exists

The application can already build bounded, tenant-scoped previews and can
identify accounting and warehouse conditions that need attention. A preview
must never become a database mutation merely because a model, worker, browser,
or API caller asks for it. A12 introduces a controlled handoff:

`server preview -> explicit human decision -> server revalidation -> one
transactional action -> immutable receipt`

The project already contains two useful precedents:

- project budget adjustments bind approval to an exact preview SHA-256,
  rebuild the preview under lock, apply once in `SERIALIZABLE`, and retain an
  immutable history;
- supplier material capability confirmations require an active two-factor
  cookie session, exact company membership, append-only evidence, idempotency,
  revocation, bounded failures, and explicit transaction resolution.

A12 reuses those principles. It does not create a generic executor and does
not grant model output authority over SQL or business records.

## Proposed first release

The first release proves the approval mechanism with exactly one low-risk
action kind:

`warehouse_anomaly_review_acknowledged`

Applying it records that an authorised human reviewed one exact, still-current
warehouse anomaly preview. It writes only the A12 proposal/event ledger and
the company-scoped audit record. It does not alter warehouse quantities,
materials, lots, movements, invoices, payments, signed documents, estimates,
project budgets, statuses, tasks, messages, or files.

Every later business action kind is a separate reviewed slice with its own
source query, mutation kernel, invariants, PostgreSQL proof, UI wording,
canary, and production approval. A new action kind cannot be introduced by a
database row, request payload, model response, environment variable, or
plugin.

## Non-goals and protected domains

A12 v1 must not:

- execute arbitrary SQL, import a function by name, or dispatch a callback
  supplied by a caller;
- accept proposed monetary values, quantities, target statuses, document
  contents, estimate rows, or mutation fields from the browser;
- infer a target by name, fuzzy match, model text, or unverified legacy owner;
- update stock, payments, salary, accountable reports, signed documents,
  estimates, reconciliations, or project budgets;
- approve or sign on behalf of a human;
- combine proposal creation and approval into one implicit click;
- treat an audit row alone as evidence that a business mutation committed;
- register or enable a production route during local implementation.

Stock, payment, salary, accountable-report, signed-document, estimate, and
project-budget actions remain outside the v1 registry. Adding any of them
requires a new ADR and explicit human approval. Money movement and signed
documents additionally require a distinct approving human; this rule cannot
be relaxed by configuration.

## Trust model

### Trusted

- exact server-owned action-kind registry;
- current rows re-read from PostgreSQL in the action transaction;
- active cookie session, two-factor state, selected company membership, and
  action-specific role resolved from stored data;
- canonical hashes calculated from closed, versioned server projections;
- PostgreSQL constraints and transaction outcome.

### Untrusted

- browser state and hidden fields;
- IDs or company claims not re-resolved on the server;
- stored model output, job payload/result JSON, free text, filenames, URLs,
  and arbitrary JSON;
- stale preview content and a previously valid role/session;
- retries, concurrent requests, proxies, extensions, and interrupted clients.

## Closed contracts

### Proposal

A proposal is immutable and contains only:

- contract version;
- exact action kind from the source-code registry;
- company ID and optional project ID resolved by the server;
- exact source job ID used to rebuild the preview;
- closed subject kind and positive subject IDs;
- source preview version and canonical SHA-256;
- canonical proposal SHA-256;
- proposer user and membership IDs;
- creation and expiry timestamps;
- a deterministic idempotency key.

The proposed expiry is 15 minutes. Expiry uses the database clock and an
expired proposal can never be revived; the server must create a fresh preview
and proposal.

The browser may request proposal creation using only the exact preview
selector needed to rebuild the server preview. It never submits the values to
be written.

### Decision

The decision request contains exactly `proposalId`, `proposalSha256`, and one
of `approve` or `reject`. Approval requires a live cookie session, passed 2FA,
one exact selected company, an active stored membership, and an allowlisted
role. The server rechecks these facts inside the transaction.

For the v1 review acknowledgement, the proposer may also approve because no
business record changes. Protected future action kinds require a different
approver user ID and action-specific authority.

### Apply

Apply is never a generic endpoint or function registry populated at runtime.
One closed source-code mapping binds each action kind to one reviewed kernel.
The kernel:

1. opens `SERIALIZABLE`, sets bounded statement/lock/idle timeouts, and fixes
   the search path;
2. authenticates and locks the exact proposal, actor, company, and source;
3. rejects expired, rejected, consumed, foreign, malformed, or stale input;
4. rebuilds the canonical preview and proposal hash from current rows;
5. performs the allowlisted mutation, if that action kind has one;
6. inserts the application event and company/project-scoped audit receipt in
   the same transaction;
7. checks exact affected-row counts and postconditions before one commit.

Any mismatch rolls back everything. A repeated identical request returns the
existing detached receipt with `idempotent=true` and performs no write. A
different hash for the same identity is a conflict, not a new action.

### Append-only evidence

The proposed schema has an immutable proposal relation and an append-only
event relation. Events are limited to `proposed`, `approved`, `rejected`,
`applied`, and `apply_failed`. Constraints enforce one terminal human decision
and at most one successful apply per proposal. Triggers reject UPDATE/DELETE.

`apply_failed` is written only when it can truthfully describe a transaction
that did not perform the business mutation. An uncertain commit returns a
fixed `commit_outcome_unknown` error and is reconciled by reading the ledger;
the service never guesses.

Public receipts expose only version, state, action kind, exact IDs, hashes,
actor IDs, timestamps, `writesAttempted`, `committed`, and `idempotent`. They
never expose SQL, raw preview/job data, notes, credentials, exception text, or
database driver objects.

## Authorization and UI

- The backend is authoritative. Hiding a button is not authorization.
- Proposal and decision routes are default-off behind strict boolean flags and
  duplicate-free company allowlists.
- Aggregate-company mode, bearer tokens, missing CSRF, stale cookies, inactive
  memberships, and failed 2FA fail before business reads or writes.
- The UI must show the exact action, company/project, affected subject,
  current preview, expiry, and fixed consequences before an explicit click.
- Approval is disabled while context is loading, after expiry, during a
  request, or after company/project/source drift. Double-clicks cannot create
  two actions.
- The v1 button says that it records review only; it must not imply that the
  anomaly itself was corrected.

## Failure and audit rules

- Public errors are fixed codes with no input, SQL, dependency, or private
  business text in cause/context/traceback surfaces returned to the client.
- Named process-control exceptions keep identity; ordinary failures map to a
  fixed category.
- Rollback is attempted after every transaction start that does not have a
  proven commit. Cursor and connection cleanup are always attempted.
- Metrics contain only action kind, outcome code, duration bucket, company
  allowlist hit, idempotent flag, and affected-row count. They contain no raw
  payload or subject text.
- Alerts cover stale approvals, conflicts, rollback/cleanup errors, uncertain
  commits, repeated denials, latency, and queue/route saturation.

## Delivery slices

1. **A12.1 — contract and inventory:** freeze the closed action/proposal/event
   shapes, threat model, allowed source call graph, and writer inventory. No
   SQL, schema, route, registration, UI, or production change.
2. **A12.2 — schema contract:** add dry-run-first, count/SHA-guarded immutable
   proposal/event schema and disposable-PostgreSQL proof. Do not apply it to
   production.
3. **A12.3 — review-acknowledgement kernel:** create/reject/approve/apply the
   single audit-only action with 2FA, exact company scope, source revalidation,
   idempotency, concurrency, rollback, and non-leaking failures.
4. **A12.4 — default-off API:** add exact proposal/decision/history routes,
   cookie/CSRF boundaries, no-store responses, rate/concurrency limits, and
   static proof that the closed v1 registry has one action.
5. **A12.5 — review UI:** show preview, expiry, consequence, explicit decision,
   and immutable receipt; no business correction control.
6. **A12.6 — real proof and local closure:** prove the full lifecycle and
   concurrent replay in disposable PostgreSQL, run complete regressions and
   prepare separate migration/canary documents.
7. **Production checkpoint:** only after a new exact approval, migrate the
   ledger, deploy inert code, enable one company, observe, and retain a tested
   rollback. This checkpoint cannot be inferred from approval of this spec.
8. **A12.7+ — one business action per separately approved ADR:** inventory the
   existing writer first, then define exact source, actor, preview, write,
   audit, postcondition, recovery, and canary contracts. Protected domains
   remain blocked until their own slice is accepted.

## Acceptance criteria

- The v1 registry contains exactly one audit-only action kind and no generic
  execution seam.
- Proposal and decision payloads are exact, bounded, detached, canonical, and
  tenant-scoped; malformed input fails before PostgreSQL.
- Approval always binds to a current server-rebuilt hash and expires after 15
  minutes.
- Concurrent/repeated approval can produce at most one successful application
  event and one audit receipt.
- Every failure path proves rollback/cleanup and no partial business or audit
  write.
- Protected domain tables are byte-for-byte unchanged in real PostgreSQL
  tests.
- Public API/UI cannot expose raw preview data, model output, secrets, SQL, or
  arbitrary error text.
- Feature flags default off; package exports, main registration, nginx,
  deployment, schema and production data remain unchanged until their named
  slices and approvals.

## Human review decision

The user continued after the four choices were presented, approving them for
A12.1 only. This does not authorize a schema migration or runtime registration:

1. the first action is review acknowledgement only;
2. the acknowledgement expires after 15 minutes;
3. the same 2FA-authenticated eligible actor may propose and approve this
   audit-only action;
4. every protected business action requires a separate ADR, with money and
   signed-document actions requiring a second human.

The user then explicitly continued into A12.2 on 2026-08-22. That approval
covered only the local schema contract, guarded runner and disposable-
PostgreSQL proof. It did not authorize applying the schema to production,
registering runtime code, deploying, enabling a flag or inserting a ledger
row.

## A12.1 closure

The private `backend.features.human_approved_actions` package now contains an
immutable, slotted proposal/event contract and a read-only writer inventory.
The registry has exactly one `audit_only` action kind. Proposal source, actor,
UTC time, 15-minute expiry, decision, idempotency and event hashes are strict;
bool/string subclasses, unknown fields/kinds, invalid anomaly/subject pairs,
non-UTC clocks, timestamp overflow, hidden instance attributes and malformed
hashes fail with one fixed non-leaking code.

The inventory pins the current warehouse preview source and the reviewed
budget, supplier-confirmation, accounting-remediation, stock, payment,
document and estimate writer modules. It fails if the new package gains SQL,
DB/HTTP/runtime imports, mutation calls, a route, an unexpected production
module or `backend.main` registration. Current inventory reports one action,
`audit_only`, zero runtime registrations, zero database calls, zero forbidden
imports and zero violations.

Focused A12 tests pass `12/12`; related warehouse, budget and supplier
contracts pass `82/82`; full backend discovery passes `2328/2328` with `56`
expected opt-in skips. Isolated compilation and `git diff --check` pass. No
schema, SQL execution, route, main/package export, UI, production flag,
network, commit, push or deployment was added.

## A12.2 closure

The private package now contains one unregistered schema module for immutable
`human_action_proposals` and append-only `human_action_events`. The exact fresh
plan has 12 changes and SHA-256
`6d570c93eb504ade2a97f88ed1d12c0ea807d218049bf0db8dcf986cc2d34951`.
It creates only the two ledger tables, history/uniqueness indexes, one immutable
trigger function and UPDATE/DELETE/TRUNCATE guards. Constraints bind the sole
audit-only action, 15-minute expiry, hashes, owner foreign keys, one proposal
event, one terminal human decision and at most one applied event.

The dry-run-first runner accepts no application database factory and has no
CLI, route, registration or automatic apply. Apply requires the exact phrase,
catalog-derived change count and plan SHA; it uses `SERIALIZABLE`, bounded
timeouts and an advisory transaction lock, re-probes the complete schema before
commit, rolls back every no-write/error path and reports an uncertain commit
with one fixed code. A complete schema produces a truthful zero-change rollback.

The readiness probe fails closed on missing/wrong parent columns or relation
kinds, partial objects, row-type/name collisions, column/default/collation
drift, constraint and index-definition SHA drift, identity-sequence options,
ownership, RLS/rules/inheritance/policies, function-body drift and trigger
conditions/arguments/columns. The A12.1 inventory now distinguishes the one
reviewed migration file from the SQL-free runtime-safe files and still reports
zero runtime registrations and zero runtime database calls.

Focused A12 and related schema/approval suites pass `100/100`; full backend
discovery passes `2337/2337` with `56` expected opt-in skips. The launcher-owned
Unix-socket-only PostgreSQL 15 proof passes `52/52`: dry-run writes nothing,
wrong SHA rolls back, the exact 12 steps apply once, repeat inspection returns
zero changes, altered partial-index semantics and RLS are detected, protected
business snapshots are unchanged, and UPDATE/TRUNCATE plus duplicate decision/
apply events are rejected. Compilation and `git diff --check` pass. No
production database, route, main registration, UI, flag, commit, push or deploy
was changed.

The A12.3 design pass found that company/project/subject plus a content hash
cannot uniquely locate one of several successful preview jobs. Before any
production migration, the local contract was corrected to persist the exact
`source_job_id` with a restrictive foreign key to `agent_jobs`. This changed
the dry-run plan hash but not its 12-step count; the corrected schema was
reproved in the disposable PostgreSQL cluster.

## A12.3 local closure

The unregistered private kernel creates one active proposal under a stable
advisory identity lock, or returns the existing proposal without a second
write. A separate decision transaction locks and revalidates the exact
proposal, active cookie session, passed 2FA, director membership, company,
project, source job and current warehouse preview. Rejection appends one
terminal event. Approval appends `approved` and `applied` plus one scoped
`audit_log` receipt in the same `SERIALIZABLE` transaction; it performs no
warehouse or other protected-domain mutation.

Repeated approval reads the immutable events and audit receipt and returns an
idempotent result. Expiry, source drift, malformed ledger state, auth drift,
partial audit failure and unknown commit outcome fail closed with fixed errors
and rollback/cleanup. Static inventory permits INSERTs only into
`human_action_proposals`, `human_action_events` and `audit_log` and keeps the
kernel unexported and unregistered. Focused A12 tests pass `34/34`, related
warehouse/A12 tests pass `102/102`, the full backend passes `2350/2350` with
56 expected skips, and the corrected disposable PostgreSQL schema proof
passes `52/52`. Full real-PostgreSQL action concurrency and UI proof remain
explicitly deferred to A12.5-A12.6. Production schema, flags, business data
and deployment remain unchanged.

## A12.4 local closure

The default-off HTTP adapter has exactly three private routes:

- `POST /human-approved-actions/proposals`;
- `POST /human-approved-actions/decisions`;
- `GET /human-approved-actions/history`.

Registration requires the literal flag
`HUMAN_APPROVED_ACTIONS_HTTP_ENABLED=true` and exactly one canonical positive
company ID in `HUMAN_APPROVED_ACTIONS_COMPANY_IDS`; malformed, duplicate or
multi-company configuration registers nothing. Every route requires the
existing signed cookie-session authentication and a CSRF token bound to that
cookie. Bearer authorization, aggregate-company mode, foreign companies,
duplicate JSON/query keys, non-canonical IDs, request bodies over 4096 bytes
and history limits outside `1..100` fail before the private kernel.

Proposal receipts must match the requested project, source job and subject.
Decision lookup authenticates the selected company before the proposal read
and locks only a matching `proposal.company_id`. History authenticates the
same company/project before one bounded newest-first event query, validates
each immutable event contract, detaches public fields and always rolls the
read transaction back. Public responses and fixed errors carry `no-store`;
they contain no SQL, raw preview/job content, cookie, CSRF value or dependency
text.

One process-wide slot prevents concurrent route execution. Proposal and
decision attempts share a ten-per-minute company bucket; history has a
thirty-per-minute company bucket. Saturation returns a fixed `429` with
`Retry-After` before any kernel call. The static inventory now requires the
exact three paths and methods, the closed one-action policy, a route import
allowlist, zero route SQL/database calls and the unchanged kernel INSERT
targets (`human_action_proposals`, `human_action_events`, `audit_log`).

Focused A12 tests pass `47/47`, related A12/A9 HTTP/runtime tests pass
`117/117`, and full backend discovery passes `2363/2363` with `56` expected
opt-in skips. Compilation and diff checks pass. The production ledger remains
unmigrated and the new flag remains disabled; no production data, UI, canary,
commit, push or deployment changed.

## A12.5 local closure

The warehouse control screen now contains a default-off director review panel
for the single audit-only action. It is rendered only in exact company mode
when `REACT_APP_HUMAN_APPROVED_ACTIONS_ENABLED=true`, exactly one canonical
company ID is configured in `REACT_APP_HUMAN_APPROVED_ACTIONS_COMPANY_IDS`,
and the selected company matches that allowlist. Aggregate mode, foreign
companies and non-director roles render no control.

The operator selects a loaded project, completed source job, one closed-registry
anomaly kind and its affected record. A separate read-only warehouse preview
shows the exact company, project, source job, affected subject, finding and
next step. The consequence text states that approval records only a review
fact: it does not change invoices, stock, movements or amounts and does not
mark the anomaly corrected. Proposal creation, approval and rejection are
separate requests; approval uses the explicit label
`Записать факт проверки — данные не исправляются` and returns an immutable
proposal/event/audit receipt.

Client responses are exact-shape validated and detached before rendering.
The API cookie-only capability inventory covers preview, proposal, decision
and history paths, so a cookie `401` cannot fall back to legacy bearer
authorization. One in-flight operation is allowed, stale async results are
discarded, expired proposals disable decisions, and company, source or loaded
project drift clears the old preview/proposal/receipt before another action.
React text rendering is used without an HTML injection seam.

Focused UI/API tests pass `28/28`, full frontend tests pass `414/414`, focused
backend A12 tests pass `47/47`,
and the optimized frontend build compiles successfully. An isolated localhost
browser harness exercised desktop, keyboard and 320-pixel mobile layouts plus
preview, proposal and approval receipt; the final production-component run had
zero console errors or warnings. The flags remain absent/default-off. No
production schema, data, environment, migration, canary, commit, push or
deployment changed; real PostgreSQL lifecycle and release proof remain A12.6.

## A12.6 local closure

The full audit-only lifecycle now has a real PostgreSQL 15 proof in the
existing launcher-owned, Unix-socket-only disposable cluster. The proof runs
the current read-only preview, proposal creation and idempotent repeat,
stale-source rollback, approve/replay, reject/replay, simultaneous approval
and bounded newest-first immutable history. Exactly three proposals, eight
events and two scoped audit receipts survive; each applied proposal has one
audit receipt and every protected business table remains byte-identical.

This proof exposed three integration defects that fake cursors could not show:

- psycopg2 `RealDictRow` values were rejected at strict row boundaries;
- the current A9 preview composition received a raw database cursor instead of
  detached rows;
- the read-only history authorization query used `FOR SHARE`, which PostgreSQL
  correctly rejects in a `READ ONLY` transaction.

The fixes detach only exact trusted database row types, keep the raw cursor
inside a private adapter, and omit the lock only from history reads while
retaining it for writes. Focused A12 passes `49/49`; the disposable PostgreSQL
suite passes `52/52`; full backend passes `2365/2365` with 56 expected skips.
The unchanged frontend remains `414/414`, with its optimized build and
desktop/mobile/keyboard browser proof green. Compilation, diff, writer and
secret scans pass. Offline `npm audit` reports zero findings in 1319
dependencies; an online registry audit was not authorized.

The separate release package consists of
`docs/human-approved-actions-migration-runbook.md`,
`docs/human-approved-actions-canary.md` and
`ops-nginx-human-approved-actions.conf`. It freezes the exact 12-change plan
SHA, backup/stop/rollback rules, one-company no-manufactured-candidate canary,
three exact loopback nginx locations, 4 KiB write bodies and JSON/no-store 429
responses. These files are procedures, not production authority. No migration,
flag, nginx installation, production data, commit, push or deployment changed.
