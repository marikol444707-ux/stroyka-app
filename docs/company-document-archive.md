# Company document archive — initial read projection

`GET /company-document-archive` is an additive, read-only endpoint for directors
and deputy directors in the selected company. It is not the supplier or customer
cabinet API. All-company context returns `requiresCompanySelection: true` with
no items. Global role alone does not authorize access: use the effective selected
company actor. No new table or original file copy is created.

Parameters: section `all|company|supplier|customer`, literal text search `q` (max 200),
limit 1–100 (default 50), offset 0–100000. Ordering: created_at descending,
source, source ID descending. Offset pagination can shift under concurrent inserts;
it is intended for interactive browsing, not export or migration.

Response items carry a stable composite ID, source/sourceId, companyId, title,
documentType, createdAt, fileUrl and fileStatus. Statuses:
- available: exact active protected file owned by the same company, with project access verified where applicable;
- not_attached: no attachment reference;
- needs_review: a reference exists but cannot safely be exposed by this projection.

The file content endpoint retains its independent authorization. Original external
or legacy URLs are never returned. Archived supplier records are excluded.
Current sources: company_documents, supplier_documents, supplier_offers,
supplier_invoices, supply_deliveries and warehouse_invoices. The supplier section
includes all procurement sources. Project documents and reusable contracts are
not included yet. Source/sourceId remain the identity of the business record;
this endpoint does not yet expand relationships between different records.

Each item also has attachments (deduplicated protected file IDs/URLs) and
unavailableAttachments. A partially available set has fileStatus needs_review,
while its individually verified attachments remain accessible. Project-scoped files require resolve_project_parent and require_project_parent_access, using the same full-view roles as the content endpoint. Missing or denied projects withhold the file; authorization is cached per project within a request only. Malformed page
arrays are marked for review, not silently dropped as missing files.

Verification: five API unit tests cover scope, effective role, query parameters,
unsafe URLs and pagination. A read-only SQL rehearsal against existing data returned
three records for company 1, zero for company 2. Rehearsal used synthetic actors;
it does not replace authenticated browser and production authorization checks.

Procurement increment: seven route tests passed. Read-only SQL rehearsal returned
100 rows on company 1's first page and two company 2 records, with no owner mixing.
Two project-scoped attachments remain withheld by the conservative file filter.
This increment is local and has not been deployed or browser-verified.

Project-access/UI increment: nine route tests and six interface tests passed. Read-only SQL rehearsal returned five available attachments for company 1 (including two project files), no cross-company rows. Settings now has a leadership-only Archive tab; existing legal document editing remains in its original tab. Customer documents, reusable contract bindings and source navigation are pending. Browser verification and deployment of the archive remain pending.

Customer increment: project_documents with side=customer are included only when
project_id resolves to the same company in SQL. Leadership archive preserves
sign_status (including annulled history); this is not automatic publication to the
customer cabinet. File project ID must equal the source document project ID.
Records include projectId/projectName/status. Read-only SQL rehearsal: company 1
has 15 customer documents, company 2 has none, no attached scans in these records.

Verification: 16 server tests and 3 archive UI tests passed. A standalone real-browser
fixture using the actual React component and synthetic fetch responses passed
section selection, file-open callback, company switch, empty search, mobile
390/390 viewport/scroll width. The fixture does not validate production authentication
or actual PDF rendering; its only console error was a missing fixture favicon.
The shared archive is still not deployed; release browser checks remain necessary.

Released 2026-09-28 at dcadb4d8: Settings > Archive documents. Production nginx must proxy /company-document-archive to the API (added and validated during release); the SPA fallback is not an API response. Public API smoke now includes this route. Live browser verified own/customer/supplier sections, search, pagination, file opening, denied foreign company and mobile width. Existing source data unchanged. Earlier not-deployed notes above describe intermediate checks.
