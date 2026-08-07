import ast
import hashlib
import json
import os
import sys
import threading
import types
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

import psycopg2
import psycopg2.extras

from backend.features.material_control_ownership.readiness_report import (
    run_readiness_report,
)
from backend.features.supply_lineage.service import (
    MATERIAL_CONTROL_REQUEST_SOURCE,
)


POSTGRES_TEST_DSN = os.getenv("E5_TEST_DATABASE_URL", "")
PROTECTED_HISTORY_TABLES = (
    "work_journal",
    "hidden_works_acts",
    "warehouse_history",
    "project_payments",
    "supply_deliveries",
    "supplier_offers",
    "supplier_invoices",
    "warehouse_invoices",
)
FIXTURE_TABLES = (
    "supply_requests",
    "materials",
    "material_transfers",
    *PROTECTED_HISTORY_TABLES,
    "estimates",
    "projects",
)


def _load_main_without_startup():
    """Load exact runtime functions without legacy import-time schema writes."""

    main_path = Path(__file__).resolve().parents[2] / "main.py"
    source = main_path.read_text(encoding="utf-8").replace(
        "int | None",
        "Optional[int]",
    )
    tree = ast.parse(source, filename=str(main_path))

    def startup_call(statement):
        return isinstance(statement, ast.Expr) and isinstance(
            statement.value,
            ast.Call,
        )

    tree.body = [statement for statement in tree.body if not startup_call(statement)]
    ast.fix_missing_locations(tree)
    module_name = "backend._e5_material_control_runtime"
    module = types.ModuleType(module_name)
    module.__file__ = str(main_path)
    module.__package__ = "backend"
    sys.modules[module_name] = module
    exec(compile(tree, str(main_path), "exec"), module.__dict__)
    return module


@unittest.skipUnless(
    os.getenv("E5_RUN_POSTGRES_INTEGRATION") == "1" and POSTGRES_TEST_DSN,
    "set E5_RUN_POSTGRES_INTEGRATION=1 and E5_TEST_DATABASE_URL for PostgreSQL fixture",
)
class MaterialControlOwnershipPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg2.connect(POSTGRES_TEST_DSN)
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            database_name = cur.fetchone()[0]
            if not str(database_name).startswith("e5_"):
                raise RuntimeError(
                    "E5 integration fixture requires a dedicated e5_* database"
                )
        cls.main = _load_main_without_startup()
        with cls.admin.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.projects (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER,
                    name TEXT,
                    archived BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS public.estimates (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    project_name TEXT,
                    name TEXT,
                    smeta_type TEXT,
                    work_package TEXT,
                    status TEXT,
                    is_template BOOLEAN DEFAULT FALSE,
                    sections_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supply_requests (
                    id SERIAL PRIMARY KEY,
                    material_name TEXT,
                    quantity NUMERIC,
                    unit TEXT,
                    project TEXT,
                    company_id INTEGER,
                    work_package TEXT,
                    created_by TEXT,
                    date TEXT,
                    notes TEXT,
                    selected_suppliers INTEGER[],
                    status TEXT,
                    requested_by_role TEXT,
                    requested_by_id INTEGER,
                    urgency TEXT,
                    category TEXT,
                    prorab_id INTEGER,
                    prorab_name TEXT,
                    prorab_confirmed_at TIMESTAMP,
                    director_id INTEGER,
                    director_name TEXT,
                    director_approved_at TIMESTAMP,
                    items_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.materials (
                    id SERIAL PRIMARY KEY,
                    project TEXT,
                    work_package TEXT,
                    name TEXT,
                    unit TEXT,
                    quantity NUMERIC
                );
                CREATE TABLE IF NOT EXISTS public.material_transfers (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    work_package TEXT,
                    status TEXT,
                    material_name TEXT,
                    unit TEXT,
                    quantity NUMERIC,
                    signed BOOLEAN DEFAULT FALSE
                );
                CREATE TABLE IF NOT EXISTS public.work_journal (
                    id SERIAL PRIMARY KEY,
                    project TEXT,
                    work_package TEXT,
                    status TEXT,
                    materials_used TEXT,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.hidden_works_acts (
                    id SERIAL PRIMARY KEY,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_history (
                    id SERIAL PRIMARY KEY,
                    project TEXT,
                    work_package TEXT,
                    type TEXT,
                    material TEXT,
                    unit TEXT,
                    quantity NUMERIC,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.project_payments (
                    id SERIAL PRIMARY KEY,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supply_deliveries (
                    id SERIAL PRIMARY KEY,
                    request_id INTEGER,
                    status TEXT,
                    material_name TEXT,
                    unit TEXT,
                    received_quantity NUMERIC,
                    work_package TEXT,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supplier_offers (
                    id SERIAL PRIMARY KEY,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supplier_invoices (
                    id SERIAL PRIMARY KEY,
                    e5_marker TEXT
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_invoices (
                    id SERIAL PRIMARY KEY,
                    e5_marker TEXT
                );
                """
            )
            for table in PROTECTED_HISTORY_TABLES:
                cur.execute(
                    "ALTER TABLE public."
                    + table
                    + " ADD COLUMN IF NOT EXISTS e5_marker TEXT"
                )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE "
                + ",".join("public." + table for table in FIXTURE_TABLES)
                + " RESTART IDENTITY CASCADE"
            )

    def tearDown(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE "
                + ",".join("public." + table for table in FIXTURE_TABLES)
                + " RESTART IDENTITY CASCADE"
            )

    def _snapshot(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT id,company_id,name,archived FROM public.projects ORDER BY id"
            )
            projects = cur.fetchall()
            cur.execute(
                """SELECT id,company_id,project_id,project_name,smeta_type,
                          work_package,status,is_template,sections_json
                     FROM public.estimates ORDER BY id"""
            )
            estimates = cur.fetchall()
        return projects, estimates

    def _protected_history_sha256(self):
        snapshot = {}
        with self.admin.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            for table in PROTECTED_HISTORY_TABLES:
                cur.execute("SELECT * FROM public." + table + " ORDER BY id")
                snapshot[table] = [dict(row) for row in cur.fetchall()]
        payload = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _seed_protected_history(self, marker):
        with self.admin.cursor() as cur:
            cur.execute(
                """INSERT INTO public.work_journal(
                       project,work_package,status,materials_used,e5_marker
                   ) VALUES ('История','Основная','Принято','[]',%s)""",
                (marker,),
            )
            cur.execute(
                """INSERT INTO public.warehouse_history(
                       project,work_package,type,material,unit,quantity,e5_marker
                   ) VALUES ('История','Основная','Приход','Маркер','шт',1,%s)""",
                (marker,),
            )
            cur.execute(
                """INSERT INTO public.supply_deliveries(
                       request_id,status,material_name,unit,received_quantity,
                       work_package,e5_marker
                   ) VALUES (999,'Получено','Маркер','шт',1,'Основная',%s)""",
                (marker,),
            )
            for table in (
                "hidden_works_acts",
                "project_payments",
                "supplier_offers",
                "supplier_invoices",
                "warehouse_invoices",
            ):
                cur.execute(
                    "INSERT INTO public." + table + "(e5_marker) VALUES (%s)",
                    (marker,),
                )

    def _insert_owner_fixture(self, company_id, project_name, planned_qty):
        sections = [{
            "name": "Раздел",
            "items": [
                {
                    "itemType": "work",
                    "name": "Монтаж перегородки",
                    "quantity": 1,
                    "unit": "м2",
                    "priceWork": 100,
                },
                {
                    "itemType": "material",
                    "name": "Грунтовка",
                    "quantity": planned_qty,
                    "unit": "кг",
                    "priceMaterial": 2,
                },
            ],
        }]
        with self.admin.cursor() as cur:
            cur.execute(
                """INSERT INTO public.projects(company_id,name,archived)
                     VALUES (%s,%s,FALSE) RETURNING id""",
                (company_id, project_name),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates(
                       company_id,project_id,project_name,name,smeta_type,
                       work_package,status,is_template,sections_json
                   ) VALUES (%s,%s,%s,%s,'Заказчик','Основная','Активная',FALSE,%s)
                   RETURNING id""",
                (
                    company_id,
                    project_id,
                    project_name,
                    "Смета " + str(company_id),
                    json.dumps(sections, ensure_ascii=False),
                ),
            )
            estimate_id = cur.fetchone()[0]
        return {
            "companyId": company_id,
            "projectId": project_id,
            "projectName": project_name,
            "estimateId": estimate_id,
            "plannedQty": planned_qty,
        }

    def _request_model(self, fixture, *, source_fixture=None):
        source = source_fixture or fixture
        return self.main.SupplyRequestModel(
            project=fixture["projectName"],
            companyId=fixture["companyId"],
            projectId=fixture["projectId"],
            workPackage="Основная",
            date="2026-08-07",
            requestSource=MATERIAL_CONTROL_REQUEST_SOURCE,
            items=[{
                "materialName": "Грунтовка",
                "quantity": 1,
                "unit": "кг",
                "workPackage": "Основная",
                "sourceType": MATERIAL_CONTROL_REQUEST_SOURCE,
                "estimateLineage": {
                    "version": 2,
                    "companyId": fixture["companyId"],
                    "projectId": fixture["projectId"],
                    "projectName": fixture["projectName"],
                    "workPackage": "Основная",
                    "sources": [{
                        "estimateId": source["estimateId"],
                        "sectionIndex": 0,
                        "itemIndex": 1,
                        "sectionName": "Раздел",
                        "materialName": "Грунтовка",
                        "unit": "кг",
                        "quantity": source["plannedQty"],
                    }],
                },
            }],
        )

    @contextmanager
    def _patched_supply_runtime(self, barrier=None):
        def company_context(
            _cur,
            _current_user,
            requested_company_id,
            _operation,
            **_kwargs,
        ):
            if barrier is not None:
                barrier.wait(timeout=15)
            return {"companyId": int(requested_company_id)}

        def material_key(_cur, _project, name, unit):
            return (
                str(name or "").strip().casefold(),
                self.main._norm_base_unit(unit or ""),
            )

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                self.main,
                "get_db",
                side_effect=lambda: psycopg2.connect(POSTGRES_TEST_DSN),
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "_ensure_supply_runtime_columns",
                side_effect=lambda _cur: None,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "_resolve_work_company_context",
                side_effect=company_context,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "require_project_or_warehouse_access",
                side_effect=lambda *_args, **_kwargs: None,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "has_package_access",
                return_value=True,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "supplier_group_scope_ids",
                side_effect=lambda _cur, values: list(values or []),
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "_material_control_key_resolved",
                side_effect=material_key,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "_attach_supply_estimate_control",
                side_effect=lambda _cur, _project, items, **_kwargs: items,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "_enforce_supply_estimate_control",
                side_effect=lambda *_args, **_kwargs: None,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "_supply_response_for_role",
                side_effect=lambda row, _user: dict(row),
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "log_audit",
                side_effect=lambda *_args, **_kwargs: None,
            ))
            stack.enter_context(mock.patch.object(
                self.main,
                "SUPPLY_SELECT",
                "SELECT id,company_id,project,status,items_json FROM supply_requests",
            ))
            yield

    def _create_request(self, model):
        return self.main.create_supply_request(
            model,
            _current_user={
                "id": 701,
                "name": "E5 integration",
                "role": "директор",
            },
        )

    def test_same_name_cross_company_fixture_is_ready_and_unchanged(self):
        collision_name = "e5-collision-" + uuid.uuid4().hex
        self._insert_owner_fixture(10, collision_name, 10)
        self._insert_owner_fixture(20, collision_name, 20)
        before = self._snapshot()

        report = run_readiness_report(
            lambda: psycopg2.connect(POSTGRES_TEST_DSN),
            collect_inventory=lambda: {
                "ok": True,
                "runtimeInventoryReady": True,
            },
        )

        self.assertTrue(report["readyForCutover"], report)
        self.assertTrue(report["rolledBack"])
        self.assertTrue(report["writerInventoryReady"])
        self.assertEqual(
            report["dataAudit"]["summary"]["nameCollisionGroups"], 1
        )
        self.assertEqual(before, self._snapshot())
        self.assertNotIn(collision_name, json.dumps(report, ensure_ascii=False))

    def test_zz_same_name_runtime_queries_are_owner_isolated(self):
        collision_name = "e5-runtime-" + uuid.uuid4().hex
        left = self._insert_owner_fixture(10, collision_name, 10)
        right = self._insert_owner_fixture(20, collision_name, 20)
        before = self._snapshot()
        conn = psycopg2.connect(POSTGRES_TEST_DSN)
        conn.set_session(
            readonly=True,
            autocommit=False,
            isolation_level="REPEATABLE READ",
        )
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            with mock.patch.object(
                self.main,
                "_material_control_key_resolved",
                side_effect=lambda _cur, _project, name, unit: (
                    str(name or "").strip().casefold(),
                    self.main._norm_base_unit(unit or ""),
                ),
            ):
                left_material = self.main._supply_material_estimate_control(
                    cur,
                    {
                        "companyId": left["companyId"],
                        "id": left["projectId"],
                        "name": left["projectName"],
                    },
                    "Грунтовка",
                    "кг",
                    "Основная",
                )
                right_material = self.main._supply_material_estimate_control(
                    cur,
                    {
                        "companyId": right["companyId"],
                        "id": right["projectId"],
                        "name": right["projectName"],
                    },
                    "Грунтовка",
                    "кг",
                    "Основная",
                )
                left_work = self.main._supply_linked_work_estimate_control(
                    cur,
                    {
                        "companyId": left["companyId"],
                        "id": left["projectId"],
                        "name": left["projectName"],
                    },
                    {"parentWorkName": "Монтаж перегородки"},
                    "Основная",
                )
                right_work = self.main._supply_linked_work_estimate_control(
                    cur,
                    {
                        "companyId": right["companyId"],
                        "id": right["projectId"],
                        "name": right["projectName"],
                    },
                    {"parentWorkName": "Монтаж перегородки"},
                    "Основная",
                )
            conn.rollback()
        finally:
            conn.close()

        self.assertEqual(left_material["plannedQty"], 10)
        self.assertEqual(right_material["plannedQty"], 20)
        self.assertEqual(left_material["estimateCount"], 1)
        self.assertEqual(right_material["estimateCount"], 1)
        self.assertEqual(left_work["estimateId"], left["estimateId"])
        self.assertEqual(right_work["estimateId"], right["estimateId"])
        self.assertEqual(before, self._snapshot())

    def test_zzz_foreign_lineage_rolls_back_without_protected_history_changes(self):
        collision_name = "e5-foreign-" + uuid.uuid4().hex
        left = self._insert_owner_fixture(10, collision_name, 10)
        right = self._insert_owner_fixture(20, collision_name, 20)
        self._seed_protected_history("foreign-lineage")
        history_before = self._protected_history_sha256()
        with self.admin.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.supply_requests")
            request_count_before = cur.fetchone()[0]

        with self._patched_supply_runtime():
            with self.assertRaises(self.main.HTTPException) as raised:
                self._create_request(
                    self._request_model(left, source_fixture=right)
                )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(history_before, self._protected_history_sha256())
        with self.admin.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.supply_requests")
            self.assertEqual(cur.fetchone()[0], request_count_before)

    def test_zzzz_concurrent_lineage_requests_serialize_without_duplicate(self):
        fixture = self._insert_owner_fixture(
            10,
            "e5-concurrent-" + uuid.uuid4().hex,
            10,
        )
        self._seed_protected_history("concurrent-lineage")
        history_before = self._protected_history_sha256()
        barrier = threading.Barrier(2)

        def submit():
            try:
                response = self._create_request(self._request_model(fixture))
                return ("created", int(response["id"]))
            except self.main.HTTPException as exc:
                return ("rejected", int(exc.status_code))

        with self._patched_supply_runtime(barrier=barrier):
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = [
                    future.result(timeout=30)
                    for future in (executor.submit(submit), executor.submit(submit))
                ]

        self.assertEqual(sorted(state for state, _value in outcomes), [
            "created",
            "rejected",
        ])
        self.assertEqual(
            [value for state, value in outcomes if state == "rejected"],
            [409],
        )
        with self.admin.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.supply_requests")
            self.assertEqual(cur.fetchone()[0], 1)
        self.assertEqual(history_before, self._protected_history_sha256())

    def test_zzzzz_final_cutover_report_is_read_only_and_exact(self):
        collision_name = "e5-final-" + uuid.uuid4().hex
        self._insert_owner_fixture(10, collision_name, 10)
        self._insert_owner_fixture(20, collision_name, 20)
        self._seed_protected_history("final-readiness")
        before = (self._snapshot(), self._protected_history_sha256())

        report = run_readiness_report(
            lambda: psycopg2.connect(POSTGRES_TEST_DSN)
        )

        self.assertTrue(report["readyForCutover"], report)
        self.assertTrue(report["dataReady"])
        self.assertTrue(report["runtimeInventoryReady"])
        self.assertTrue(report["writerInventoryReady"])
        self.assertEqual(report["writerInventory"]["dmlStatements"], 5)
        self.assertEqual(
            report["writerInventory"]["requiredIntegrationChecks"], 5
        )
        self.assertEqual(
            report["writerInventory"]["missingIntegrationChecks"], []
        )
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(before, (
            self._snapshot(),
            self._protected_history_sha256(),
        ))
        self.assertNotIn(collision_name, json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
