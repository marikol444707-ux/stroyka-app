# Unified physical receipt contract

Status: unified receipt implementation and durable zero-receipt evidence prepared and independently reviewed; not deployed. Baseline: c30b5c7a.

## Existing records, not a new accounting model

- `supplier_invoices` is a supplier payment/debt invoice. Its number is not a
  waybill number. Immutable line specifications and managed receipt proofs are
  reused where enabled; their activation and live permissions are unchanged.
- `supplier_shipment_batches` groups one supplier dispatch. Its `delivery_ids`
  point to one `supply_deliveries` row per shipped line; waybill number/date and
  original are saved on those rows.
- A delivery row is accepted once. A shortage is final for that shipment and
  creates a claim. Further supply uses another shipment/replacement, not another
  increment on an already accepted row. Accepted/remaining invoice quantities
  aggregate distinct shipments. Existing receipts retain their IDs.
- `warehouse_invoices` records accepted stock. Receiving a delivery creates this
  record through the existing writer; never additionally call standalone receipt.

## Interaction and server contract

1. Both entry points start with an uploaded original and the existing scanner.
   Recognition is a draft only. Failed recognition permits manual transcription
   with the original retained, never blind posting.
2. Resolve only documents visible to the effective company/project/package actor.
   Match legal supplier and buyer identities, document kind, number/date, then all
   shipment lines and units. Names alone, incomplete snapshots and ambiguous
   batches require explicit review; no first-word matching.
3. A payment invoice can locate authorized linked shipments but cannot itself
   prove dispatch quantity. Ask for the relevant shipment; never equate its
   number with the waybill number.
4. Existing accepted receipt opens read-only. Partial batch shows accepted and
   remaining lines. The operator explicitly confirms physical arrival and actual
   quantities for remaining lines, with discrepancy/claim controls.
5. Revalidate original ownership, source linkage, actor authority and quantities
   under existing writer locks. Repeat confirmation must return the existing
   receipt without stock/accounting changes. An unknown document requires an
   explicit create-new confirmation and uses the standalone receipt writer.
6. Preserve manual edits per document/company. Async recognition must not modify
   another draft. Upload once and reuse the stored original.

## Implementation stages and completion evidence

A. Deterministic matching policy and cross-company/ambiguous/multiline/replay
   regressions; server authorized resolver. No inventory mutation in resolver.
B. Reuse scanner at both entry points; explicit review and actual quantities;
   preserve scoped drafts and originals. Existing standalone input is retained
   for documents with failed OCR, subject to explicit new-document confirmation.
C. Mutation-side document/confirmation admission and concurrent replay checks;
   receipt-level ledger/quality regressions using disposable PostgreSQL. Existing
   one-shot delivery semantics remain authoritative.
D. Frontend regressions/build and realistic multi-line workflow verification.

No stage alone constitutes completion of the entire user request. Do not claim
live verification, installed migrations, permission expansion or deployment.
Chief engineer is not in the existing WAREHOUSE_ROLES set; any narrow receipt
permission addition must be separately tested and reviewed before deployment.

## Verified stage boundary (2026-10-18)

Implemented: shared upload-first scanner; editable review; exact frozen-party and
full shipment-line matching; transaction-owned batch confirmation through the
existing stock writer; replay locking and revalidation; canonical original
persistence; standalone admission guard; existing linked standalone receipt
lookup; narrow chief-engineer receipt authorization without changing generic
warehouse roles; scoped draft preservation and explicit different-document reset.
Existing receipt proofs provide accepted/remaining quantities only when the
existing managed-receipt flag, schema and baseline are already present. Preview
never creates or activates a baseline.

Implemented next stage: explicit authorized shipment selection, payment-invoice
source discovery followed by mandatory physical-waybill upload, company-wide
non-disclosing duplicate conflicts, canonical legal-document locks, transactional
original retention, and preflight legacy schema locks. Payment invoices never
admit physical stock, including through direct standalone requests. Standalone
originals must match the authoritative target project/main warehouse.

Still requiring historical review: incomplete immutable legal-party provenance,
incomplete/partially authorized batches, and unavailable managed receipt proofs.
No invented legal identities or invoice totals are introduced. Real PostgreSQL
execution remains unavailable. An opt-in isolated PostgreSQL suite is prepared;
it exercises actual resolver/transaction code with explicitly labeled SQL stock,
history and accounting-proof stand-ins, not the full production accounting writer.

The Python package tests are mock/unit/structural checks, not database proof.
An official PyPI pgserver helper was installed only in the task workspace for a
disposable synthetic cluster. Startup was blocked by sandbox Unix socket EPERM;
the approved escalation also failed in the environment runtime. No database was
running afterward. Production data or server settings were not used or changed.

Latest verified checks (2026-10-18):
- Receipt package: 181 collected, 150 passed, 31 opt-in PostgreSQL skipped.
- New isolated PostgreSQL suite alone: 36 collected, 5 safety-gate tests passed,
  31 PostgreSQL cases skipped. No PostgreSQL connection attempted.
- Document-access focused suite: 9 collected, 2 passed, 7 PostgreSQL skipped.
- Full frontend: 309 suites / 1,956 tests passed.
- Production build compiled successfully; focused eslint, compileall and
  git diff --check passed.

Migration 0101_receipt_originals is prepared, NOT APPLIED. It stores an ordered,
nullable, immutable JSON list on each delivery, including zero-quantity claims;
NULL remains legacy unknown. Saved source/company/project/waybill identity is
also immutable. Claims and accepted-receipt views link every original using
existing authorization. Missing migration blocks new batch acceptance with 503
before posting. Legacy read projections tolerate its absence. Downgrade preserves
stored evidence and safeguards rather than deleting receipt history.

Payment-invoice discovery selects existing authorized shipment batches. It does
not invent a shipment where none exists: register the real dispatch through the
existing supply flow, or use explicitly confirmed standalone physical-document
receipt where permitted. Missing historical provenance remains a review case.

Deployment remains gated on disposable PostgreSQL integration tests and a review
of the narrow role change. Production readiness is not established until the database checks pass and the migration/role changes are approved for deployment.
