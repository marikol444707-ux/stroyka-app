# ADR-0006: Explicit receipt allocations use immutable full-map revisions

Date: 2026-09-18. Status: accepted for the internal, unmounted implementation.
Business rule: owner-approved optional receipt allocation in
`docs/supplier-payment-ledger-spec.md`. Not approval to migrate production.

## Context

A payment reduces invoice debt immediately, even if its receipt designation is
unknown. Existing 0018 attachments mirror the entire invoice balance to one
full-value warehouse document. Relaxing their uniqueness would duplicate coverage
and reinterpret historical money. They are not partial-receipt allocations.

## Decision

Add 0021 with separate invoice-only groups, exact receipt relations and immutable
full-map revision headers/rows. Keep 0017–0020 evidence unchanged. A revision
replaces the current designation map, not the underlying payments. An empty map
explicitly removes designations without returning money.

The command carries expectedVersion and one stable request UUID. Current owner/
payer/scope authorization precedes replay. The existing company transaction lock
serializes CAS with payments/reversals. Exact replay returns the original revision
receipt, not a recomputed balance. New revisions re-read financial evidence.

All rows close with their creating transaction; deferred completeness and capacity
checks prevent late additions, partial maps and over-allocation. Corrections retain
older versions and actor/reason/server timestamp. No extra project payment,
financial impact, paid_amount update or stock movement is created.

Reversal invalidates effective coverage by its authoritative existing payment
evidence. It does not overwrite allocation history or transfer coverage to another
payment. The read model separates active and reversed designations. New revisions
must omit reversed payment IDs. Invoice opening paid stays a separate undistributed
historical amount, not a fabricated allocatable payment.

## Alternatives rejected

- Reusing full-value mirrors: wrong cardinality and financial semantics.
- Overwriting allocation rows: loses who changed the designation and why.
- Header plus freely appendable rows: a supposedly saved version could change later.
- Only a global paid cap: could consume a reversed payment using another payment's
  balance; per-source and per-receipt checks are both required.
- Mandatory extra allocation revision from payment engine on reversal: avoid
  premature engine coupling; derive effective coverage from immutable reversal.

## Consequences and release boundaries

No public route, registration adapter or real company data is activated. The
worker requires an injected trusted current-scope authorizer. The initial storage
tests used a labelled synthetic membership-backed adapter. The subsequent local
slice adds `build_allocation_access` using current platform owner/payer/scope
policies, and explicit default-off, unmounted GET/POST routes; actual HTTP/PG
authority tests are documented in `../supplier-payment-allocation-api-check-2026-09-18.md`.
Session/CSRF mounting and authoritative receipt registration remain unverified.

Existing 0021 excludes new revisions for annulled invoices. Historical reads and
saved-UUID replay remain available after current authority checks; the worker
returns explicit 409 for new revisions rather than a generic database failure.

This conservative relation guard accepts a matching contract/offer/request binding
and one exact accepted delivery/warehouse line without VAT. It freezes physical
receipt/delivery data, including metadata. It does **not** prove cumulative invoice
line consumption: immutable invoice-line specifications are absent. Runtime receipt
registration, multiline/VAT support and editable metadata need their own verified
adapter before activation; manual/unbound receipts are not claimed supported.

0021 also adds admission triggers to existing tables; it is not merely inert DDL.
Migration requires writer quiescence and copied-data rehearsal. Row-trigger lock
acquisition does not establish safe lock ordering for every unadapted legacy
writer. Rollback refuses nonempty evidence instead of erasing business history.
