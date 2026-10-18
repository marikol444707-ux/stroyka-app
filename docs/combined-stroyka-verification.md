# Combined Stroyka verification

Prepared locally on 2026-10-18 from baseline
`c30b5c7a6b641bc59860ea5eed6e743f67f1318d`.
Prepared for a draft PR. No deployment, server change or live migration was performed.

## Composition

The unified receipt, three scoped economy corrections, and movement retry patches
were applied to a new isolated worktree. Source worktrees and original patch
checkpoints were preserved. All three patches applied cleanly. Shared changes in
`backend/main.py`, `warehouseCrudActions.js`, and `buildAppShellProps.js` coexist.

Patch SHA256 inputs:
- Receipt: db27ad33a1adf5762a8637a6ba6153ddfc0c15926571514fbde11c60a330ee37
- Economy: 5297f02390a5d40fbbd1f45fc0413df7247cf6ea03ada7db27a3a762ee57a298
- Movement: ca2155536d68a0d5f860531c3f0a76eae8548c20e7e7c604d9cc690f9f49cf6c

Integration-only changes reconcile migration ancestry and its documentation:
`0100_packaging_history_guard` → `0101_receipt_originals` →
`0102_movement_commands`. AST inspection of every revision verifies exactly one
head, `0102_movement_commands`. Both additive migrations are prepared, not applied;
missing schema fails before affected stock writes. Evidence/command history is
preserved on downgrade.

## Verification boundary

Combined backend suite was executed in one runner, not summed from separate
worktrees: warehouse_receipts, warehouse_movements, material_traceability, and
focused document-access cases. Result: 292 collected, 201 passed, 91 skipped.
All 91 skipped cases require explicit isolated PostgreSQL setup: 31 receipt,
2 movement retry, 51 existing material-traceability and 7 file-access cases.
They are not passing database/concurrency evidence. The new receipt and movement
suites use synthetic stock/accounting mutations around real transaction code;
the existing skipped suites have their own fixtures and are not all the same stand-in.

Full frontend and production build were executed in this combined worktree.
Result: 312 frontend suites and 2,033 tests passed. Production build
compiled successfully. Focused shared-file ESLint, compileall and diff checks pass.

## Release gates and limits

- PostgreSQL socket execution remains blocked in this environment. Migration,
  trigger, concurrency and real accounting-writer integration must be tested in
  an explicitly provisioned disposable database before release.
- Scope remains the requested receipt logic, three economy corrections, and
  movement retries; this is not a complete accrual-cost accounting redesign.
- Legacy data without frozen legal evidence requires review.
- Movement command identity persists in the open form, not across reload or form
  discard. Uncertain-result warnings tell operators to retry the same form or
  inspect history before creating a new request.
- Postcommit ancillary review/AI tasks remain best-effort.

## Independent integration review

No new integration-blocking finding. Shared-file changes and transaction/tenant
boundaries compose; migration ancestry was independently checked. The subsequent
partial-cost change received a separate read-only review with 92 focused frontend
tests passed and 20,064 independent Python/JavaScript rounding comparisons matched.

The partial-receipt material-cost correction uses actual accepted quantity rather
than the shipped `totalPrice`: 10 shipped, 4 received, unit price 100 yields 400.
One exact linked, non-cancelled saved warehouse receipt amount takes precedence,
with line, quantity, unit, package and available company identities checked.
This preserves saved gross totals and rounding without adding VAT again.
Confirmed zero suppresses stale history/stock fallback; missing actual quantity
is never replaced by shipped or planned quantity. Supplier invoice face values,
contract totals and financial debt writers are unchanged.

Legacy supply-history responses omit delivery/request linkage, so their existing
material/package-level de-duplication remains a known limitation. This patch does
not migrate or reconstruct historical receipt evidence.
