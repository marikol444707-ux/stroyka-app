# A11 accounting ownership migration runbook

Status: reviewed local operator procedure only. Production execution requires
separate explicit approval for the exact commit, database, company scope,
maintenance window, backup location and operator. This document does not
authorize a migration, deploy, feature flag, nginx reload or remediation.

## Purpose and order

The migration gives seven legacy accounting tables explicit, verified company
ownership before the read-only exception checker is enabled. The only allowed
order is:

1. preflight inventory;
2. database backup and protected before-state evidence;
3. guarded additive schema apply;
4. a second inventory and guarded provable-only backfill;
5. exact-record remediation, one approved quarantined row at a time;
6. strict postchecks;
7. deploy the tenant-aware writers with the A11 route still disabled;
8. run the separately approved canary.

Never infer company `1`, the current user's company, or a free-form employee or
project name. `ambiguous`, `orphaned` and `conflicting` records remain in
quarantine until an operator supplies exact stored IDs through the dedicated
remediation command.

## Scope

Schema and ownership metadata may change only in:

- `staff`;
- `accountable_payments`;
- `accountable_expenses`;
- `expense_reports`;
- `salary_payments`;
- `own_expenses`;
- `expenses`.

The migration must not alter amounts, dates, names, descriptions, purposes,
notes, photos, files, item JSON, approval state or payment state. It does not
touch project, brigade, supplier or warehouse accounting tables.

## Required evidence folder

Create a root-owned, mode `0700` folder outside the repository. Record:

- reviewed commit and clean-worktree status;
- database identity, PostgreSQL version and UTC timestamp;
- preflight inventory JSON;
- pre/post row counts and quarantine counts;
- schema `changeCount` and `planSha256`;
- backfill `readyCount`, `quarantinedCount`, `conflictingCount` and
  `planSha256`;
- backup filename, size and SHA-256;
- every exact remediation request/evidence SHA-256 and audit event ID;
- final catalog/data audit and operator decision.

Do not store database credentials, cookies, raw business rows, names, notes,
amounts or file URLs in the evidence folder.

## 1. Preflight inventory

Preconditions:

- [ ] production execution requires separate explicit approval;
- [ ] the exact reviewed commit is checked out and the worktree is clean;
- [ ] the application and worker write paths are identified for the maintenance
      window;
- [ ] the A11 HTTP and frontend flags are absent;
- [ ] PostgreSQL health, disk space and replication/backup health are green;
- [ ] no older runtime that depends on the pre-A11 schema will be restarted
      after schema application;
- [ ] a rollback owner and stop authority are present.

Run the default read-only inventory through
`run_accounting_ownership_inventory`. It opens a read-only transaction,
performs bounded SELECTs and rolls back. Save only its closed report. Require:

```text
version = accounting-ownership-inventory-v1
dryRun = true
writesAttempted = 0
truncated = false
totalRecords = provable + ambiguous + orphaned + conflicting
```

Record the preflight inventory and its four classification counts. A truncated
report, source-limit error, unexpected source, missing table or connection to
the wrong database is an immediate stop.

Capture exact row counts separately, without business columns:

```sql
SELECT 'staff' AS source, COUNT(*) FROM public.staff
UNION ALL SELECT 'accountable_payments', COUNT(*) FROM public.accountable_payments
UNION ALL SELECT 'accountable_expenses', COUNT(*) FROM public.accountable_expenses
UNION ALL SELECT 'expense_reports', COUNT(*) FROM public.expense_reports
UNION ALL SELECT 'salary_payments', COUNT(*) FROM public.salary_payments
UNION ALL SELECT 'own_expenses', COUNT(*) FROM public.own_expenses
UNION ALL SELECT 'expenses', COUNT(*) FROM public.expenses
ORDER BY source;
```

These are the authoritative row counts. Also record quarantine counts as the
sum of `ambiguous`, `orphaned` and `conflicting`; keep each category separate.

## 2. Database backup and before-state

Take a database backup before any apply operation. Use the deployment's normal
credential mechanism; never put a password in shell history. A typical custom
format backup is:

```text
pg_dump --format=custom --file=<APPROVED_BACKUP_PATH> <APPROVED_DATABASE>
sha256sum <APPROVED_BACKUP_PATH>
pg_restore --list <APPROVED_BACKUP_PATH> > <APPROVED_BACKUP_PATH>.list
```

This is the database backup gate, not a substitute for the provider snapshot.
Verify that the file is nonempty, owner-restricted and restorable in an
isolated database. Additionally export an ID-only before-state for the seven
tables containing `id`, existing owner IDs and `company_scope_verified`; this
is the reversible data ledger. Do not export private business fields into the
operator log.

Stop if the backup, checksum, restore-list inspection or storage-capacity check
fails.

## 3. Guarded schema apply

First call `build_accounting_ownership_schema_plan()` and record its exact
`changeCount` and `planSha256`. A dry invocation of
`run_accounting_ownership_schema(connection)` must report zero writes and a
rollback.

Only after a distinct apply approval may the operator call:

```python
run_accounting_ownership_schema(
    connection,
    apply=True,
    expected_change_count=DRY_RUN_CHANGE_COUNT,
    expected_plan_sha256=DRY_RUN_PLAN_SHA256,
)
```

The function uses one serializable transaction, access-exclusive locks, an
exact catalog postcheck and one commit. The schema is additive: nullable owner
IDs, `company_scope_verified=FALSE`, finite-money checks and partial indexes.
No legacy record becomes verified in this phase.

Immediately repeat the dry schema plan and catalog inspection. Require the
same plan hash, the exact columns/defaults/check constraints/indexes, unchanged
row counts and every legacy verification marker still false.

## 4. Guarded provable-only backfill

Run `run_accounting_ownership_backfill(connection)` without `apply`. Record:

```text
totalRecords
readyCount
verifiedCount
quarantinedCount
conflictingCount
planSha256
rolledBack = true
writesAttempted = 0
```

The `totalRecords` and per-source row counts must equal the preflight values.
`conflictingCount` must be zero before bulk apply. The quarantine counts must
match the inventory classifications and be accepted explicitly by the
operator; a count change requires a fresh review, not an override.

Only after separate apply approval may the exact dry-run values be replayed:

```python
run_accounting_ownership_backfill(
    connection,
    apply=True,
    expected_ready_count=DRY_RUN_READY_COUNT,
    expected_plan_sha256=DRY_RUN_PLAN_SHA256,
)
```

Require `readyCount=0`, `conflictingCount=0`, unchanged
`quarantinedCount`, `updated=DRY_RUN_READY_COUNT`, `complete=true` and the
matching `appliedPlanSha256` afterward. Repeat the dry run: it must be
idempotent and report zero ready rows.

## 5. Exact quarantine remediation

Bulk guessing is forbidden. For one human-approved record, first run the
module without `--apply`:

```text
python3 -m backend.features.accounting_exception_checks.ownership_remediation_command \
  --source <ALLOWLISTED_SOURCE> \
  --record-id <EXACT_RECORD_ID> \
  --company-id <EXACT_COMPANY_ID> \
  [--project-id <EXACT_PROJECT_ID>] \
  --operator-user-id <EXACT_ACTIVE_FINANCE_OPERATOR_ID>
```

Review and record `requestSha256` and `evidenceSha256`. Then obtain a new
per-record approval. The only apply confirmation is:

```text
--apply --confirm APPLY_EXACT_ACCOUNTING_OWNERSHIP_REMEDIATION
```

The apply command must also repeat both exact SHA-256 values. It locks and
updates one row, validates exact company/project/staff/parent ownership and
writes one minimal `audit_log` event in the same transaction. A rerun must
write zero rows and no duplicate audit event.

## Transactional stop conditions

These transactional stop conditions prohibit commit and require investigation:

- count or SHA-256 drift between dry run and apply;
- any truncated/source-limit result;
- nonzero stored conflict before backfill;
- an ambiguous, orphaned or conflicting row entering the bulk ready set;
- table/column/constraint/index mismatch;
- lock or statement timeout, serialization failure or row-count conflict;
- non-finite numeric value or failed finite-money constraint;
- foreign/missing company, project, staff, parent or operator membership;
- audit insert or postcheck failure;
- any changed business-field checksum or total row count;
- any unexpected commit, DML target or output containing private fields.

Do not rerun apply with altered guards. Return to preflight and produce a new
review package.

## 6. Postchecks

Before releasing maintenance mode:

- repeat the inventory and backfill dry run;
- repeat row counts and quarantine counts;
- require no conflicting stored owners and no bulk-ready rows;
- compare the ID-only ownership ledger with the approved plan;
- prove all business-field hashes and total rows unchanged;
- run the focused accounting tests and the disposable PostgreSQL proof on the
  deployed commit;
- keep both A11 feature flags off;
- deploy tenant-aware writers only after the schema/data audit is accepted;
- run unauthenticated/default-off route smoke before any canary.

## Rollback and recovery

Rollback and recovery depend on the commit point:

1. Before commit, let the guarded function roll back; do not issue a manual
   commit or retry with weaker guards.
2. After committed schema but before backfill, roll the application back to a
   schema-compatible reviewed version. The additive columns may remain inert
   while the incident is assessed.
3. After committed backfill but before any A11 writer is enabled, restore exact
   owner/verification values from the protected ID-only before-state inside a
   reviewed transaction, then repeat counts and hashes.
4. After any new A11 writer has run, never blindly restore old owner columns or
   drop schema. Disable the route/UI, stop affected writers, preserve logs and
   recover from the verified database backup under a separate incident plan.
5. Drop A11 indexes, constraints or columns only after the old runtime is
   restored, all new writes are stopped, data recovery is complete and a
   separately reviewed reverse plan proves no owned row will be lost.

Recovery is complete only when health is green, row counts and business hashes
match the chosen recovery point, quarantine is accounted for, no feature flag
is enabled and the operator records an explicit hold/abort decision.
