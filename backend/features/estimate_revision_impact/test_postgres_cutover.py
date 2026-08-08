import hashlib
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

import psycopg2

from backend.features.agent_jobs.handler_registry import AgentJobHandlerRegistry
from backend.features.agent_jobs.runner import AgentJobRunner, AgentJobRunnerConfig
from backend.features.agent_jobs.schema import ensure_agent_jobs_schema
from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.handler import (
    build_estimate_revision_impact_handler,
)
from backend.features.estimate_revision_impact.handoff import (
    handoff_estimate_revision_impact_transition,
)
from backend.features.estimate_revision_impact.job_contract import JOB_TYPE
from backend.features.estimate_revision_impact.producer import (
    prepare_estimate_revision_impact_job,
    run_estimate_revision_impact_producer,
)
from backend.features.estimate_revision_impact.readiness_report import (
    run_readiness_report,
)


A7_TEST_DATABASE_URL = os.getenv("A7_TEST_DATABASE_URL", "")


class NoopHeartbeat:
    lost_lease = False

    def __init__(self, **_kwargs):
        pass

    def start(self):
        pass

    def stop(self):
        pass


@unittest.skipUnless(
    os.getenv("A7_RUN_POSTGRES_INTEGRATION") == "1" and A7_TEST_DATABASE_URL,
    "set A7_RUN_POSTGRES_INTEGRATION=1 and A7_TEST_DATABASE_URL",
)
class EstimateRevisionImpactCutoverPostgresTests(unittest.TestCase):
    BUSINESS_TABLES = (
        "project_budget_adjustments",
        "warehouse_lot_movements",
        "warehouse_movements",
        "warehouse_receipt_lots",
        "warehouse_history",
        "warehouse_invoices",
        "supplier_invoices",
        "estimate_row_supply_allocations",
        "supply_deliveries",
        "supply_requests",
        "material_aliases",
        "brigade_payments",
        "project_payments",
        "brigade_acts",
        "hidden_works_acts",
        "work_journal",
        "brigade_contract_items",
        "brigade_contracts",
        "estimate_versions",
        "estimate_reconciliations",
        "estimates",
        "projects",
    )
    SECTIONS = [{"name": "Private fixture", "items": []}]

    @classmethod
    def connection(cls):
        return psycopg2.connect(A7_TEST_DATABASE_URL)

    @classmethod
    def setUpClass(cls):
        cls.admin = cls.connection()
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
                    id INTEGER PRIMARY KEY, company_id INTEGER, name TEXT,
                    budget NUMERIC(14,2)
                );
                CREATE TABLE IF NOT EXISTS public.estimates (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    project_id INTEGER, version TEXT, sections_json TEXT,
                    status TEXT, is_template BOOLEAN, smeta_type TEXT,
                    work_package TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimate_reconciliations (
                    id INTEGER PRIMARY KEY, base_estimate_id INTEGER,
                    next_estimate_id INTEGER, status TEXT, smeta_type TEXT,
                    work_package TEXT, base_total NUMERIC(14,2),
                    next_total NUMERIC(14,2)
                );
                CREATE TABLE IF NOT EXISTS public.estimate_versions (
                    id INTEGER PRIMARY KEY, estimate_id INTEGER,
                    sections_json TEXT, sections_sha256 TEXT
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contracts (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    project_id INTEGER, work_package TEXT
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contract_items (
                    id INTEGER PRIMARY KEY, contract_id INTEGER,
                    estimate_item_key TEXT, work_package TEXT,
                    quantity DOUBLE PRECISION, source_type TEXT,
                    source_estimate_version_id INTEGER,
                    source_section_index INTEGER, source_item_index INTEGER,
                    source_item_key TEXT
                );
                CREATE TABLE IF NOT EXISTS public.work_journal (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    contract_item_id INTEGER, quantity DOUBLE PRECISION,
                    status TEXT
                );
                CREATE TABLE IF NOT EXISTS public.hidden_works_acts (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    work_journal_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.brigade_acts (
                    id INTEGER PRIMARY KEY, contract_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.project_payments (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    company_scope_verified BOOLEAN
                );
                CREATE TABLE IF NOT EXISTS public.brigade_payments (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    contract_id INTEGER, project_payment_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.material_aliases (
                    id INTEGER PRIMARY KEY, project_name TEXT,
                    alias_name TEXT, canonical_name TEXT,
                    canonical_unit TEXT, active BOOLEAN
                );
                CREATE TABLE IF NOT EXISTS public.supply_requests (
                    id INTEGER PRIMARY KEY, company_id INTEGER, project TEXT,
                    status TEXT, work_package TEXT, items_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supply_deliveries (
                    id INTEGER PRIMARY KEY, request_id INTEGER,
                    company_id INTEGER, project TEXT, work_package TEXT,
                    material_name TEXT, unit TEXT,
                    received_quantity NUMERIC(14,6)
                );
                CREATE TABLE IF NOT EXISTS public.estimate_row_supply_allocations (
                    id INTEGER PRIMARY KEY, request_id INTEGER,
                    request_item_index INTEGER, company_id INTEGER,
                    source_estimate_id INTEGER, source_section_index INTEGER,
                    source_item_index INTEGER,
                    allocation_quantity NUMERIC(14,6)
                );
                CREATE TABLE IF NOT EXISTS public.supplier_invoices (
                    id INTEGER PRIMARY KEY, request_id INTEGER,
                    company_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_invoices (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    supply_request_id INTEGER, supply_delivery_id INTEGER,
                    supplier_invoice_id INTEGER, project TEXT, items TEXT
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_history (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    work_package TEXT, source_invoice_id INTEGER,
                    source_invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_receipt_lots (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    project_id INTEGER, warehouse_invoice_id INTEGER,
                    invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_movements (
                    id INTEGER PRIMARY KEY, company_id INTEGER,
                    work_package TEXT, source_invoice_id INTEGER,
                    source_invoice_line_index INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_lot_movements (
                    id INTEGER PRIMARY KEY, lot_id INTEGER,
                    company_id INTEGER, warehouse_movement_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.project_budget_adjustments (
                    id INTEGER PRIMARY KEY, reconciliation_id INTEGER
                );
                """
            )
        ensure_agent_jobs_schema(cls.connection)

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.agent_jobs," + ",".join(
                    "public." + table for table in self.BUSINESS_TABLES
                ) + " CASCADE"
            )
            encoded = json.dumps(self.SECTIONS, ensure_ascii=False)
            cur.execute(
                "INSERT INTO public.projects(id,company_id,name,budget) VALUES "
                "(17,4,'Одинаковый объект',1000.00),"
                "(18,5,'Одинаковый объект',2000.00)"
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
                (encoded, encoded, encoded, encoded),
            )
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (id,base_estimate_id,next_estimate_id,status,smeta_type,
                      work_package,base_total,next_total)
                   VALUES
                     (91,51,52,'Черновик','Заказчик','Основная',0,0),
                     (92,61,62,'Черновик','Заказчик','Основная',0,0)"""
            )

    def _source(self, *, company_id=4, project_id=17, estimate_id=52):
        return build_estimate_revision_source(
            company_id=company_id,
            project_id=project_id,
            estimate_id=estimate_id,
            version="v2.0",
            sections=self.SECTIONS,
        )

    def _business_snapshot_sha256(self):
        snapshot = []
        with self.admin.cursor() as cur:
            for table in self.BUSINESS_TABLES:
                cur.execute(
                    "SELECT row_to_json(snapshot_row)::text FROM "
                    "(SELECT * FROM public." + table + " ORDER BY id) snapshot_row"
                )
                snapshot.append((table, cur.fetchall()))
        encoded = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _job_rows(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT id,company_id,project_id,status,result_json "
                "FROM public.agent_jobs ORDER BY id"
            )
            return cur.fetchall()

    def _runner(self):
        handler = build_estimate_revision_impact_handler(
            connection_factory=self.connection,
        )
        registry = AgentJobHandlerRegistry(((JOB_TYPE, handler),))
        return AgentJobRunner(
            registry=registry,
            connection_factory=self.connection,
            config=AgentJobRunnerConfig(
                worker_id="agent-worker:a7-cutover",
                lease_seconds=120,
                heartbeat_interval_seconds=30,
            ),
            emit_event=lambda *_args, **_kwargs: None,
            heartbeat_factory=NoopHeartbeat,
        )

    def test_same_name_readiness_rolls_back_and_preserves_business_tables(self):
        before = self._business_snapshot_sha256()
        report = run_readiness_report(self.connection, self._source())

        self.assertTrue(report["readyForCanary"], report)
        self.assertTrue(report["combinedReportReady"])
        self.assertTrue(report["agentJobSchemaReady"])
        self.assertTrue(report["writerInventoryReady"])
        self.assertEqual(report["ledgerAudit"]["state"], "absent")
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertNotIn("Одинаковый объект", json.dumps(report, ensure_ascii=False))
        self.assertEqual(self._business_snapshot_sha256(), before)

    def test_repeat_and_concurrent_enqueue_create_one_exact_job(self):
        before = self._business_snapshot_sha256()
        barrier = threading.Barrier(2)

        def enqueue_once():
            barrier.wait(timeout=10)
            try:
                return run_estimate_revision_impact_producer(
                    self._source(),
                    apply=True,
                    connection_factory=self.connection,
                )
            except Exception as exc:
                return {"state": "failed", "errorType": type(exc).__name__}

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: enqueue_once(), range(2)))

        rows = self._job_rows()
        self.assertEqual(len(rows), 1, results)
        self.assertEqual(rows[0][1:4], (4, 17, "queued"))
        self.assertIn("enqueued", {result["state"] for result in results})
        self.assertTrue(all(
            result["state"] in {"enqueued", "existing", "failed"}
            for result in results
        ))

        repeated = run_estimate_revision_impact_producer(
            self._source(),
            apply=True,
            connection_factory=self.connection,
        )
        self.assertEqual(repeated["state"], "existing")
        self.assertEqual(len(self._job_rows()), 1)
        self.assertEqual(self._business_snapshot_sha256(), before)

    def test_exact_runner_completes_only_selected_tenant_job(self):
        before = self._business_snapshot_sha256()
        selected = run_estimate_revision_impact_producer(
            self._source(), apply=True, connection_factory=self.connection,
        )
        foreign = run_estimate_revision_impact_producer(
            self._source(company_id=5, project_id=18, estimate_id=62),
            apply=True,
            connection_factory=self.connection,
        )

        outcome = self._runner().run_once(job_id=selected["jobId"])

        self.assertTrue(outcome.processed)
        self.assertEqual(outcome.status, "succeeded")
        rows = self._job_rows()
        selected_row = next(row for row in rows if row[0] == selected["jobId"])
        foreign_row = next(row for row in rows if row[0] == foreign["jobId"])
        self.assertEqual(selected_row[3], "succeeded")
        self.assertEqual(foreign_row[3], "queued")
        self.assertTrue(selected_row[4]["readOnlyTransaction"])
        self.assertTrue(selected_row[4]["rolledBack"])
        self.assertEqual(selected_row[4]["writesAttempted"], 0)
        self.assertEqual(self._business_snapshot_sha256(), before)

    def test_failure_rolls_back_queue_and_preserves_business_tables(self):
        before = self._business_snapshot_sha256()

        def prepare_then_fail(cur, exact_source, **kwargs):
            prepare_estimate_revision_impact_job(cur, exact_source, **kwargs)
            raise RuntimeError("post-enqueue failure")

        report = handoff_estimate_revision_impact_transition(
            previous_status="Черновик",
            next_status="Активная",
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=self.SECTIONS,
            enabled=True,
            connection_factory=self.connection,
            prepare_job=prepare_then_fail,
            log_fn=lambda _line: None,
        )

        self.assertEqual(report["state"], "failed")
        self.assertTrue(report["enqueueAttempted"])
        self.assertFalse(report["committed"])
        self.assertEqual(self._job_rows(), [])
        self.assertEqual(self._business_snapshot_sha256(), before)

    def test_final_readiness_is_read_only_and_exact(self):
        before = self._business_snapshot_sha256()
        queued = run_estimate_revision_impact_producer(
            self._source(), apply=True, connection_factory=self.connection,
        )
        self.assertEqual(
            self._runner().run_once(job_id=queued["jobId"]).status,
            "succeeded",
        )

        report = run_readiness_report(self.connection, self._source())

        self.assertTrue(report["readyForCanary"], report)
        self.assertEqual(report["ledgerAudit"]["state"], "succeeded")
        self.assertEqual(report["ledgerAudit"]["jobIds"], [queued["jobId"]])
        self.assertTrue(report["combinedAudit"]["complete"])
        self.assertFalse(report["combinedAudit"]["actionable"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["rolledBack"])
        self.assertEqual(self._business_snapshot_sha256(), before)


if __name__ == "__main__":
    unittest.main()
