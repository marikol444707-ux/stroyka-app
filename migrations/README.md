# Database Migrations

The current production schema is still bootstrapped by `init_db()` in `backend/main.py`.

Alembic is introduced here as a safe baseline only:

- `0001_baseline_inline_init_db` does not change tables.
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
