# A12 one-company audit-only canary plan

Status: local release package only. Production execution requires separate
explicit approval for the exact company, commit, migration, deployment,
frontend build, nginx change, operator, observation window and rollback.

## Purpose and invariant

The canary lets one 2FA-authenticated director record that one current
warehouse anomaly was reviewed. It creates immutable proposal/event/audit
evidence only. There is no business correction: invoices, stock, lots,
movements, estimates, accounting, payments and statuses must remain unchanged.

Do not manufacture an anomaly, edit production lineage or insert a fake source
job to make the canary succeed. If the approved company has no naturally ready
candidate, record a valid no-candidate result, test only the disabled/auth
boundaries and end the canary without a proposal write.

## Exact configuration

Backend runtime:

```text
HUMAN_APPROVED_ACTIONS_HTTP_ENABLED=true
HUMAN_APPROVED_ACTIONS_COMPANY_IDS=<CANARY_COMPANY_ID>
```

Frontend build:

```text
REACT_APP_HUMAN_APPROVED_ACTIONS_ENABLED=true
REACT_APP_HUMAN_APPROVED_ACTIONS_COMPANY_IDS=<CANARY_COMPANY_ID>
```

`<CANARY_COMPANY_ID>` is one canonical positive integer, not a list. Missing,
duplicate, zero, signed, whitespace-padded or leading-zero input fails closed.
The backend and compiled frontend values must match exactly.

The reviewed proxy source is `ops-nginx-human-approved-actions.conf`; its zone
declarations belong in nginx `http {}` and its three exact locations in the
active application `server {}`. Back up the active config and run `nginx -t`
before reload. Keep uvicorn on `127.0.0.1:8001`.

## Preconditions

- [ ] The migration runbook completed with backup and clean postchecks.
- [ ] Exact-code focused/full tests, disposable PostgreSQL proof, frontend
      build, dependency audit and static inventory are green.
- [ ] Baseline health, error rate, p95 latency, DB connections, CPU and memory
      are recorded.
- [ ] One natural succeeded source job and ready anomaly may be selected by
      exact IDs; absence is accepted and no data is fabricated.
- [ ] The operator can disable the backend flag first and restore saved
      systemd/nginx/frontend state.

## Staged rollout

1. Deploy inert code with all four flags absent. Install the reviewed nginx
   fragment only after backup and `nginx -t`. Verify loopback/public health,
   service activity, zero restart loop, route unavailable and panel absent.
2. Enable only the two backend variables for the approved company. Restart,
   wait for loopback health, then public health. Keep the frontend off.
3. Verify unauthenticated and bearer-only requests fail, missing/invalid CSRF
   fails, aggregate/foreign company fails, non-director/failed-2FA fails, and
   POST/GET methods are exact. Require `no-store` and fixed errors.
4. Build/deploy the frontend with the matching two values. In a fresh browser,
   verify exact company/project/job/subject, consequence and expiry, then the
   separate proposal and decision clicks. Switching company/project/source
   must clear the prior state. Check keyboard and mobile layout.
5. For one naturally ready candidate, capture protected-table ID-only
   counts/checksums, approve once, and require exactly one proposal, proposed,
   approved, applied and scoped audit receipt. Repeat approval must be
   idempotent with zero new writes. Recompute protected evidence exactly.
6. Observe the one company for at least 24 hours. Never expand automatically.

## Monitoring and stop thresholds

Record route status counts, nginx/backend `429`, p50/p95, timeout and conflict
counts, DB connections/locks, service restarts, new client error types and A12
fixed reason counts without request payloads. Record proposal/event/audit
counts only; never log session hashes, CSRF values, raw job/preview data or
business text.

Advance only with no tenant/data-integrity issue, no new error type, error rate
within 10% of baseline and p95 within 20%. Hold for repeated timeout/conflict,
10-100% error increase or 20-50% p95 increase. Roll back immediately for any
protected business write, cross-company disclosure, auth/CSRF bypass,
duplicate apply/audit receipt, malformed receipt, error rate over 2x baseline,
p95 over 50%, restart loop or client errors above 0.1% of sessions.

## Rollback

Always disable the backend flag first:

1. Remove `HUMAN_APPROVED_ACTIONS_HTTP_ENABLED` and
   `HUMAN_APPROVED_ACTIONS_COMPANY_IDS`, restart and verify health/route off.
2. Rebuild/redeploy the frontend with both A12 frontend values absent.
3. Restore nginx only if it contributed to the incident; run `nginx -t` before
   reload.
4. Verify panel absent, service stable and protected counts/checksums unchanged.
5. Preserve immutable proposal/event/audit evidence. Do not delete receipts or
   drop a nonempty ledger. Database recovery follows the separate migration
   runbook and requires new approval.

Retain the commit, asset hash, exact company ID, flag values, nginx checksum,
health/smoke results, browser evidence, baseline/canary metrics, ledger counts,
protected checksums, UTC start/end, operator and final decision. Retain no
credentials or private payloads.
