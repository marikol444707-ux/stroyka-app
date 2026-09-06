# Supply requests: current implementation map

Code audit: 2026-09-06, runtime fixes at `197464ac`.
This is an implementation map, not evidence of production delivery or a new
workflow specification. Last user-confirmed production code was `20cf455a`.

## Separate records, not one status

The current chain uses:

- `supply_requests`: company, project, work package, author, approvals, status,
  selected suppliers and positions in `items_json`.
- `supply_request_recipients`: addressed suppliers, account link and channel evidence.
- `supplier_offers`: a requested/received/selected commercial offer.
- `supplier_invoices`: invoice approval and manually recorded payment amounts.
- `supply_deliveries`: shipment/receipt facts, one record per position.
- `warehouse_invoices`, `materials`, `warehouse_history`: receipt documents and stock.
- `supply_claims`: delivery problems and their separately recorded resolution.

There is no separate purchase-order entity in this route chain: the selected
offer currently fills that role. Physical delivery, payment and claim closure
are independent states.

## Request composition and origins

One request can contain several positions, but not mixed work packages. The
header title/quantity are compatibility summaries; positions live in JSON.
Origin is reconstructed from exact estimate lineage and/or note markers rather
than a canonical persisted source column.

Creation paths include manual forms, material-control procurement, invoice
shortage procurement, material norms, and optional request creation with a
norm-generated estimate. A work may legitimately require several materials or
several purchases; matching work names alone cannot establish duplicate orders.

The list groups by project and origin bucket. Thus the same project can have
separate manual and review groups; that alone does not mean duplicated records.

## Human actions and resulting states

1. Create a request. At `197464ac`, director/deputy and other creators start at
   `Новая`; a foreman creates `Подтверждена прорабом` with their own stamp.
2. A foreman confirms a new request. A director/deputy approves it, with an
   estimate-control recheck: `Утверждена`.
3. A director/deputy/supply specialist explicitly requests offers from selected
   suppliers. Both approval stamps and linked supplier accounts are required.
   Recipients and `Ожидает ответа` offer records are created; request becomes
   `КП запрошены`. Merely selecting suppliers does not dispatch a request.
4. A supplier submits prices, quantities, delivery/payment conditions and
   optionally a file: offer becomes `Получено`.
5. Management can request a comparison. Arithmetic ranking and optional AI
   advice do not select a winner. Technical PDF comparison is separately flagged.
6. A director/deputy selects a received offer: it becomes `Утверждено`, other
   offers become `Отклонено`. The request itself still says `КП запрошены`.
7. A separate action creates the supplier invoice: `На утверждении`. An
   accountant/director/deputy approves it and records payment manually.
8. Shipment creates per-position deliveries and moves the request to `В пути`.
   Prepayment/50-50 require the relevant payment first; postpayment can ship
   before payment and before invoice creation.
9. Foreman/storekeeper/supply specialist/director/deputy records actual receipt
   quantity and quality. The system writes receipt history, warehouse invoice,
   project stock and, where applicable, a claim.
10. Deliveries determine request state: `Поставлено`, `Частично поставлено` or
    `Проблема поставки`. `Поставлено` does not certify payment/document closure.

The pure policy also names the chief engineer as a confirmer, but the outer
API role allowlist currently excludes that role. Do not promise that path as
functional until the role boundaries are aligned and tested.

## Notification boundary

Supplier cabinet visibility requires approval stamps and recipient access in
the same company (with the documented legacy selected-supplier fallback).
SMTP acceptance and MAX queue state are not proof of receipt or reading. No
end-to-end notification guarantee follows from unauthenticated smoke tests.

In `20cf455a`, director-created requests could be marked approved without a
foreman stamp and dispatch could occur during creation. Supplier reads already
required both stamps. `197464ac` removes that contradictory path. Old incomplete
requests are not automatically repaired, approved, deleted or resent.

## Confirmed code gaps; not part of the runtime fixes above

- Work labels repeat inside a single request card. Two concurrent ordinary
  save actions can issue identical POSTs; no production duplicate count was
  established. Exact material-control source locks already protect some paths,
  but a repeated source within the same multi-position payload remains a gap.
- Source types, work names and purchased materials are not presented as a
  consistently separated hierarchy.
- Invoice payment update and `project_payments` creation are two independent
  browser requests. This is recording a payment, not executing a bank transfer.
- Some downstream supplier-response/selection UI handlers announce success
  without checking HTTP success.
- Closing a claim does not clear the delivery problem state. Re-receiving an
  already accepted/problem delivery does not alter its recorded fact; the
  current reshipment route requires a new request/offer after receipt.
- No single final procurement-closure gate combines delivery, payment and claims.

Recommended next slice: agree the request header/position/work-source display,
then remove repeated labels and implement retry/double-submit protection without
merging legitimate purchases by name. Historical QA records need a separate
read-only inventory and approved cleanup scope, never a mass resend.

## Release procedure

`scripts/deploy-supply-delivery-fix.sh` is a pinned, root-run server helper for
the reviewed `20cf455a`/`a559ae9a` production baseline, main branch, schema 0006.
Set `SUPPLY_RELEASE_COMMIT` to the reviewed full release SHA; main must match it.
The helper checks a clean tracked tree and unchanged migrations/dependencies,
takes the deployment lock, backs up the frontend, and runs the existing deploy
with the hard reset and unpinned pull removed. Business-write smoke probes are
disabled. Configuration and existing request data are not repaired or rewritten.

On a caught failure/signal, it stops the deployment child and attempts to restore
the previous code/frontend and restart the previously active worker. A successful
rollback leaves a detached checkout and prints the backup location. Do not
blindly repeat deployment after rollback; inspect its result first. SIGKILL,
power loss and external concurrent writes bypassing the deployment lock are not
covered by shell traps.

After successful deployment: verify logout on iPhone/PWA, then one authorized
real request through foreman confirmation, director approval, explicit RFQ and
supplier view. Check actual email/MAX reception separately. Do not create or
send QA orders to real suppliers for a smoke check.
