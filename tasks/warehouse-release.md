# Warehouse distribution and transfers release

Base: live `435c3bf4c1e7`, schema `0024_company_material_aliases`; local
`4f83bd22` adds its verification report. The user agreed to continue warehouse
transfers and distribution after the material mapping release.

Reuse the established contracts in `warehouse-distribution.md`,
`warehouse-project-transfers.md` and `stock-chain-integration.md` from the
supplier-catalog development branch. Keep its supplier invoice/payment work out.

## Acceptance

- Exact receipt lots distribute atomically to same-company projects; physical
  returns preserve the original source and never exceed entitlement or stock.
- Project transfer separates dispatch, transit and actual receipt. Partial and
  discrepancy receipts preserve quantity; accepted quantity alone creates stock
  and quality entries. Repeat commands cannot duplicate movement or history.
- Effective active membership, exact owners, stock precision, guarded historical
  identity, bounded waits and concurrent legacy writes are checked before release.
- Warehouse users see editing controls; accounting sees the same history without
  writes. Unknown outcomes retain the original command ID and payload for retry.

## Steps

- [x] Inventory live schema, stock, source lots and operator memberships.
  173 main-stock rows, 298 object/material rows, 146 lots (144 main/2 object),
  52 invoices, zero movements/transfers; every active warehouse operator has
  active membership. All 144 main lots pass existing source identity validation.
- [x] Integrate movement transactions, company material access, source indices
  and compatible stock locks without replacing the deployed alias/journal fixes.
- [x] Integrate atomic distribution, two-stage transfers, owned quality entries
  and independent additive migrations after 0024.
- [x] Integrate warehouse/accounting views and verify scope changes, retry state,
  immutable source indices and mobile layout.
- [x] Audit legacy writers and prove concurrent conservation/rollback in isolated
  PostgreSQL; resolve findings with failing regressions first.
- [x] Rehearse migrations on a fresh private production copy; compare original
  data fingerprints and inspect source/stock precision without historical repair.
- [ ] Complete full regression, enabled build and authenticated browser rehearsal.
- [ ] Back up and publish a pinned release; verify live API/UI, owners and counts.

Preserve all old records and balances. Do not infer per-lot provenance for old
object stock, import financial migrations, send RFQs/notifications or introduce
fake production movements for smoke tests. A discovered historical ambiguity
must produce a concrete review inventory, not guessed data correction.
