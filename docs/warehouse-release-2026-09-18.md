# Warehouse distribution release — 2026-09-18

Prepared on `codex/warehouse-completion` from the live alias release
`435c3bf4c1e7` (schema `0024_company_material_aliases`). The development
specifications copied into this branch contain historical milestones; this
report governs this release's actual scope and verification.

## Behavior

- Allocate selected receipt lots to exact projects in one company atomically;
  return actual goods against the original allocation and receipt.
- Dispatch allocated goods to another project, track them in transit, and accept
  actual quantities separately. Partial and zero receipts record discrepancies;
  unaccepted quantities remain in transit. Accepted goods may be returned or
  forwarded, preserving the source chain.
- Preserve command identities through retry and lost responses; recheck company
  membership, source evidence and stock before writes or replay. Accounting reads
  the same history without write controls.
- Create owned quality entries for actual receipts. Disable the old immediate
  movement endpoint while owned distribution quality is enabled.
- Serialize legacy receipt, stock metadata, executor issue/return/cancel and
  work-journal consumption with distribution. Bounded stock lock conflicts return
  409 with no partial writes. No automatic retry of legacy commands.
- Keep actual user identities on executor returns, personal balance views and
  reconciliation holders;
  name-only historical evidence is used only when unambiguous. Restoring excluded
  work revalidates its complete material consumption. No historic data
  is rewritten to guess a user, company, project or lot.

No supplier invoice/payment implementation is imported from the parallel branch.
These operations do not create new supplier debt. Tests and browser commands use
synthetic local data; production smoke checks are read-only.

## Inventory and migration rehearsal

Read-only live inventory: 173 main-stock rows, 298 material rows, 52 warehouse
invoices, 146 receipt lots (144 main / 2 object), 515 history entries; no warehouse
movements or executor transfers. Every active warehouse operator has active
company membership. All 144 main lots validate against the original receipt.
Stock precision, normalized key uniqueness and lot-to-physical-stock checks found
zero anomalies. Old object stock is not assigned guessed lot provenance.

Additive revisions `0025_warehouse_distribution` and
`0026_distribution_transfers` were rehearsed on a fresh private production copy.
All original columns in all **144** application tables retain their row counts
and SHA-256 fingerprints; all new business tables remain empty. Downgrades refuse
business data and stale transaction snapshots; a failing regression reproduced
an otherwise unsafe repeatable-read drop before the guard was added.

## Validation and practical limits

Evidence is private under `~/.codex/tmp/warehouse-release/`.

- Full frontend: **157 suites / 926 tests passed**. Enabled production build
  compiled successfully; main asset `main.4ba22335.js`.
- Distribution PostgreSQL: atomic failure rollback, repeated identities,
  competing allocations/returns, revocation while waiting, pagination and exact
  quantities. A 16-command / 8-worker contention run conserved all balances.
- Two-stage PostgreSQL: dispatch, partial/discrepancy receipt, child return and
  onward dispatch, immutable lineage, corrupted-proof refusal, quality ownership
  and precision, flag-off protections, empty downgrade/re-upgrade.
- Additional regressions: 21 authenticated work-consumption/identity cases,
  16 material-directory membership cases, and 5 lock-order/bounded-wait cases
  passed. Work author IDs are pinned to the authenticated worker; a matching
  display name cannot override another stored user ID.
- Integrated real HTTP/PostgreSQL: receipt/delivery lock order, executor lifecycle,
  source indices after filtering, failures after writes, ownership and isolation.
- Browser: synthetic distribution, dispatch 6 / accept 4 / transit 2,
  read-only controls, 390-pixel mobile layout without horizontal overflow.
- PostgreSQL fixtures disable external AI/network work. Their minimal api_errors
  fixture lacks owner_scope, so intentional failure cases can print a logging
  warning; this is not evidence of a production API error.
- Coarse stock locks serialize across companies. The bounded contention checks
  support this small deployment; they are not a high-volume capacity benchmark.
- Existing tooling dependency advisories and unrelated startup rate-limit
  responses were already recorded in the material-alias release; dependency
  manifests are unchanged.

## Deployment and rollback

Keep the six existing alias/quality backend flags enabled. Add:
`WAREHOUSE_DISTRIBUTION_ENABLED=1`,
`WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=1`,
`OWNED_DISTRIBUTION_QUALITY_ENABLED=1`.
Frontend adds both `REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true` and
`REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=true`, retaining the deployed
alias, accounting exceptions, comparison and daily-draft flags.

Pinned deployment uses the shared deploy lock, verifies the previous live HEAD,
backs up code/environment/nginx/frontend/database, stops managed writers, migrates
and compares original data fingerprints before restart. Nginx explicitly routes
`/warehouse-distributions`; static publication preserves previous hashed assets.
If new distribution records exist, retain the additive schema and fix forward;
never drop business history or restore a stale database automatically.

## Final release evidence

Release candidate backend SHA-256:
`2ee437ceaba01b00b38959f6a718a1965f794420c9d4e7833f5d5e5225cc7088`.
Focused final backend: 78 tests, 5 opt-in skips; standalone PostgreSQL: 89
allocation/transit + 24 integrated stock/quality + 28 existing alias/owned receipt
+ 21 work-consumption/identity + 16 material-directory + 5 lock-boundary cases
passed. An additional 7-case executor lifecycle passed with the new legacy locks.
Full backend and live publication evidence will be appended after completion.

A separate read-only review found no blocking issues in distribution, custody,
owner guards, migration protections and UI scope. The final journal author-ID
correction was reviewed separately after its four failing HTTP regressions passed.
