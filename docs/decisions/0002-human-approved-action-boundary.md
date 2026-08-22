# ADR-0002: Closed registry for human-approved actions

## Status

Accepted for A12.1. Schema, runtime and production slices require separate
approval.

## Date

2026-08-22

## Context

Read-only recommendation and exception previews now cover warehouse,
estimate-impact, and accounting domains. Turning those results into actions
creates a new trust boundary: browser state and model output cannot be allowed
to select arbitrary writes, and a stale preview cannot authorize a current
mutation.

The repository already proves exact-hash budget approval and append-only,
two-factor supplier confirmation. A12 needs a shared policy without replacing
those domain-specific kernels or widening their authority.

## Decision

Use a source-code-only closed action registry. Every action kind has a fixed
preview validator, authorization policy, mutation kernel, postcondition, and
audit projection. Approval references only an immutable proposal ID and hash;
the server rebuilds and locks current evidence before applying once in a
`SERIALIZABLE` transaction.

The first registered kind records only a warehouse-anomaly review
acknowledgement. It changes no business record. Stock, money, salary,
accountable reports, signed documents, estimates, and project budgets require
separate future ADRs and explicit approval.

## Alternatives considered

### Generic action table with SQL or handler names

Rejected. Configuration or compromised data could create new write authority,
and static call-graph review would no longer prove the reachable mutations.

### Reuse `audit_log` as the approval state machine

Rejected. An audit row records an event but does not provide proposal expiry,
one-use consumption, conflict identity, or a truthful atomic link to a future
business mutation.

### Let the client submit the final values

Rejected. Browser state is stale and untrusted. The client submits identity
and exact hash only; the server derives current values.

### Enable a high-risk business action as the first pilot

Rejected. The approval infrastructure should first be proven without changing
money, inventory, legal documents, or estimates.

## Consequences

- Each new action costs a small, explicit implementation and review slice.
- A new immutable ledger schema is required before runtime enablement.
- Static inventory can prove every reachable writer and prevent registry
  expansion by data or configuration.
- The audit-only pilot validates authorization, expiry, idempotency,
  concurrency, rollback, receipts, API, UI, and operations with low business
  risk.
- The four A12.1 choices were accepted on 2026-08-22; that approval does not
  extend to schema migration, runtime registration or production enablement.
