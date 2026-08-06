# ADR-0001: Canonical source lineage for brigade assignments

## Status

Proposed. The read-only data audit is implemented first; no schema or runtime
writer has been changed yet.

## Date

2026-08-06

## Context

`brigade_contract_items` currently stores a mutable `estimate_item_key` plus
descriptive fields, quantities and prices. It does not identify the immutable
estimate state from which an assignment was issued. Existing writers may match
by key or name and overwrite quantity, estimate price and a manually negotiated
brigade price.

There are also two revision mechanisms:

- a change may create a new `estimates` row;
- `PUT /estimates/{id}` saves the previous state in `estimate_versions` and
  then mutates the parent estimate in place.

The current estimate state therefore has no immutable `estimate_versions.id`
until a later update. A version label is not unique identity, and a bare
`estimate_id` points to mutable content.

## Decision

Before changing assignment writers, introduce a canonical immutable revision
snapshot that is created or resolved inside the assignment transaction.
`estimate_versions.estimate_id -> estimates` remains the authoritative owner.
The snapshot will gain a canonical `sections_sha256`; it will not duplicate
company or project ownership.

An assignment's minimal source coordinate is:

- exact lowercase `source_type`: `estimate`, `manual`, `pricelist` or `legacy`;
- `source_estimate_version_id` for estimate-derived rows;
- zero-based `source_section_index` and `source_item_index`;
- `source_item_key` as an additional row-identity check.

The item key is an exact, non-empty string and is never trimmed during
verification. A snapshot uses `estimateItemKey`, then `estimate_item_key`; if
both are present they must be equal. When neither is present, the only accepted
fallback is the generated `<estimate_id>:<section_index>:<item_index>` key.
Names, generic IDs, codes and other descriptive aliases are not lineage.

`sections_sha256` uses `canonical-json-v1`: parse `sections_json` as an array,
wrap it as `{"sections": ...}`, then serialize with UTF-8, sorted object keys,
no insignificant whitespace and no non-finite numbers before SHA-256. The hash
is calculated over the complete stored sections document, detects changed
content and does not by itself make a row immutable.

Company, project and estimate ownership are derived and checked through both
authoritative parent chains:

```text
assignment -> contract -> project/company
assignment -> estimate version -> estimate -> project/company
```

The assignment does not duplicate `source_company_id`, `source_project_id`,
`source_estimate_id` or the revision hash. Manual and pricelist rows have no
estimate coordinate. The migration must mark existing ambiguous rows with the
explicit `legacy` source type; once the complete lineage schema exists, a NULL
source type is invalid. A legacy key or name match is never treated as proof.

## First delivery slice

`npm run audit:brigade-lineage` is a read-only, rolled-back data report. It:

- checks the base and proposed column sets;
- classifies only structural lineage evidence;
- verifies contract/project ownership;
- verifies an estimate snapshot's parent, canonical hash, coordinates and key;
- requires the compatibility `estimate_item_key` to equal the authoritative
  `source_item_key` until all existing consumers are migrated;
- emits only row IDs and reason codes, never work descriptions or prices;
- reports `baseSchemaPresent` and `lineageDataReady`, not runtime readiness.

The first report deliberately sets `constraintAuditIncluded=false` and
`writerAuditIncluded=false`. FK, CHECK, index, delete-restriction,
writer-coverage and immutability enforcement must be added and audited in later
slices before strict runtime can be enabled.

## Required writer changes before enforcement

- `POST /estimates/{id}/work-assignment`: remove name fallback and destructive
  overwrite; exact repeat becomes idempotent and a new revision creates a new
  row. Preserve whether the brigade price was manually negotiated; automatic
  assignment must never overwrite it.
- `POST /estimates/{id}/distribute`: persist the exact revision coordinate and
  add idempotency.
- Generic brigade item POST/PUT: never accept or mutate server-owned lineage;
  manual and pricelist origins remain explicit.
- Estimate update synchronization: change execution progress only; never
  rewrite issued quantity or brigade price.
- ЖПР synchronization: `done_quantity` remains derived from confirmed work and
  cannot identify assignments by name.
- Estimate deletion: reject deletion through the stored revision relationship,
  including rows whose source key is not generated from an estimate ID.

## Alternatives considered

### Store only `source_estimate_id` and version label

Rejected because both values identify mutable or non-unique state.

### Duplicate company/project/estimate/hash on every assignment

Rejected because the values can disagree with authoritative parents and simple
row CHECK constraints cannot keep cross-table ownership synchronized.

### Backfill from names, sections or legacy item keys

Rejected because keys may be reused between revisions and names are not unique.
Unproven rows remain visible for human review.

## Consequences

- The next schema change stays additive and nullable.
- Current rows are not guessed or rewritten.
- Strict constraints and writer cutover require separate, rollback-friendly
  releases.
- E4 revision transfer can later operate on confirmed immutable source rows
  instead of fuzzy names.
