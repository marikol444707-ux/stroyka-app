import json
import os
import unittest

import psycopg2

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_revision_impact.assignment_projection import (
    MAX_ASSIGNMENT_ROWS,
    PROTECTED_ID_LIMIT,
    build_assignment_projection,
    collect_assignment_impact_audit,
    run_assignment_impact_audit,
)
from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)

from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    REQUIRED_SCHEMA_ROWS,
    estimate_row,
    reconciliation_row,
)


ASSIGNMENT_REQUIRED_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in {
        "projects": ("id", "company_id"),
        "estimates": ("id", "company_id", "project_id"),
        "estimate_versions": (
            "id", "estimate_id", "sections_json", "sections_sha256",
        ),
        "brigade_contracts": (
            "id", "company_id", "project_id", "work_package",
        ),
        "brigade_contract_items": (
            "id", "contract_id", "estimate_item_key", "work_package",
            "quantity", "source_type", "source_estimate_version_id",
            "source_section_index", "source_item_index", "source_item_key",
        ),
        "work_journal": (
            "id", "company_id", "contract_item_id", "quantity", "status",
        ),
        "hidden_works_acts": ("id", "company_id", "work_journal_id"),
        "brigade_acts": ("id", "contract_id"),
        "brigade_payments": (
            "id", "company_id", "contract_id", "project_payment_id",
        ),
        "project_payments": (
            "id", "company_id", "company_scope_verified",
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


def assignment_context():
    return {
        "companyId": 4,
        "projectId": 17,
        "baseEstimateId": 51,
        "targetEstimateId": 52,
        "workPackage": "Основная",
    }


def assignment_row(**overrides):
    sections = [{
        "name": "Секция не должна попасть в отчёт",
        "items": [{
            "name": "Работа не должна попасть в отчёт",
            "estimateItemKey": "base-row",
            "priceWork": 700,
        }],
    }]
    row = {
        "contract_item_id": 41,
        "contract_id": 7,
        "contract_exists": True,
        "contract_company_id": 4,
        "contract_project_id": 17,
        "contract_work_package": "Основная",
        "project_exists": True,
        "project_company_id": 4,
        "legacy_item_key": "base-row",
        "source_type": "estimate",
        "source_estimate_id": 51,
        "source_estimate_version_id": 71,
        "source_section_index": 0,
        "source_item_index": 0,
        "source_item_key": "base-row",
        "snapshot_exists": True,
        "snapshot_version_id": 71,
        "snapshot_estimate_id": 51,
        "snapshot_sections_json": json.dumps(sections, ensure_ascii=False),
        "snapshot_sections_sha256": sections_sha256(sections),
        "estimate_exists": True,
        "estimate_company_id": 4,
        "estimate_project_id": 17,
        "impact_work_package": "Основная",
        "assignment_quantity": 10,
        "confirmed_quantity": 4,
        "journal_count": 3,
        "confirmed_journal_count": 2,
        "hidden_act_count": 1,
        "brigade_act_count": 1,
        "brigade_payment_count": 2,
        "project_payment_count": 1,
        "journal_ids": [101, 102, 103],
        "confirmed_journal_ids": [101, 102],
        "hidden_act_ids": [201],
        "brigade_act_ids": [301],
        "brigade_payment_ids": [401, 402],
        "project_payment_ids": [501],
        "protected_owner_mismatch_count": 0,
        "description": "never expose this text",
        "price_smeta": 900,
        "price_brigade": 700,
    }
    row.update(overrides)
    return row


class AssignmentProjectionContractTests(unittest.TestCase):
    def test_exact_assignment_separates_uncompleted_and_protected_ids(self):
        projection = build_assignment_projection(
            assignment_context(),
            [assignment_row()],
        )

        self.assertEqual(projection["state"], "complete")
        self.assertTrue(projection["complete"])
        self.assertEqual(projection["uncompletedAssignmentIds"], [41])
        self.assertEqual(projection["protectedAssignmentIds"], [41])
        self.assertEqual(projection["protectedHistory"], {
            "workJournal": {
                "count": 3, "ids": [101, 102, 103], "idsTruncated": False,
            },
            "confirmedWorkJournal": {
                "count": 2, "ids": [101, 102], "idsTruncated": False,
            },
            "hiddenActs": {
                "count": 1, "ids": [201], "idsTruncated": False,
            },
            "brigadeActs": {
                "count": 1, "ids": [301], "idsTruncated": False,
            },
            "brigadePayments": {
                "count": 2, "ids": [401, 402], "idsTruncated": False,
            },
            "projectPayments": {
                "count": 1, "ids": [501], "idsTruncated": False,
            },
        })
        self.assertEqual(projection["summary"], {
            "assignmentRows": 1,
            "uncompletedAssignments": 1,
            "protectedAssignments": 1,
            "needsReview": 0,
            "workJournalRows": 3,
            "confirmedWorkJournalRows": 2,
            "hiddenActs": 1,
            "brigadeActs": 1,
            "brigadePayments": 2,
            "projectPayments": 1,
        })

        serialized = json.dumps(projection, ensure_ascii=False)
        for forbidden in (
            "never expose this text", "Работа не должна", "Секция не должна",
            "base-row", "price", "quantity", "sectionsSha256",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_fully_confirmed_assignment_has_no_uncompleted_exposure(self):
        projection = build_assignment_projection(
            assignment_context(),
            [assignment_row(assignment_quantity=4, confirmed_quantity=4)],
        )

        self.assertEqual(projection["uncompletedAssignmentIds"], [])
        self.assertEqual(projection["protectedAssignmentIds"], [41])
        self.assertTrue(projection["complete"])

    def test_e3_lineage_and_e4_balance_failures_become_review(self):
        no_history = {
            "confirmed_quantity": 0,
            "journal_count": 0,
            "confirmed_journal_count": 0,
            "hidden_act_count": 0,
            "brigade_act_count": 0,
            "brigade_payment_count": 0,
            "project_payment_count": 0,
            "journal_ids": [],
            "confirmed_journal_ids": [],
            "hidden_act_ids": [],
            "brigade_act_ids": [],
            "brigade_payment_ids": [],
            "project_payment_ids": [],
        }
        rows = [
            assignment_row(
                **no_history,
                contract_item_id=41,
                source_type="legacy",
                source_estimate_version_id=None,
                source_section_index=None,
                source_item_index=None,
                source_item_key=None,
                snapshot_exists=False,
            ),
            assignment_row(
                **no_history, contract_item_id=42, source_item_key=None,
            ),
            assignment_row(
                **no_history,
                contract_item_id=43,
                snapshot_sections_sha256="0" * 64,
            ),
            assignment_row(
                **no_history,
                contract_item_id=44,
                contract_company_id=5,
                project_company_id=5,
                estimate_company_id=5,
            ),
            assignment_row(
                **{**no_history, "confirmed_quantity": 11},
                contract_item_id=45,
            ),
        ]

        projection = build_assignment_projection(assignment_context(), rows)

        self.assertEqual(projection["state"], "review_required")
        self.assertFalse(projection["complete"])
        self.assertEqual(projection["uncompletedAssignmentIds"], [])
        self.assertEqual(projection["needsReview"], [
            {
                "sourceKind": "assignment",
                "sourceId": 41,
                "reasonCode": "explicit_legacy_source",
            },
            {
                "sourceKind": "assignment",
                "sourceId": 42,
                "reasonCode": "estimate_source_incomplete",
            },
            {
                "sourceKind": "assignment",
                "sourceId": 43,
                "reasonCode": "snapshot_hash_mismatch",
            },
            {
                "sourceKind": "assignment",
                "sourceId": 44,
                "reasonCode": "assignment_owner_mismatch",
            },
            {
                "sourceKind": "assignment",
                "sourceId": 45,
                "reasonCode": "confirmed_quantity_exceeds_assignment",
            },
        ])

    def test_foreign_protected_history_is_reviewed_and_never_exposed(self):
        projection = build_assignment_projection(
            assignment_context(),
            [assignment_row(protected_owner_mismatch_count=1)],
        )

        self.assertEqual(projection["protectedAssignmentIds"], [])
        for history in projection["protectedHistory"].values():
            self.assertEqual(history["count"], 0)
            self.assertEqual(history["ids"], [])
        self.assertEqual(projection["needsReview"], [{
            "sourceKind": "assignment",
            "sourceId": 41,
            "reasonCode": "assignment_protected_history_owner_mismatch",
        }])

    def test_id_previews_are_bounded_and_make_projection_incomplete(self):
        identifiers = list(range(1, PROTECTED_ID_LIMIT + 2))
        projection = build_assignment_projection(
            assignment_context(),
            [assignment_row(
                journal_count=len(identifiers),
                journal_ids=identifiers,
            )],
        )

        journal = projection["protectedHistory"]["workJournal"]
        self.assertEqual(len(journal["ids"]), PROTECTED_ID_LIMIT)
        self.assertTrue(journal["idsTruncated"])
        self.assertEqual(projection["state"], "incomplete")
        self.assertFalse(projection["complete"])


class AssignmentProjectionCollectorTests(unittest.TestCase):
    def test_exact_source_runs_bounded_selects_only(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            ASSIGNMENT_REQUIRED_SCHEMA_ROWS,
            (assignment_row(),),
        ))

        report = collect_assignment_impact_audit(cursor, source())

        self.assertTrue(report["readyForAssignmentProjection"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["assignmentImpact"]["uncompletedAssignmentIds"], [41])
        self.assertEqual(len(cursor.calls), 5)
        for sql, _params in cursor.calls:
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            for mutation in ("INSERT ", "UPDATE ", "DELETE "):
                self.assertNotIn(mutation, normalized)
        assignment_sql, assignment_params = cursor.calls[-1]
        self.assertIn("LIMIT %s", assignment_sql)
        self.assertIn(MAX_ASSIGNMENT_ROWS + 1, assignment_params)
        self.assertNotIn("project_name", assignment_sql.lower())
        self.assertNotIn("description", assignment_sql.lower())
        self.assertNotIn("price_", assignment_sql.lower())

    def test_source_blocker_stops_before_assignment_schema_or_data_scan(self):
        cursor = FakeCursor((REQUIRED_SCHEMA_ROWS, ()))

        report = collect_assignment_impact_audit(cursor, source())

        self.assertFalse(report["readyForAssignmentProjection"])
        self.assertEqual(report["assignmentImpact"]["state"], "not_collected")
        self.assertEqual(len(cursor.calls), 2)

    def test_assignment_scan_limit_is_fail_closed(self):
        rows = tuple(
            assignment_row(contract_item_id=index)
            for index in range(1, MAX_ASSIGNMENT_ROWS + 2)
        )
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            ASSIGNMENT_REQUIRED_SCHEMA_ROWS,
            rows,
        ))

        report = collect_assignment_impact_audit(cursor, source())

        self.assertFalse(report["readyForAssignmentProjection"])
        self.assertFalse(report["assignmentImpact"]["scanComplete"])
        self.assertEqual(report["assignmentImpact"]["reasonCounts"], {
            "assignment_scan_limit_exceeded": 1,
        })


class AssignmentProjectionRunnerTests(unittest.TestCase):
    def test_runner_uses_one_read_only_transaction_and_rolls_back(self):
        cursor = FakeCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            ASSIGNMENT_REQUIRED_SCHEMA_ROWS,
            (assignment_row(),),
        ))
        connection = FakeConnection(cursor)

        report = run_assignment_impact_audit(lambda: connection, source())

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_runner_rolls_back_when_assignment_collection_raises(self):
        class FailingCursor(FakeCursor):
            def execute(self, sql, params=()):
                if len(self.calls) == 3:
                    raise RuntimeError("assignment scan unavailable")
                super().execute(sql, params)

        cursor = FailingCursor((
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
        ))
        connection = FakeConnection(cursor)

        with self.assertRaisesRegex(RuntimeError, "assignment scan unavailable"):
            run_assignment_impact_audit(lambda: connection, source())

        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)

    def test_operator_command_is_additive_and_not_registered_at_runtime(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["audit:estimate-revision-assignment-impact"],
            "python3 -m "
            "backend.features.estimate_revision_impact.assignment_projection",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "assignment_projection",
                (root / relative).read_text(encoding="utf-8"),
            )


A7_TEST_DATABASE_URL = os.getenv("A7_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("A7_RUN_POSTGRES_INTEGRATION") == "1" and A7_TEST_DATABASE_URL,
    "set A7_RUN_POSTGRES_INTEGRATION=1 and A7_TEST_DATABASE_URL",
)
class AssignmentProjectionPostgresTests(unittest.TestCase):
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
                CREATE TABLE IF NOT EXISTS public.estimate_versions (
                    id INTEGER PRIMARY KEY,
                    estimate_id INTEGER,
                    sections_json TEXT,
                    sections_sha256 TEXT
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contracts (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    work_package TEXT
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contract_items (
                    id INTEGER PRIMARY KEY,
                    contract_id INTEGER,
                    estimate_item_key TEXT,
                    work_package TEXT,
                    quantity DOUBLE PRECISION,
                    source_type TEXT,
                    source_estimate_version_id INTEGER,
                    source_section_index INTEGER,
                    source_item_index INTEGER,
                    source_item_key TEXT
                );
                CREATE TABLE IF NOT EXISTS public.work_journal (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    contract_item_id INTEGER,
                    quantity DOUBLE PRECISION,
                    status TEXT
                );
                CREATE TABLE IF NOT EXISTS public.hidden_works_acts (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    work_journal_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.brigade_acts (
                    id INTEGER PRIMARY KEY,
                    contract_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.project_payments (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    company_scope_verified BOOLEAN
                );
                CREATE TABLE IF NOT EXISTS public.brigade_payments (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    contract_id INTEGER,
                    project_payment_id INTEGER
                );
                """
            )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.brigade_payments,public.project_payments,"
                "public.brigade_acts,public.hidden_works_acts,"
                "public.work_journal,public.brigade_contract_items,"
                "public.brigade_contracts,public.estimate_versions,"
                "public.estimate_reconciliations,public.estimates,"
                "public.projects"
            )

    @staticmethod
    def _base_sections():
        return [{
            "name": "Protected fixture text",
            "items": [{
                "name": "Protected work text",
                "estimateItemKey": "base-row",
            }],
        }]

    @staticmethod
    def _target_sections():
        return [{"name": "Next", "items": []}]

    def _seed(self):
        base_sections = self._base_sections()
        target_sections = self._target_sections()
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
                (
                    json.dumps(base_sections), json.dumps(target_sections),
                    json.dumps(base_sections), json.dumps(target_sections),
                ),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,smeta_type,
                      work_package)
                   VALUES
                     (91,51,52,'Черновик','Заказчик','Основная'),
                     (92,61,62,'Черновик','Заказчик','Основная')"""
            )
            cur.execute(
                """INSERT INTO public.estimate_versions
                     (id,estimate_id,sections_json,sections_sha256)
                   VALUES (71,51,%s,%s),(81,61,%s,%s)""",
                (
                    json.dumps(base_sections), sections_sha256(base_sections),
                    json.dumps(base_sections), sections_sha256(base_sections),
                ),
            )
            cur.execute(
                "INSERT INTO public.brigade_contracts"
                "(id,company_id,project_id,work_package) VALUES "
                "(7,4,17,'Основная'),(8,5,18,'Основная')"
            )
            cur.execute(
                """INSERT INTO public.brigade_contract_items
                     (id,contract_id,estimate_item_key,work_package,quantity,
                      source_type,source_estimate_version_id,
                      source_section_index,source_item_index,source_item_key)
                   VALUES
                     (41,7,'base-row','Основная',10,'estimate',71,0,0,'base-row'),
                     (42,8,'base-row','Основная',20,'estimate',81,0,0,'base-row')"""
            )
            cur.execute(
                """INSERT INTO public.work_journal
                     (id,company_id,contract_item_id,quantity,status)
                   VALUES
                     (101,4,41,4,'Подтверждено'),
                     (102,4,41,1,'На проверке'),
                     (111,5,42,3,'Подтверждено')"""
            )
            cur.execute(
                "INSERT INTO public.hidden_works_acts"
                "(id,company_id,work_journal_id) VALUES "
                "(201,4,101),(211,5,111)"
            )
            cur.execute(
                "INSERT INTO public.brigade_acts(id,contract_id) VALUES "
                "(301,7),(311,8)"
            )
            cur.execute(
                "INSERT INTO public.project_payments"
                "(id,company_id,company_scope_verified) VALUES "
                "(501,4,TRUE),(511,5,TRUE)"
            )
            cur.execute(
                "INSERT INTO public.brigade_payments"
                "(id,company_id,contract_id,project_payment_id) VALUES "
                "(401,4,7,501),(411,5,8,511)"
            )
        return build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=target_sections,
        )

    def _protected_snapshot(self):
        tables = (
            "brigade_contract_items",
            "work_journal",
            "hidden_works_acts",
            "brigade_acts",
            "brigade_payments",
            "project_payments",
        )
        snapshot = {}
        with self.admin.cursor() as cur:
            for table in tables:
                cur.execute("SELECT * FROM public." + table + " ORDER BY id")
                snapshot[table] = cur.fetchall()
        return snapshot

    def test_same_name_tenant_isolation_and_unchanged_protected_snapshots(self):
        exact_source = self._seed()
        before = self._protected_snapshot()

        ready = run_assignment_impact_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL),
            exact_source,
        )

        self.assertTrue(ready["readyForAssignmentProjection"])
        impact = ready["assignmentImpact"]
        self.assertEqual(impact["uncompletedAssignmentIds"], [41])
        self.assertEqual(impact["protectedAssignmentIds"], [41])
        self.assertEqual(impact["protectedHistory"]["workJournal"]["ids"], [101, 102])
        self.assertEqual(impact["protectedHistory"]["hiddenActs"]["ids"], [201])
        self.assertEqual(impact["protectedHistory"]["brigadeActs"]["ids"], [301])
        self.assertEqual(impact["protectedHistory"]["brigadePayments"]["ids"], [401])
        self.assertEqual(impact["protectedHistory"]["projectPayments"]["ids"], [501])
        exposed_ids = set(impact["uncompletedAssignmentIds"])
        exposed_ids.update(impact["protectedAssignmentIds"])
        for history in impact["protectedHistory"].values():
            exposed_ids.update(history["ids"])
        self.assertTrue(exposed_ids.isdisjoint({42, 111, 211, 311, 411, 511}))
        self.assertNotIn("Одинаковый объект", json.dumps(ready, ensure_ascii=False))
        self.assertEqual(self._protected_snapshot(), before)

        with self.admin.cursor() as cur:
            cur.execute(
                """INSERT INTO public.brigade_contract_items
                     (id,contract_id,estimate_item_key,work_package,quantity,
                      source_type,source_estimate_version_id,
                      source_section_index,source_item_index,source_item_key)
                   VALUES (43,7,'legacy-row','Основная',2,'legacy',NULL,NULL,NULL,NULL)"""
            )
        blocker_before = self._protected_snapshot()

        blocked = run_assignment_impact_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL),
            exact_source,
        )

        self.assertFalse(blocked["readyForAssignmentProjection"])
        self.assertIn({
            "sourceKind": "assignment",
            "sourceId": 43,
            "reasonCode": "explicit_legacy_source",
        }, blocked["assignmentImpact"]["needsReview"])
        self.assertEqual(self._protected_snapshot(), blocker_before)


if __name__ == "__main__":
    unittest.main()
