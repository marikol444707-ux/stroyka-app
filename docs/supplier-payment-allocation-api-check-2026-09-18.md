# Allocation authority and unmounted HTTP adapter

Local continuation of `supplier-payment-allocation-storage-check-2026-09-18.md`.
No production migration, runtime mount, frontend change or real notification.

## Contract and boundaries

`build_allocation_access(deps, operation='update'|'read')` reuses existing finance
membership, owner/payer company, project/package and invoice-contract policies.
All receipt relations are checked, including receipts omitted from the submitted
replacement map. Stored author identity and client rows never grant authority.
Current authorization is required for saved UUID replay as well as new writes.

`register_supplier_allocation_routes(app, deps)` is explicit and **not called by
the application**. Both `SUPPLIER_PAYMENTS_ENABLED=1` and
`SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED=1` are required. Future mounting must retain
existing session authentication, CSRF and subscription middleware. Test identity
injection does not prove that future middleware integration.

- POST `/companies/{company_id}/supplier-payments/allocations`: full replacement
  command `{requestId,groupId,expectedVersion,reason,rows}`; saved receipt plus
  `companyId`. Each row uses payment ID, **receipt relation ID** and exact amount.
- GET `/companies/{company_id}/supplier-payments/allocation-groups/{group_id}`:
  current projection/version and active/reversed designations plus company ID.
  Uses distinct read authority; always rolls back/closes its transaction.
- Strict singleton selected-company headers; no aggregate company mode or query
  overrides. Responses, including errors, are `Cache-Control: no-store`.
- Connection/commit uncertainty returns generic 503. POST instructs retrying the
  **same UUID and identical command**, never fabricates success or a new UUID.
- Required schema is checked read-only after authorization and before replay or
  saving. Missing/disabled allocation or underlying payment guards block access;
  the request never creates or repairs tables/triggers.
- Annulled invoices retain historical GET and exact saved-UUID replay. A NEW
  revision is rejected with 409 under existing 0021 eligibility, after replay and
  version checks. This patch does not change that database/business restriction.

This endpoint only designates existing invoice payments. It does not create
payments, bank transfers, stock receipts or additional project expenses.
The reader still has no authoritative receipt deadlines wired into it.

## Independently verified local results

Main reran each PG fixture class against its own empty synthetic database on the
private Unix-only PostgreSQL, port 55442. Prefix: `supply_chain_test_`.

| Class | Passed | Database suffix |
|---|---:|---|
| `test_allocation_access_postgres.AllocationAccessPostgresTests` | 20 | `alloc_access_main_20260918a` |
| `test_allocation_routes_postgres.AllocationHTTPPostgresTests` | 6 | `alloc_http_main_20260918c` |
| `test_allocation_schema_postgres.AllocationSchemaTests` | 6 | `alloc_schema_20260918d` |
| `test_allocation_store_postgres.AllocationStorePostgresTests` | 14 | `alloc_store_main_20260918b` |

**46 PG tests passed**, including rerun of the 14 existing storage-service cases.
Separately **59 unit/contract tests passed**: projection, allocation commands,
read shape, store signature, access contract, HTTP adapter, payment commands,
payment policy and attachment commands. These are not 105 new tests, and are not
a full-project, browser, production-session or production-data verification.

HTTP tests use actual current platform authority, schema readiness and storage
against PG; only authenticated identity is injected into an isolated FastAPI app.
They cover save/read/correction/replay, selected-company denial, revoked authority,
missing schema, disabled guards and annulment, with unchanged financial snapshots.
Access tests additionally cover distinct canonical payer membership, all receipt
scopes, frozen provenance, malformed input denial order and non-financial
membership denial despite the user's global role.

Readiness checks all 30 allocation triggers plus four foundational anti-TRUNCATE
triggers, in addition to existing 0017–0020 checks. Tests disable/drop each guard.
Independent review found the omitted base anti-TRUNCATE checks; RED was observed
before adding them. Review also found cancellation masking historical reads,
schema discovery preceding revoked authority, and package-parser differences;
regressions were observed failing before fixes. Final focused reviews found no
blockers within this unmounted scope. No old migration was modified.

## Why receipt registration is still closed

Source inspection found immutable contract versions, but not immutable supplier
invoice item specifications/consumption. `create_invoice_from_offer` stores the
invoice amount and document bindings; shipment creation derives item data from
current request/KP JSON. Matching names/units/packages cannot prove which invoice
line was consumed or prevent repeated consumption across partial deliveries.
Warehouse lot line indexes identify received stock, not supplier invoice lines.

Next implementation must be future-only:

1. Freeze item specifications atomically with creation of a NEW invoice: stable
   line IDs, quantities, exact prices/amounts and source document/version. Seal
   completeness at commit; sum of lines must equal the invoice amount.
2. Bind NEW deliveries to those IDs, not text names or mutable JSON positions.
3. Record immutable accepted quantity/value per line, delivery and warehouse row
   in the same transaction as acceptance. Serialize capacity checks so concurrent
   receipts cannot exceed ordered quantity or reuse the same accepted row.
4. Test competing final quantities, identical item names, changed request/KP,
   UUID replay and rollback after stock writes. Old invoices without a snapshot
   stay unsupported; do not invent historical specifications on first receipt.

Multiline/VAT/discount arithmetic, physical receipt correction, metadata editing,
deadline/reminder integration, editor UI, browser/API/PG verification and copied-
data migration rehearsal remain separate gates. Payment reversal cannot alter
physical quantity consumption. No schema migration for this future layer is
included in the current authority/API patch.
