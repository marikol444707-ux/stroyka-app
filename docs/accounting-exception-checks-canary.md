# A11 accounting exception checks canary plan

Status: local release package only. Production execution requires separate
explicit approval for the exact company, commit, deployment, migration,
feature flags, nginx change/reload, smoke and rollback authority.

## Purpose and safety boundary

The canary exposes one read-only Accounting review panel to one exact company.
It reports only hard stored contradictions already covered by the closed
`accounting-exception-projection-v1` contract. It cannot pay, approve, repair,
reassign, edit ownership or change status.

Release blockers:

- the ownership schema/backfill and post-audit are complete for the canary
  company;
- backend and frontend are default-off and use the same one-company allowlist;
- only cookie-session users with passed 2FA and one active director,
  deputy-director or accountant membership may read the result;
- aggregate mode and every other company fail closed;
- the backend remains bound to `127.0.0.1:8001`;
- nginx proxies only exact `GET /accounting-exception-checks`, with the reviewed
  rate/concurrency/time limits and `no-store` responses;
- every business read is inside one `REPEATABLE READ READ ONLY` transaction
  followed by rollback;
- the route, panel and global error path contain no accounting writer.

Flag owner: the named production operator for this rollout. Remove the flags
within two weeks of a separately approved full release, or disable them when
the canary ends.

## Exact configuration

Backend runtime:

```text
ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED=true
ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS=<CANARY_COMPANY_ID>
```

Frontend build:

```text
REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_ENABLED=true
REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS=<CANARY_COMPANY_ID>
```

`<CANARY_COMPANY_ID>` is one canonical positive integer, not a list. Missing,
duplicate, leading-zero, whitespace-padded or malformed values fail closed.
The frontend values are compiled into the bundle and require a new build.

The reviewed nginx source is `ops-nginx-accounting-exception-checks.conf`.
Its zone declarations belong in `http {}` and its locations belong in the
active application `server {}`. Never paste the whole file into one context.
Back up the active nginx config and run `nginx -t` before reload.

## Preconditions

- [ ] A human approves the exact company ID and every production action.
- [ ] The migration runbook completed with backup, matching row counts,
      accepted quarantine counts and clean postchecks.
- [ ] The reviewed commit is the only deployed change and the worktree is
      clean.
- [ ] Focused/full backend and frontend suites, disposable PostgreSQL proof,
      production build, dependency audit and static no-write scans are green.
- [ ] Direct port `8001` exposure is impossible outside the host.
- [ ] Baseline health, route error rate, database connections, CPU/memory and
      p95 latency are recorded.
- [ ] One real eligible finance user exists naturally. Do not create or edit a
      production accounting row merely to manufacture a finding.
- [ ] The operator has the saved systemd/nginx/frontend configuration and can
      disable the backend flag first.

## Staged rollout

### 1. Deploy inert code

Deploy the reviewed code with all four A11 variables absent. Do not apply the
migration as part of the deploy command. If the reviewed nginx fragment is
installed, first save the active config, split it into correct contexts, run
`nginx -t` and reload.

Verify public and loopback health, service `active` state, zero restart loop,
loopback-only port binding, absence of the Accounting panel and route
unavailability while the backend flag is off. Hold for at least 15 minutes and
compare errors and latency with baseline.

### 2. Enable the one-company backend canary

Install only the two backend variables with the approved company ID, reload
systemd if required, restart the backend and wait for loopback health before
public smoke. Keep the frontend disabled.

Smoke exact `GET /accounting-exception-checks`:

- no cookie -> `401` fixed authentication error;
- malformed company mode/ID -> `422` fixed request error;
- valid cookie for another allowlisted state/company -> opaque `404`;
- valid session with a non-finance role -> `403`;
- approved finance role/company -> `200` with one closed projection;
- POST/PUT/PATCH/DELETE -> `405`;
- every response is `no-store` and contains no stack, SQL, names, notes,
  purpose, bank, photo, file, raw row or size metadata.

For the successful request, verify the server performs the settings query, two
authorization queries and twelve bounded source SELECTs, then zero commits and
one rollback. Compare any displayed finding to its source by exact IDs only;
do not paste private fields into the evidence log.

### 3. Enable the matching frontend canary

Build and deploy the frontend with the two frontend variables set to the same
company ID. In a fresh browser session:

1. Sign in as an approved finance role and select the canary company.
2. Open `Бухгалтерия` and refresh the exception panel.
3. Verify state, counts, fixed reason labels and exact IDs against the API.
4. Confirm there is no apply, pay, approve, repair, reassign, edit or status
   action.
5. Switch to another company and aggregate mode; the panel must disappear,
   abort the old request and make no new A11 request.
6. Verify desktop and mobile layout, no horizontal overflow and no new console
   error type.

### 4. Observe one company

Keep the canary at one exact company for at least 24 hours. There is no
automatic expansion. Record:

- request count and HTTP status distribution for the exact route;
- p50 and p95 latency, timeout count and maximum in-flight request count;
- `accounting_exception_review_unavailable`, nginx `429` and connection-limit
  counts;
- backend restarts, CPU/memory and database connection pressure;
- PostgreSQL statement/lock timeout and read-only violation counts;
- new client JavaScript error types;
- source/result mismatches, tenant-isolation concerns and user reports;
- confirmation that no A11-attributed business or audit write occurred.

## Stop thresholds

Advance only when there is no new error type, no tenant/data-integrity concern,
error rate remains within 10% of baseline and p95 latency remains within 20%.

Hold and investigate when error rate is 10-100% above baseline, p95 latency is
20-50% above baseline, any repeated timeout occurs or users report a result
that cannot be reproduced from exact IDs.

Rollback immediately when any of these stop thresholds is reached:

- any business/audit write attributed to the read-only route;
- cross-company row or private-field disclosure;
- security/authentication/authorization bypass;
- error rate above 2x baseline;
- p95 latency more than 50% above baseline;
- a new client error affecting more than 0.1% of sessions;
- sustained database connection pressure, lock contention or service restart;
- malformed projection accepted by the UI or any source/result mismatch.

## Rollback

The fastest safety action is backend disablement:

1. Remove `ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED` and
   `ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS`.
2. Reload systemd if its drop-in changed, restart the backend and wait for
   loopback then public health.
3. Rebuild/redeploy the frontend with both A11 frontend variables absent.
4. If nginx is implicated, restore the saved configuration, run `nginx -t` and
   reload. Otherwise the exact location may remain inert while the frontend is
   rolled back.
5. Verify the route is unavailable, the panel is absent, service restarts and
   errors are stable, and no accounting/audit row changed during the window.

Do not reverse the ownership migration merely to disable the feature. The
schema is additive and the hardened accounting writers depend on verified
ownership. Database recovery follows the separate migration runbook and needs
new approval. Any unexpected write or tenant leak is an incident: preserve
logs/evidence and do not retry the canary until root cause is fixed.

## Evidence to retain

Record the deployed commit, frontend asset hash, exact company ID, four flag
values, nginx config checksum, health/smoke statuses, browser result, baseline
and canary metrics, start/end UTC timestamps, operator and final
advance/hold/rollback decision. Never record passwords, cookies, CSRF values,
session hashes, raw accounting JSON, private error traces or business text.
