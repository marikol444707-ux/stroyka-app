# Spec: A9.4 — HTTP adapter for warehouse anomaly preview

## Status

Approved by the human for implementation planning on 2026-08-21 with the
recommended endpoint, opaque-auth, initial rate and operational-telemetry
defaults below. A9.4a–A9.4d are complete locally: the exact route contract
drives the real private A9.3e runner through one recording connection, keeps
only privacy-safe process aggregates and is wired behind exact lowercase
`true` plus a fail-closed immutable company allowlist. Both values remain unset,
so registration stays default-off. The nginx contract exists only as reviewed
local deployment fragments; it was not installed, reloaded or exposed. Focused
HTTP, package, A7 and full-backend closure plus live cookie/CSRF/auth precedence
proofs are green. UI work, production access, origin restriction, commit, push
and deployment remain separate unperformed steps.

## Assumptions to review

1. The first public surface is one read-only `POST` endpoint, not a UI.
2. Authentication is cookie-session only; Bearer and mixed authentication are
   rejected. The session must already have passed 2FA.
3. A CSRF token is mandatory even though the operation is read-only because the
   endpoint uses `POST` and consumes scarce runtime capacity.
4. Rollout is default-off and restricted to an explicit company allowlist.
5. No persistent audit/session-last-seen/error-log write is permitted.
6. The endpoint returns the already-frozen minimal A9.3c projection; it never
   returns stored job JSON, A7 facts, hashes, actor/session data or SQL details.

If any assumption changes, update this draft before implementation.

## Objective

Allow one passed-2FA company director to request an up-to-date, preview-only
warehouse anomaly explanation for one exact succeeded system job and candidate.
The adapter must invoke the completed A9.3e runner without weakening its single
lease, single connection, single read-only snapshot, 18-statement ceiling,
rollback-before-content, byte budgets or 30-second cooperative deadline.

Success means an allowlisted director can receive the minimal preview through a
stable HTTP contract while invalid, unauthorized, overloaded and broken paths
remain opaque, bounded, non-writing and non-cacheable.

## Non-goals

- No stock movement, inventory adjustment, confirmation or apply endpoint.
- No latest-job lookup, candidate discovery or server-side candidate choice.
- No UI, notification, model/provider, background job or websocket.
- No new session/authentication flow and no Bearer compatibility.
- No database schema, migration, read audit or API-error database write.
- No production enablement or deployment in the first implementation slice.

## Tech stack

- Python 3.9 and the existing FastAPI application/route-registration pattern.
- Existing `backend.auth.build_cookie_session_authentication` for cookie/CSRF.
- Existing private A9.3e runner and psycopg2/PostgreSQL controls; no new package.
- Existing nginx reverse proxy with one dedicated exact-match location.
- Built-in `unittest` plus the existing recording-cursor and route harnesses.

## Proposed endpoint

```http
POST /warehouse-anomaly-previews
Cookie: <configured httpOnly session cookie>
X-CSRF-Token: <session-bound CSRF token>
X-Company-Mode: company
X-Company-Id: 4
Content-Type: application/json
```

Candidate and job identifiers are deliberately absent from the URL so nginx
access logs never contain them. The operation creates no durable resource;
`POST` is used because the exact request has a bounded JSON selector and runs a
costly on-demand preview computation.

### Exact request body

```json
{
  "projectId": 9,
  "jobId": 123,
  "selected": {
    "subjectKind": "warehouseInvoice",
    "subjectId": 456,
    "anomalyCode": "warehouse_invoice_project_mismatch"
  }
}
```

Rules:

- Body must be UTF-8 JSON with exactly the three top-level fields shown.
- `selected` must contain exactly `subjectKind`, `subjectId`, `anomalyCode`.
- IDs are built-in positive integers in `1..9223372036854775807`; JSON booleans,
  floats, strings and leading-zero header IDs are rejected.
- Candidate kind/code pairing uses the existing closed 18-code A9.3c allowlist.
- `X-Company-Mode` is exactly `company`; `X-Company-Id` is a canonical positive
  decimal string and is the only company selector.
- No company/session/report/source/hash/content fields are accepted in body.
- The application stops reading after 4096 body bytes. Nginx independently
  applies `client_max_body_size 4k` and a JSON-formatted 413 response.
- Any extra key, duplicate semantic selector or malformed/deep JSON is invalid.

## Authentication and authorization order

The adapter executes these gates in order:

1. Validate method, content type and syntactic company headers without opening
   a database connection.
2. Build authentication only through `build_cookie_session_authentication()`
   with `require_csrf=True`. Any `Authorization` header, including an empty or
   Bearer value, is rejected.
3. Check the parsed company ID against the immutable startup allowlist. A valid
   cookie targeting a non-allowlisted company receives the same opaque 404 as
   an unavailable resource; body and runtime are not reached.
4. Stream and validate the bounded exact JSON body.
5. Call `run_warehouse_anomaly_runtime_preview()` once with a strict copy of
   the five-field `DB_CONFIG`, the cookie authentication mapping, exact company
   headers and body.
6. Live A9.3d authorization inside the same guarded snapshot proves active,
   unrevoked, unexpired, passed-2FA session; active user; exact director
   membership/company/platform account binding; and selected project access.

The route never calls `get_current_user()`: that legacy dependency permits
Bearer authentication and writes `user_sessions.last_seen_at`, both forbidden
for this surface.

## Successful response

Status is `200` for all three valid preview states: `preview_ready`, `blocked`
and `stale`. The body is exactly the existing A9.3c public projection:

```json
{
  "warehouseAnomalyRuntimeVersion": 1,
  "ok": true,
  "dryRun": true,
  "writesAttempted": 0,
  "previewOnly": true,
  "stockMovementAllowed": false,
  "inventoryAdjustmentAllowed": false,
  "applyAllowed": false,
  "state": "preview_ready",
  "candidate": {
    "subjectKind": "warehouseInvoice",
    "subjectId": 456,
    "anomalyCode": "warehouse_invoice_project_mismatch",
    "recommendationCode": "<fixed allowlisted code>"
  },
  "content": {
    "title": "<fixed server text>",
    "finding": "<fixed server text>",
    "nextSafeAction": "<fixed server text>"
  },
  "blockers": [],
  "readOnlyTransaction": true,
  "rolledBack": true
}
```

For `blocked` or `stale`, `content` is `null` and `blockers` contains exactly
one already-public fixed blocker. No response contains company/project/job,
session/user/membership, estimate/reconciliation, source hashes or evidence.

## Public error contract

Every handled error is JSON `{"detail":"<public code>"}`. Internal A9.3 codes,
dependency messages, tracebacks, SQL, configuration and private identifiers are
never exposed.

| HTTP | Public detail | Condition |
|---:|---|---|
| 401 | `warehouse_anomaly_preview_authentication_required` | Missing/malformed cookie, expired/revoked/non-2FA/inactive actor, wrong actor membership/role, or any `Authorization` header |
| 403 | `warehouse_anomaly_preview_request_forbidden` | Missing or invalid session-bound CSRF token |
| 404 | `warehouse_anomaly_preview_not_found` | Company outside rollout allowlist, unavailable project/job/resource, foreign/wrong-status/human job |
| 409 | `warehouse_anomaly_preview_conflict` | Exact selected artifact exists but is corrupt or fails provenance |
| 413 | `warehouse_anomaly_preview_request_too_large` | Request body exceeds the fixed transport limit |
| 415 | `warehouse_anomaly_preview_media_type_invalid` | Content type is not JSON |
| 422 | `warehouse_anomaly_preview_request_invalid` | Header/body/selector shape is invalid |
| 429 | `warehouse_anomaly_preview_busy` | Nginx rate/connection limit or backend one-slot acquisition fails |
| 503 | `warehouse_anomaly_preview_unavailable` | Deadline, read, rollback, cleanup, contract or unexpected dependency failure |

`blocked` and `stale` are successful domain results and remain HTTP 200; they
must not be rewritten as 409/503. Error precedence is authentication/CSRF and
allowlist at the HTTP boundary, followed by the already-approved A9.3e runtime
precedence after capacity acquisition.

All responses, including errors, set:

```http
Cache-Control: no-store, max-age=0
Pragma: no-cache
Vary: Cookie, X-Company-Id, X-Company-Mode
```

No ETag or conditional response is generated. All 429 responses include
`Retry-After: 10`; 503 responses include `Retry-After: 30`.

## Runtime and database invariants

- One process-global `BoundedSemaphore(1)` lease; one-second slot wait.
- One strict libpq connection with fixed connect/startup controls.
- One explicit read-only `REPEATABLE READ` transaction and guarded cursor.
- Exactly one auth SELECT, artifact SELECT and current 14-query A7 pass.
- Maximum 18 guarded server statements plus unconditional cleanup rollback.
- Existing UTF-8 field/query/cumulative transport budgets remain unchanged.
- No commit, DDL/DML, lock, `FOR UPDATE`, advisory lock or second connection.
- Final content/public projection occurs only after rollback and both closes.
- The lease remains held through finalization and final deadline guard.

The HTTP adapter may translate fixed errors but may not retry the runner; a
retry would violate capacity and snapshot expectations.

## Feature flag and rollout allowlist

- `WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED` defaults to absent/false; only exact
  lowercase `true` enables registration.
- `WAREHOUSE_ANOMALY_PREVIEW_COMPANY_IDS` is required when enabled. It contains
  1–100 unique canonical positive decimal IDs separated by commas.
- Empty, duplicate, malformed, leading-zero or out-of-range values fail closed:
  no route is registered and no runtime module is imported/called.
- The allowlist is parsed once into an immutable value before registration.
- Non-allowlisted companies receive opaque 404 after cookie/CSRF validation and
  before body buffering or capacity acquisition.

Any default change, broader role, all-company mode or flag/allowlist bypass
requires a new human approval.

## Nginx and overload controls

The production rollout, if later approved, adds dedicated zones rather than
reusing the broad login limit:

```nginx
# http {}
limit_req_zone $binary_remote_addr
    zone=warehouse_anomaly_preview_limit:10m rate=6r/m;
limit_conn_zone $server_name
    zone=warehouse_anomaly_preview_conn:10m;

# server {}
location = /warehouse-anomaly-previews {
    limit_req zone=warehouse_anomaly_preview_limit burst=1 nodelay;
    limit_conn warehouse_anomaly_preview_conn 1;
    limit_req_status 429;
    limit_conn_status 429;
    client_max_body_size 4k;
    proxy_connect_timeout 6s;
    proxy_send_timeout 10s;
    proxy_read_timeout 45s;
    proxy_pass http://127.0.0.1:8001;
}
```

The final nginx config must supply the same JSON/no-store/Retry-After contract
for nginx-generated 413/429 responses. It must not log cookies, CSRF, headers or
request bodies. Existing path-only access logging is safe because selectors are
not in the URL. The connection zone is intentionally keyed by `$server_name`,
not client IP: it enforces one in-flight request globally for this route even if
the backend later uses more than one worker. Production must keep the backend
origin reachable only through the reviewed nginx boundary; direct public access
would bypass this process-wide protection.

## No-write and observability policy

The existing global API-error middleware writes every 5xx response to the
database. The implementation must add an exact path exclusion for
`/warehouse-anomaly-previews`; otherwise a read/rollback/deadline failure would
violate the zero-write contract. The exclusion must not affect any other path.

Allowed operational telemetry is privacy-minimized and non-business:

- current in-flight count (`0` or `1`);
- total outcome buckets: `ok`, `busy`, `deadline`, `unavailable`;
- coarse duration buckets with no raw duration label cardinality.

No metric/log label may include session, actor, company, project, job,
candidate, anomaly, report/source hash or dependency text. No new public
metrics endpoint is part of the local adapter slice. Wiring these aggregate
metrics to production monitoring belongs to the separately approved rollout
checkpoint.

## Threat model

### Trust boundaries and assets

- Boundary: browser → nginx → FastAPI. Untrusted headers/body may attempt
  injection, parser exhaustion, CSRF or capacity abuse.
- Boundary: session cookie → live database authorization. Assets are director
  identity, tenant isolation and private artifact/evidence.
- Boundary: private runtime result → HTTP response. Assets are job payload,
  report provenance, current A7 facts and internal failure details.
- Scarce asset: one runtime slot, database connection time and bounded SQL.

### STRIDE controls

| Threat | Required control |
|---|---|
| Spoofing | Cookie only, exact hashed session, live passed-2FA director checks; Bearer rejected |
| Tampering | Exact key/type allowlists, canonical IDs, CSRF, parameterized reviewed SQL |
| Repudiation | No business audit write; privacy-safe nginx status/latency and aggregate outcome metrics only |
| Information disclosure | IDs absent from URL, no-store/no-ETag, opaque 401/404, exact public projection and fixed errors |
| Denial of service | 4 KiB body, nginx request/connection limits, one backend slot, connect/statement/deadline caps |
| Elevation of privilege | Exact company mode/allowlist plus same-snapshot director/company/project authorization |

### Abuse cases that must become tests

- Bearer token, Bearer+cookie, empty Authorization header and stolen cookie
  without CSRF never reach body/runtime.
- Valid cookie for deputy/accountant/project role, stale/revoked/non-2FA
  session, inactive actor or foreign company/project returns opaque fixed error.
- Huge, chunked, deeply nested, duplicate/extra-field or type-confused JSON
  stops before capacity/DB.
- Repeated/concurrent calls hit nginx/backend limits without opening a second
  runtime connection.
- Foreign/nonallowlisted/missing/wrong-status/human job cannot be distinguished.
- Internal exception text containing credentials/SQL/private JSON never appears
  in body, headers, context, logs or metrics.
- A 503 response performs zero API-error/audit/session/database writes.
- Blocked/stale results cannot be converted into partial preview content.

## Proposed project structure

The later implementation should touch only these focused surfaces:

```text
backend/features/warehouse_recommendation_preview/runtime_routes.py
backend/features/warehouse_recommendation_preview/test_runtime_routes.py
backend/main.py                         # conditional registration + exact log exclusion
ops-nginx-stroyka-public-api.conf       # later ops checkpoint only
docs/warehouse-anomaly-http-adapter.md  # living contract/evidence
tasks/plan.md, tasks/todo.md             # only after spec approval
```

No change is expected in `runtime_preview.py`, A9.3 byte/time/auth contracts,
database schema, package `__init__.py` or frontend during the adapter slice.

## Code style and boundary shape

Follow the existing dependency-injected route module pattern. The route module
owns only HTTP parsing, fixed error translation, headers and response-shape
validation; the canonical private runner owns all database/runtime behavior.

```python
def register_warehouse_anomaly_preview_routes(app, deps):
    if deps.get("enabled") is not True:
        return None

    @app.post("/warehouse-anomaly-previews")
    async def create_preview(request: Request, ...):
        authentication = build_authentication(
            request, authorization, csrf_token, require_csrf=True,
        )
        body = await bounded_exact_json(request, limit=4096)
        return fixed_no_store_response(
            run_preview(db_config, authentication, ...),
        )
```

The implementation must not catch named process-control exceptions as public
HTTP failures; A9.3 cleanup runs first and identity propagation remains intact.

## Testing strategy and commands

Use TDD and stop at each checkpoint:

1. **A9.4a contract RED/GREEN:** disabled registration, one exact route,
   cookie/CSRF/header/body parser, exact public success/error table, no-store.
2. **A9.4b integration RED/GREEN:** real private A9.3e runner through one
   recording connection; fixed allowlist, zero DB writes and exact 18 SELECT
   inventory remain unchanged.
3. **A9.4c ops proof:** nginx 413/429 JSON parity, connection/request limits,
   concurrent busy behavior and privacy-safe aggregate telemetry.
4. **A9.4d closure:** focused/package/A7/full backend, browser role/tenant/CSRF
   checks, security review and separately approved production rollout plan.

Commands after implementation:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a94-pycache \
  python3 -m unittest \
  backend.features.warehouse_recommendation_preview.test_runtime_routes \
  backend.features.warehouse_recommendation_preview.test_runtime_routes_closure

PYTHONPYCACHEPREFIX=/private/tmp/a94-preview-pycache \
  python3 -m unittest discover \
  -s backend/features/warehouse_recommendation_preview -p 'test_*.py'

PYTHONPYCACHEPREFIX=/private/tmp/a94-a7-pycache \
  python3 -m unittest discover \
  -s backend/features/estimate_revision_impact -p 'test_*.py'

PYTHONPYCACHEPREFIX=/private/tmp/a94-backend-pycache \
  python3 -m unittest discover -s backend -p 'test_*.py'

python3 -m py_compile \
  backend/features/warehouse_recommendation_preview/runtime_routes.py \
  backend/features/warehouse_recommendation_preview/test_runtime_routes.py \
  backend/features/warehouse_recommendation_preview/test_runtime_routes_closure.py

git diff --check
```

Before any production release: `nginx -t`, the applicable ops smoke commands,
browser cookie/CSRF verification, dependency audit, and an explicit human
approval for flag/allowlist values and deployment.

## Unperformed production rollout and rollback checklist

This checklist is documentation, not authorization. Every item remains
unchecked after the local A9.4d checkpoint.

### Approval and preflight

- [ ] Obtain explicit human approval for the exact company allowlist, exact
  flag value, deployment window, commit/push and production access.
- [ ] Ensure the backend origin is not publicly reachable except through the
  reviewed nginx boundary; direct origin exposure blocks the rollout.
- [ ] Install the two zones in nginx `http {}` and the exact location/error
  handlers in the active server; run `nginx -t` before any reload.
- [ ] Capture a flags-off health baseline and confirm the endpoint is absent,
  existing routes still proxy normally and API-error logging still works on a
  neighboring path.

### Small canary

- [ ] Set exact lowercase `WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED=true` and the
  separately approved canonical company-ID list; reject an empty or malformed
  allowlist rather than widening it.
- [ ] Restart only the approved backend unit, reload nginx only after a green
  syntax check and verify that no second public/origin path reaches the route.
- [ ] From a real browser, prove signed cookie + matching CSRF + passed-2FA
  allowlisted director success; prove Bearer, deputy/accountant/project roles,
  stale/revoked/non-2FA sessions, foreign tenant/project and nonallowlisted
  company remain the fixed opaque outcomes.
- [ ] Verify exact 413/429 JSON/no-store/Retry-After behavior, global one-request
  capacity and that a concurrent request opens no second database connection.
- [ ] Monitor fixed outcome/duration aggregates, latency, backend errors and DB
  connection count; confirm zero session/audit/API-error/business writes.

### Rollback triggers and procedure

- [ ] Roll back immediately on any private-data/error leak, auth/tenant bypass,
  write, second runtime connection, timeout/cleanup drift, non-JSON proxy error
  or unexplained availability regression.
- [ ] Unset both warehouse-anomaly feature variables and restart the approved
  backend unit; the route must disappear before any further investigation.
- [ ] Restore the previous nginx server/http configuration, run `nginx -t`,
  reload, and verify the exact route and direct-origin path are unreachable.
- [ ] Re-run flags-off health/error-log checks and preserve only privacy-safe
  aggregate diagnostics. There is no database migration or data rollback for
  this read-only feature.

## Success criteria

- The route is absent when disabled or misconfigured and exact-only when on.
- Invalid/unauthenticated/nonallowlisted requests never acquire runtime capacity.
- One valid request calls the private A9.3e runner exactly once and returns only
  the frozen minimal public projection with no-store headers.
- All public errors match the fixed table and contain no internal code/text.
- One request performs zero writes, one lease/connection/snapshot and at most
  18 guarded statements plus rollback.
- Concurrent/rate-limited requests cannot create a second connection.
- 503 paths are excluded only from the global DB error logger; all other paths
  retain existing logging behavior.
- No route/UI/export is enabled in production until a separate rollout approval.

## Boundaries

### Always

- Validate every external byte before the runtime boundary.
- Use existing cookie/CSRF and A9.3e contracts without duplicating auth/SQL.
- Keep errors fixed, responses no-store and all selectors out of the URL/logs.
- Preserve zero writes, tenant isolation, exact limits and rollback-before-content.
- Run focused/full/security tests before asking to enable anything.

### Ask first

- Approval of this spec, PLAN/TASKS and each implementation checkpoint.
- Any auth/role/CSRF/CORS/rate/body/time/capacity/error/default change.
- Editing nginx, global middleware, system-status/metrics or feature flags.
- Any browser/UI work, production canary, enablement, commit, push or deploy.

### Never

- Accept Bearer, all-company mode, client report/hash/content or latest job.
- Log or expose cookie/CSRF/session hash, actor/company/project/job/candidate,
  stored/current evidence, SQL, traceback or dependency text.
- Write session last-seen, audit/error tables, stock/inventory or any business row.
- Retry the runner, open a second connection, weaken resource caps or add writes.
- Enable the route for an empty/unbounded company set or bypass the feature flag.

## Resolved design decisions

- Stable endpoint: `POST /warehouse-anomaly-previews`.
- Every live-auth failure remains opaque 401; CSRF alone is fixed 403.
- Initial canary limit: 6 requests/minute, burst 1, and one global in-flight
  nginx request in addition to the process-local backend semaphore.
- Privacy-safe aggregate metrics remain operational telemetry in A9.4; the
  existing protected system-status contract is not expanded.
