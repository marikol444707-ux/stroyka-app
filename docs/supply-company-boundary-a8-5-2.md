# A8.5.2 — company boundary for supply comparison

## Rule

One supply-comparison run belongs to exactly one server-verified company.

The boundary is created before any invoice, offer, request, warehouse document,
project or file is loaded.  Business payload values never select or widen the
company scope.

## Server-owned scope

The route must first call the existing company-context resolver and accept only
`mode=company`.  `all_companies`, account summaries and platform-wide contexts
cannot start a working supply analysis.

The durable job stores the selected company in `agent_jobs.company_id`.
Handlers use that server-owned value as the source of truth.  A `companyId`
inside `payload_json` is only an assertion to verify, never an authority.

## Required equality chain

Every loaded source must satisfy:

```text
job.company_id
= request.company_id
= offer.company_id
= supplier_invoice.company_id
= warehouse_invoice.company_id
= file_ownership.company_id
= project.company_id
```

A missing company, a conflicting duplicate company field or one foreign row
fails closed with the fixed code `supply_company_boundary_violation`.

## Project scope

A payload cannot create a project scope.  When a project is selected, the
server must also store it in `agent_jobs.project_id`; any project identifier in
payload or stored source must match it.

Company-level document analysis may have no project scope.  In that case the
resolver must not infer a project from untrusted payload content.

## A8.5.2 safety state

This slice is metadata-only and pure:

- no database access;
- no filesystem or document reads;
- no HTTP or model calls;
- no business writes;
- `writesAttempted=0`;
- `automaticApprovalAllowed=false`.

The next slice may add a read-only source resolver.  Its SQL must include an
explicit parameterized company predicate for every tenant-owned table and must
run inside a read-only transaction.
