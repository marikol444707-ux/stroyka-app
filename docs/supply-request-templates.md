# Company supply request templates

Scope: reusable material request sets, selected-company isolation and safe retries.
Supplier invoices/payments and actual request approval/stock operations are excluded.

## Contract

- `GET /supply-request-templates` preserves the active-template array response;
  all-company mode returns `[]`. Owned rows only, never infer legacy ownership.
- `GET /supply-request-templates/catalog` returns `{items, truncated, canCreate,
  canArchive}` for one selected company. Active rows only, maximum 1000.
- Internal supply roles (director, deputy, chief engineer, supply, storekeeper,
  foreman, master, subcontractor, brigadier, accountant) may read. Accountant
  cannot create. Supplier role has no access to internal reusable sets.
- `POST /supply-request-templates`: `{name, category?, items, requestId,
  expectedCompanyId, expectedActorId, materialAccountingVersion?}`. Name 1–255,
  category 0–100; 1–200 items, each `{materialName, quantity, unit, workPackage?}`.
  Material 1–500, unit 1–40, section 0–255; positive finite quantity below
  100000000, at most 6 decimals. Invalid rows reject the whole command.
  Unknown fields (including client author/owner) rejected. Server records actor.
- Names normalize whitespace and casefold for active uniqueness per company.
- `POST /supply-request-templates/{id}/archive`: `{requestId, expectedCompanyId,
  expectedActorId, expectedVersion, materialAccountingVersion?}`; directors only.
  Version checked, physical record retained. Returns `{ok:true,id,eventId}`.
- Existing DELETE is permanently closed with 409; auth still required.
- Writes require real active company membership and actor locks, company advisory
  serialization, atomic audit and existing operation ledger. Same UUID/content
  returns original result, changed content rejects; permissions rechecked on replay.
- Migration 0032 adds nullable company ownership, normalized name, archive/version,
  audit events. Legacy columns/data remain untouched; no inferred backfill. Owned
  owner/content immutable; archive increments version. Audit immutable. Downgrade
  refuses to discard ownership/history.

## Interface

Company-scoped template controls live in the existing request form, fetch their
own catalogue and expose load errors/retry. Changing company/user remounts private
template state. Saving validates every request row, does not create a request,
send notifications or change stock. Show a named save form and director archive
confirmation. Shared persistent command recovery preserves exact UUID/payload.
Template application copies rows, retains current object/notes/urgency, maps only
valid sections for that object (sole section default, otherwise empty). Changing
the request object similarly clears sections absent from its estimate. Form
remains usable at 320px width. Existing requests retain their independent copies.

## Verification / release

Reproduce cross-company visibility first in disposable PostgreSQL. Cover actual
authenticated ownership, roles, strict input, author spoofing, idempotency,
concurrent replay/archive, disabled writes and unchanged business tables.
Check UI errors, scope changes, pending/retry and section application; browser
exercise create/apply/archive and lost response. Build and full regression gates.
Rehearse migration on private production backup and compare all existing columns.
Release with pinned production base eeb98bf3948108de684b46ff33b1df9188220806 and
schema 0031. Rollback must quarantine old global template endpoints before starting
old runtime. Legacy warehouse ID 1 and template ID 1 ownership remain pending
explicit user confirmation; do not interpret continuation as that confirmation.

## Verification evidence, 2026-09-19

- Reproduced both legacy leaks through authenticated PostgreSQL HTTP: company 2
  received company 3's template and an unowned historical template. Both now pass.
- Real PostgreSQL: 19/19, including concurrent replay/archive, revoked membership,
  strict quantities/fields, category 100/101, immutable audit and atomic rollback.
  Every case verifies that requests, inventory and financial tables stay unchanged.
- Backend: canonical `python -m unittest discover -s backend -t .` passed 3745
  tests (623 opt-in cases skipped; the 19 new PG cases run separately). Use the
  repository as top-level import root; omitting `-t .` loads duplicate package
  identities and breaks two unrelated mocked model-gateway cases.
- Frontend: 173 suites / 1083 tests passed, including exact lost-response recovery,
  company/user draft reset and real master-route section wiring. Production build
  passed. Independent backend/frontend reviews have no outstanding blockers.
- Browser with synthetic records: create, drop the committed response, replay the
  identical request twice, apply, archive; one original card/event per command.
  Master applies the active company template with the current object's section;
  archive controls are absent. Director and master checked at 320px, no horizontal
  overflow. No material request was submitted; project stock remained 2 units.
- Fixture-only console responses: unprepared supplier directory 503, own-expenses
  scope 409, intentional aborted POST; no template JavaScript/runtime errors.
- Real database copy: migration 0031→0032 preserves all original columns and rows
  in 171 tables, leaves the historical template unowned and audit empty.
- Private logs/scripts: `/Users/nikolas/.codex/tmp/supply-templates/`. Screenshots:
  `output/playwright/supply-templates-{mobile,master,mobile-items}.png`.
