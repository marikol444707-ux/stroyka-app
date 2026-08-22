# Spec: Preview-only assignment and daily-work drafts (A10)

## Status

Approved by the human on 2026-08-21 with the recommended safe defaults:
director/deputy only, no money in the first version and exactly one selected
project per preview. A10.1 through A10.4 are complete locally. The HTTP route
is disabled unless both its exact feature flag and company allowlist are set.
UI, database changes, commit, push, deployment and production enablement remain
separate approvals.

## Objective

Give an authorized leader a deterministic preview of two operational drafts
for one exact company and project:

1. an assignment draft listing confirmed estimate work that still needs a
   human-selected assignee;
2. a daily-work-report draft built only from confirmed work-journal facts for
   one selected date.

The first release is preview-only. It does not create or update contracts,
assignments, work-journal rows, acts, payments, stock records or agent jobs.

## Proposed user flow

1. A director selects one company, one project and a date.
2. The system reads one consistent, read-only snapshot.
3. The system displays:
   - work still available for assignment, grouped by work package;
   - confirmed work completed on the selected date;
   - fixed warnings when exact source lineage is missing or ambiguous.
4. The user may print or copy the preview.
5. Applying assignments or saving a report remains a separate, explicit,
   human-confirmed future task.

## Confirmed source policy

### Assignment draft

- Use only the exact active estimate owned by the selected company/project.
- Use stored estimate-item lineage; never match rows by names alone.
- Subtract only existing non-cancelled assignment/contract quantities with
  compatible stored lineage.
- Include only positive remaining quantities.
- Leave the assignee empty. The preview must not guess a person or brigade.
- Missing, duplicate or incompatible lineage produces a fixed review warning,
  not a guessed assignment.

### Daily-work-report draft

- Use only `work_journal` rows owned by the selected company/project.
- Include only rows with status `Подтверждено` for the exact selected
  date.
- Preserve exact work description, unit and confirmed quantity.
- Money, materials and photo references may be shown only when already present
  on those confirmed rows and allowed by the existing role policy.
- Draft generation never changes journal status and never creates an act.

## Public result shape

The result is detached data, not HTML and not a database row:

```python
{
    "version": 1,
    "state": "ready",  # ready | clear | review_required
    "companyId": 1,
    "projectId": 10,
    "date": "2026-08-21",
    "assignmentDraft": {
        "items": [],
        "review": [],
    },
    "dailyWorkDraft": {
        "items": [],
        "summary": {},
    },
}
```

No raw SQL, database errors, tokens, internal job payloads or unrestricted
source JSON may appear in this result.

## HTTP preview boundary (A10.4)

- Route: `POST /assignment-daily-draft-previews`.
- Registration is default-off. It requires
  `ASSIGNMENT_DAILY_DRAFT_HTTP_ENABLED=true` and a strict positive-integer
  `ASSIGNMENT_DAILY_DRAFT_COMPANY_IDS` allowlist.
- Authentication is cookie-session only; an `Authorization` header is not a
  fallback. A valid session-bound `X-CSRF-Token` is mandatory.
- `X-Company-Mode` must be exactly `company`; `X-Company-Id` is the sole
  company routing hint and is re-authorized against the session in PostgreSQL.
- The JSON body contains exactly `projectId`, `date`, `estimateId`,
  `estimateVersionId` and `workPackage`, with a 4096-byte transport ceiling.
- Only active `директор` and `зам_директора` memberships with passed 2FA may
  read the preview. The session, role, exact project and all draft facts are
  checked in one `REPEATABLE READ READ ONLY` transaction.
- The response is `no-store`, contains only the reviewed camelCase allowlist
  and always states `previewOnly=true`, `applyAllowed=false`,
  `writesAttempted=0`, `readOnlyTransaction=true` and `rolledBack=true`.
- There is no apply, save, approve, assignment-create or journal-create route.

## Tech stack and project structure

- Python/FastAPI/PostgreSQL backend under `backend/features/`.
- Existing exact-lineage services under `backend/features/brigade_lineage/`.
- Existing assignment write routes under
  `backend/features/work_assignment/` remain unchanged.
- Existing work-journal ownership rules under
  `backend/features/work_journal/` remain canonical.
- Existing document builders under `src/utils/printDocumentBuilders.js` may be
  reused only after the server preview contract is complete.
- New implementation should live in one private feature package with colocated
  unit tests; UI and route registration are later vertical slices.

## Commands

Focused backend tests:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a10-pycache \
python3 -m unittest backend.features.assignment_daily_drafts.test_projection
```

Full backend regression:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/a10-pycache \
python3 -m unittest discover -s backend -p 'test_*.py'
```

Frontend verification when a UI slice is separately approved:

```bash
npm test -- --runInBand
npm run build
```

## Testing strategy

- Start with pure projection tests and no database access.
- Add fake-cursor ownership, cardinality and lineage tests before SQL.
- Prove exact company/project isolation and read-only rollback in disposable
  PostgreSQL before any route registration.
- Cover empty, ready, ambiguous, duplicate-lineage, cancelled-assignment and
  confirmed/unconfirmed journal cases.
- Assert source inputs are not mutated and output contains only allowlisted
  fields.

## Boundaries

### Always

- Resolve one exact company and project on the server.
- Use stored lineage and current ownership checks.
- Stay deterministic, bounded and read-only.
- Keep preview generation separate from apply/save actions.
- Run focused and full regressions before each checkpoint.

### Ask first

- Adding an HTTP route or UI.
- Choosing which roles may see money, materials or photos.
- Adding a database table, migration, feature flag or dependency.
- Adding any apply/save/approve operation.
- Committing, pushing, deploying or enabling production access.

### Never in A10

- Guess an assignee, estimate row or project from text similarity.
- Create assignments, journal rows, acts, payments or stock movements.
- Call a model/provider or send a notification.
- Read across companies or use an aggregate-company context.
- Manufacture production data to obtain a positive preview.

## Success criteria

- The same confirmed snapshot always produces the same canonical result.
- No unconfirmed journal row appears in the daily report.
- No already fully assigned estimate quantity appears as available.
- Missing exact lineage fails closed with a fixed review warning.
- Every path performs zero business writes and closes/rolls back its read
  transaction.
- Existing assignment and work-journal APIs remain byte-for-byte compatible.

## Proposed implementation slices

1. **A10.1:** Pure immutable input/result contracts and daily-work projection.
2. **A10.2:** Pure assignment-availability projection using exact lineage.
3. **A10.3:** One bounded, tenant/project-scoped read-only snapshot composer.
4. **A10.4:** Default-off HTTP preview adapter with role and CSRF checks.
5. **A10.5:** Review-only UI and printable document; no apply button.
   Completed locally behind the default-off frontend flag
   `REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED`; the panel is available
   only to director/deputy roles in the strict
   `REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS` allowlist and validates
   the exact preview-only response before rendering or printing.
6. **A10.6:** Full regression, disposable-PostgreSQL proof and canary plan.
   Completed locally; the still-unapproved production sequence is documented in
   `docs/assignment-daily-draft-preview-canary.md`.

## Open questions for human approval

1. Should the first version be visible only to `Директор`, or also to
   `Заместитель` and `Прораб` for their assigned projects?
2. Should the daily draft initially include money, or only work, quantity,
   unit, responsible person and confirmation status?
3. Is one selected project per preview the correct first scope?

Recommended safe defaults: director and deputy only, no money in the first
version, and exactly one selected project per preview.

## A10.4 verification evidence

The first focused run failed honestly with `ModuleNotFoundError` for the absent
runtime modules. The completed adapter authenticates before parsing business
coordinates, rejects Bearer fallback, duplicate JSON keys, oversized bodies,
aggregate-company mode and non-allowlisted companies, and serializes only exact
A10 dataclasses whose nested scopes match the selected request. Unknown review
codes or foreign nested scopes fail closed without exposing source content.

The same private transaction performs one bounded authorization SELECT and the
three approved A10.3 business SELECTs after transaction settings, then always
attempts rollback, cursor close and connection close. Directors and deputies
are accepted; absent, duplicate, foreign-project and other-role actors stop
before business reads. Focused A10 tests pass `35/35`; the full backend passes
`2203/2203` with 56 expected opt-in PostgreSQL skips. Compilation, exact A9
closed-surface hash updates and `git diff --check` pass. The A10.3 disposable
PostgreSQL proof remains valid; a route/auth PostgreSQL proof and canary plan
remain A10.6 work.

No UI, nginx rule, schema/migration, dependency, model, queue, apply action,
commit, push, deployment or production enablement was added. SHA-256:
`runtime_preview.py`
`f4ed01a35152acb9a343454842d54464eeb8db28a8b5e9df68a502bec1d22c0c`,
`runtime_routes.py`
`9fb7080b294268dd9de80a09f80c4696a7bb8e25a34b65f28f33a5c47709b535`,
route/runtime tests
`07d619d0992e93185ecc77025637defa9bc2330dd459c64b14cddf0c0ba0b907`
and `backend/main.py`
`b6000a63ba05cb2414a6a9b56e3f3c34414b9038ff500b43fe3bdfe276f13a7e`.

## A10.6 local release evidence

The reusable launcher-owned PostgreSQL 15 fixture now crosses the real FastAPI
route, real director authorization SQL and all three A10 snapshot reads in one
request. The successful case executes five SELECT statements, zero commits,
one rollback and leaves every fixture table byte-equivalent. A real `прораб`
membership returns the opaque not-found result after settings plus authorization
only, before every business read. The disposable suite passes `37/37` and
destroys its private Unix-socket cluster after the run.

Two release-review findings were fixed through observed RED tests. First, the
frontend boolean flag was global; a strict duplicate-free
`REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS` parser now keeps the
panel absent outside the canary company. Second, the global 5xx middleware could
write an API-error row for an A10 read failure; the exact preview path now shares
the reviewed zero-write exclusion while its neighboring path still logs. A
separate nginx contract adds a 4 KiB request limit, per-IP `6r/m` rate limit,
one global in-flight request, bounded proxy timeouts and JSON/no-store `413`/
`429` responses without selectors in URLs or logs.

Final verification passes focused A10 `37/37`, combined A10/A9 closed-surface
`93/93`, full backend `2205/2205` with 56 expected opt-in PostgreSQL skips,
focused frontend/API `22/22`, full frontend `375/375` in `86/86` suites and the
optimized production build. `py_compile`, static no-secret/no-debug scans and
`git diff --check` pass. Offline full and production-only `npm audit` both
report zero vulnerabilities; the environment blocked the online registry audit,
so a fresh online audit remains an explicit pre-deploy gate. Local nginx is not
installed, so `nginx -t` remains a production/staging prerequisite.

The rollout, observation thresholds and rollback are recorded in
`docs/assignment-daily-draft-preview-canary.md`. Both backend/frontend flags
remain absent, no nginx fragment was installed and no production system,
database, dependency, commit, push or deploy was changed. SHA-256: `main.py`
`258d1821804a6c68c8af8f5abb6cc8f62df3bd20e4c6eff9354e29832bbebfbb`,
route/runtime tests
`d06c43cdb43e52af180d78cc9a1ab79124b86f132a4fdd08466ddde149d542ed`,
PostgreSQL proof
`b741efc599b84f364c3b181e6fda68323a8d5de574bb0d8ec2481e454daed98a`,
UI panel
`9637522da2ef497fc7d9fab3885f2390de92d59e6be34dece1ac56d97435a88e`
and nginx fragment
`9d9fda6c071a2af5e3fdc35657904c0d30e15e4ca99bb0130eb1aa386efc0bfd`.
