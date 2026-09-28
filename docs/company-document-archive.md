# Company document archive

`GET /company-document-archive` is a read-only projection for the effective director
or deputy director of the selected company. It does not grant supplier/customer
cabinet access. All-company mode returns an empty list and requiresCompanySelection.
Settings > Archive documents uses existing originals, without copying files.

## Sources and links

- Company: company_documents.
- Suppliers: supplier_documents (not archived), supplier_offers, supplier_invoices,
  supply_deliveries, warehouse_invoices, supplier_contract_versions.
- Customers: project_documents with side=customer and an exact same-company project.
  Existing signature status is preserved; inclusion does not publish to a customer.

Contract records show number/version and offerId; their source offer must belong to
the same company. The file comes from source_file_id. Invoice offerId is resolved
within the same company. Its contractNumber/contractVersion are returned only for
an exact contract_version_id with matching company and offer. No inference by
name, amount or supplier. Invoice-to-contract and contract/invoice-to-quotation navigation is available inside
the archive. Each contract version also opens its bound invoices, with separate pagination.
Reused versions expose originContractId only when the recorded source ID, offer,
version and hash match a same-company contract with the same original file.
“Исходный договор” opens that exact version. Missing or invalid lineage has no link.
A canonical contract registry remains pending.

## API and files

Parameters: section all|company|supplier|customer; literal search q (max 200);
limit 1–100 (default 50); offset 0–100000. Sort: created_at DESC NULLS LAST, source,
id DESC. Offset pages may shift with concurrent inserts; this is not an export API.

Optional category filters one source family before pagination (same allowlist as
source). It must match the selected section and cannot be combined with exact
record or contract-invoice navigation. UI labels distinguish supply contracts,
quotations, invoices, shipments and warehouse waybills; returning from a linked
record preserves category/search/page. Company or section switch clears category.

Optional source and recordId select one exact record; both are required together,
source is allowlisted and ID is bounded. Company/role and file checks still apply.
The UI preserves the prior search/section/page when returning from a related record.

Optional contractId lists invoices for one exact contract version using matching
company and offer. It cannot be combined with source/recordId or a non-supplier
section. Unbound invoices stay absent. The client validates each returned binding.

Each row has stable source/sourceId identity, companyId, title, documentType,
createdAt, attachments, unavailableAttachments, fileUrl and fileStatus:
- available: active protected original owned by the selected company;
- not_attached: no attachment reference;
- needs_review: missing/unsafe references or malformed attachment arrays.

URLs are deduplicated within a record. Legacy external URLs are withheld. Project
files require resolve_project_parent and require_project_parent_access with the
same role configuration as file contents; authorization is cached per request.
Customer file project must also match the document project. The file-content API
performs its own independent authorization.

## Deployment and validation

Production nginx proxies /company-document-archive to the API; the public API
smoke checks for accidental SPA fallback. Base archive deployed dcadb4d8 with
company isolation, search, pagination, file-open and mobile browser checks.

Contract increment: 12 route tests and 4 UI tests passed. Read-only SQL rehearsal
with synthetic leadership context found the existing contract and quotation;
this alone is not authentication evidence. Release results are recorded in
tasks/counterparty-documents-todo.md and server release receipts.

## Reviewed contract applicability

New review UI explicitly asks for company-wide or current-project scope and a
start date with either an end date or an explicit open-ended term. Conditions are
saved in immutable snapshot.applicability and displayed in the archive. Legacy
versions remain unchanged; missing applicability is unknown, never open-ended.

Reuse requires current validity (inclusive dates, Europe/Moscow), exact parties
and INNs, and the matching authorized project when restricted. Project originals
can only be reviewed for their own project and cannot become company-wide. Legacy
request project names must resolve uniquely inside the already authorized company;
otherwise the project option is unavailable. Saving revalidates eligibility and
requires unchanged applicability from the selected version. Deal-specific payment
schedules remain excluded from reuse.

The legacy API still accepts reviews without applicability for compatibility, but
these versions are not candidates for reuse. No historic invoices are rebound.
This extends existing offer-bound versions; a canonical pair-level registry,
archiving, addenda and expiry controls for other issuance paths remain pending.
