import copy
import inspect
import unittest
from unittest import mock

from backend.features.human_approved_actions import schema_contract as schema


def absent_catalog(**overrides):
    value = {
        "parentColumnsMissing": [],
        "parentRelations": {
            name: {"relkind": "r", "persistence": "p"}
            for name in schema.PARENT_REQUIRED_COLUMNS
        },
        "catalogComplete": True,
        "relations": {},
        "typeHolders": {},
        "sequences": {},
        "columns": {},
        "constraints": {},
        "indexes": {},
        "functions": {},
        "triggers": {},
    }
    value.update(overrides)
    return value


def exact_catalog():
    return copy.deepcopy(schema.human_action_schema_contract())


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, query, params=None):
        self.calls.append((" ".join(str(query).split()), params))

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.sessions = []
        self.commits = 0
        self.rollbacks = 0

    def set_session(self, **kwargs):
        self.sessions.append(dict(kwargs))

    def cursor(self, **_kwargs):
        return self.fake_cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class CommitFailsConnection(FakeConnection):
    def commit(self):
        self.commits += 1
        raise RuntimeError("PRIVATE commit outcome")


class HumanActionSchemaPlanTests(unittest.TestCase):
    def test_absent_schema_has_one_deterministic_append_only_plan(self):
        first = schema.build_human_action_schema_plan(absent_catalog())
        second = schema.build_human_action_schema_plan(absent_catalog())

        self.assertEqual(first, second)
        self.assertTrue(first["ok"])
        self.assertFalse(first["complete"])
        self.assertTrue(first["readyForApply"])
        self.assertEqual(first["blockers"], [])
        self.assertEqual(first["changeCount"], 12)
        self.assertEqual(len(first["changes"]), 12)
        self.assertEqual(len(first["rollbackSql"]), 12)
        self.assertRegex(first["planSha256"], r"^[0-9a-f]{64}$")

        sql = "\n".join(item["sql"] for item in first["changes"])
        self.assertIn("CREATE TABLE public.human_action_proposals", sql)
        self.assertIn("CREATE TABLE public.human_action_events", sql)
        self.assertIn("source_job_id BIGINT NOT NULL", sql)
        self.assertIn("FOREIGN KEY (source_job_id)", sql)
        self.assertIn(
            "REFERENCES public.agent_jobs(id) ON DELETE RESTRICT", sql,
        )
        self.assertEqual(sql.count("warehouse_anomaly_review_acknowledged"), 2)
        self.assertIn("expires_at=created_at+INTERVAL '15 minutes'", sql)
        self.assertIn("WHERE event_kind IN ('approved','rejected')", sql)
        self.assertIn("WHERE event_kind='applied'", sql)
        self.assertEqual(sql.count("BEFORE UPDATE OR DELETE"), 2)
        self.assertEqual(sql.count("BEFORE TRUNCATE"), 2)
        for protected in (
            "materials", "warehouse_invoices", "project_payments",
            "salary_payments", "accountable_payments", "estimates",
        ):
            self.assertNotIn(f"public.{protected}", sql)

    def test_exact_schema_is_complete_and_any_drift_blocks_apply(self):
        complete = schema.build_human_action_schema_plan(exact_catalog())
        self.assertTrue(complete["complete"])
        self.assertFalse(complete["readyForApply"])
        self.assertEqual(complete["changeCount"], 0)

        cases = []
        for category in (
            "relations", "typeHolders", "sequences", "columns", "constraints",
            "functions", "triggers",
        ):
            value = exact_catalog()
            key = next(iter(value[category]))
            value[category][key] = {"private": "drift"}
            cases.append((category, value))
        value = exact_catalog()
        value["indexes"][next(iter(value["indexes"]))] = {
            "private": "drift",
        }
        cases.append(("indexes", value))
        collision = absent_catalog(relations={
            schema.PROPOSAL_TABLE: {"relkind": "v", "persistence": "p"},
        })
        cases.append(("collision", collision))
        type_collision = absent_catalog(typeHolders={
            schema.PROPOSAL_TABLE: {"type": "e", "relationOid": 0},
        })
        cases.append(("type-collision", type_collision))
        parent_view = absent_catalog()
        parent_view["parentRelations"]["companies"]["relkind"] = "v"
        cases.append(("parent-view", parent_view))
        missing_parent = absent_catalog(parentColumnsMissing=["companies.id"])
        cases.append(("parent", missing_parent))

        for name, catalog in cases:
            with self.subTest(name=name):
                result = schema.build_human_action_schema_plan(catalog)
                self.assertFalse(result["ok"])
                self.assertFalse(result["readyForApply"])
                self.assertEqual(result["changes"], [])
                self.assertTrue(result["blockers"])

    def test_schema_module_is_private_and_has_no_automatic_apply(self):
        source = inspect.getsource(schema)
        self.assertNotIn("backend.main", source)
        self.assertNotIn("get_db", source)
        self.assertNotIn("register_", source)
        self.assertNotIn("if __name__", source)
        self.assertNotIn("argparse", source)


class HumanActionSchemaRunnerTests(unittest.TestCase):
    def test_dry_run_reads_catalog_and_rolls_back_without_schema_write(self):
        connection = FakeConnection()
        with mock.patch.object(
            schema, "_collect_catalog", return_value=absent_catalog(),
        ):
            report = schema.run_human_action_schema_migration(connection)

        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(connection.sessions, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.fake_cursor.closed)
        self.assertEqual(connection.fake_cursor.calls, [])

    def test_apply_requires_exact_count_hash_and_confirmation_before_ddl(self):
        plan = schema.build_human_action_schema_plan(absent_catalog())
        invalid = (
            ({"apply": 1}, "human_action_schema_apply_guard_invalid", True),
            ({}, "human_action_schema_apply_guard_invalid", True),
            (
                {"confirm": schema.APPLY_CONFIRMATION},
                "human_action_schema_apply_guard_invalid",
                True,
            ),
            ({
                "confirm": schema.APPLY_CONFIRMATION,
                "expected_change_count": plan["changeCount"],
                "expected_plan_sha256": "0" * 64,
            }, "human_action_schema_apply_guard_mismatch", False),
        )
        for kwargs, code, before_connect in invalid:
            connection = FakeConnection()
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(
                schema.HumanActionSchemaMigrationError,
                code,
            ):
                explicit_apply = kwargs.pop("apply", True)
                schema.run_human_action_schema_migration(
                    connection, apply=explicit_apply, **kwargs,
                )
            if before_connect:
                self.assertEqual(connection.fake_cursor.calls, [])
            else:
                self.assertTrue(all(
                    not sql.startswith(("CREATE ", "ALTER ", "DROP "))
                    for sql, _params in connection.fake_cursor.calls
                ))
            self.assertEqual(connection.commits, 0)

    def test_guarded_apply_rechecks_plan_executes_exact_steps_and_commits(self):
        before = absent_catalog()
        plan = schema.build_human_action_schema_plan(before)
        connection = FakeConnection()
        with mock.patch.object(
            schema, "_collect_catalog",
            side_effect=(before, exact_catalog()),
        ):
            report = schema.run_human_action_schema_migration(
                connection,
                apply=True,
                confirm=schema.APPLY_CONFIRMATION,
                expected_change_count=plan["changeCount"],
                expected_plan_sha256=plan["planSha256"],
            )

        self.assertFalse(report["dryRun"])
        self.assertTrue(report["schemaReady"])
        self.assertEqual(report["writesAttempted"], 12)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        calls = [sql for sql, _params in connection.fake_cursor.calls]
        self.assertEqual(calls[0], "SET LOCAL search_path=pg_catalog,public")
        self.assertIn("pg_advisory_xact_lock", calls[3])
        self.assertEqual(
            calls[4:],
            [" ".join(item["sql"].split()) for item in plan["changes"]],
        )

    def test_plan_mismatch_or_postcheck_failure_rolls_back_without_commit(self):
        before = absent_catalog()
        plan = schema.build_human_action_schema_plan(before)
        cases = (
            (absent_catalog(), "human_action_schema_apply_guard_mismatch", 0),
            ({**exact_catalog(), "triggers": {}}, "human_action_schema_postcheck_failed", 12),
        )
        for after, code, write_count in cases:
            connection = FakeConnection()
            side_effect = (
                (before, after)
                if write_count
                else (before,)
            )
            with self.subTest(code=code), mock.patch.object(
                schema, "_collect_catalog", side_effect=side_effect,
            ), self.assertRaisesRegex(
                schema.HumanActionSchemaMigrationError, code,
            ):
                schema.run_human_action_schema_migration(
                    connection,
                    apply=True,
                    confirm=schema.APPLY_CONFIRMATION,
                    expected_change_count=(
                        plan["changeCount"] + (1 if not write_count else 0)
                    ),
                    expected_plan_sha256=plan["planSha256"],
                )
            self.assertEqual(connection.commits, 0)
            self.assertEqual(connection.rollbacks, 1)
            ddl_calls = connection.fake_cursor.calls[4:]
            self.assertEqual(len(ddl_calls), write_count)

    def test_zero_change_apply_rolls_back_and_reports_the_truth(self):
        catalog = exact_catalog()
        plan = schema.build_human_action_schema_plan(catalog)
        connection = FakeConnection()
        with mock.patch.object(
            schema, "_collect_catalog", return_value=catalog,
        ):
            report = schema.run_human_action_schema_migration(
                connection,
                apply=True,
                confirm=schema.APPLY_CONFIRMATION,
                expected_change_count=0,
                expected_plan_sha256=plan["planSha256"],
            )
        self.assertFalse(report["committed"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)

    def test_commit_failure_has_fixed_uncertain_outcome_without_private_text(self):
        before = absent_catalog()
        plan = schema.build_human_action_schema_plan(before)
        connection = CommitFailsConnection()
        caught = None
        with mock.patch.object(
            schema, "_collect_catalog", side_effect=(before, exact_catalog()),
        ):
            try:
                schema.run_human_action_schema_migration(
                    connection,
                    apply=True,
                    confirm=schema.APPLY_CONFIRMATION,
                    expected_change_count=plan["changeCount"],
                    expected_plan_sha256=plan["planSha256"],
                )
            except schema.HumanActionSchemaMigrationError as exc:
                caught = exc
        self.assertIsNotNone(caught)
        self.assertEqual(
            caught.code, "human_action_schema_commit_outcome_unknown"
        )
        self.assertNotIn("PRIVATE", repr(caught))
        self.assertIsNone(caught.__cause__)
        self.assertEqual(connection.commits, 1)


if __name__ == "__main__":
    unittest.main()
