# A10 assignment/daily draft preview canary plan

Status: local release package only. Nothing in this document authorizes a
commit, push, deploy, nginx reload, feature-flag change or production request.

## Purpose and invariants

The canary exposes one review-only preview for one explicitly approved company.
It may read a selected active customer estimate, one saved version and confirmed
daily-work facts. It must never create an assignment, journal row, payment,
stock movement or any other business record.

The following invariants are release blockers:

- backend and frontend are both default-off;
- backend and frontend use the same strict company-ID allowlist;
- only active `директор` and `зам_директора` memberships with passed 2FA can
  receive a preview;
- authentication is cookie-session only and every POST requires CSRF;
- direct access to port `8001` is unavailable outside the host;
- nginx applies the reviewed 4 KiB body limit, per-IP rate limit and one global
  in-flight request before proxying the exact path;
- every successful response states `previewOnly=true`, `applyAllowed=false`,
  `writesAttempted=0`, `readOnlyTransaction=true` and `rolledBack=true`;
- no apply/save/approve endpoint or UI control exists.

Flag owner: the production operator responsible for the A10 rollout. Remove the
two A10 flags within two weeks of a separately approved full rollout, or disable
them when the canary ends.

## Reviewed configuration

Backend runtime:

```text
ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true
ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS=<CANARY_COMPANY_ID>
```

Frontend build:

```text
REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED=true
REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS=<CANARY_COMPANY_ID>
```

`<CANARY_COMPANY_ID>` must be one exact positive integer verified immediately
before deployment. Do not use a list for the first canary. Missing, malformed,
leading-zero or duplicate values fail closed. The frontend value is embedded at
build time; changing it requires a new frontend build/deploy.

The reviewed nginx source is
`ops-nginx-assignment-daily-draft-preview.conf`. Lines 7-8 are `http {}` zone
declarations. Lines 10 onward are server-level locations. Do not install the
whole file into one nginx context. Keep the backend bound to `127.0.0.1:8001`
and run `nginx -t` before every reload.

## Preconditions

- [ ] Human explicitly approves the exact company ID, commit, push, deploy,
      nginx change/reload, canary start and rollback authority.
- [ ] The reviewed commit is the only deployed change and the worktree is
      clean.
- [ ] Focused A10, disposable PostgreSQL, full backend/frontend tests and the
      production frontend build are green on that exact commit.
- [ ] `npm audit` has no reachable critical/high production vulnerability, or
      every exception has an owner, reason and review date.
- [ ] A database backup and the normal deployment rollback are confirmed. No
      A10 migration is expected or permitted.
- [ ] One real eligible director/deputy, exact project, active customer estimate,
      saved estimate version and confirmed-work date exist naturally. Do not
      manufacture or edit production business facts for the smoke test.
- [ ] Baseline health, backend/nginx error count and endpoint latency are
      recorded before enablement.

## Staged rollout

### 1. Deploy inert code

Deploy the reviewed commit with all four A10 variables absent. Install the
reviewed nginx zones/locations only after taking a copy of the active config.
Run `nginx -t`, reload nginx, restart the backend only if its unit changed, and
verify:

- public and loopback `/health` return `200`;
- the service is `active`, has no restart loop and listens only on loopback;
- the A10 panel is absent;
- the exact POST is unavailable while the backend flag is off;
- neighboring application routes remain unchanged.

Hold for at least 15 minutes and compare errors/latency with the recorded
baseline.

### 2. Enable one-company backend canary

Set the two backend variables to the approved company ID, restart the service
and wait for loopback health before public smoke. Keep the frontend off. Verify
the exact route behavior:

- no cookie -> `401`;
- valid cookie with missing/invalid CSRF -> `403`;
- wrong content type -> `415`;
- body over 4 KiB -> JSON `413`;
- non-allowlisted company -> opaque `404`;
- response/error headers remain `no-store` and contain no source details.

Do not paste session cookies, CSRF values or response source content into shell
history or logs.

### 3. Enable the matching frontend canary

Build and deploy the frontend with both frontend variables set to the same
single company ID. In a real browser, signed in as the approved role/company:

1. Open `Поручения` and confirm the panel appears only in the approved company.
2. Select one exact project, active estimate, saved version and confirmed date.
3. Generate the preview and verify work-only rows and totals against source.
4. Open the printable view and confirm its only actions are `Распечатать` and
   `Закрыть`.
5. Confirm no `Применить`, `Сохранить`, assignee selection, price, payment,
   material, photo or stock action is present.
6. Switch to a non-allowlisted company and confirm the panel is absent and no
   A10 request is made.

Use DevTools only to check status, timing and console errors; never extract or
print authentication secrets.

### 4. Observe before any expansion

Keep the canary at one company for at least 24 hours. There is no automatic
expansion. Record:

- request count and HTTP status distribution for the exact path;
- p50/p95 latency and timeout count;
- backend `assignment_daily_preview_unavailable` count;
- nginx `413`/`429` count;
- service restarts, CPU/memory and database connection pressure;
- new client JavaScript error types;
- operator/user reports and preview/source mismatches.

Advance only when there are no new error types, no data-integrity concern,
error rate is within 10% of baseline and p95 latency is within 20%. Hold and
investigate at 10-100% error growth or 20-50% p95 growth. Roll back immediately
for any write/data-integrity signal, security issue, more than 2x error rate,
more than 50% p95 growth, a new client error affecting over 0.1% of sessions,
or repeated unavailable/timeouts.

## Rollback

The fast safety action is backend disablement; it stops all successful preview
reads even if an old frontend bundle is cached:

1. Remove/disable `ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED` and
   `ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS`.
2. Reload systemd configuration if a drop-in changed, restart the backend and
   wait for loopback `/health`.
3. Rebuild/redeploy the frontend with both A10 variables absent so the panel is
   removed.
4. If nginx itself is implicated, restore the saved active config, run
   `nginx -t`, then reload. Otherwise the exact proxy location may remain inert
   until the frontend rollback finishes.
5. Verify public health, route unavailability, zero new backend/nginx errors and
   absence of the panel in a fresh browser session.

No database rollback or cleanup is expected because A10 adds no schema and
performs no business write. Any observed A10-attributed write is a security/data
integrity incident: disable immediately, preserve logs and investigate before
retrying.

## Evidence to retain

Record the deployed commit, frontend asset hash, exact company ID, flag values,
nginx config checksum, `nginx -t` result, health responses, smoke status codes,
browser result, baseline/canary metrics, start/end times, operator and final
advance/hold/rollback decision. Never record cookies, CSRF tokens, raw estimate
JSON, journal descriptions or private error traces.
