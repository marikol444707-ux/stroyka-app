# Read-only Accounting Exception Checks

## Purpose

Task A11 adds deterministic accounting checks for one exact company. The
feature points an accountant or director to stored facts that contradict each
other; it does not create, approve, execute, reverse or mark a payment as paid.
It does not call a model and does not infer intent from comments, descriptions
or payment-purpose text.

The existing Accounting page also reads legacy tables that are not reliably
company-scoped. A11 therefore begins with an ownership migration before it
builds exception checks. Only rows whose company ownership and linkage can be
proved from stored keys participate. A missing proof is a coverage limitation,
never permission to join by a similar name.

## Ownership migration prerequisite

The following tables must receive server-owned tenant coordinates before their
facts can participate in A11:

- `accountable_payments`: `company_id`, exact `project_id` and
  `company_scope_verified`;
- `accountable_expenses`: the same coordinates inherited from its verified
  parent payment;
- `expense_reports`: `company_id`, exact `project_id` and
  `company_scope_verified`;
- `salary_payments`: `company_id` and `company_scope_verified`, derived from a
  separately verified staff owner;
- `own_expenses`: `company_id`, exact nullable `project_id` and
  `company_scope_verified`; a raw legacy `employee_id` is not ownership proof
  because existing writers can store either a `users` ID or a `staff` ID. It
  proves company-only ownership only when both namespaces are checked and all
  exact active identity memberships resolve to one company;
- `expenses`: the same coordinates inherited from a verified linked
  `own_expenses` parent, or proved independently by one globally unique exact
  project when `own_expense_id` is absent;
- `staff`: an explicit ownership-verification marker so its historical
  `company_id DEFAULT 1` is not silently treated as proof.

New writes take company/project identity only from the authenticated server
context and exact stored IDs. The client may display names but cannot choose a
tenant by submitting a name or an unchecked `companyId`.

Legacy migration is two-stage and idempotent:

1. a default read-only inventory classifies every row as `provable`,
   `ambiguous`, `orphaned` or `conflicting` without changing it;
2. explicit `--apply` backfills only `provable` rows and leaves every other row
   with `company_scope_verified=FALSE`.

The local A11.2a backfill primitive now implements the second rule without an
automatic call site. Its default is a rolled-back dry-run. A write requires the
exact ready count and SHA-256 from that dry-run, repeats classification under
locks and writes only still-unverified rows with empty owner fields. Plan
drift, pre-existing conflicting owner metadata, a changed row count, a failed
constraint or an incomplete postcheck rolls back the entire transaction.
Running the primitive against production is not authorized by local test
completion; the operator command/runbook and exact-record remediation remain
the separate A11.2b checkpoint.

The A11.2b request contract identifies only one allowlisted source row, one
exact company, an exact project where that table is project-scoped, and one
operator user — all as built-in positive integer IDs. Names, notes, descriptions
and implicit current/default-company fallbacks are not accepted. Its
transactional runner defaults to a rolled-back dry-run and returns a detached
evidence SHA-256 bound to the stored verification/owner state and fixed parent
IDs. Apply accepts only that exact preceding fingerprint, repeats company,
project, target, parent and verified-staff checks under one serializable
transaction, updates one still-unverified row, writes one minimal `audit_log`
event and postchecks before commit. Any drift, invalid owner, update conflict,
audit failure or postcheck failure rolls back both writes. An already-verified
exact rerun performs no write and creates no duplicate audit event.

The runner remains private and has no automatic application call site. Its
operator command is also local-only and defaults to dry-run. Apply-time
revalidation locks only the exact target row and its selected company, project,
operator and parent/staff proof rows. The operator ID must resolve to one active
director, deputy director or accountant role in that exact company.

Dry-run example (IDs are examples only):

```bash
python3 -m backend.features.accounting_exception_checks.ownership_remediation_command \
  --source accountable_payments \
  --record-id 200 \
  --company-id 4 \
  --project-id 19 \
  --operator-user-id 31
```

The output's `requestSha256` and `evidenceSha256` must be reviewed and copied
unchanged into the separately approved apply command:

```bash
python3 -m backend.features.accounting_exception_checks.ownership_remediation_command \
  --source accountable_payments \
  --record-id 200 \
  --company-id 4 \
  --project-id 19 \
  --operator-user-id 31 \
  --apply \
  --confirm APPLY_EXACT_ACCOUNTING_OWNERSHIP_REMEDIATION \
  --expected-request-sha256 REQUEST_SHA256_FROM_DRY_RUN \
  --expected-evidence-sha256 EVIDENCE_SHA256_FROM_DRY_RUN
```

Company-only `staff` and `salary_payments` commands omit `--project-id`.
Incomplete guards and changed IDs fail before connecting. This runbook documents
the local mechanism only: local completion does not authorize a production
schema change, backfill or remediation.

A project-name backfill is allowed only when it resolves to exactly one stored
project globally. A staff proof may be used only when that staff row is itself
verified. If project, parent and staff proofs are all present they must agree.
For legacy staff without a usable project, exact email/Telegram identity may
prove company-only ownership only when it resolves through active user-company
memberships to exactly one company. Multiple candidate companies remain
quarantined. The same rule applies to a legacy `own_expenses.employee_id` after
checking both its historical `users` and `staff` meanings; linked `expenses`
may then inherit the same company with a nullable project.
Accountable expenses inherit scope only from one verified parent payment and
must agree with its project; they are never independently assigned by their
description or employee name. A linked manual expense inherits scope only from
its verified `own_expenses` parent and must agree with that parent's exact
project. Employee names or raw IDs, note prefixes, categories, source labels
and money values never establish tenant ownership.

Ambiguous/orphaned/conflicting rows remain quarantined from company APIs. A
later operator remediation command may bind one exact record ID to exact
company/project/staff IDs, but it must default to dry-run, validate all owners,
record an audit event and require a separate production approval. No production
backfill or automatic reassignment is authorized by this specification update.

## Accountable route cutover

The A11.3a local implementation preserves the four public URLs for accountable
payments and expenses while replacing their legacy name-only trust boundary.
Every request resolves one finance actor for one selected company; aggregate
mode is rejected. Reads require both the selected `company_id` and
`company_scope_verified=TRUE`, so quarantined and foreign legacy rows remain
invisible.

Payment creation accepts exact `projectId` and `givenToId` only. The server
resolves and locks the project and verified staff row in the selected company,
then derives `project_name`, `given_to` and `added_by` from stored/authenticated
state. Expense creation locks a verified parent payment, inherits its exact
company/project and scopes the parent balance update by the same stored owner.
Client-supplied project, employee or author names are not ownership evidence.
The UI sends the exact IDs and displays the inherited project for a child
expense instead of allowing a second project choice.

Fake-route tests and the launcher-owned disposable PostgreSQL fixture prove
cross-company/quarantine exclusion, owner-derived writes, rollback on a
foreign project and exact parent balance updates. This is local code evidence;
it does not apply the A11 schema or backfill to production and does not authorize
a deployment.

The expense-report quartet follows the same cutover boundary. A report is
visible or mutable only when its stored company matches the one selected
finance actor and its scope marker is verified. Creation resolves and locks
the stored project and verified staff rows by ID; display names and canonical
balance are derived on the server. Approval and soft-cancellation lock the
stored report and derive the approving actor on the server. Quarantined or
foreign rows remain unreachable even when another tenant uses the same project
name. The browser sends IDs only and cannot select ownership by a display name.

Salary payments use the verified staff row as their sole employee ownership
source. A payment stores the selected company and exact staff ID; staff name,
payer and payment date are server-derived. Reads and deletes require the same
verified company marker, and delete locks the stored payment before repeating
its company/staff predicate. The browser submits only staff ID, canonical month
and amount.

The staff-directory cutover now uses the same selected-company boundary.
Lists and profiles expose only verified staff rows in that company; creates
store the selected company and verification marker, while updates and dismissal
lock the exact verified row before writing. A custom staff document is visible
or mutable only through its verified staff parent. Profile linkage to a system
user requires the staff email and an active membership in the selected company,
not a legacy same-name match. Dismissal deactivates only that company's
membership, preserving the global account and any active membership the person
has in another company. A company manager cannot reset an existing shared
user's global password through the staff endpoint.

## First-release scope

After the ownership migration, the first release checks these company-owned
fact groups:

1. `brigade_payments` linked to `brigade_contracts` and the verified
   `project_payments` ledger.
2. `supplier_invoices` explicitly linked to company-owned
   `warehouse_invoices`.
3. verified accountable payments and their exact child expenses.
4. verified expense reports.
5. verified salary payments and their exact staff owner.
6. verified `own_expenses` and manual `expenses` rows joined only through exact
   stored IDs or their separately proved exact project owner.

It may report only these exact contradictions:

- a brigade payment has no ledger link even though the current writer contract
  requires one;
- its stored ledger target is absent, belongs to another company, is not a
  verified company-scoped payment, or has a different stored amount/project;
- an invoice's explicit warehouse link points to an absent or foreign row;
- two explicit supplier/warehouse link fields disagree with each other;
- a supplier invoice's stored paid amount exceeds its stored invoice amount;
- a verified accountable expense is orphaned/foreign, its exact child sum
  disagrees with stored `spent_amount`, or that sum exceeds the advance;
- a verified expense report's stored balance disagrees with the canonical
  `issued_amount - spent_amount` equation;
- a verified salary payment has an absent/foreign staff owner or a malformed
  canonical `YYYY-MM` month.
- an explicit `own_expenses.expense_id` / `expenses.own_expense_id` link points
  to an absent/foreign row, is non-reciprocal, or the verified linked pair has
  conflicting exact project ownership.

These are review findings, not accusations and not payment instructions. Exact
money values may be returned only where they are necessary to explain a stored
numeric contradiction. Notes, purpose text, bank details, photos, files,
invoice item JSON and raw database rows are never returned.

## Explicitly deferred

The first release must not evaluate:

- quarantined rows before an operator has supplied and verified their exact
  ownership;
- "оплата без первички" based on note prefixes, UI state or a missing optional
  link;
- debt maturity, overdue status, VAT correctness, duplicate invoices,
  contractor performance or whether a payment should be made;
- fuzzy matching by project, supplier, employee, invoice number or free text;
- bank integrations, payment orders, accounting-system synchronization or any
  mutation endpoint.

The existing frontend heuristic for primary-document gaps remains a UI hint
and is not promoted to server truth by A11.

## Ownership and read boundary

Every request is bound to one positive `company_id`. Aggregate-company mode is
not supported. A source row participates only after all immediate owner and
parent keys agree with that company. `project_payments` additionally requires
`company_scope_verified=TRUE`. Quarantined or owner-ambiguous rows do not leak
into another company's result; if their safe attribution is required, a later
system-only integrity report needs its own contract.

The A11 exception-check runtime uses one PostgreSQL `REPEATABLE READ READ ONLY`
transaction, parameterized `SELECT` statements, bounded ordered source sets
and one rollback. It has no commit, DDL, DML, `FOR UPDATE`, queue write, model
call, filesystem write or network call. Variable payload is measured before it
can cross libpq, and malformed size metadata or query-wide gating fails closed.

The ownership migration is a separate operator workflow. Its default inventory
mode is read-only. Schema/backfill/remediation writes run only with explicit
apply flags, inside bounded transactions, with pre/post counts and rollback on
any mismatch; executing them against production requires a separate approval.

The local A11.1 schema contract is complete but deliberately unregistered. It
adds only the metadata needed for later verified ownership: nullable owner IDs,
a false-by-default verification marker, finite-value checks and partial
indexes. Its apply path requires the exact reviewed plan count and SHA-256,
locks the seven accounting tables, validates the resulting `public` catalog
and commits only if that postcheck is exact. A disposable PostgreSQL 15 cluster
proves two applications are idempotent and byte-preserving for legacy business
columns. No production schema or row has been changed; production application
and the provable-only A11.2 backfill remain separate approvals.

The projection is built first as a pure function over normalized detached
rows. SQL, HTTP and UI are separate later slices so no route can expose an
unreviewed interpretation.

## Result contract

The immutable result contains:

- exact version and one-company scope;
- state: `clear`, `review_required` or `incomplete`;
- bounded source counts and a `truncated` flag;
- at most 100 deterministic findings with fixed reason codes;
- subject kind/ID, exact project ID when proven, and only the small allowlisted
  numeric fields required by that reason.

`clear` means no contradiction was found inside the complete reviewed scope;
it does not certify the company's entire accounting. `incomplete` means a row,
byte, schema or ownership guard prevented a complete reviewed scan. Unknown
reason codes and malformed stored facts fail closed instead of being copied.

### A11.4 pure projection contract

The private `accounting-exception-projection-v1` function accepts exactly one
positive company ID and the twelve normalized source sets named in
`ACCOUNTING_EXCEPTION_SOURCES`. Every detached row has a built-in positive ID,
the same company ID and `owner_status="verified"`; this synthetic status means
that the later collector has already proved the row's exact stored ownership.
It is not copied from a free-form business-status field. A foreign company,
quarantined or unknown owner status, duplicate ID, missing source, float,
non-finite/oversized decimal, malformed link or more than 1,000 rows in one
source returns one fixed `incomplete` result with no partial findings.

The closed reason vocabulary is:

- `accounting_brigade_ledger_link_missing`,
  `accounting_brigade_ledger_not_found`,
  `accounting_brigade_ledger_project_mismatch`,
  `accounting_brigade_ledger_amount_mismatch`;
- `accounting_supplier_warehouse_link_not_found`,
  `accounting_supplier_warehouse_link_nonreciprocal`,
  `accounting_supplier_invoice_overpaid`;
- `accounting_accountable_expense_parent_not_found`,
  `accounting_accountable_expense_parent_project_mismatch`,
  `accounting_accountable_spent_sum_mismatch`,
  `accounting_accountable_advance_exceeded`;
- `accounting_expense_report_balance_mismatch`;
- `accounting_salary_staff_not_found`,
  `accounting_salary_month_invalid`;
- `accounting_own_expense_link_not_found`,
  `accounting_own_expense_link_nonreciprocal`,
  `accounting_own_expense_link_project_mismatch`.

Money is compared only with finite bounded `Decimal` values and is rendered as
canonical decimal text only for the five numeric reason families that require
it. Findings are independent of input order, counted before the deterministic
100-item display cap and contain no notes, purpose, names, photos, files, bank
data, item JSON or raw rows. The module is deliberately absent from package
exports, `backend/main.py` and every SQL/HTTP call graph.

### A11.5 bounded one-company snapshot

The private snapshot collector reads the twelve A11 sources in their closed
order inside one `REPEATABLE READ READ ONLY` transaction. Every query is a
parameterized top-level `SELECT` scoped to one positive company ID. Rows whose
stored company scope is not verified are excluded, immediate project/parent
ownership is joined by exact IDs, and legacy project-name links are accepted
only when the name identifies exactly one project in that company.

Each source first materializes at most 1,001 ordered rows, measures the exact
UTF-8 representation that would be returned, then applies one query-wide gate.
The accepted ceiling is 1,000 rows per source, 64 bytes per numeric field,
7 bytes for a salary month, 1 MiB per query and 4 MiB for the whole snapshot.
If a row, field, query or cumulative ceiling is exceeded, all variable fields
are nulled before crossing the driver boundary and the result is the fixed
empty `incomplete` projection. Contradictory metadata, unexpected aliases and
raw data in a denied batch fail closed.

Only detached IDs, exact finite decimal values, the validated salary month and
the synthetic `owner_status="verified"` reach the pure A11.4 projection. Notes,
purposes, names, photos/files, bank details and item JSON are never selected.
The lifecycle performs zero commits, exactly one rollback after connection,
and attempts both cursor and connection cleanup. The collector remains absent
from package exports, `backend/main.py`, routes and frontend call graphs.

## Authorization and delivery

The A11.6 HTTP adapter registers exactly one
`GET /accounting-exception-checks` route only when both
`ACCOUNTING_EXCEPTION_CHECKS_HTTP_ENABLED=true` and a strict duplicate-free
`ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS` allowlist are valid. Missing,
partial, differently cased or malformed configuration keeps the route absent.
The route accepts only cookie-session authentication, exact
`X-Company-Mode: company` and one canonical positive `X-Company-Id` already in
the allowlist. It then verifies the live session, two-factor state, active user,
active company membership and one of the existing director, deputy or
accountant finance roles before starting any A11 business read.

Authorization and the twelve bounded source collectors execute in the same
`REPEATABLE READ READ ONLY` transaction: one settings query, two authorization
queries and twelve source queries, followed by zero commits and one rollback.
The HTTP boundary accepts only the exact closed A11.4 response and reason-code
vocabulary. Every success and fixed error is `no-store`; unknown fields,
malformed authentication, foreign companies, raw rows and dependency text fail
closed. The exact route is also excluded from the global API-error database
writer so a failed read cannot create a diagnostic business-database write.

`ops-nginx-accounting-exception-checks.conf` is a local deployment fragment
with an exact local upstream, request and connection limits, bounded timeouts
and a fixed JSON 429 response. It is not installed by this slice. There is no
POST, PUT, PATCH, DELETE, apply, save, approve, pay or status-changing route.
Nginx installation, commit, push, deployment and production enablement remain
separate review checkpoints.

### A11.7 review-only Accounting panel

The existing Accounting summary now contains a separate review panel, but it
is absent unless both frontend settings are exact:

- `REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_ENABLED=true`;
- `REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS` is a canonical,
  duplicate-free comma-separated allowlist of positive company IDs.

The browser additionally requires one selected company (never aggregate mode)
and the director, deputy-director or accountant role. It performs one
cookie-session `GET /accounting-exception-checks`, validates the complete
closed `accounting-exception-projection-v1` response against the selected
company before rendering, and aborts/clears the previous result immediately
when company scope changes. The route remains the final authorization boundary;
the frontend gates only prevent unintended presentation and traffic.

Only fixed Russian reason labels, subject/project/link IDs and the exact
reason-specific canonical money strings are displayed. Notes, names, payment
purposes, bank data, photos, file URLs, unknown fields and raw JSON are rejected
rather than copied. The panel offers only a safe GET refresh and explicitly has
no apply, pay, approve, repair, reassign or status-changing control.

Local browser inspection used an isolated fake session and mocked localhost
responses. At 1440 px and 390 px the panel remained readable above the existing
financial summary; the mobile document width equalled the viewport width, with
no horizontal overflow. Screenshots are kept under `output/playwright/` and no
production account, route flag, nginx file or business row was touched.

### A11.8 local closure

The local implementation is closed without activating production. A real
FastAPI route proof now runs inside the existing launcher-owned disposable
PostgreSQL 15 cluster. An active company-4 accountant completes exactly one
settings query, two authorization queries and twelve bounded accounting
SELECTs, receives only the validated company-4 result, commits zero times,
rolls back once and leaves all fixture tables unchanged. A `прораб` stops after
the three settings/authorization queries with a fixed `403`; no business source
is read. Foreign-company marker data crosses neither the driver nor HTTP
boundary.

The reviewed runtime call graph is closed: `runtime_routes` receives the
authorized `runtime_access` dependency, which calls only the read-only
`snapshot`, which calls only the pure `projection`. None imports the ownership
schema, backfill or remediation writers. Static inspection finds no DML, DDL,
commit or frontend mutation method in that path. Existing mutation routes
remain separately role/tenant guarded and are unreachable from the A11 GET or
panel.

Production operations are split into two documents:

- `docs/accounting-exception-checks-migration-runbook.md` covers the reversible
  inventory/backup/schema/backfill/quarantine/remediation sequence and its
  transactional stop/recovery conditions;
- `docs/accounting-exception-checks-canary.md` covers the later one-company,
  default-off deploy, exact route/browser smoke, metrics, stop thresholds and
  backend-first rollback.

Neither document is authorization. Production migration, flags, nginx,
deployment and canary require separate explicit approval.

Final local evidence: focused accounting `83/83`, disposable PostgreSQL
`51/51`, full backend `2316/2316` with 56 expected skips, full frontend
`400/400` in 97 suites, successful production build, zero vulnerabilities in
both offline npm audits, isolated compilation, static no-write/call-graph scans
and clean diff checks. The online npm registry audit remains a pre-deploy check
because this execution environment did not authorize sending dependency
metadata to the public registry.

## Verification strategy

Development proceeds tests-first:

1. read-only ownership inventory and idempotent schema-contract tests;
2. provable-only backfill/quarantine and future-writer ownership tests;
3. pure exception projection and fixed-code tests;
4. bounded SQL collectors, one-transaction composition and disposable
   PostgreSQL 15 proof;
5. default-off authorization/tenant tests;
6. review-only UI/browser tests;
7. full regression, migration runbook, static no-write checks and a separate
   canary plan.

The real PostgreSQL proof must include same-name cross-tenant data, explicit
link mismatches, exact decimal comparisons, row/byte boundaries, zero commits,
one rollback and byte-equivalent business tables before and after the read.

## Assumptions requiring approval

1. A11 starts with hard stored contradictions only; operational reminders and
   fuzzy reconciliation stay out.
2. Company-unscoped legacy rows are migrated only when ownership is provable;
   ambiguous rows are quarantined and require explicit operator remediation.
3. The migration also hardens every future write path before any newly scoped
   row is trusted by A11.
4. The first useful surface is company-wide but still one exact company per
   request; optional project filtering may be added only after the company-wide
   ownership proof.
5. No A11 code or schema implementation begins until this expanded scope is
   accepted.
