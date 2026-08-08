import json
import os
import unittest
from pathlib import Path

import psycopg2

from backend.features.estimate_revision_impact.combined_report import (
    DOMAIN_ORDER,
    build_combined_report,
    collect_combined_impact_audit,
    run_combined_impact_audit,
)
from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    source,
)


def source_context():
    return {
        "companyId": 4,
        "projectId": 17,
        "estimateId": 52,
        "sourceRevision": source().source_revision,
        "reconciliationId": 91,
        "baseEstimateId": 51,
        "reconciliationStatus": "Черновик",
    }


def assignment_projection(**changes):
    value = {
        "state": "complete",
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": True,
        "complete": True,
        "summary": {
            "assignmentRows": 1,
            "uncompletedAssignments": 1,
            "protectedAssignments": 0,
            "needsReview": 0,
            "workJournalRows": 0,
            "confirmedWorkJournalRows": 0,
            "hiddenActs": 0,
            "brigadeActs": 0,
            "brigadePayments": 0,
            "projectPayments": 0,
        },
        "uncompletedAssignmentIds": [10],
        "protectedAssignmentIds": [],
        "protectedHistory": {
            key: {"count": 0, "ids": [], "idsTruncated": False}
            for key in (
                "workJournal", "confirmedWorkJournal", "hiddenActs",
                "brigadeActs", "brigadePayments", "projectPayments",
            )
        },
        "reasonCounts": {},
        "needsReview": [],
        "needsReviewTruncated": False,
        "secret": "must-not-leak",
    }
    value.update(changes)
    return value


def material_projection(**changes):
    value = {
        "state": "complete",
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": True,
        "complete": True,
        "summary": {
            "baseMaterialRows": 1,
            "targetMaterialRows": 1,
            "pairedRows": 1,
            "changedPairs": 1,
            "baseOnlyRows": 0,
            "targetOnlyRows": 0,
            "needsReview": 0,
        },
        "changedPairs": [{
            "base": {"estimateId": 51, "sectionIndex": 0, "itemIndex": 0},
            "target": {"estimateId": 52, "sectionIndex": 0, "itemIndex": 0},
            "matchKind": "stable_item_key",
            "aliasIds": [],
            "changeKinds": ["quantity_changed"],
            "materialName": "must-not-leak",
        }],
        "baseOnlyRows": [],
        "targetOnlyRows": [],
        "factsTruncated": False,
        "reasonCounts": {},
        "needsReview": [],
        "needsReviewTruncated": False,
    }
    value.update(changes)
    return value


def supply_warehouse_projection(**changes):
    value = {
        "state": "complete",
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": True,
        "complete": True,
        "summary": {
            "supplyRequestRows": 1,
            "supplyItems": 1,
            "openSupplyItems": 1,
            "protectedSupplyItems": 0,
            "closedSupplyRequests": 0,
            "deliveries": 0,
            "allocations": 0,
            "supplierInvoices": 0,
            "warehouseInvoices": 0,
            "warehouseHistoryRows": 0,
            "receiptLots": 0,
            "warehouseMovements": 0,
            "lotMovements": 0,
            "needsReview": 0,
        },
        "openSupply": [{
            "requestId": 21,
            "requestItemIndex": 0,
            "sourceEstimateId": 51,
            "sourceSectionIndex": 0,
            "sourceItemIndex": 0,
            "state": "open_balance",
            "materialName": "must-not-leak",
        }],
        "protectedEvidence": {
            "closedSupplyRequestIds": [],
            "deliveryIds": [],
            "allocationIds": [],
            "supplierInvoiceIds": [],
            "warehouseInvoiceIds": [],
            "warehouseHistoryIds": [],
            "receiptLotIds": [],
            "warehouseMovementIds": [],
            "lotMovementIds": [],
        },
        "factsTruncated": False,
        "reasonCounts": {},
        "needsReview": [],
        "needsReviewTruncated": False,
    }
    value.update(changes)
    return value


def economics_projection(*, actionable=False, **changes):
    value = {
        "state": "non_actionable" if not actionable else "complete",
        "schemaReady": True,
        "missingColumns": [],
        "scanComplete": True,
        "complete": True,
        "actionable": actionable,
        "authorizationState": "not_evaluated" if not actionable else "authorized",
        "summary": {
            "evidenceComplete": 1,
            "actionablePlans": 1 if actionable else 0,
            "nonActionablePlans": 0 if actionable else 1,
            "needsReview": 0 if actionable else 1,
        },
        "budget": {
            "projectBudgetBefore": "1000.00",
            "estimateBaseTotal": "250.00",
            "estimateNextTotal": "275.50",
            "adjustmentAmount": "25.50",
            "projectBudgetAfter": "1025.50",
        },
        "planSha256": (
            "697113e2eeec51f1126b57d12bf8f1d4347cd4c2acdedced45a4b8e6ba042f4f"
        ),
        "reasonCounts": (
            {} if actionable else {"budget_adjustment_authorization_required": 1}
        ),
        "needsReview": (
            [] if actionable else [{
                "reasonCode": "budget_adjustment_authorization_required",
            }]
        ),
        "needsReviewTruncated": False,
    }
    value.update(changes)
    return value


def combined(**overrides):
    values = {
        "assignment": assignment_projection(),
        "material": material_projection(),
        "supply_warehouse": supply_warehouse_projection(),
        "economics": economics_projection(),
    }
    values.update(overrides)
    return build_combined_report(source_context(), **values)


def collector_report(projection_key, projection):
    return {
        "source": source_context(),
        projection_key: projection,
        "writesAttempted": 0,
    }


class CombinedReportContractTests(unittest.TestCase):
    def test_composes_five_ordered_allowlisted_domains_and_stable_hash(self):
        first = combined()
        second = combined()

        self.assertEqual(DOMAIN_ORDER, (
            "assignments", "materials", "supply", "warehouse", "economics",
        ))
        self.assertEqual(list(first["domains"]), list(DOMAIN_ORDER))
        self.assertTrue(first["complete"])
        self.assertFalse(first["actionable"])
        self.assertEqual(first["evidenceSha256"], second["evidenceSha256"])
        self.assertEqual(
            first["evidenceSha256"],
            "f6143dae204bb81813a32d4730f64c2c502829364fd4ed124a643cbc4cc8b6c5",
        )
        self.assertRegex(first["evidenceSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(set(first["source"]), {
            "companyId", "projectId", "estimateId", "sourceRevision",
            "reconciliationId", "baseEstimateId", "reconciliationStatus",
        })
        serialized = json.dumps(first, ensure_ascii=False)
        self.assertNotIn("must-not-leak", serialized)
        self.assertNotIn("materialName", serialized)
        self.assertEqual(
            first["domains"]["supply"]["openSupply"][0]["requestId"], 21,
        )

    def test_only_exact_authorized_economics_can_make_report_actionable(self):
        report = combined(economics=economics_projection(actionable=True))

        self.assertTrue(report["complete"])
        self.assertTrue(report["actionable"])

        tampered = combined(economics=economics_projection(
            actionable=True, planSha256="a" * 64,
        ))
        self.assertFalse(tampered["complete"])
        self.assertFalse(tampered["actionable"])
        self.assertEqual(tampered["domains"]["economics"]["reasonCounts"], {
            "economics_projection_contract_invalid": 1,
        })

    def test_truncated_warehouse_fails_only_warehouse_and_preserves_other_facts(self):
        projection = supply_warehouse_projection()
        projection["complete"] = False
        projection["state"] = "incomplete"
        projection["factsTruncated"] = True
        projection["summary"]["warehouseInvoices"] = 101
        projection["protectedEvidence"]["warehouseInvoiceIds"] = list(range(1, 101))

        report = combined(supply_warehouse=projection)

        self.assertTrue(report["domains"]["supply"]["complete"])
        self.assertFalse(report["domains"]["warehouse"]["complete"])
        self.assertTrue(report["domains"]["warehouse"]["factsTruncated"])
        self.assertFalse(report["complete"])
        self.assertFalse(report["actionable"])
        self.assertEqual(report["domains"]["assignments"]["summary"][
            "uncompletedAssignments"
        ], 1)

    def test_incomplete_domain_changes_hash_and_preserves_fixed_reason_counts(self):
        material = material_projection(
            complete=False,
            state="review_required",
            reasonCounts={"material_quantity_invalid": 1},
            needsReview=[{
                "sourceKind": "material",
                "sourceId": 51,
                "itemIndex": 2,
                "reasonCode": "material_quantity_invalid",
                "name": "must-not-leak",
            }],
        )
        report = combined(material=material)

        self.assertFalse(report["complete"])
        self.assertNotEqual(report["evidenceSha256"], combined()["evidenceSha256"])
        self.assertEqual(report["reasonCounts"], {
            "budget_adjustment_authorization_required": 1,
            "material_quantity_invalid": 1,
        })
        self.assertEqual(report["domains"]["materials"]["needsReview"], [{
            "sourceKind": "material",
            "sourceId": 51,
            "itemIndex": 2,
            "reasonCode": "material_quantity_invalid",
        }])

    def test_every_incomplete_domain_makes_the_envelope_non_actionable(self):
        supply_failure = supply_warehouse_projection(
            complete=False,
            state="review_required",
            reasonCounts={"supply_quantity_invalid": 1},
            needsReview=[{
                "sourceKind": "supply",
                "sourceId": 21,
                "reasonCode": "supply_quantity_invalid",
            }],
        )
        warehouse_failure = supply_warehouse_projection(
            complete=False,
            state="review_required",
            reasonCounts={"warehouse_invoice_identity_invalid": 1},
            needsReview=[{
                "sourceKind": "warehouseInvoice",
                "sourceId": 31,
                "reasonCode": "warehouse_invoice_identity_invalid",
            }],
        )
        cases = {
            "assignments": {"assignment": assignment_projection(
                complete=False,
                state="incomplete",
                reasonCounts={"assignment_scan_limit_exceeded": 1},
            )},
            "materials": {"material": material_projection(
                complete=False,
                state="incomplete",
                factsTruncated=True,
            )},
            "supply": {"supply_warehouse": supply_failure},
            "warehouse": {"supply_warehouse": warehouse_failure},
            "economics": {"economics": economics_projection(
                complete=False,
                actionable=False,
                state="incomplete",
                budget={},
                planSha256=None,
                reasonCounts={"budget_adjustment_source_drift": 1},
                needsReview=[{
                    "reasonCode": "budget_adjustment_source_drift",
                }],
            )},
        }

        for domain, override in cases.items():
            with self.subTest(domain=domain):
                report = combined(**override)
                self.assertFalse(report["domains"][domain]["complete"])
                self.assertFalse(report["complete"])
                self.assertFalse(report["actionable"])


class CombinedReportCollectionTests(unittest.TestCase):
    def collectors(self, calls, *, drift=False):
        def wrap(name, key, projection):
            def collect(cur, exact_source):
                calls.append((name, cur, exact_source))
                report = collector_report(key, projection)
                if drift and name == "material":
                    report["source"] = {**report["source"], "projectId": 18}
                return report
            return collect

        return {
            "assignment": wrap(
                "assignment", "assignmentImpact", assignment_projection(),
            ),
            "material": wrap(
                "material", "materialImpact", material_projection(),
            ),
            "supply_warehouse": wrap(
                "supply_warehouse", "supplyWarehouseImpact",
                supply_warehouse_projection(),
            ),
            "economics": wrap(
                "economics", "economicsImpact", economics_projection(),
            ),
        }

    def test_collectors_share_one_cursor_and_exact_source(self):
        cursor = FakeCursor(())
        calls = []

        report = collect_combined_impact_audit(
            cursor, source(), collectors=self.collectors(calls),
        )

        self.assertEqual([name for name, *_rest in calls], [
            "assignment", "material", "supply_warehouse", "economics",
        ])
        self.assertTrue(all(call[1] is cursor for call in calls))
        self.assertTrue(all(call[2] == source() for call in calls))
        self.assertTrue(report["complete"])
        self.assertEqual(report["writesAttempted"], 0)

    def test_cross_collector_source_drift_fails_closed(self):
        report = collect_combined_impact_audit(
            FakeCursor(()), source(), collectors=self.collectors([], drift=True),
        )

        self.assertFalse(report["complete"])
        self.assertFalse(report["actionable"])
        self.assertEqual(report["reasonCounts"], {
            "combined_source_context_mismatch": 1,
        })

    def test_runner_uses_one_read_only_transaction_and_rolls_back(self):
        connection = FakeConnection(FakeCursor(()))

        report = run_combined_impact_audit(
            lambda: connection,
            source(),
            collectors=self.collectors([]),
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

    def test_operator_command_is_registered(self):
        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text())

        self.assertEqual(
            package["scripts"]["audit:estimate-revision-combined-impact"],
            "python3 -m backend.features.estimate_revision_impact.combined_report",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "combined_report",
                (root / relative).read_text(encoding="utf-8"),
            )


A7_TEST_DATABASE_URL = os.getenv("A7_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("A7_RUN_POSTGRES_INTEGRATION") == "1" and A7_TEST_DATABASE_URL,
    "set A7_RUN_POSTGRES_INTEGRATION=1 and A7_TEST_DATABASE_URL",
)
class CombinedReportPostgresTests(unittest.TestCase):
    TABLES = (
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
                ALTER TABLE public.projects
                    ADD COLUMN IF NOT EXISTS budget NUMERIC(14,2);
                ALTER TABLE public.estimate_reconciliations
                    ADD COLUMN IF NOT EXISTS base_total NUMERIC(14,2);
                ALTER TABLE public.estimate_reconciliations
                    ADD COLUMN IF NOT EXISTS next_total NUMERIC(14,2);
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

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE " + ",".join(
                    "public." + table for table in self.TABLES
                ) + " CASCADE"
            )

    def _snapshot(self):
        result = {}
        with self.admin.cursor() as cur:
            for table in self.TABLES:
                cur.execute(
                    "SELECT row_to_json(snapshot_row)::text FROM "
                    "(SELECT * FROM public." + table + " ORDER BY id) snapshot_row"
                )
                result[table] = cur.fetchall()
        return result

    def test_single_snapshot_preserves_every_business_table(self):
        sections = [{"name": "Private fixture", "items": []}]
        encoded = json.dumps(sections, ensure_ascii=False)
        with self.admin.cursor() as cur:
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
        exact_source = build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=sections,
        )
        before = self._snapshot()

        report = run_combined_impact_audit(
            lambda: psycopg2.connect(A7_TEST_DATABASE_URL), exact_source,
        )

        self.assertTrue(report["complete"])
        self.assertFalse(report["actionable"])
        self.assertEqual(list(report["domains"]), list(DOMAIN_ORDER))
        self.assertTrue(all(
            report["domains"][name]["complete"] for name in DOMAIN_ORDER
        ))
        self.assertEqual(report["domains"]["economics"]["reasonCounts"], {
            "budget_adjustment_reconciliation_not_approved": 1,
        })
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])
        self.assertNotIn("Одинаковый объект", json.dumps(report, ensure_ascii=False))
        self.assertEqual(self._snapshot(), before)


if __name__ == "__main__":
    unittest.main()
