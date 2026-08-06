# ADR-0001: Canonical source lineage for brigade assignments

## Status

Accepted. E3.1 established the production baseline. E3.2 added only the
nullable storage contract and an explicit legacy classification. E3.3.1 added
the inert exact snapshot resolver. E3.3.2 cuts all local runtime writers over
to explicit, exact lineage. Production runtime `6f5ab8a4430a` passed writer
verification; E3.4 strict constraints remain pending.

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

## Second delivery slice

`npm run migrate:brigade-lineage` is an explicit guarded migration. It is not
called by `init_db()` or `deploy.sh` and defaults to a read-only dry-run. Apply
requires the exact ready-row count and plan SHA-256 emitted by that dry-run.

E3.2 adds these nullable columns without FK, CHECK, index or NOT NULL
enforcement:

- `brigade_contract_items.source_type VARCHAR(20)`;
- `source_estimate_version_id INT`, `source_section_index INT` and
  `source_item_index INT`;
- `source_item_key VARCHAR(255)`;
- `estimate_versions.sections_sha256 VARCHAR(64)`.

The apply is split into two short, idempotent transactions so it never holds
exclusive locks on both live tables at once. The snapshot column is added and
verified first. A fresh transaction then locks `brigade_contract_items`,
recomputes the complete plan, validates count and hash, adds the assignment
columns and updates only the exact audited IDs whose five lineage values are
still NULL. Any partial coordinate, incompatible existing column definition,
plan drift, row-count conflict or failed post-check blocks that phase.
Catalog checks and every operational statement target the `public` schema
explicitly and do not depend on the connection `search_path`.

Existing rows are classified only as `legacy`; no estimate version or row
coordinate is inferred. `sections_sha256` is not backfilled in E3.2. A
temporary database default of `source_type='legacy'` protects inserts from the
unchanged writers until E3.3 writes every source explicitly. The default must
be removed before E3.4 strict enforcement. If the first additive phase commits
and the guarded assignment phase fails, the intermediate schema is
fail-closed and the same command is safe to retry after a new dry-run.

## Third delivery slice

E3.3.1 adds no route or background-task integration. It centralizes
`canonical-json-v1` and introduces a transaction-neutral batch resolver for the
next writer cutover. The resolver:

- requires a server-resolved positive estimate, company and project ID;
- rejects malformed or duplicate coordinate batches before taking a database
  lock;
- locks the exact owned estimate once and parses/hashes its complete current
  sections once;
- accepts only zero-based integer coordinates plus the exact canonical item
  key defined above;
- creates or reuses one content-verified snapshot for the complete batch;
- fails closed on duplicate hash claims, corrupt stored snapshot content or a
  changed owner; and
- leaves commit and rollback to the surrounding assignment transaction.

The API intentionally accepts server-constructed coordinate records rather
than client dictionaries. Future routes must copy only the three allowlisted
coordinate fields into those records after their normal authentication and
tenant-context checks. No existing writer imports the resolver in E3.3.1.

## Fourth delivery slice

E3.3.2 connects both estimate-derived assignment routes to the shared
tenant-bound snapshot resolver. `/work-assignment` and `/distribute` accept
only exact section/item coordinates plus the canonical item key, lock existing
assignments once per contract/version, and reuse an exact full-lineage match.
They never identify a row by name, section label, unit, generic ID or code, and
they never update an already issued quantity or brigade price.

Generic brigade item POST creates only explicit `manual` rows and rejects
client-owned source fields. Generic PUT cannot mutate source fields and changes
only editable plan fields while preserving/clamping server-stored progress.
Pricelist autoload
creates explicit `pricelist` rows with no estimate coordinate and participates
in the surrounding contract transaction. Estimate saves no longer rewrite
assignment state; confirmed ЖПР may update only `done_quantity` through the
exact stored contract-item ID.

The frontend distribute payload now carries the three exact coordinate fields,
and the obsolete generic estimate-loader is removed. A bounded static audit is
part of `npm run audit:brigade-lineage`: it allowlists every INSERT/UPDATE site,
requires explicit source classification, and rejects source mutation,
descriptive assignment lookup and unsafe quantity synchronization. Runtime
writer readiness is reported separately from data and constraint readiness.

Production verification on 2026-08-06 ran the complete report read-only and
rolled it back. It found the complete additive schema, `151` explicit legacy
rows, zero invalid or unclassified rows, exactly three allowlisted INSERT
statements and three allowlisted UPDATE statements, and no writer violation.
The public deployment smoke passed on runtime `6f5ab8a4430a`. The expected
post-E3.3 boundary remains `lineageDataReady=false` and
`constraintAuditIncluded=false` until E3.4 is designed and enforced.

## Fifth delivery slice

E3.4.1 is diagnostic only. It extends the same read-only repeatable-read report
with structural catalog facts and bounded aggregate data checks before any DDL
is authored or executed. The audit distinguishes an object with the expected
name from an object with the expected type, validated definition and enabled
trigger function.

The enforcement contract to preflight is:

- restrictive foreign keys from a contract item to its contract and optional
  source estimate version, and from an estimate version to its estimate;
- CHECK rules for the four allowlisted source types, their conditional lineage
  shape and canonical snapshot-hash format;
- `source_type` NOT NULL with no default after the temporary E3.2 legacy
  compatibility period;
- valid partial indexes for exact estimate-lineage uniqueness, version delete
  lookup and one canonical snapshot per estimate/hash;
- enabled database guards that prevent assignment source mutation, reject a
  cross-owner estimate snapshot and make snapshot owner/content/hash immutable;
  and
- an estimate deletion blocker that follows the stored
  `source_estimate_version_id -> estimate_versions.estimate_id` relationship,
  retaining compatibility-key matching only for explicit legacy rows.

Explicit legacy rows are permitted by the future shape constraint and remain
review-only evidence. Therefore `lineageDataReady=false` may coexist with a
clean E3.4 data preflight; `readyForStrictRuntime` still requires the writer,
catalog, aggregate-data and deletion-policy gates together. E3.4.1 reports the
missing gates and performs no repair. E3.4.2 remains a separately reviewed,
guarded and rollback-friendly enforcement release.

## Writer changes completed in production before enforcement

- `POST /estimates/{id}/work-assignment` and `/distribute` now persist the exact
  revision coordinate and make exact repeats idempotent without destructive
  overwrite.
- Generic brigade item POST/PUT cannot accept or mutate server-owned lineage;
  manual and pricelist origins are explicit.
- Estimate synchronization does not rewrite issued quantity or brigade price.
  ЖПР progress is derived from confirmed work by exact contract-item ID.
- E3.4 still must enforce estimate deletion restrictions through the stored
  revision relationship, including rows whose source key is not generated
  from an estimate ID.

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
- Current row origin is not guessed; E3.2 writes only the explicit `legacy`
  classification to the exact guarded ID set.
- Strict constraints remain a separate, rollback-friendly E3.4 release after
  production writer verification.
- E4 revision transfer can later operate on confirmed immutable source rows
  instead of fuzzy names.
