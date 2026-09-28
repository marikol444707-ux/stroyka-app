# Supplier finance release preflight — 2026-09-28

## Live observations (read-only)

- Production application HEAD: `780798ab`; backend service active.
- Alembic current: `0051_supplier_offer_item_scopes`.
- Root filesystem: 77 GB total, 24 GB used, 53 GB available (31%).
- Existing production smoke script passed. Protected authenticated checks were
  explicitly skipped because no test login was supplied; this is not an
  end-to-end financial workflow verification.
- Supplier payment, allocation, settlement, opening, partial/unpaid receipt,
  VAT, invoice-line specification and allocated-refund switches are unset.
  Owned delivery sources and quality switches are 1.
- Tracked server tree is clean. Untracked historical directories and files
  exist; they were not removed or treated as disposable release artefacts.
- No deployment, migrations, feature activation or business-data writes made.

## Corrected release configuration

`resolve-frontend-build-env.sh` now exports the three supplier UI switches from
the explicitly allowlisted backend settings. Defaults are explicit false.
Systemd values override the file; duplicate file settings use the first value,
matching backend.config. Secrets are never exported.

Openings require payments. Allocated refunds require payments, allocations and
settlements. Invalid values or missing dependencies stop the build. All flag
output is withheld until the complete configuration, including the existing
A10 allowlist, validates. This also fixes pre-existing partial output from the
warehouse flag resolver on A10 validation errors.

Verification: 19 tests passed across supplier/warehouse configuration and deploy
migration/build ordering. New tests first reproduced the missing supplier flags.
No frontend component or financial posting code changed in this increment.

## Remaining release gates

The earlier UI/API evidence is recorded in supplier-refund-form-2026-09-28.md.
It does not replace these remaining checks:

1. Rehearse the exact Alembic 0051 → 0059 upgrade path with preserved existing
   financial records, checking migration guards and post-upgrade old behaviour.
2. Inspect current legacy invoice/receipt readiness using a read-only report
   compatible with the production schema; do not run the newer audit against
   0051 because it expects invoice-line specification tables from 0052.
3. Verify financial report projections and the complete current invoice →
   partial receipt → allocation → refund flow in the integrated app, not only
   the isolated payment dialog. Determine the release switches as a set.
4. Deploy with a bounded rollback stage; verify backend, database, published
   frontend and authenticated browser workflow before enabling and finalizing.
   Follow deployment-retention.md; do not create multiple full repository copies.

Current status: release preparation advanced; production activation not ready.
