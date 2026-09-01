# A8.5.2 — Read-only supply comparison source resolver

## Purpose

This slice connects the pure A8.5.1 technical matcher to one selected supply
request and one selected supplier offer or invoice. It resolves only
previously stored structured lines and a registered protected document inside
one exact company/project boundary.

The slice does not add an HTTP route, background job or business writer.

## Read-only flow

The resolver accepts six explicit identities:

- company ID;
- project ID;
- supply request ID;
- source kind (`supplier_offer` or `supplier_invoice`);
- selected source ID;
- protected file registry ID.

It then performs three bounded `SELECT` queries:

1. Load the request through an active project with the same company, project
   ID and stored project name.
2. Load the selected offer, or load the selected invoice through its exact
   offer/company/request relationship.
3. Load the active file registry row with the same company and project IDs.

The transaction is `READ ONLY`, `REPEATABLE READ` and is always rolled back,
including validation failures. Public results report `writesAttempted=0` and
`modelCalls=0`.

## Document safety

The resolver returns only `/tenant-files/{id}/content`; it never returns the
raw storage URL or storage key. The registered storage pointer must belong to
the selected company/project namespace. A source cannot substitute a file
from another company, project or inactive registry entry.

The document is not downloaded, opened or sent to OCR/model services in this
slice. Its stored structured lines are the only comparison input.

## Line pairing boundary

Required and offered lines are paired by their stored order only. The resolver
requires:

- equal line counts;
- equal normalized quantities;
- equal work packages.

If these conditions are not satisfied, it returns one fixed non-leaking error
instead of guessing a match or comparing a partial set. Each paired line is
then delegated to the pure A8.5.1 matcher.

## Explicit non-goals

A8.5.2 performs none of the following:

- supplier ranking or selection;
- request-for-quotation sending;
- supplier invoice approval;
- payment;
- warehouse, estimate or supply-request mutation;
- automatic approval.

Every successful result reports `automaticApprovalAllowed=false` and contains
a deterministic SHA-256 hash binding the selected identities to the technical
comparison hashes.

## Next integration slice

A later slice may expose this resolver through an authenticated, rate-limited
read-only route. That route must preserve exact tenant/project authorization
and must not turn a technical comparison into an automatic business decision.
