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

## Follow-up: request clarity and creation safety (2026-09-07)

Local follow-up to release `354bc020`; production deployment is not confirmed.
This changes new request validation and presentation, not stored purchases:

- Each card shows `Заявка #ID`. Its item name is shown once as a heading/list
  position, rather than again as the estimate-control heading. Multi-item
  controls retain their original `Позиция N` mapping, quantities and warnings.
- An exactly matching source work already visible in the card is omitted from
  duplicate work-label fields. Different/combined source descriptions remain.
  The server's full explanatory `controlMessage` remains intact, even if its
  prose mentions the work again. No name-based record merging is performed.
- Both manual creation forms disable their fields/save/cancel while pending.
  A synchronous, app-instance-scoped ref protects both creation actions across
  renders. HTTP rejection retains the draft. Confirmed success clears it before
  list refresh; refresh failure says the request was created, not to recreate it.
- A lost/invalid response is an unknown outcome: check the list before manually
  retrying. There is no automatic retry. This is **not** server-side replay
  idempotency across tabs, page reloads or client restarts.
- Material-control validation rejects a repeated exact estimate source tuple
  `(estimateId, sectionIndex, itemIndex)` anywhere in one new request, including
  across two positions. Different source rows (even with the same work/material
  name) remain valid. Existing records and transaction locks are unchanged.

No migration, historical cleanup, permission expansion or supplier dispatch is
part of this follow-up. Browser guards do not replace backend ownership checks.

Local verification: 556 frontend tests (128 suites), 29 lineage/transaction/
inventory tests and 57 supplier-access tests passed; ESLint and production build
passed. An isolated Chrome SSR fixture using the real card components and themes
passed at 390×844 and 1440×1000 with no clipping or console errors. It used only
synthetic data; async submit interactions are covered by RTL, not a production
browser flow. Authenticated production receipt/notification checks remain open.

## Remaining code gaps

- Server-side request replay idempotency for all creation paths is still absent.
  No production duplicate count has been established; UI counts are not evidence
  that two purchases are the same transaction.
- Source types, work names and purchased materials are not presented as a
  consistently separated hierarchy.
- Invoice payment update and `project_payments` creation are two independent
  browser requests. This is recording a payment, not executing a bank transfer.
- Closing a claim does not clear the delivery problem state. Re-receiving an
  already accepted/problem delivery does not alter its recorded fact; the
  current reshipment route requires a new request/offer after receipt.
- No single final procurement-closure gate combines delivery, payment and claims.

Recommended next slice: design persisted request origins and server-side replay
idempotency across all creation paths, without merging legitimate purchases by
name. Historical QA records need a separate
read-only inventory and approved cleanup scope, never a mass resend.

## Release procedure

**The newer local chain repair below includes migration 0007. Do not use the
old no-migrations deployment helper for that release or disable its guard.**

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

## Authenticated chain repair and rehearsal (2026-09-07)

The following fixes were developed locally after `e6f81599`. This is not a
claim that the production supplier flow or external notifications are fixed:

- An external supplier can mutate an addressed offer without becoming an
  employee of the buyer. Only the exact offer response/invoice/shipment routes
  use this resolver. Canonical recipient access is checked first; the real
  offer/request owner's subscription is then checked. A company header cannot
  select a different billing owner. Expired buyers remain read-only.
- Response/selection UI checks HTTP errors before closing a form or announcing
  success. A delivery list longer than eight rows has an accessible show-more
  control, so older pending receipts are reachable.
- Project stock lookup, update and insert use the delivery's company. Existing
  stock in another company or with unknown ownership is not reassigned.
- Migration `0007_warehouse_vat_labels` repairs the legacy BOOLEAN VAT column
  to the labels already used by receipt handlers. False becomes `Без НДС`, true
  becomes `С НДС`, NULL stays NULL; no tax rate or total is inferred. Existing
  TEXT/VARCHAR, defaults and labels are untouched. Unknown/missing types stop
  the migration. Fresh bootstrap now creates TEXT.

An isolated PostgreSQL and authenticated ASGI test traverses the real routes:
new request → foreman confirmation → director approval → RFQ → addressed
supplier read/response → selection → invoice → approval/payment → project
payment ledger → shipment → receipt → company-2 stock and warehouse invoice.
It also checks premature RFQ/shipment rejection, foreign director/supplier
denial, expired buyer plus forged company header, continued reads, invoice
replay and receipt replay without duplicate stock/history/invoices.

The test uses a synthetic signed bearer representing completed login/2FA,
not substituted auth/tenant dependencies. It does not test login, SMTP/MAX
delivery, AI workers, partial/defective deliveries, cross-tab creation replay,
or atomicity of the separate invoice-payment and ledger requests. The optional
post-receipt AI job is not configured in the fixture. No live data is copied.
Legacy bootstrap needs five existing CREATE declarations before earlier ALTERs;
the helper documents that accommodation and Python-3.9 annotation compatibility.

Verification: 570 frontend tests (131 suites), 86 supplier-access checks (7
explicit PostgreSQL skips in the default run), 57 adjacent checks and 56
warehouse-preview baseline checks passed. The separately enabled real
PostgreSQL chain passed, as did all 9 VAT migration checks. Six interactive
isolated Chrome cases passed at 390×844 and 1440×1000: older receipt reachable,
HTTP rejection preserved the offer form and did not announce success. ESLint
and production frontend build passed. PostgreSQL migration SQL was executed
directly with transaction rollback; Alembic CLI is absent from the local Python
environment, so the production-style Alembic rehearsal is still a release gate.

### Reproduce locally, never on production

Provision a fresh empty database named `supply_chain_test_<suffix>`, owned by
`chain_test`, in a dedicated Unix-socket-only local PostgreSQL cluster. Then:

```sh
SUPPLY_CHAIN_RUN_POSTGRES=1 \
SUPPLY_CHAIN_TEST_DB_HOST=/absolute/path/to/test/socket \
SUPPLY_CHAIN_TEST_DB_PORT=55439 \
SUPPLY_CHAIN_TEST_DB_NAME=supply_chain_test_full \
python3 -m unittest backend.features.supplier_access.test_postgres_chain -v
```

The guard refuses nonempty databases, TCP/DSN overrides and ordinary database
names. The helper ignores ambient credentials and `.env`, disables outbound
network, and restores process patches on cleanup. It leaves synthetic rows for
inspection; reruns require another empty test database. Without opt-in the
integration test skips. Migration SQL tests additionally accept an explicit
`VAT_SCHEMA_TEST_DSN` only for the separate local `chain_vat_test` database.

### Release gates for this repair

Before production deployment, inspect the actual commit, Alembic revision and
VAT type; preserve existing untracked files/configuration. Pin the reviewed
release, back up PostgreSQL and code/frontend, and rehearse migration 0007 on
a restored database before applying it. The old pinned deployment script
deliberately rejects migration changes and must not be used for this release.

Rollback restores the previous application/frontend while retaining the
compatible VAT labels. `downgrade()` intentionally does not collapse labels or
rates back to BOOLEAN; it is not a physical-schema rollback. An exact database
rollback requires the verified backup and an agreed write-loss/recovery plan.

After deployment, use one authorized real purchase to verify recipient cabinet
visibility and actual email/MAX reception, then invoice/payment/receipt. Do not
approve, repair, resend or delete old QA requests automatically. HTTP health
alone does not satisfy this gate.

### Post-merge CI fixture classification

CI run `34063263159` for merge `37b45fd2` ran 3010 backend tests and failed
one repository writer-inventory check: the synthetic `_seed` helper was named
`postgres_chain_fixture.py`, so it was scanned as a production budget writer.
The helper is now `test_postgres_chain_support.py`, matching the repository's
test-only convention; both test imports are updated. Its isolation guards and
opt-in integration test are preserved. The budget inventory implementation,
allowlist, runtime application, and migrations are unchanged by this correction.
The corrected tree passes the full Python 3.11 backend discovery: 3012 tests,
63 explicit skips, no failures. GitHub CI must also pass before deployment.
