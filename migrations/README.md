# Database Migrations

The current production schema is still bootstrapped by `init_db()` in `backend/main.py`.

Alembic was introduced with a safe metadata baseline, then small schema slices
are moved in one at a time:

- `0001_baseline_inline_init_db` does not change tables.
- `0002_ops_error_logging` creates the operational `api_errors` table and index
  idempotently. The same `CREATE TABLE IF NOT EXISTS` remains in `init_db()` as
  a temporary compatibility guard until deploy runs `alembic upgrade head`.
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
