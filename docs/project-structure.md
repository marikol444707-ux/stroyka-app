# Project Structure

This document describes the current repository shape and the target structure to move toward without destabilizing production.

## Current Shape

```text
stroyka-app/
  backend/
    main.py                 # FastAPI app, inline DB bootstrap, models, routes, services
    .env.example            # backend runtime configuration template
    uploads/                # runtime upload files; should move to external storage/S3 for production
  src/
    App.js                  # main React shell and still a large part of app orchestration
    api.js                  # browser API base URL and auth-aware fetch wrapper
    components/             # feature and UI components
    components/materials/   # materials-specific parts
    components/supply/      # supply-specific parts
    components/warehouse/   # warehouse-specific parts
    constants/              # roles, catalogs, theme, estimate constants
    hooks/                  # React hooks
    pages/                  # top-level auth/pages
    services/               # frontend service helpers
    utils/                  # frontend business/helper utilities
  scripts/                  # smoke checks, data guards, test helpers
  docs/                     # product, launch, role, and technical notes
  public/                   # CRA static assets and public site files
  requirements.txt          # pinned Python backend/check dependencies
  README_LOCAL_RUN.md       # local launch guide
  ONBOARDING.md             # current product and workflow rules
```

## Structure Rules

- Keep user-facing product rules in `ONBOARDING.md`.
- Keep setup/run instructions in `README_LOCAL_RUN.md`.
- Keep technical architecture and refactor sequence in `docs/project-structure.md`.
- Do not create new parallel product screens when an existing module can be extended.
- Do not split `backend/main.py` by moving unrelated routes at the same time as behavior changes.
- Every backend extraction must keep `uvicorn backend.main:app` working.
- Every extraction step must pass:

```bash
PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py
npm run build
```

## Target Backend Layout

Move toward this layout gradually:

```text
backend/
  __init__.py
  main.py                   # app creation, middleware, static mounts, router registration only
  config.py                 # env loading, constants, runtime settings
  db.py                     # DB_CONFIG, get_db, common SQL helpers
  auth.py                   # token, password, current user, role/package access checks
  audit.py                  # audit_log helpers and audit endpoints
  models.py                 # Pydantic request/response models shared across routers
  routers/
    projects.py
    estimates.py
    materials.py
    warehouse.py
    supply.py
    work_journal.py
    documents.py
    accounting.py
    staff.py
    crm.py
    public_site.py
    ai.py
    integrations.py
  services/
    estimate_totals.py
    material_matching.py
    invoice_normalization.py
    access_policy.py
    notifications.py
  migrations/
    env.py                  # Alembic runtime, builds DB URL from backend/db.py
    versions/               # Alembic revisions
    README.md               # migration safety rules while init_db still owns most schema
```

## Safe Extraction Order

1. `config.py` - done
   `.env` loading and runtime constants live in `backend/config.py`.

2. `db.py` - done
   `DB_CONFIG`, `get_db`, and `limit_offset_sql` live in `backend/db.py`. Keep `init_db()` in `main.py` until migrations are introduced.

3. `auth.py`
   Move auth/token helpers and role/package access checks only after `config.py` and `db.py` are stable.

4. Route groups with low cross-coupling
   Start with `audit-log`, system status, and static/simple reference endpoints.

5. Route groups with core business coupling
   Move estimates, materials, warehouse, supply, work journal, documents, and accounting one domain at a time.

6. Migrations - baseline done
   Alembic has a metadata-only baseline. Convert `init_db()` in small slices instead of replacing it all at once.

## Target Frontend Layout

The frontend is already partially split. Continue moving toward feature folders while leaving shared utilities in `src/utils` and shared constants in `src/constants`.

```text
src/
  app/                      # app shell, route/page orchestration
  api/                      # API clients and auth fetch wrapper
  features/
    projects/
    estimates/
    materials/
    warehouse/
    supply/
    work-journal/
    documents/
    accounting/
    staff/
    crm/
    public-site/
    ai/
  components/common/        # generic UI-only pieces
  constants/
  hooks/
  utils/
```

## Frontend Extraction Rules

- Move one visible workflow at a time.
- Keep existing prop names until the target feature is stable.
- Do not move styling and behavior separately unless the diff is purely mechanical.
- For mobile-heavy modules, verify responsive behavior before marking the move complete.

## Generated And Local Artifacts

The following should stay out of Git unless explicitly promoted to product docs or fixtures:

- `.venv/`, `venv/`
- `/tmp/`
- `/outputs/`
- local `.env` files
- Python caches and test caches

## Next Technical Steps

1. Add a minimal CI workflow for backend compile and frontend build after GitHub token has `workflow` scope.
2. Add Docker Compose for local PostgreSQL + backend - done.
3. Move one low-risk `init_db()` table/column group into a real Alembic migration.
