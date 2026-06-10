# Stroyka ERP Copilot Instructions

## Project Context

This repository is the production codebase for Stroyka ERP, a construction management system.
The app manages projects, estimates, materials, supply, warehouse, work journals, hidden works acts, contracts, finance, role cabinets, and AI control tasks.

Primary stack:
- Backend: FastAPI in `backend/main.py`
- Frontend: React in `src/App.js`
- Production deploy script: `deploy.sh`
- Production smoke test: `scripts/prod-smoke-check.sh`
- Estimate parser check: `scripts/check-smeta-parser.py`

## Production Safety Rules

- Production deploys must use `main` only.
- Never deploy from temporary branches such as `claude/*`, `codex/*`, experiment branches, or detached HEAD.
- Before any production deploy, verify:
  - `git branch --show-current`
  - `git rev-parse --short HEAD`
  - `git log -1 --oneline`
- After deploy, run the smoke check.
- Do not delete, archive, reset, or bulk-update production data unless the user explicitly asks for that exact action and a fresh backup exists.
- Never auto-archive or auto-delete projects, estimates, staff, users, warehouse data, materials, work journals, or finance records.
- A project may be archived or closed only by an explicit director action in the product flow.
- Do not commit `.env`, passwords, API keys, tokens, database dumps, or private credentials.

## Required Checks

For backend changes:

```bash
PYTHONPYCACHEPREFIX=/tmp/stroyka-pycache python3 -m py_compile backend/main.py
```

For frontend changes:

```bash
npm run build
```

For estimate import/parser changes:

```bash
npm run check:smeta
```

For production verification after deploy:

```bash
bash scripts/prod-smoke-check.sh
```

If credentials are available for a protected smoke test:

```bash
SMOKE_EMAIL='admin@stroyka.ru' SMOKE_PASSWORD='<password>' npm run smoke:prod
```

## Estimate Import Rules

The estimate import is a core business flow. Be conservative.

- Excel units must be preserved from the source estimate.
- Do not guess all imported units in the frontend.
- `100 м2 x 72.1` must become `7210 м2` in the working document.
- `100 м`, `100 шт`, `1000 шт`, `т`, `кг`, `м2`, `м3`, and similar estimate units must be parsed according to the source unit and quantity coefficient.
- Row totals must come from the source estimate where available.
- Do not apply one global coefficient to the whole estimate total. This breaks subcontractor/master payment logic.
- Work payment must remain per work row and per completed volume.
- Work/material classification should come from estimate structure, resource rows, codes, and parser rules, not from manual user dropdowns as the main workflow.
- Materials created from norms or resources must keep sane quantities and units because supply, warehouse, write-off, and accounting depend on them.
- Every estimate parser change must run `npm run check:smeta`.

## Data Chain Rules

Keep these chains consistent:

- Estimate -> working document -> work journal -> progress -> KS-2/KS-3 -> accounting.
- Estimate resources/norms -> material requirement -> supply request -> invoice -> warehouse/project stock -> issue/write-off -> accounting.
- Project rooms/openings -> work volumes -> estimate mismatch control -> AI control tasks.
- Subcontractor/master contract -> assigned works -> act -> payment reserve -> accounting folder.

Do not fix one screen by breaking another chain.

## Role Rules

Keep role access conservative:

- Director: full control, system status, AI control, finance, staff, contracts, estimates.
- Deputy director: operational control, projects, estimates, supply, materials, staff visibility as needed.
- Foreman: project execution, work journals, materials on assigned objects, acts, instructions.
- Master: assigned object/work execution, work journal, material needs/write-off by allowed flow.
- Accountant: contracts, acts, payments, expenses, documents, counterparties.
- Procurement: suppliers, supply requests, offers, deliveries, invoices, material status.
- Client/technical supervision: customer-facing documents and approvals without internal cost exposure unless explicitly enabled.

## Refactoring Rules

- Prefer small, reversible extractions from `src/App.js` and `backend/main.py`.
- Keep behavior identical during refactoring unless the task explicitly changes behavior.
- Do not touch unrelated untracked folders such as `outputs/` and `tmp/`.
- Do not reformat huge files unless required for the specific change.
- Preserve existing Russian UI labels unless the requested change says otherwise.

## Git Rules

- Keep commits focused and descriptive.
- Before committing, review `git diff --check`.
- Do not include generated caches, dumps, secrets, or unrelated files.
- If the server branch is not `main`, fix that before deploy.
