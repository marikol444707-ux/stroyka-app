# Local Run

This project has a Create React App frontend and a FastAPI backend backed by PostgreSQL.

For the repository map and safe refactor sequence, see [docs/project-structure.md](docs/project-structure.md).

## Prerequisites

- Node.js and npm
- Python 3.11+
- PostgreSQL 14+

## Backend

Create and activate a Python virtual environment from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create backend configuration:

```bash
cp backend/.env.example backend/.env
```

Fill `backend/.env` with local values. At minimum, configure:

```bash
DB_NAME=stroyka
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
```

Create the PostgreSQL database and user to match `backend/.env`. The backend calls `init_db()` on startup and creates/updates the application tables with inline `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE` statements. This is enough for local bootstrap, but it is not a replacement for versioned migrations.

Start the backend on port `8001`; the frontend uses this port on localhost:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
```

## Backend With Docker Compose

For a local PostgreSQL + backend stack:

```bash
docker compose -f docker-compose.local.yml up backend
```

This starts PostgreSQL on `localhost:5432` and the backend on `localhost:8001` with local development credentials from the compose file. Use manual setup when you need to connect to an existing database or test production-like secrets.

## Migrations

Alembic is configured, but the current schema is still bootstrapped by `init_db()` in `backend/main.py`.

For a new local database:

1. Start the backend once so `init_db()` creates the current tables.
2. Mark the database as matching the Alembic baseline:

```bash
alembic stamp head
```

Useful read-only command:

```bash
alembic history
```

Do not replace `init_db()` with Alembic in one step. Move small schema changes into migrations gradually.

## Frontend

Install frontend dependencies:

```bash
npm install
```

Start the development frontend:

```bash
npm start
```

Build production frontend assets:

```bash
npm run build
```

## Checks

Backend syntax check:

```bash
PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py
```

Frontend production build:

```bash
npm run build
```

Production smoke checks require a reachable API and valid credentials. Do not put the password directly in shell history:

```bash
read -s PASS
SMOKE_EMAIL='admin@stroyka.ru' SMOKE_PASSWORD="$PASS" npm run smoke:prod
```

Public-site API proxy check after nginx changes:

```bash
npm run smoke:public-api
```

This check fails if `/site/pricing`, `/site/projects`, `/site/leads`, or `/site-price-rules` are served by the React SPA fallback instead of the backend.

## Notes

- `backend/.env` is intentionally ignored by Git.
- Root `.env` is also ignored by Git.
- Python dependencies are pinned in `requirements.txt`.
- Database schema changes are currently embedded in `backend/main.py`; moving them to Alembic is the next reliability step.
