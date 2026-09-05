# A8.5.2 — Supply request workflow boundary

## Human workflow

The enforced sequence is:

1. A master, subcontractor or brigade leader creates a request.
2. A project foreman or chief engineer confirms a `Новая` request.
3. A director or deputy director approves a
   `Подтверждена прорабом` request.
4. A director, deputy director or supply specialist dispatches an
   approved request to selected suppliers.
5. Only an addressed supplier receives the supplier-safe request view.
6. The technical comparison remains an explicit human-triggered action.

Repeated, skipped and backward approval transitions are rejected.

## Supplier disclosure

`supply_request_recipients` is authoritative. A recipient with
`visible_to_supplier=FALSE` cannot regain access through the legacy
`selected_suppliers` array. The legacy array is used only when no recipient
rows exist for the request.

Supplier visibility also requires both the foreman-confirmation and
director-approval timestamps.

The supplier response excludes internal actors, recipient lists, approval
metadata, rejection details, internal notes, estimate lineage, estimate
control and pricing fields.

## Safety boundary

This change does not select a supplier, approve an offer, create payment,
alter warehouse stock or run the technical matcher automatically.
