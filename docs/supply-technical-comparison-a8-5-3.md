# A8.5.3 — Authenticated supply technical comparison route

## Outcome

A8.5.3 exposes the A8.5.2 deterministic source resolver through one
authenticated, rate-limited, read-only HTTP resource. It does not add a user
interface or any business action.

## Resource

```text
GET /supply-requests/{requestId}/technical-comparisons/{sourceKind}/{sourceId}?projectId={projectId}&fileId={fileId}
```

`sourceKind` is exactly `supplier_offer` or `supplier_invoice`. All identifiers
are positive PostgreSQL `BIGINT` values without signs, whitespace or leading
zeroes. Requests use the existing cookie session and the exact headers:

```text
X-Company-Id: {companyId}
X-Company-Mode: company
```

Bearer credentials and aggregate-company mode are rejected. The route is
available only to active `директор`, `зам_директора` and `снабженец`
memberships in the selected active company and active platform account. The
session, membership, request, project, selected source and protected file are
resolved in one `READ ONLY`, `REPEATABLE READ` transaction which is always
rolled back and closed.

## Public result

The response contains only validated public comparison fields and the
protected `/tenant-files/{id}/content` URL. Raw object-storage URLs, storage
keys, session hashes and database rows never cross the route boundary.

Every successful result proves:

- `dryRun=true`;
- `readOnlyTransaction=true`;
- `rolledBack=true`;
- `writesAttempted=0`;
- `modelCalls=0`;
- `automaticApprovalAllowed=false`;
- deterministic line and result SHA-256 values.

The route cannot rank or select suppliers, approve an invoice, initiate a
payment, change a request or write an audit/business record.

## Default-off gates

Both environment settings are required before the route is registered:

```text
SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED=true
SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS=1
```

The company list is an exact, duplicate-free allowlist of at most 100 positive
IDs. A missing, malformed or partial configuration leaves the route absent.

## Public error contract

- `401 supply_technical_comparison_authentication_required` — cookie session
  is absent or invalid;
- `403 supply_technical_comparison_request_forbidden` — authentication policy
  rejects the request;
- `404 supply_technical_comparison_not_found` — company is not allowlisted,
  actor is not authorized or a scoped source is unavailable;
- `422 supply_technical_comparison_request_invalid` — selector syntax is
  invalid;
- `429 supply_technical_comparison_busy` — Nginx rate or connection limit;
- `503 supply_technical_comparison_unavailable` — closed internal failure.

All application responses are `no-store`; internal dependency messages are
not returned.

## Deployment boundary

`ops-nginx-supply-technical-comparison.conf` supplies the exact path matcher,
rate limit, single-connection limit, timeouts and stable `429` response. The
Nginx fragments and the two application flags must be introduced as a
separately reviewed company canary. This code slice itself performs no
production enablement.
