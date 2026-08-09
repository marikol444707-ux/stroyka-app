import io
import hashlib
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from backend.features.supply_recommendation_preview.index_migration import (
    APPLY_CONFIRMATION,
    CREATE_SQL,
    INDEX_CONTRACT_VERSION,
    INDEX_NAME,
    PLAN_SHA256_RE,
    ROLLBACK_SQL,
    SupplierReviewIndexMigrationError,
    _collect_catalog,
    build_supplier_user_index_plan,
    main,
    run_supplier_user_index_migration,
    supplier_user_index_plan_sha256,
)


_AUTO_HOLDER = object()


def index_fact(
    *,
    name="idx_existing_supplier_user",
    oid=501,
    method="btree",
    key_columns=("user_id", "id"),
    key_count=None,
    attribute_count=None,
    valid=True,
    ready=True,
    live=True,
    checkxmin=False,
    partial=False,
    expression=False,
    unique=False,
    exclusion=False,
    key_options=None,
    operator_classes=None,
    collation_oids=None,
):
    keys = list(key_columns)
    if key_options is None:
        key_options = [0 for _key in keys]
    if operator_classes is None:
        operator_classes = ["pg_catalog.int4_ops" for _key in keys]
    if collation_oids is None:
        collation_oids = [0 for _key in keys]
    return {
        "oid": oid,
        "name": name,
        "method": method,
        "keyColumns": keys,
        "keyCount": len(keys) if key_count is None else key_count,
        "attributeCount": (
            len(keys) if attribute_count is None else attribute_count
        ),
        "valid": valid,
        "ready": ready,
        "live": live,
        "checkxmin": checkxmin,
        "partial": partial,
        "expression": expression,
        "unique": unique,
        "exclusion": exclusion,
        "keyOptions": list(key_options),
        "operatorClasses": list(operator_classes),
        "collationOids": list(collation_oids),
    }


def catalog(
    *indexes,
    table_exists=True,
    relkind="r",
    columns=None,
    can_manage=True,
    indexes_complete=True,
    holder=_AUTO_HOLDER,
):
    if columns is None:
        columns = {
            "id": {"exists": True, "integer": True, "notNull": True},
            "user_id": {
                "exists": True,
                "integer": True,
                "notNull": False,
            },
        }
    indexes = [dict(item) for item in indexes]
    if holder is _AUTO_HOLDER:
        canonical = next(
            (item for item in indexes if item["name"] == INDEX_NAME),
            None,
        )
        holder = (
            {
                "exists": True,
                "oid": canonical["oid"],
                "relkind": "i",
            }
            if canonical
            else {"exists": False, "oid": None, "relkind": None}
        )
    return {
        "table": {
            "exists": table_exists,
            "oid": 101 if table_exists else None,
            "relkind": relkind if table_exists else None,
            "canManage": can_manage if table_exists else False,
            "estimatedRows": 12 if table_exists else None,
        },
        "columns": columns,
        "canonicalNameHolder": holder,
        "indexes": indexes,
        "indexesComplete": indexes_complete,
    }


def missing_plan():
    return build_supplier_user_index_plan(catalog())


def complete_catalog(*, name=INDEX_NAME):
    return catalog(index_fact(name=name))


class ScriptedCursor:
    def __init__(self, responses=(), fail_on=None):
        self.responses = list(responses)
        self.current = []
        self.calls = []
        self.closed = False
        self.fail_on = fail_on

    def execute(self, sql, params=()):
        compact = " ".join(str(sql).split())
        self.calls.append((compact, tuple(params or ())))
        if self.fail_on and self.fail_on in compact:
            raise RuntimeError("private database detail")
        if compact.upper().startswith("SELECT") and self.responses:
            self.current = self.responses.pop(0)

    def fetchall(self):
        return list(self.current or [])

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        *,
        cursor=None,
        rollback_fails=False,
        commit_fails=False,
        close_fails=False,
    ):
        self.cursor_value = cursor or ScriptedCursor()
        self.rollback_fails = rollback_fails
        self.commit_fails = commit_fails
        self.close_fails = close_fails
        self.session_calls = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1
        if self.commit_fails:
            raise RuntimeError("private commit detail")

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_fails:
            raise RuntimeError("private rollback detail")

    def close(self):
        self.closed = True
        if self.close_fails:
            raise RuntimeError("private close detail")


class SupplierUserIndexPlanTests(unittest.TestCase):
    def test_even_empty_plan_sha_binds_the_complete_fixed_contract(self):
        expected_payload = {
            "contract": {
                "contractVersion": INDEX_CONTRACT_VERSION,
                "schema": "public",
                "table": "suppliers",
                "indexName": INDEX_NAME,
                "method": "btree",
                "columns": ["user_id", "id"],
                "createSql": CREATE_SQL,
                "rollbackSql": ROLLBACK_SQL,
            },
            "changes": [],
        }
        encoded = json.dumps(
            expected_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        self.assertEqual(
            supplier_user_index_plan_sha256([]),
            hashlib.sha256(encoded).hexdigest(),
        )

    def test_missing_index_has_one_deterministic_guarded_change(self):
        first = missing_plan()
        second = missing_plan()

        self.assertTrue(first["readyForApply"])
        self.assertFalse(first["complete"])
        self.assertEqual(first["changeCount"], 1)
        self.assertEqual(first["changes"], second["changes"])
        self.assertEqual(first["planSha256"], second["planSha256"])
        self.assertRegex(first["planSha256"], PLAN_SHA256_RE)
        self.assertEqual(first["changes"][0]["sql"], CREATE_SQL)
        self.assertNotIn("IF NOT EXISTS", CREATE_SQL)
        self.assertEqual(first["rollbackSql"], [ROLLBACK_SQL])

    def test_missing_or_invalid_canonical_schema_blocks_without_a_change(self):
        cases = {
            "table_missing": catalog(table_exists=False),
            "wrong_relkind": catalog(relkind="v"),
            "id_missing": catalog(columns={
                "id": {"exists": False, "integer": False, "notNull": False},
                "user_id": {
                    "exists": True,
                    "integer": True,
                    "notNull": False,
                },
            }),
            "user_id_wrong_type": catalog(columns={
                "id": {"exists": True, "integer": True, "notNull": True},
                "user_id": {
                    "exists": True,
                    "integer": False,
                    "notNull": False,
                },
            }),
            "privilege_missing": catalog(can_manage=False),
            "catalog_incomplete": catalog(indexes_complete=False),
        }

        for case, facts in cases.items():
            with self.subTest(case=case):
                plan = build_supplier_user_index_plan(facts)
                self.assertFalse(plan["readyForApply"])
                self.assertFalse(plan["complete"])
                self.assertEqual(plan["changeCount"], 0)
                self.assertTrue(plan["blockers"])
                self.assertEqual(plan["rollbackSql"], [])

    def test_matcher_accepts_runtime_usable_full_btree_variants(self):
        accepted = (
            index_fact(name="idx_exact"),
            index_fact(name="idx_unique", unique=True),
            index_fact(
                name="idx_wider",
                key_columns=("user_id", "id", "status"),
            ),
            index_fact(
                name="idx_include",
                key_columns=("user_id", "id"),
                key_count=2,
                attribute_count=3,
            ),
        )

        for existing in accepted:
            with self.subTest(index=existing["name"]):
                plan = build_supplier_user_index_plan(catalog(existing))
                self.assertTrue(plan["complete"], plan["blockers"])
                self.assertFalse(plan["readyForApply"])
                self.assertEqual(plan["changeCount"], 0)
                self.assertEqual(plan["matchingIndex"], existing["name"])

    def test_matcher_rejects_every_non_runtime_usable_variant(self):
        rejected = (
            index_fact(name="idx_reversed", key_columns=("id", "user_id")),
            index_fact(name="idx_one_key", key_columns=("user_id",)),
            index_fact(
                name="idx_include_id",
                key_columns=("user_id",),
                key_count=1,
                attribute_count=2,
            ),
            index_fact(
                name="idx_wrong_prefix",
                key_columns=("status", "user_id", "id"),
            ),
            index_fact(name="idx_partial", partial=True),
            index_fact(name="idx_expression", expression=True),
            index_fact(name="idx_hash", method="hash"),
            index_fact(
                name="idx_custom_opclass",
                operator_classes=(
                    "public.custom_int_ops",
                    "pg_catalog.int4_ops",
                ),
            ),
            index_fact(
                name="idx_custom_collation",
                collation_oids=(9001, 0),
            ),
            index_fact(name="idx_invalid", valid=False),
            index_fact(name="idx_not_ready", ready=False),
            index_fact(name="idx_not_live", live=False),
            index_fact(name="idx_checkxmin", checkxmin=True),
        )

        for existing in rejected:
            with self.subTest(index=existing["name"]):
                plan = build_supplier_user_index_plan(catalog(existing))
                self.assertFalse(plan["complete"])
                self.assertTrue(plan["readyForApply"], plan["blockers"])
                self.assertEqual(plan["changeCount"], 1)

    def test_wrong_object_at_canonical_name_is_a_fixed_collision(self):
        wrong_variants = (
            index_fact(
                name=INDEX_NAME,
                key_columns=("id", "user_id"),
            ),
            index_fact(
                name=INDEX_NAME,
                key_options=(1, 0),
            ),
            index_fact(
                name=INDEX_NAME,
                operator_classes=(
                    "public.custom_int_ops",
                    "pg_catalog.int4_ops",
                ),
            ),
            index_fact(
                name=INDEX_NAME,
                collation_oids=(9001, 0),
            ),
            index_fact(name=INDEX_NAME, exclusion=True),
        )
        for wrong in wrong_variants:
            with self.subTest(index=wrong):
                plan = build_supplier_user_index_plan(catalog(wrong))
                self.assertFalse(plan["complete"])
                self.assertFalse(plan["readyForApply"])
                self.assertEqual(
                    plan["blockers"],
                    ["supplier_index_name_conflict"],
                )
                self.assertEqual(plan["changeCount"], 0)


class SupplierUserIndexCatalogTests(unittest.TestCase):
    def test_collector_uses_only_bounded_exact_pg_catalog_queries(self):
        cursor = ScriptedCursor((
            [{
                "table_oid": 101,
                "relkind": "r",
                "can_manage": True,
                "estimated_rows": 12,
            }],
            [
                {
                    "column_name": "id",
                    "is_integer": True,
                    "not_null": True,
                },
                {
                    "column_name": "user_id",
                    "is_integer": True,
                    "not_null": False,
                },
            ],
            [],
            [],
        ))

        facts = _collect_catalog(cursor)

        self.assertTrue(facts["table"]["exists"])
        self.assertTrue(facts["indexesComplete"])
        self.assertEqual(len(cursor.calls), 4)
        for sql, _params in cursor.calls:
            self.assertTrue(sql.startswith("SELECT"), sql)
            self.assertIn("pg_catalog.", sql)
            self.assertIn("LIMIT", sql)
            self.assertNotIn("information_schema", sql)
            self.assertNotIn("pg_indexes", sql)
            self.assertNotIn("COUNT(", sql.upper())
        self.assertNotIn(
            "ORDER BY index_relation.oid",
            cursor.calls[-1][0],
        )

    def test_index_catalog_sentinel_fails_closed(self):
        index_rows = [
            {
                "index_oid": 1000 + number,
                "index_name": "idx_%s" % number,
                "method": "btree",
                "valid": True,
                "ready": True,
                "live": True,
                "checkxmin": False,
                "partial": False,
                "expression": False,
                "unique": False,
                "key_count": 1,
                "attribute_count": 1,
                "key_columns": ["status"],
            }
            for number in range(65)
        ]
        cursor = ScriptedCursor((
            [{
                "table_oid": 101,
                "relkind": "r",
                "can_manage": True,
                "estimated_rows": 12,
            }],
            [
                {
                    "column_name": "id",
                    "exists": True,
                    "is_integer": True,
                    "not_null": True,
                },
                {
                    "column_name": "user_id",
                    "exists": True,
                    "is_integer": True,
                    "not_null": False,
                },
            ],
            [],
            index_rows,
        ))

        facts = _collect_catalog(cursor)
        plan = build_supplier_user_index_plan(facts)

        self.assertFalse(facts["indexesComplete"])
        self.assertEqual(len(facts["indexes"]), 64)
        self.assertFalse(plan["readyForApply"])
        self.assertIn("supplier_index_catalog_incomplete", plan["blockers"])


class SupplierUserIndexRunnerTests(unittest.TestCase):
    def test_dry_run_is_read_only_rolls_back_and_closes_without_ddl(self):
        connection = FakeConnection()
        get_db = Mock(return_value=connection)
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            return_value=catalog(),
        ):
            result = run_supplier_user_index_migration(get_db)

        self.assertTrue(result["dryRun"])
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        self.assertEqual(get_db.call_count, 1)
        self.assertEqual(connection.session_calls, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertNotIn("CREATE INDEX", sql)
        self.assertNotIn("LOCK TABLE", sql)

    def test_apply_guards_are_validated_before_get_db(self):
        invalid = (
            {"confirm": APPLY_CONFIRMATION, "expected_change_count": True,
             "expected_plan_sha256": "a" * 64},
            {"confirm": "wrong", "expected_change_count": 1,
             "expected_plan_sha256": "a" * 64},
            {"confirm": APPLY_CONFIRMATION, "expected_change_count": 1,
             "expected_plan_sha256": "not-a-sha"},
            {"confirm": APPLY_CONFIRMATION, "expected_change_count": 2,
             "expected_plan_sha256": "a" * 64},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                get_db = Mock()
                with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                    run_supplier_user_index_migration(
                        get_db,
                        apply=True,
                        **kwargs,
                    )
                self.assertEqual(
                    error.exception.code,
                    "supplier_index_apply_guard_invalid",
                )
                get_db.assert_not_called()

    def test_apply_rejects_count_or_sha_drift_under_lock_before_ddl(self):
        connection = FakeConnection()
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            return_value=catalog(),
        ):
            with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                run_supplier_user_index_migration(
                    lambda: connection,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_change_count=1,
                    expected_plan_sha256="f" * 64,
                )

        self.assertEqual(
            error.exception.code,
            "supplier_index_apply_guard_mismatch",
        )
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertIn("LOCK TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)
        self.assertEqual(connection.rollbacks, 1)

    def test_apply_rechecks_locked_plan_then_creates_and_postchecks(self):
        before = missing_plan()
        connection = FakeConnection()
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            side_effect=[catalog(), complete_catalog()],
        ):
            result = run_supplier_user_index_migration(
                lambda: connection,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_change_count=1,
                expected_plan_sha256=before["planSha256"],
            )

        self.assertTrue(result["complete"])
        self.assertTrue(result["committed"])
        self.assertEqual(result["schemaWritesAttempted"], 1)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.session_calls, [{
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        }])
        calls = [call[0] for call in connection.cursor_value.calls]
        lock_index = calls.index(
            "LOCK TABLE public.suppliers IN SHARE ROW EXCLUSIVE MODE"
        )
        create_index = calls.index(CREATE_SQL)
        advisory_index = next(
            index for index, call in enumerate(calls)
            if "pg_advisory_xact_lock" in call
        )
        self.assertLess(lock_index, advisory_index)
        self.assertLess(lock_index, create_index)
        self.assertIn("pg_advisory_xact_lock", " ".join(calls))

    def test_locked_current_plan_drift_rolls_back_before_create(self):
        before = missing_plan()
        connection = FakeConnection()
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            return_value=complete_catalog(name="idx_elsewhere"),
        ):
            with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                run_supplier_user_index_migration(
                    lambda: connection,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_change_count=1,
                    expected_plan_sha256=before["planSha256"],
                )

        self.assertEqual(
            error.exception.code,
            "supplier_index_apply_guard_mismatch",
        )
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertIn("LOCK TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)
        self.assertEqual(connection.rollbacks, 1)

    def test_failed_postcheck_rolls_back_the_attempted_ddl(self):
        before = missing_plan()
        connection = FakeConnection()
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            side_effect=[catalog(), catalog()],
        ):
            with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                run_supplier_user_index_migration(
                    lambda: connection,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_change_count=1,
                    expected_plan_sha256=before["planSha256"],
                )

        self.assertEqual(
            error.exception.code,
            "supplier_index_postcheck_failed",
        )
        self.assertIn(
            CREATE_SQL,
            [call[0] for call in connection.cursor_value.calls],
        )
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_existing_equivalent_index_is_a_zero_write_idempotent_apply(self):
        facts = complete_catalog(name="idx_existing_supplier_user")
        plan = build_supplier_user_index_plan(facts)
        connection = FakeConnection()
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            return_value=facts,
        ):
            result = run_supplier_user_index_migration(
                lambda: connection,
                apply=True,
                confirm=APPLY_CONFIRMATION,
                expected_change_count=0,
                expected_plan_sha256=plan["planSha256"],
            )

        self.assertTrue(result["complete"])
        self.assertEqual(result["schemaWritesAttempted"], 0)
        self.assertEqual(connection.rollbacks, 1)
        sql = " ".join(call[0] for call in connection.cursor_value.calls)
        self.assertIn("LOCK TABLE", sql)
        self.assertNotIn("CREATE INDEX", sql)

    def test_rollback_and_commit_uncertainty_are_fixed_safe_errors(self):
        with self.subTest(path="rollback"):
            connection = FakeConnection(rollback_fails=True)
            with patch(
                "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
                return_value=catalog(),
            ):
                with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                    run_supplier_user_index_migration(lambda: connection)
            self.assertEqual(
                error.exception.code,
                "supplier_index_rollback_failed",
            )
            self.assertTrue(connection.cursor_value.closed)
            self.assertTrue(connection.closed)

        with self.subTest(path="commit"):
            before = missing_plan()
            connection = FakeConnection(commit_fails=True)
            with patch(
                "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
                side_effect=[catalog(), complete_catalog()],
            ):
                with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                    run_supplier_user_index_migration(
                        lambda: connection,
                        apply=True,
                        confirm=APPLY_CONFIRMATION,
                        expected_change_count=1,
                        expected_plan_sha256=before["planSha256"],
                    )
            self.assertEqual(
                error.exception.code,
                "supplier_index_commit_outcome_unknown",
            )
            self.assertEqual(connection.rollbacks, 1)

    def test_ddl_and_cleanup_failures_never_expose_private_text(self):
        before = missing_plan()
        connection = FakeConnection(
            cursor=ScriptedCursor(fail_on="CREATE INDEX")
        )
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            return_value=catalog(),
        ):
            with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                run_supplier_user_index_migration(
                    lambda: connection,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_change_count=1,
                    expected_plan_sha256=before["planSha256"],
                )
        self.assertEqual(
            error.exception.code,
            "supplier_index_migration_failed",
        )
        self.assertNotIn("private", str(error.exception))
        self.assertEqual(connection.rollbacks, 1)

        cleanup_connection = FakeConnection(close_fails=True)
        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            return_value=catalog(),
        ):
            with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                run_supplier_user_index_migration(lambda: cleanup_connection)
        self.assertEqual(
            error.exception.code,
            "supplier_index_cleanup_failed",
        )
        self.assertNotIn("private", str(error.exception))


class SupplierUserIndexCliBoundaryTests(unittest.TestCase):
    def test_blocked_audit_plan_returns_nonzero_exit_status(self):
        blocked = {
            "ok": False,
            "blockers": ["supplier_index_name_conflict"],
        }
        with patch(
            "backend.features.supply_recommendation_preview.index_migration.run_supplier_user_index_migration",
            return_value=blocked,
        ):
            with redirect_stdout(io.StringIO()):
                status = main(["--dry-run"])
        self.assertEqual(status, 1)

    def test_cli_requires_all_apply_guards_before_connecting(self):
        with patch("backend.db.get_db") as get_db:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([
                    "--apply",
                    "--confirm",
                    APPLY_CONFIRMATION,
                    "--expected-change-count",
                    "1",
                ])
        get_db.assert_not_called()

    def test_package_commands_are_inert_and_deploy_startup_do_not_import_tool(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        deploy = (root / "deploy.sh").read_text(encoding="utf-8")
        main_source = (root / "backend" / "main.py").read_text(encoding="utf-8")
        module = (
            "python3 -m "
            "backend.features.supply_recommendation_preview.index_migration"
        )

        self.assertEqual(
            package["scripts"]["audit:supplier-review-index"],
            module + " --dry-run",
        )
        self.assertEqual(
            package["scripts"]["migrate:supplier-review-index"],
            module,
        )
        self.assertNotIn("index_migration", deploy)
        self.assertNotIn("supply_recommendation_preview.index_migration", main_source)

    def test_audit_mode_cannot_be_combined_with_apply(self):
        with patch("backend.db.get_db") as get_db:
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main([
                    "--dry-run",
                    "--apply",
                    "--confirm",
                    APPLY_CONFIRMATION,
                    "--expected-change-count",
                    "1",
                    "--expected-plan-sha256",
                    "a" * 64,
                ])
        get_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
