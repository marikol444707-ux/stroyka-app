# Supply history company boundary verification

The authenticated two-company document chain exposed missing company checks in
GET/POST /supply-history. PUT ownership enforcement is tracked separately in
PR #281. A global director role and unrestricted project list do not grant access
to another company. The selected context and effective local role determine reads
and creation; conflicting project ownership and company headers are rejected.

The PostgreSQL regression covers rejected foreign creation without partial rows,
foreign reads, a forged company header, all-companies mode, legitimate owner
creation, rejected updates without changes, and legitimate owner updates. The
full chain covers requests, quotation selection, separate contracts/archives,
invoices, shipments, receipt and legacy claim updates that remain disabled.
Shipment before payment remains allowed; receipt does not imply payment.

The bound contract context suite verifies frozen invoice bank details, exact
contract versions, profile changes, receipt identity and company isolation. The
fixture uses the supplier-document statements from migration 0086; project-launch
tables are outside this fixture. No production migration or data modification is
performed by this verification.

Local result: 22 PostgreSQL checks passed. Browser validation remains unavailable
because the browser connection cannot initialize. The local isolated PDF worker
also lacks pypdf under Python isolated mode; its PDF check is not claimed passed.
Production installation remains a separate step after CI and merge.
