# Database Migrations

The current production schema is still bootstrapped by `init_db()` in `backend/main.py`.

Alembic was introduced with a safe metadata baseline, then small schema slices
are moved in one at a time:

- `0001_baseline_inline_init_db` does not change tables.
- `0002_ops_error_logging` creates the operational `api_errors` table and index
  idempotently. The same `CREATE TABLE IF NOT EXISTS` remains in `init_db()` as
  a temporary compatibility guard until deploy runs `alembic upgrade head`.
- `0003_accounting_link_integrity` idempotently records the two validated,
  nullable supplier/warehouse invoice foreign keys. Deleting either target
  clears only the stale link; business rows, amounts, statuses and stock remain.
- `0004_active_estimate_snapshots` installs the canonical estimate-
  snapshot hash guard and creates one immutable initial version only for active
  customer estimates that have no saved versions. Existing histories are not
  changed. Its downgrade intentionally preserves business snapshots because
  assignments may already reference them.
- `0005_platform_client_contracts` adds a separate licensor profile, immutable
  client-contract snapshots and optional links from existing billing documents
  and payments. Composite foreign keys prevent cross-company contract links;
  existing rows remain unchanged. Downgrade is allowed only while both new
  business tables are empty.
- `0006_user_company_staff_links` adds an optional, company-scoped link from a
  user membership to its staff record. Existing memberships remain unchanged;
  new and edited staff access records receive the explicit link automatically.
- Existing databases should only be stamped after the backend has already bootstrapped the schema.
- Future migrations should move small, well-understood slices out of `init_db()` one at a time.

## Local Commands

Show migration history:

```bash
alembic history
```

After a local database has been initialized by starting the backend once, mark it as matching the baseline:

```bash
alembic stamp head
```

Create a new revision:

```bash
alembic revision -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

## Safety Rules

- Do not delete or disable `init_db()` until its table/column ownership has been migrated and tested.
- Do not combine behavior changes with schema migration extraction.
- Every production migration must be reviewed with its rollback strategy.
- Keep migrations idempotent where possible when converting old inline `ALTER TABLE ... IF NOT EXISTS` logic.
