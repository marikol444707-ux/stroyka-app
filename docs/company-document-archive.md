# Company document archive — initial read projection

`GET /company-document-archive` is an additive, read-only endpoint for directors
and deputy directors in the selected company. It is not the supplier or customer
cabinet API. All-company context returns `requiresCompanySelection: true` with
no items. Global role alone does not authorize access: use the effective selected
company actor. No new table or original file copy is created.

Parameters: section `all|company|supplier`, literal text search `q` (max 200),
limit 1–100 (default 50), offset 0–100000. Ordering: created_at descending,
source, source ID descending. Offset pagination can shift under concurrent inserts;
it is intended for interactive browsing, not export or migration.

Response items carry a stable composite ID, source/sourceId, companyId, title,
documentType, createdAt, fileUrl and fileStatus. Statuses:
- available: exact active protected file owned by the same company, no project scope;
- not_attached: no attachment reference;
- needs_review: a reference exists but cannot safely be exposed by this projection.

The file content endpoint retains its independent authorization. Original external
or legacy URLs are never returned. Archived supplier records are excluded.
Current sources: company_documents and supplier_documents only. Quotes, invoices,
deliveries, project documents and reusable contracts are not included yet.

Verification: five API unit tests cover scope, effective role, query parameters,
unsafe URLs and pagination. A read-only SQL rehearsal against existing data returned
three records for company 1, zero for company 2. Rehearsal used synthetic actors;
it does not replace authenticated browser and production authorization checks.
