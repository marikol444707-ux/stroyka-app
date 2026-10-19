# Warehouse receipt PostgreSQL regression gate

Run from the repository root as a non-root user with Python dependencies installed:

```sh
export PATH="$(pg_config --bindir):$PATH"
python scripts/run_warehouse_receipt_postgres_tests.py
```

The runner requires `initdb`, `pg_ctl`, `createdb`, and `createuser`. It starts a
new temporary PostgreSQL cluster with TCP disabled. It never uses the application
database, an inherited DSN, or a PostgreSQL service definition. The cluster,
roles, and data are disposable and are removed after the run, including test
failure or timeout. Do not point a fixture at a shared or existing database.

The first two suites run all 31 resolver/confirmation PostgreSQL cases (21
confirmation and 10 resolver), each in a separate empty database, using the
unchanged safety checks: explicit receipt opt-in, Unix socket, empty
`warehouse_receipts_test_*` database, and `receipt_test` role. These cases use a
synthetic accounting writer and test concurrency, tenant boundaries, evidence,
and atomic adapter behavior.

The third suite runs six production-writer integration cases in a separate
empty `supply_chain_test_*` database as `chain_test`. The existing guarded
supply-chain fixture loads production code with AST-controlled startup, isolated
configuration, and outbound TCP blocked. The actual
`_receive_supply_delivery_record`, invoice writer, stock writer, claims,
history, resolver, and authorization execute against PostgreSQL. Only the
optional post-commit AI callback is replaced with an observer.

Production-writer cases cover:

- Multi-line shortage receipt, one owner commit, actual stock/invoices/claims,
  canonical originals, and callbacks observing committed data
- Replay without duplicate stock, invoices, claims, or history
- A second-line stock constraint error rolling back both lines
- A second-line production estimate-admission error rolling back both lines
- A later excessive quantity rolling back the earlier real receipt
- Zero-quantity receipt with real claims and originals, no stock/invoice, and
  idempotent replay

This suite covers the legacy receipt-accounting configuration. It does not prove
the enabled managed payment-ledger, receipt-line-proof, or owned-quality-journal
feature combinations, the complete migration chain, or browser behavior.

Every selected test must execute. Missing opt-in, skipped cases, an empty suite,
setup errors, and ordinary test failures all fail the gate. Normal backend
discovery continues to skip opt-in PostgreSQL tests when no database is requested.
An inventory regression compares every collected receipt PostgreSQL test ID
against the explicitly selected suites, so omitted classes fail that regression.

The shared supplier catalog runner also has an opt-in strict mode for other
isolated suites, without changing its existing default skip behavior:

```sh
python scripts/run_supplier_catalog_postgres_tests.py --require-no-skips package.module.TestClass
```

Both runners clear inherited `PG*`, `DB*`, `DATABASE_URL`, and fixture destination
variables for PostgreSQL utility commands and test subprocesses. They set a
fresh nonexistent `PGPASSFILE`, then construct explicit socket/database/opt-in
settings. Supplier capability flags are reconstructed as before, and unrelated
feature flags remain unchanged.

The workflow adds only two focused steps: the receipt gate and a strict
movement/return/traceability/source-access gate. Existing security, sandbox,
deployment, and other test configuration is unchanged.

Runner-only checks do not launch PostgreSQL:

```sh
python -m unittest backend.features.warehouse_receipts.test_ci_runner -v
```
