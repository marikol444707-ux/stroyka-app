# P1 — reliable supplier inbox loading

Scope: route-owned incoming requests/offers on ordinary supplier entry. The existing
app default page is dashboard; supplier tab navigation never activates the internal
supply loader. Therefore offers were not fetched at boot and the inbox falsely
reported empty. Load the addressed request/offer pair from the supplier route itself.
The route snapshot overrides generic application arrays for this cabinet, avoiding
late unrelated dashboard loads overwriting it. Backend authorization remains canonical.

Only a successful coherent pair may display an empty result. Loading/error/timeout
have distinct UI states, unknown counters show dashes, and a refresh button retries.
Clearing cached rows while refreshing avoids actions against a revoked snapshot.
Actor/API/role changes clear the displayed pair immediately; superseded/unmounted
requests cannot publish. Timeout20seconds bounds the wait. Missing request for an
offer is a visible reload error instead of silently hiding the card. Refresh after
supplier actions refreshes this pair and retains existing other refresh work.

No external messages, approvals, RFQ state transitions, invoices/payments or database
schema are changed. No claim that external email/MAX delivery is fixed (P3 remains).

Verification: old route test reproduced no automatic offers load (RED), then passed.
Targeted route/UI/hook/offer tests15/15 pass, including timeout, failed half-snapshot,
retry, identity change and stale action callback after leaving the cabinet. Independent
review passed. Existing PostgreSQL authenticated full-chain test passes (one scenario;
external services blocked) including addressed visibility and denial for other actors.
Existing fixture emits an ownerless-AI409 diagnostic; no new backend runtime change.

Final frontend183suites/1138tests passed; production build passed. Browser at ordinary
/app: addressed request appears without internal page navigation; HTTP503 shows error
and zero stale cards (no false empty message); explicit retry restores the card. Second
supplier receives empty requests/offers via real API and sees no first supplier card.
Mobile320 viewport/document320; screenshot inspected. No real supplier notification
sent. Browser console only fixture online403, injected503 and preload warnings.

Release56c0d2ac9d5797eb2f73042d7198727d5107d3b6 completed2026-09-19T13:33:01Z.
Backup `/root/stroyka-inbox-loading-a0kmucWk/backup`;173tables preserved,319assetsverified.
Read-only smoke13:33:20Z healthy, DB11.3ms, runtimeErrors0; requests/offers without session401.
Schema unchanged0033. Synthetic database/auth files removed. Private logs and screenshot:
`/Users/nikolas/.codex/tmp/supplier-inbox-loading/`. P1 complete; P2 and external-notification
P3 remain pending, with existing PostgreSQL baseline evidence available for P2.
