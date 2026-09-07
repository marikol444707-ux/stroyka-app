# A8.5.2 — Supply request workflow boundary

## Human workflow

The enforced sequence is:

1. A master, subcontractor or brigade leader creates a request.
2. An assigned project foreman or chief engineer confirms a
   `Новая` request. If no active reviewer is assigned to the project,
   a director or deputy director may perform a separate fallback
   confirmation.
3. A director or deputy director approves a
   `Подтверждена прорабом` request.
4. A director, deputy director or supply specialist dispatches an
   approved request to selected suppliers.
5. Only an addressed supplier receives the supplier-safe request view.
6. The technical comparison remains an explicit human-triggered action.

Repeated, skipped and backward approval transitions are rejected.

Leadership fallback confirmation is denied whenever an active foreman or
chief engineer is assigned to the request project. Fallback confirmation
does not replace the separate director-approval action.

## Supplier disclosure

`supply_request_recipients` is authoritative. A recipient with
`visible_to_supplier=FALSE` cannot regain access through the legacy
`selected_suppliers` array. The legacy array is used only when no recipient
rows exist for the request.

Supplier visibility also requires both the foreman-confirmation and
director-approval timestamps.

Creation by a director/deputy starts at `Новая`, without either approval stamp.
Creation by a foreman retains its existing `Подтверждена прорабом` behavior.
Choosing suppliers during creation records a selection, not an RFQ dispatch.
The explicit `request-kp` action validates both real approval timestamps before
creating recipients/offers or attempting email/MAX notifications. A legacy
`Утверждена` status without those timestamps returns HTTP 409. This preserves
the existing supplier-read boundary instead of inventing approval evidence.

Every creation path now uses one business transaction and rolls back on errors;
ordinary/manual requests must not leave a saved request after reporting failure.

The supplier response excludes internal actors, recipient lists, approval
metadata, rejection details, internal notes, estimate lineage, estimate
control and pricing fields.

## Safety boundary

This change does not select a supplier, approve an offer, create payment,
alter warehouse stock or run the technical matcher automatically.

## Delivery evidence, not delivery promises

`POST /supply-requests/{id}/request-kp` retains its response shape. `ok` and
`created` describe RFQ processing, not email receipt. `notifications` describes
individual email/MAX attempts. The UI distinguishes SMTP submission, missing
email/configuration, queueing and errors, and does not claim receipt or reading.
Creation responses that already include `notifications` must not trigger a
second dispatch from the browser.

`GET /supply-requests/{id}/recipients` adds optional per-recipient fields:

- `approvalComplete`: whether both approval timestamps exist;
- `approvalBlockReason`: explanation when an approval is absent;
- `actualMaxQueueStatus`: current outbox status, `unknown` when an associated
  outbox row cannot be verified, or null when no queue ID is recorded.

Outbox evidence must match the recipient, company, user, MAX provider, RFQ event
and request ID. The historical `visibleToSupplier` value is an account-link
snapshot, not proof that the supplier has opened the request. An old saved
`В очереди MAX` must not override a current failed/sent/cancelled queue state.

## Rollout and remaining operational verification

No migration, deletion, mass resend, automatic legacy repair or token change is
included. Old incomplete requests stay blocked and require a separately reviewed
repair/cancellation decision; do not fill approval timestamps to force delivery.
In particular, an absent supplier card is not fixed by recreating its numeric ID.

After deployment, verify one authorized real request through creation, foreman
confirmation, director approval, explicit RFQ dispatch and supplier cabinet view.
Verify email/MAX channels separately; passing unauthenticated smoke routes does
not prove delivery. Do not use the production QA supply-chain smoke script for
this check: it creates business records and may notify recipients.

Local regressions execute real route functions with a transactional fake DB,
pure policy/diagnostic tests, and UI tests with mocked requests. They do not prove
PostgreSQL integration or actual SMTP/MAX receipt. SMTP currently occurs inside
the RFQ transaction, so exactly-once external delivery across a later commit
failure is not guaranteed; a durable email outbox is separate future work.
The legacy selected-supplier read fallback and historical offer/invoice access
are unchanged. Fully approved legacy requests may be readable by a selected
supplier before explicit RFQ dispatch; harmonizing that history needs a separate
compatibility review, not silent removal of access to past financial documents.
