# Manual supplier catalogue changes

Fix the manual create/delete paths in SupplierCabinetPage: rejected requests must
not add/remove visible rows or clear a draft. Validate manual inputs with the same
normalizer as file import. Fresh same-supplier name/unit duplicate check before POST;
no automatic retry for an unknown outcome. Confirm valid create ID and delete ok=true.
Lock manual controls during a request, retain draft on errors, ignore late callbacks
following actor/supplier changes or unmount. New rows show inStock=true consistently.
Existing supplier identity/auth/billing requirements apply; no backend/schema change.
This is UI duplicate protection, not a database guarantee for concurrent sessions.
Invoices and payments remain owned by the other work stream.

Verification: both old HTTP403 phantom-create and phantom-delete defects reproduced
as failing RTL tests, then passed. Shared normalizer/import regression tests remain green.
A shared catalogue mutex serializes manual mutations and file imports in one cabinet;
competing actions report wait without releasing the owner's lock. Independent review:
30 targeted tests plus3 private race/context/unmount regressions pass, no blocking findings.
Production build passes; final full suite and browser/release evidence follows below.

Final full frontend: 180 suites /1128 tests passed. Browser with isolated PostgreSQL:
manual POST403 preserves name/price/notes; successful retry stores150.5,days0,inStocktrue;
DELETE403 retains row, confirmed DELETE removes it. Mobile320 viewport/document320,
form and buttons visible; screenshot inspected. Only intentionally denied requests
and fixture preload warnings in browser console; no new application exceptions.

Release961e2ef841d63b8883441e16291d6be5747ccd91 completed2026-09-19T13:05:15Z.
Backup `/root/stroyka-catalog-manual-vZ5sS879/backup`;173tables preserved,319assetsverified.
Smoke13:05:25Z healthy, DB11.8ms, runtimeErrors0; catalogue GET/POST without session401.
Schema remains0033; backend runtime unchanged. Synthetic PG and auth files removed.
Private evidence: `/Users/nikolas/.codex/tmp/supplier-catalog-manual/`.
