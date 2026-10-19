# Warehouse follow-up verification

This follow-up was reconstructed from published draft PR 372 head
`f75bf57007664b4c122277207457f206dcbcdd31` after the earlier unpublished workspace
artifacts became unavailable. Earlier unpublished hashes and test counts are not
verification of this reconstructed tree.

## Changes

- Server-owned immutable movement drafts survive reload and lost responses.
  Actor/company locks reconcile committed commands before cancellation; cancelled
  command bindings cannot be revived. Current selected-company membership gates
  preparation, recovery, cancellation and execution. Restricted project drafts
  expose only recovery metadata and safe cancellation. UI generation checks fence
  account/company/logout changes and delayed refresh/printing.
- Material issues preserve their exact source stock row. Cancellation restores
  one authorized original row once. Returns preserve issued identity and serialize
  balance checking; ambiguous/missing historical sources require reconciliation.
  Main-warehouse historical issues are not silently returned into project stock.
- Receipt HTTP fixtures now upload a genuine synthetic original and use the
  mandatory confirmation route. Supplier creation/signup races and original
  accounting/access assertions remain intact.
- Disposable PostgreSQL runners fail on unexpected skips or empty suites. Receipt
  inventory is 21 confirmation, 10 resolver and 6 actual-writer cases. Additional
  movement/return/traceability/source-file suites are explicitly selected in CI.

## Fresh local checks

- Full frontend: 315 suites / 2,043 tests passed.
- Full backend: 6,371 collected, 3,988 passed, 2,380 skipped and 3 errors.
  The three DOCX/PDF sandbox parser errors also reproduce on the unchanged f75
  baseline. They are not counted as passing; CI must verify them.
- Combined focused checks: 71 passed. Independent combined review: 46 passed.
- Independent runner review: 14 runner contracts passed; exact selected receipt
  inventory verified. The PostgreSQL runner fails closed locally because the
  PostgreSQL binaries are absent. No database cases are claimed as passed.
- Warehouse preview registration block remains byte-identical to f75 (2,765 bytes,
  SHA256 ffad8cb8e7637ff489fb2bb8ba05009468185912e27c01ecf4014e148ba31433).
  Three whole-main hash guards were updated only after that check.

## Release gates

Exact-head GitHub CI, including real PostgreSQL transaction/concurrency tests,
must finish successfully. Migration ancestry is linear 0100 -> 0101 -> 0102 ->
0103 -> 0104. Migrations are prepared, not applied to a live database. Narrow receipt
role changes and deployment remain separate approval/release gates. No merge or
server deployment is included.

Enabled payment-ledger, receipt-line-proof and owned-quality feature combinations,
and browser end-to-end operation against a deployed server, are outside these
local checks. Legacy documents without frozen ownership evidence require review;
existing incorrect historical stock credits are not repaired automatically.
