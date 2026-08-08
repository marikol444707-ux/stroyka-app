import json
import os
import unittest

import psycopg2

from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    MAX_DOMAIN_ROWS,
    SUPPLY_WAREHOUSE_REQUIRED_COLUMNS,
    collect_supply_warehouse_impact_audit,
    run_supply_warehouse_impact_audit,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    REQUIRED_SCHEMA_ROWS,
    estimate_row,
    reconciliation_row,
)
from backend.features.estimate_revision_impact.test_supply_warehouse_projection import (
    allocation_row,
    context,
    delivery_row,
    history_row,
    lot_movement_row,
    lot_row,
    movement_row,
    request_item,
    request_row,
    supplier_invoice_row,
    warehouse_invoice_row,
)


def source():
    return build_estimate_revision_source(
        company_id=4,
        project_id=17,
        estimate_id=52,
        version="v2.0",
        sections=[{"name": "Работы", "items": []}],
    )


SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in SUPPLY_WAREHOUSE_REQUIRED_COLUMNS.items()
    for column in columns
)


class SupplyWarehouseProjectionCollectorTests(unittest.TestCase):
    def result_sets(self):
        return (
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            SUPPLY_WAREHOUSE_REQUIRED_SCHEMA_ROWS,
            ({
                "project_name": "Private project",
                "owner_count": 1,
                "base_work_package": "Основная",
                "base_sections_json": json.dumps(context()["baseSections"]),
            },),
            (request_row(),),
            (delivery_row(),),
            (allocation_row(),),
            (supplier_invoice_row(),),
            (warehouse_invoice_row(),),
            (history_row(),),
            (lot_row(),),
            (movement_row(),),
            (lot_movement_row(),),
        )

    def test_exact_source_runs_bounded_parameterized_selects_only(self):
        cursor = FakeCursor(self.result_sets())

        report = collect_supply_warehouse_impact_audit(cursor, source())

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["supplyWarehouseImpact"]["openSupply"][0]["requestId"], 61)
        self.assertEqual(len(cursor.calls), 14)
        for index, (sql, params) in enumerate(cursor.calls):
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            for mutation in ("INSERT ", "UPDATE ", "DELETE "):
                self.assertNotIn(mutation, normalized)
            if index >= 5:
                self.assertIn("LIMIT %s", sql)
                self.assertIn(MAX_DOMAIN_ROWS + 1, params)

    def test_runner_uses_one_read_only_transaction_and_rolls_back(self):
        cursor = FakeCursor(self.result_sets())
        connection = FakeConnection(cursor)

        report = run_supply_warehouse_impact_audit(
            lambda: connection, source(),
        )

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_operator_command_is_additive_and_not_registered_at_runtime(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["audit:estimate-revision-supply-warehouse-impact"],
            "python3 -m backend.features.estimate_revision_impact."
            "supply_warehouse_audit",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "supply_warehouse_audit",
                (root / relative).read_text(encoding="utf-8"),
            )


A7_TEST_DATABASE_URL = os.getenv("A7_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("A7_RUN_POSTGRES_INTEGRATION") == "1" and A7_TEST_DATABASE_URL,
    "set A7_RUN_POSTGRES_INTEGRATION=1 and A7_TEST_DATABASE_URL",
)
class SupplyWarehouseProjectionPostgresTests(unittest.TestCase):
    TABLES = (
        "supply_requests",
        "supply_deliveries",
        "estimate_row_supply_allocations",
        "supplier_invoices",
        "warehouse_invoices",
        "warehouse_history",
        "warehouse_receipt_lots",
        "warehouse_movements",
        "warehouse_lot_movements",
    )

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
                CREATE TABLE IF NOT EXISTS public.supply_requests (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project TEXT,
                    status TEXT,
                    work_package TEXT,
                    items_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supply_deliveries (
                    id INTEGER PRIMARY KEY,
                    request_id INTEGER,
                    company_id INTEGER,
                    project TEXT,
                    work_package TEXT,
                    material_name TEXT,
                    unit TEXT,
                    received_quantity NUMERIC(14,6)
                );
                CREATE TABLE IF NOT EXISTS public.estimate_row_supply_allocations (
                    id INTEGER PRIMARY KEY,
                    request_id INTEGER,
                    request_item_index INTEGER,
                    company_id INTEGER,
                    source_estimate_id INTEGER,
                    source_section_index INTEGER,
                    source_item_index INTEGER,
                    allocation_quantity NUMERIC(14,6)
                );
                CREATE TABLE IF NOT EXISTS public.supplier_invoices (
                    id INTEGER PRIMARY KEY,
                    request_id INTEGER,
                    company_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_invoices (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    supply_request_id INTEGER,
                    supply_delivery_id INTEGER,
                    supplier_invoice_id INTEGER,
                    project TEXT,
                    items TEXT
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_history (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    work_package TEXT,
                    source_invoice_id INTEGER,
                    source_invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_receipt_lots (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    project_id INTEGER,
                    warehouse_invoice_id INTEGER,
                    invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_movements (
                    id INTEGER PRIMARY KEY,
                    company_id INTEGER,
                    work_package TEXT,
                    source_invoice_id INTEGER,
                    source_invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_lot_movements (
                    id INTEGER PRIMARY KEY,
                    lot_id INTEGER,
                    company_id INTEGER,
                    warehouse_movement_id INTEGER
                );
                """
            )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.warehouse_lot_movements,"
                "public.warehouse_movements,public.warehouse_receipt_lots,"
                "public.warehouse_history,public.warehouse_invoices,"
                "public.supplier_invoices,"
                "public.estimate_row_supply_allocations,"
                "public.supply_deliveries,public.supply_requests,"
                "public.estimate_reconciliations,public.estimates,"
                "public.projects CASCADE"
            )

    def _seed(self):
        base_sections = context()["baseSections"]
        target_sections = [{"name": "Target", "items": []}]
        item = request_item()
        item["estimateLineage"]["projectName"] = "Одинаковый объект"
        foreign_item = request_item()
        foreign_item["estimateLineage"]["projectName"] = "Одинаковый объект"
        foreign_item["estimateLineage"]["companyId"] = 5
        foreign_item["estimateLineage"]["projectId"] = 18
        foreign_item["estimateLineage"]["sources"][0]["estimateId"] = 61
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
                tuple(json.dumps(value, ensure_ascii=False) for value in (
                    base_sections, target_sections, base_sections, target_sections,
                )),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,smeta_type,work_package)
                   VALUES (91,51,52,'Черновик','Заказчик','Основная'),
                          (92,61,62,'Черновик','Заказчик','Основная')"""
            )
            cur.execute(
                """INSERT INTO public.supply_requests
                     (id,company_id,project,status,work_package,items_json)
                   VALUES (61,4,'Одинаковый объект','Новая','Основная',%s),
                          (62,5,'Одинаковый объект','Новая','Основная',%s)""",
                (
                    json.dumps([item], ensure_ascii=False),
                    json.dumps([foreign_item], ensure_ascii=False),
                ),
            )
            for company_id, offset, request_id, project_id in (
                (4, 0, 61, 17), (5, 1000, 62, 18),
            ):
                cur.execute(
                    """INSERT INTO public.supply_deliveries
                         (id,request_id,company_id,project,work_package,
                          material_name,unit,received_quantity)
                       VALUES (%s,%s,%s,'Одинаковый объект','Основная',
                               'Private material','кг',3)""",
                    (71 + offset, request_id, company_id),
                )
                cur.execute(
                    """INSERT INTO public.estimate_row_supply_allocations
                         (id,request_id,request_item_index,company_id,
                          source_estimate_id,source_section_index,
                          source_item_index,allocation_quantity)
                       VALUES (%s,%s,0,%s,%s,0,0,2)""",
                    (81 + offset, request_id, company_id, 51 if company_id == 4 else 61),
                )
                cur.execute(
                    "INSERT INTO public.supplier_invoices(id,request_id,company_id) "
                    "VALUES (%s,%s,%s)",
                    (91 + offset, request_id, company_id),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_invoices
                         (id,company_id,supply_request_id,supply_delivery_id,
                          supplier_invoice_id,project,items)
                       VALUES (%s,%s,%s,%s,%s,'Одинаковый объект',%s)""",
                    (
                        101 + offset, company_id, request_id, 71 + offset,
                        91 + offset,
                        json.dumps([{"name": "Private material"}]),
                    ),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_history
                         (id,company_id,work_package,source_invoice_id,
                          source_invoice_line_index)
                       VALUES (%s,%s,'Основная',%s,0)""",
                    (111 + offset, company_id, 101 + offset),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_receipt_lots
                         (id,company_id,project_id,warehouse_invoice_id,
                          invoice_line_index)
                       VALUES (%s,%s,%s,%s,0)""",
                    (121 + offset, company_id, project_id, 101 + offset),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_movements
                         (id,company_id,work_package,source_invoice_id,
                          source_invoice_line_index)
                       VALUES (%s,%s,'Основная',%s,0)""",
                    (131 + offset, company_id, 101 + offset),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_lot_movements
                         (id,lot_id,company_id,warehouse_movement_id)
                       VALUES (%s,%s,%s,%s)""",
                    (141 + offset, 121 + offset, company_id, 131 + offset),
                )
        return build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=target_sections,
        )

    def _snapshot(self):
        result = {}
        with self.admin.cursor() as cur:
            for table in self.TABLES:
                cur.execute(
                    "SELECT row_to_json(t)::text FROM public." + table
                    + " t ORDER BY id"
                )
                result[table] = [row[0] for row in cur.fetchall()]
        return result

    def test_same_name_tenant_isolation_and_protected_rows_unchanged(self):
        exact_source = self._seed()
        before = self._snapshot()

        report = run_supply_warehouse_impact_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL), exact_source,
        )

        self.assertTrue(report["readyForSupplyWarehouseProjection"])
        self.assertEqual(report["supplyWarehouseImpact"]["openSupply"][0]["requestId"], 61)
        self.assertEqual(
            report["supplyWarehouseImpact"]["protectedEvidence"],
            {
                "closedSupplyRequestIds": [],
                "deliveryIds": [71],
                "allocationIds": [81],
                "supplierInvoiceIds": [91],
                "warehouseInvoiceIds": [101],
                "warehouseHistoryIds": [111],
                "receiptLotIds": [121],
                "warehouseMovementIds": [131],
                "lotMovementIds": [141],
            },
        )
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])



if __name__ == "__main__":
    unittest.main()
