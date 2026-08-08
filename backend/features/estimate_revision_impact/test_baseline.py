import json
import os
import unittest
from pathlib import Path

import psycopg2

from backend.features.estimate_revision_impact.baseline import (
    collect_baseline_audit,
    run_baseline_audit,
)
from backend.features.estimate_revision_impact.contract import (
    MAX_CANONICAL_SOURCE_BYTES,
    build_estimate_revision_source,
)


REQUIRED_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in {
        "projects": ("id", "company_id"),
        "estimates": (
            "id", "company_id", "project_id", "version", "sections_json",
            "status", "is_template", "smeta_type", "work_package",
        ),
        "estimate_reconciliations": (
            "id", "base_estimate_id", "next_estimate_id", "status",
            "smeta_type", "work_package",
        ),
    }.items()
    for column in columns
)


def source():
    return build_estimate_revision_source(
        company_id=4,
        project_id=17,
        estimate_id=52,
        version="v2.0",
        sections=[{"name": "Работы", "items": []}],
    )


def estimate_row(**overrides):
    row = {
        "estimate_id": 52,
        "company_id": 4,
        "project_id": 17,
        "version": "v2.0",
        "sections_json": json.dumps(
            [{"name": "Работы", "items": []}], ensure_ascii=False,
        ),
        "status": "Активная",
        "is_template": False,
        "smeta_type": "Заказчик",
        "work_package": "Основная",
    }
    row.update(overrides)
    return row


def reconciliation_row(**overrides):
    row = {
        "reconciliation_id": 91,
        "reconciliation_status": "Черновик",
        "reconciliation_smeta_type": "Заказчик",
        "reconciliation_work_package": "Основная",
        "base_estimate_id": 51,
        "next_estimate_id": 52,
        "project_id": 17,
        "project_company_id": 4,
        "base_company_id": 4,
        "base_project_id": 17,
        "base_smeta_type": "Заказчик",
        "base_work_package": "Основная",
        "next_company_id": 4,
        "next_project_id": 17,
        "next_status": "Активная",
        "next_is_template": False,
        "next_smeta_type": "Заказчик",
        "next_work_package": "Основная",
    }
    row.update(overrides)
    return row


class FakeCursor:
    def __init__(self, result_sets):
        self.result_sets = [list(rows) for rows in result_sets]
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return self.result_sets.pop(0) if self.result_sets else []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.session = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1
        raise AssertionError("A7.1 baseline audit must never commit")

    def close(self):
        self.closed = True


class EstimateRevisionImpactBaselineCollectionTests(unittest.TestCase):
    def test_exact_source_returns_bounded_id_only_ready_report(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
        ))

        report = collect_baseline_audit(cursor, source())

        self.assertTrue(report["schemaReady"])
        self.assertTrue(report["scanComplete"])
        self.assertTrue(report["sourceReady"])
        self.assertTrue(report["readyForDomainScan"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["source"], {
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "sourceRevision": source().source_revision,
            "reconciliationId": 91,
            "baseEstimateId": 51,
            "reconciliationStatus": "Черновик",
        })
        self.assertEqual(report["summary"], {
            "estimateRows": 1,
            "reconciliationRows": 1,
        })
        self.assertEqual(report["issues"], [])
        serialized = json.dumps(report, ensure_ascii=False)
        for forbidden in (
            "Работы", "sections", "projectName", "estimateName", "notes",
            "createdBy",
        ):
            self.assertNotIn(forbidden, serialized)

        self.assertEqual(len(cursor.calls), 3)
        for sql, _params in cursor.calls:
            self.assertTrue(sql.upper().startswith("SELECT "))
            for forbidden_column in (
                "project_name", "base_estimate_name", "next_estimate_name",
                "notes", "created_by", "approved_by",
            ):
                self.assertNotIn(forbidden_column, sql.lower())
        estimate_sql, estimate_params = cursor.calls[1]
        self.assertIn("id=%s AND company_id=%s AND project_id=%s", estimate_sql)
        self.assertEqual(estimate_params[0], MAX_CANONICAL_SOURCE_BYTES)
        self.assertEqual(estimate_params[1:4], (52, 4, 17))

    def test_missing_or_foreign_estimate_fails_closed_without_reconciliation_scan(self):
        cursor = FakeCursor((REQUIRED_SCHEMA_ROWS, ()))

        report = collect_baseline_audit(cursor, source())

        self.assertFalse(report["sourceReady"])
        self.assertFalse(report["readyForDomainScan"])
        self.assertEqual(report["issues"], [{
            "reasonCode": "impact_source_not_found",
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
        }])
        self.assertEqual(len(cursor.calls), 2)

    def test_source_revision_drift_fails_before_reconciliation_scan(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(version="v3.0"),),
        ))

        report = collect_baseline_audit(cursor, source())

        self.assertEqual(report["reasonCounts"], {"source_revision_mismatch": 1})
        self.assertFalse(report["readyForDomainScan"])
        self.assertEqual(len(cursor.calls), 2)

    def test_oversized_stored_snapshot_fails_before_content_is_loaded(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(
                sections_json=None,
                sections_bytes=MAX_CANONICAL_SOURCE_BYTES + 1,
            ),),
        ))

        report = collect_baseline_audit(cursor, source())

        self.assertEqual(report["reasonCounts"], {
            "impact_estimate_snapshot_too_large": 1,
        })
        self.assertFalse(report["readyForDomainScan"])
        self.assertEqual(len(cursor.calls), 2)
        estimate_sql, estimate_params = cursor.calls[1]
        self.assertIn("octet_length", estimate_sql.lower())
        self.assertIn("CASE WHEN", estimate_sql)
        self.assertEqual(estimate_params[0], MAX_CANONICAL_SOURCE_BYTES)

    def test_duplicate_reconciliation_is_ambiguous(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(reconciliation_id=91),
             reconciliation_row(reconciliation_id=92)),
        ))

        report = collect_baseline_audit(cursor, source())

        self.assertFalse(report["sourceReady"])
        self.assertEqual(report["reasonCounts"], {
            "impact_reconciliation_ambiguous": 1,
        })
        self.assertNotIn("reconciliationId", report["source"])

    def test_owner_type_package_status_and_template_drift_fail_closed(self):
        estimate_failures = (
            ({"status": "Черновик"}, "impact_estimate_not_active"),
            ({"is_template": True}, "impact_estimate_template"),
            ({"smeta_type": "Подрядчик"}, "impact_estimate_not_customer"),
            ({"work_package": ""}, "impact_estimate_package_invalid"),
        )
        for overrides, reason in estimate_failures:
            with self.subTest(reason=reason):
                cursor = FakeCursor((
                    REQUIRED_SCHEMA_ROWS,
                    (estimate_row(**overrides),),
                ))
                report = collect_baseline_audit(cursor, source())
                self.assertEqual(report["reasonCounts"], {reason: 1})
                self.assertEqual(len(cursor.calls), 2)

        reconciliation_failures = (
            ({"base_company_id": 5}, "impact_reconciliation_owner_mismatch"),
            ({"next_status": "Черновик"}, "impact_reconciliation_next_not_active"),
            ({"base_smeta_type": "Подрядчик"}, "impact_reconciliation_not_customer"),
            ({"base_work_package": "Отделка"}, "impact_reconciliation_package_mismatch"),
            ({"reconciliation_status": "Неизвестно"}, "impact_reconciliation_status_invalid"),
        )
        for overrides, reason in reconciliation_failures:
            with self.subTest(reason=reason):
                cursor = FakeCursor((
                    REQUIRED_SCHEMA_ROWS,
                    (estimate_row(),),
                    (reconciliation_row(**overrides),),
                ))
                report = collect_baseline_audit(cursor, source())
                self.assertEqual(report["reasonCounts"], {reason: 1})

    def test_missing_schema_and_reconciliation_scan_limit_are_bounded(self):
        missing_schema = REQUIRED_SCHEMA_ROWS[:-1]
        cursor = FakeCursor((missing_schema,))

        missing = collect_baseline_audit(cursor, source())

        self.assertFalse(missing["schemaReady"])
        self.assertFalse(missing["scanComplete"])
        self.assertFalse(missing["sourceReady"])
        self.assertEqual(missing["missingColumns"], [
            "estimate_reconciliations.work_package",
        ])
        self.assertEqual(len(cursor.calls), 1)

        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(reconciliation_id=91),
             reconciliation_row(reconciliation_id=92)),
        ))
        limited = collect_baseline_audit(
            cursor,
            source(),
            max_reconciliation_rows=1,
        )
        self.assertFalse(limited["scanComplete"])
        self.assertEqual(limited["reasonCounts"], {
            "impact_reconciliation_scan_limit_exceeded": 1,
        })


class EstimateRevisionImpactBaselineRunnerTests(unittest.TestCase):
    def test_runner_is_repeatable_read_read_only_and_always_rolls_back(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
        ))
        connection = FakeConnection(cursor)

        report = run_baseline_audit(lambda: connection, source())

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_runner_rolls_back_and_closes_when_collection_fails(self):
        cursor = FakeCursor(())
        connection = FakeConnection(cursor)

        def fail(_cur, _source):
            raise RuntimeError("database unavailable")

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            run_baseline_audit(
                lambda: connection,
                source(),
                collect_data=fail,
            )

        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

    def test_operator_command_is_inert_and_not_registered_at_runtime(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["audit:estimate-revision-impact"],
            "python3 -m backend.features.estimate_revision_impact.baseline",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "estimate_revision_impact",
                (root / relative).read_text(encoding="utf-8"),
            )


A7_TEST_DATABASE_URL = os.getenv("A7_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("A7_RUN_POSTGRES_INTEGRATION") == "1" and A7_TEST_DATABASE_URL,
    "set A7_RUN_POSTGRES_INTEGRATION=1 and A7_TEST_DATABASE_URL",
)
class EstimateRevisionImpactPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg2.connect(A7_TEST_DATABASE_URL)
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            if not str(cur.fetchone()[0]).startswith("a7_"):
                raise RuntimeError(
                    "A7 integration fixture requires a dedicated a7_* database"
                )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.projects (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    name TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimates (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    version TEXT,
                    sections_json TEXT,
                    status TEXT,
                    is_template BOOLEAN,
                    smeta_type TEXT,
                    work_package TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimate_reconciliations (
                    id INTEGER PRIMARY KEY,
                    base_estimate_id INTEGER,
                    next_estimate_id INTEGER,
                    status TEXT,
                    smeta_type TEXT,
                    work_package TEXT
                );
                """
            )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.estimate_reconciliations,public.estimates,"
                "public.projects"
            )

    def _counts(self):
        with self.admin.cursor() as cur:
            return {
                table: self._count(cur, table)
                for table in (
                    "projects",
                    "estimates",
                    "estimate_reconciliations",
                )
            }

    @staticmethod
    def _count(cur, table):
        cur.execute("SELECT COUNT(*) FROM public." + table)
        return cur.fetchone()[0]

    def test_same_name_cross_company_isolation_and_zero_writes(self):
        stored_sections = [{"name": "Fixture", "items": []}]
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name) VALUES "
                "(17,4,'Одинаковый объект'),(18,5,'Одинаковый объект')"
            )
            cur.execute(
                """INSERT INTO public.estimates
                     (id,company_id,project_id,version,sections_json,status,
                      is_template,smeta_type,work_package)
                   VALUES
                     (51,4,17,'v1.0',%s,'Черновик',FALSE,'Заказчик','Основная'),
                     (52,4,17,'v2.0',%s,'Активная',FALSE,'Заказчик','Основная'),
                     (61,5,18,'v1.0',%s,'Черновик',FALSE,'Заказчик','Основная'),
                     (62,5,18,'v2.0',%s,'Активная',FALSE,'Заказчик','Основная')""",
                tuple(json.dumps(stored_sections) for _ in range(4)),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,smeta_type,
                      work_package)
                   VALUES
                     (91,51,52,'Черновик','Заказчик','Основная'),
                     (92,61,62,'Черновик','Заказчик','Основная')"""
            )
        before = self._counts()
        exact_source = build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=stored_sections,
        )

        ready = run_baseline_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL),
            exact_source,
        )
        foreign = run_baseline_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL),
            validate_foreign_source(exact_source),
        )

        self.assertTrue(ready["readyForDomainScan"])
        self.assertEqual(ready["source"]["reconciliationId"], 91)
        self.assertTrue(ready["readOnlyTransaction"])
        self.assertTrue(ready["rolledBack"])
        self.assertFalse(foreign["readyForDomainScan"])
        self.assertEqual(foreign["reasonCounts"], {"impact_source_not_found": 1})
        self.assertNotIn("Одинаковый объект", json.dumps(foreign, ensure_ascii=False))
        self.assertEqual(self._counts(), before)


def validate_foreign_source(exact_source):
    from backend.features.estimate_revision_impact.contract import (
        validate_estimate_revision_source,
    )

    return validate_estimate_revision_source({
        "schemaVersion": exact_source.schema_version,
        "eventType": exact_source.event_type,
        "companyId": 5,
        "projectId": 18,
        "estimateId": exact_source.estimate_id,
        "sourceRevision": exact_source.source_revision,
    })


if __name__ == "__main__":
    unittest.main()
