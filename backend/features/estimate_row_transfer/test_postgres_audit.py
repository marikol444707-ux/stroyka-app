import json
import os
import threading
import unittest
import uuid
from decimal import Decimal

import psycopg2
import psycopg2.extras

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.assignment_apply import (
    AssignmentApplyError,
    apply_assignment_plan,
)
from backend.features.estimate_row_transfer.audit import run_impact_audit
from backend.features.estimate_row_transfer.plan import normalize_draft_payload
from backend.features.estimate_row_transfer.schema import run_schema_migration
from backend.features.estimate_row_transfer.service import build_current_plan
from backend.features.estimate_row_transfer.supply_apply import (
    SupplyApplyError,
    apply_supply_plan,
)
from backend.features.estimate_row_transfer.storage import (
    approve_plan,
    insert_draft,
    load_stored_plan,
)


POSTGRES_TEST_DSN = os.getenv("E4_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("E4_RUN_POSTGRES_INTEGRATION") == "1" and POSTGRES_TEST_DSN,
    "set E4_RUN_POSTGRES_INTEGRATION=1 and E4_TEST_DATABASE_URL for PostgreSQL fixture",
)
class EstimateRowTransferPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg2.connect(POSTGRES_TEST_DSN)
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            database_name = cur.fetchone()[0]
            if not str(database_name).startswith("e4_"):
                raise RuntimeError("E4 integration fixture requires a dedicated e4_* database")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.projects (
                    id SERIAL PRIMARY KEY, company_id INTEGER, name TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimates (
                    id SERIAL PRIMARY KEY, company_id INTEGER, project_id INTEGER,
                    work_package TEXT, smeta_type TEXT, sections_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.estimate_reconciliations (
                    id SERIAL PRIMARY KEY, status TEXT, work_package TEXT,
                    smeta_type TEXT, base_estimate_id INTEGER, next_estimate_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.estimate_versions (
                    id SERIAL PRIMARY KEY, estimate_id INTEGER, sections_json TEXT,
                    sections_sha256 VARCHAR(64)
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contracts (
                    id SERIAL PRIMARY KEY, company_id INTEGER, project_id INTEGER,
                    work_package TEXT, total_amount NUMERIC(20,2)
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contract_items (
                    id SERIAL PRIMARY KEY, contract_id INTEGER, work_package TEXT,
                    estimate_section TEXT, description TEXT,
                    estimate_item_key TEXT, unit TEXT,
                    quantity NUMERIC(20,6), price_smeta NUMERIC(20,6),
                    price_brigade NUMERIC(20,6), done_quantity NUMERIC(20,6),
                    status TEXT, source_type TEXT,
                    source_estimate_version_id INTEGER, source_section_index INTEGER,
                    source_item_index INTEGER, source_item_key TEXT
                );
                CREATE TABLE IF NOT EXISTS public.work_journal (
                    id SERIAL PRIMARY KEY, contract_item_id INTEGER,
                    quantity DOUBLE PRECISION, status TEXT
                );
                CREATE TABLE IF NOT EXISTS public.hidden_works_acts (
                    id SERIAL PRIMARY KEY, work_journal_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.brigade_acts (
                    id SERIAL PRIMARY KEY, contract_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.brigade_payments (
                    id SERIAL PRIMARY KEY, contract_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.supply_requests (
                    id SERIAL PRIMARY KEY, company_id INTEGER, project TEXT,
                    work_package TEXT, status TEXT, items_json TEXT
                );
                CREATE TABLE IF NOT EXISTS public.supplier_offers (
                    id SERIAL PRIMARY KEY, request_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.supplier_invoices (
                    id SERIAL PRIMARY KEY, request_id INTEGER, paid_at DATE,
                    paid_amount NUMERIC
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_invoices (
                    id SERIAL PRIMARY KEY, supply_request_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.warehouse_history (
                    id SERIAL PRIMARY KEY, source_invoice_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.supply_history (
                    id SERIAL PRIMARY KEY, request_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.supply_claims (
                    id SERIAL PRIMARY KEY, request_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.supply_deliveries (
                    id SERIAL PRIMARY KEY, request_id INTEGER, company_id INTEGER,
                    material_name TEXT, unit TEXT, received_quantity NUMERIC
                );
                ALTER TABLE public.brigade_contracts
                    ADD COLUMN IF NOT EXISTS work_package TEXT,
                    ADD COLUMN IF NOT EXISTS total_amount NUMERIC(20,2);
                ALTER TABLE public.brigade_contract_items
                    ADD COLUMN IF NOT EXISTS estimate_section TEXT,
                    ADD COLUMN IF NOT EXISTS description TEXT,
                    ADD COLUMN IF NOT EXISTS estimate_item_key TEXT,
                    ADD COLUMN IF NOT EXISTS unit TEXT,
                    ADD COLUMN IF NOT EXISTS price_smeta NUMERIC(20,6),
                    ADD COLUMN IF NOT EXISTS price_brigade NUMERIC(20,6),
                    ADD COLUMN IF NOT EXISTS done_quantity NUMERIC(20,6),
                    ADD COLUMN IF NOT EXISTS status TEXT;
                """
            )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def _counts(self):
        tables = (
            "projects",
            "estimates",
            "estimate_reconciliations",
            "estimate_versions",
            "brigade_contracts",
            "brigade_contract_items",
            "work_journal",
        )
        with self.admin.cursor() as cur:
            result = {}
            for table in tables:
                cur.execute("SELECT COUNT(*) FROM public." + table)
                result[table] = cur.fetchone()[0]
            return result

    def _ensure_transfer_schema(self):
        dry_run = run_schema_migration(lambda: psycopg2.connect(POSTGRES_TEST_DSN))
        if dry_run["changeCount"]:
            applied = run_schema_migration(
                lambda: psycopg2.connect(POSTGRES_TEST_DSN),
                apply=True,
                expected_change_count=dry_run["changeCount"],
                expected_plan_sha256=dry_run["planSha256"],
            )
            self.assertTrue(applied["schemaReady"])
        else:
            self.assertTrue(dry_run["schemaReady"])

    def _create_approved_assignment_fixture(self, company_id, *, protected=False):
        self._ensure_transfer_schema()
        marker = "e4-apply-" + uuid.uuid4().hex
        source_sections = [{
            "name": "Fixture",
            "items": [{
                "name": "Old work",
                "unit": "m2",
                "quantity": 10,
                "estimateItemKey": marker + "-source",
                "priceWork": 850,
            }],
        }]
        target_sections = [{
            "name": "Fixture",
            "items": [{
                "name": "New work",
                "unit": "m2",
                "quantity": 10,
                "estimateItemKey": marker + "-target",
                "priceWork": 900,
            }],
        }]
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(company_id,name) VALUES (%s,%s) RETURNING id",
                (company_id, marker),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (%s,%s,'Fixture','Заказчик',%s) RETURNING id""",
                (company_id, project_id, json.dumps(source_sections)),
            )
            source_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (%s,%s,'Fixture','Заказчик',%s) RETURNING id""",
                (company_id, project_id, json.dumps(target_sections)),
            )
            target_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                       (status,work_package,smeta_type,base_estimate_id,next_estimate_id)
                     VALUES ('Утверждена','Fixture','Заказчик',%s,%s) RETURNING id""",
                (source_estimate_id, target_estimate_id),
            )
            reconciliation_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (
                    source_estimate_id,
                    json.dumps(source_sections),
                    sections_sha256(source_sections),
                ),
            )
            source_version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (
                    target_estimate_id,
                    json.dumps(target_sections),
                    sections_sha256(target_sections),
                ),
            )
            target_version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.brigade_contracts
                       (company_id,project_id,work_package,total_amount)
                     VALUES (%s,%s,'Fixture',7000) RETURNING id""",
                (company_id, project_id),
            )
            contract_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.brigade_contract_items
                       (contract_id,estimate_section,description,work_package,
                        estimate_item_key,unit,quantity,price_smeta,price_brigade,
                        done_quantity,status,source_type,source_estimate_version_id,
                        source_section_index,source_item_index,source_item_key)
                     VALUES (%s,'Fixture','Old work','Fixture',%s,'m2',10,850,700,
                             4,'В работе','estimate',%s,0,0,%s) RETURNING id""",
                (
                    contract_id,
                    marker + "-source",
                    source_version_id,
                    marker + "-source",
                ),
            )
            source_item_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.work_journal(contract_item_id,quantity,status)
                     VALUES (%s,4,'Подтверждено') RETURNING id""",
                (source_item_id,),
            )
            work_journal_id = cur.fetchone()[0]
            if protected:
                cur.execute(
                    "INSERT INTO public.hidden_works_acts(work_journal_id) VALUES (%s)",
                    (work_journal_id,),
                )
                cur.execute(
                    "INSERT INTO public.brigade_acts(contract_id) VALUES (%s)",
                    (contract_id,),
                )
                cur.execute(
                    "INSERT INTO public.brigade_payments(contract_id) VALUES (%s)",
                    (contract_id,),
                )
                cur.execute(
                    """INSERT INTO public.supply_requests
                           (company_id,project,work_package,status,items_json)
                         VALUES (%s,%s,'Fixture','Закрыта','[]') RETURNING id""",
                    (company_id, marker),
                )
                request_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO public.supplier_offers(request_id) VALUES (%s)",
                    (request_id,),
                )
                cur.execute(
                    """INSERT INTO public.supplier_invoices
                           (request_id,paid_at,paid_amount) VALUES (%s,CURRENT_DATE,1)""",
                    (request_id,),
                )
                cur.execute(
                    """INSERT INTO public.warehouse_invoices(supply_request_id)
                         VALUES (%s) RETURNING id""",
                    (request_id,),
                )
                invoice_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO public.warehouse_history(source_invoice_id) VALUES (%s)",
                    (invoice_id,),
                )
                cur.execute(
                    "INSERT INTO public.supply_history(request_id) VALUES (%s)",
                    (request_id,),
                )
                cur.execute(
                    "INSERT INTO public.supply_claims(request_id) VALUES (%s)",
                    (request_id,),
                )
                cur.execute(
                    """INSERT INTO public.supply_deliveries
                           (request_id,company_id,material_name,unit,received_quantity)
                         VALUES (%s,%s,'Fixture material','pcs',1)""",
                    (request_id, company_id),
                )

        payload = normalize_draft_payload({
            "reconciliationId": reconciliation_id,
            "entries": [{
                "sourceKind": "assignment",
                "sourceId": source_item_id,
                "quantity": "3",
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": marker + "-target",
            }],
        })
        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        connection.set_session(autocommit=False, isolation_level="REPEATABLE READ")
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                plan = build_current_plan(cur, payload)
                plan_id = insert_draft(
                    cur,
                    plan,
                    {"id": 12, "name": "Estimator", "role": "сметчик"},
                )
                self.assertTrue(approve_plan(
                    cur,
                    plan_id=plan_id,
                    company_id=company_id,
                    expected_plan_sha256=plan["planSha256"],
                    actor={"id": 2, "name": "Director", "role": "директор"},
                ))
            connection.commit()
        finally:
            connection.close()
        return {
            "companyId": company_id,
            "projectId": project_id,
            "contractId": contract_id,
            "sourceItemId": source_item_id,
            "workJournalId": work_journal_id,
            "sourceVersionId": source_version_id,
            "targetVersionId": target_version_id,
            "planId": plan_id,
            "planSha256": plan["planSha256"],
        }

    def _apply_serializable(self, fixture):
        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        connection.set_session(autocommit=False, isolation_level="SERIALIZABLE")
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                stored = load_stored_plan(
                    cur,
                    fixture["planId"],
                    fixture["companyId"],
                    for_update=True,
                )
                result = apply_assignment_plan(
                    cur,
                    stored=stored,
                    actor={
                        "id": 2,
                        "companyId": fixture["companyId"],
                        "name": "Director",
                        "role": "директор",
                    },
                )
            if result["idempotent"]:
                connection.rollback()
            else:
                connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_approved_supply_fixture(self, company_id):
        self._ensure_transfer_schema()
        marker = "e4-supply-" + uuid.uuid4().hex
        source_sections = [{
            "name": "Fixture",
            "items": [{
                "name": "Old mix", "unit": "kg", "quantity": 10,
                "itemType": "material",
                "estimateItemKey": marker + "-source",
            }],
        }]
        target_sections = [{
            "name": "Fixture",
            "items": [{
                "name": "New mix", "unit": "kg", "quantity": 10,
                "itemType": "material",
                "estimateItemKey": marker + "-target",
            }],
        }]
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(company_id,name) VALUES (%s,%s) RETURNING id",
                (company_id, marker),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (%s,%s,'Fixture','Материалы',%s) RETURNING id""",
                (company_id, project_id, json.dumps(source_sections)),
            )
            source_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (%s,%s,'Fixture','Материалы',%s) RETURNING id""",
                (company_id, project_id, json.dumps(target_sections)),
            )
            target_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                       (status,work_package,smeta_type,base_estimate_id,next_estimate_id)
                     VALUES ('Утверждена','Fixture','Материалы',%s,%s) RETURNING id""",
                (source_estimate_id, target_estimate_id),
            )
            reconciliation_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (
                    source_estimate_id, json.dumps(source_sections),
                    sections_sha256(source_sections),
                ),
            )
            source_version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (
                    target_estimate_id, json.dumps(target_sections),
                    sections_sha256(target_sections),
                ),
            )
            target_version_id = cur.fetchone()[0]
            request_item = {
                "materialName": "Old mix",
                "quantity": 10,
                "unit": "kg",
                "workPackage": "Fixture",
                "sourceType": "estimate_material_control",
                "estimateLineage": {
                    "version": 1,
                    "validated": True,
                    "projectName": marker,
                    "workPackage": "Fixture",
                    "sources": [{
                        "estimateId": source_estimate_id,
                        "sectionIndex": 0,
                        "itemIndex": 0,
                        "materialName": "Old mix",
                        "unit": "kg",
                        "quantity": 10,
                        "validated": True,
                    }],
                },
            }
            cur.execute(
                """INSERT INTO public.supply_requests
                       (company_id,project,work_package,status,items_json)
                     VALUES (%s,%s,'Fixture','КП запрошены',%s) RETURNING id""",
                (company_id, marker, json.dumps([request_item])),
            )
            request_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.supply_deliveries
                       (request_id,company_id,material_name,unit,received_quantity)
                     VALUES (%s,%s,'Old mix','kg',2) RETURNING id""",
                (request_id, company_id),
            )
            delivery_id = cur.fetchone()[0]

        payload = normalize_draft_payload({
            "reconciliationId": reconciliation_id,
            "entries": [{
                "sourceKind": "supply",
                "sourceId": request_id,
                "requestItemIndex": 0,
                "sourceEstimateVersionId": source_version_id,
                "quantity": "3",
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": marker + "-target",
            }],
        })
        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        connection.set_session(autocommit=False, isolation_level="REPEATABLE READ")
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                plan = build_current_plan(cur, payload)
                plan_id = insert_draft(
                    cur, plan, {"id": 12, "name": "Estimator", "role": "сметчик"},
                )
                self.assertTrue(approve_plan(
                    cur,
                    plan_id=plan_id,
                    company_id=company_id,
                    expected_plan_sha256=plan["planSha256"],
                    actor={"id": 2, "name": "Director", "role": "директор"},
                ))
            connection.commit()
        finally:
            connection.close()
        return {
            "companyId": company_id,
            "projectId": project_id,
            "reconciliationId": reconciliation_id,
            "requestId": request_id,
            "deliveryId": delivery_id,
            "sourceEstimateId": source_estimate_id,
            "targetEstimateId": target_estimate_id,
            "sourceVersionId": source_version_id,
            "targetVersionId": target_version_id,
            "planId": plan_id,
            "planSha256": plan["planSha256"],
        }

    def _apply_supply_serializable(self, fixture):
        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        connection.set_session(autocommit=False, isolation_level="SERIALIZABLE")
        try:
            with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                stored = load_stored_plan(
                    cur, fixture["planId"], fixture["companyId"], for_update=True,
                )
                result = apply_supply_plan(
                    cur,
                    stored=stored,
                    actor={
                        "id": 2,
                        "companyId": fixture["companyId"],
                        "name": "Director",
                        "role": "директор",
                    },
                )
            if result["idempotent"]:
                connection.rollback()
            else:
                connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _protected_rows_snapshot(self):
        tables = (
            "work_journal", "hidden_works_acts", "brigade_acts",
            "brigade_payments", "supply_requests", "supplier_offers",
            "supplier_invoices", "warehouse_invoices", "warehouse_history",
            "supply_history", "supply_claims", "supply_deliveries",
        )
        result = {}
        with self.admin.cursor() as cur:
            for table in tables:
                cur.execute(
                    "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id), '[]'::jsonb)::text "
                    "FROM public." + table + " t"
                )
                result[table] = cur.fetchone()[0]
        return result

    def test_real_postgres_report_is_read_only_and_recomputes_confirmed_quantity(self):
        marker = "e4-fixture-" + uuid.uuid4().hex
        source_sections = [{
            "name": "Fixture",
            "items": [{"name": "Work", "unit": "m2", "quantity": 10,
                       "estimateItemKey": marker + "-source"}],
        }]
        target_sections = [{
            "name": "Fixture",
            "items": [{"name": "Work", "unit": "m2", "quantity": 10,
                       "estimateItemKey": marker + "-target"}],
        }]
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(company_id,name) VALUES (%s,%s) RETURNING id",
                (701, marker),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (701, project_id, "Fixture", "Заказчик", json.dumps(source_sections)),
            )
            base_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (701, project_id, "Fixture", "Заказчик", json.dumps(target_sections)),
            )
            target_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                       (status,work_package,smeta_type,base_estimate_id,next_estimate_id)
                     VALUES ('Утверждена','Fixture','Заказчик',%s,%s) RETURNING id""",
                (base_estimate_id, target_estimate_id),
            )
            reconciliation_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (
                    base_estimate_id,
                    json.dumps(source_sections),
                    sections_sha256(source_sections),
                ),
            )
            source_version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.brigade_contracts(company_id,project_id)
                     VALUES (701,%s) RETURNING id""",
                (project_id,),
            )
            contract_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.brigade_contract_items
                       (contract_id,work_package,quantity,source_type,
                        source_estimate_version_id,source_section_index,
                        source_item_index,source_item_key)
                     VALUES (%s,'Fixture',10,'estimate',%s,0,0,%s) RETURNING id""",
                (contract_id, source_version_id, marker + "-source"),
            )
            contract_item_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.work_journal(contract_item_id,quantity,status)
                     VALUES (%s,4,'Подтверждено')""",
                (contract_item_id,),
            )

        before = self._counts()
        report = run_impact_audit(
            lambda: psycopg2.connect(POSTGRES_TEST_DSN),
            reconciliation_id,
        )
        after = self._counts()

        self.assertEqual(before, after)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["summary"]["assignmentCandidates"], 1)
        self.assertEqual(report["assignmentCandidates"][0]["confirmedQuantity"], 4.0)
        self.assertEqual(report["assignmentCandidates"][0]["transferableQuantity"], 6.0)

    def test_z_inert_schema_draft_and_approval_never_mutate_business_rows(self):
        with self.admin.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS public.estimate_row_supply_allocations CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.estimate_row_assignment_transfers CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.estimate_row_transfer_entries CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.estimate_row_transfer_plans CASCADE")
            cur.execute("DROP FUNCTION IF EXISTS public.reject_estimate_row_transfer_entry_mutation()")
            cur.execute("DROP FUNCTION IF EXISTS public.guard_estimate_row_transfer_plan_mutation()")
            cur.execute("DROP FUNCTION IF EXISTS public.guard_estimate_row_assignment_transfer()")
            cur.execute("DROP FUNCTION IF EXISTS public.guard_estimate_row_supply_allocation()")

        dry_run = run_schema_migration(lambda: psycopg2.connect(POSTGRES_TEST_DSN))
        applied = run_schema_migration(
            lambda: psycopg2.connect(POSTGRES_TEST_DSN),
            apply=True,
            expected_change_count=dry_run["changeCount"],
            expected_plan_sha256=dry_run["planSha256"],
        )
        self.assertTrue(applied["schemaReady"])

        marker = "e4-plan-" + uuid.uuid4().hex
        source_sections = [{
            "name": "Fixture",
            "items": [{"name": "Work", "unit": "m2", "quantity": 10,
                       "estimateItemKey": marker + "-source"}],
        }]
        target_sections = [{
            "name": "Fixture",
            "items": [{"name": "Work", "unit": "m2", "quantity": 10,
                       "estimateItemKey": marker + "-target"}],
        }]
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(company_id,name) VALUES (702,%s) RETURNING id",
                (marker,),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (702,%s,'Fixture','Заказчик',%s) RETURNING id""",
                (project_id, json.dumps(source_sections)),
            )
            base_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                       (company_id,project_id,work_package,smeta_type,sections_json)
                     VALUES (702,%s,'Fixture','Заказчик',%s) RETURNING id""",
                (project_id, json.dumps(target_sections)),
            )
            target_estimate_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                       (status,work_package,smeta_type,base_estimate_id,next_estimate_id)
                     VALUES ('Утверждена','Fixture','Заказчик',%s,%s) RETURNING id""",
                (base_estimate_id, target_estimate_id),
            )
            reconciliation_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (base_estimate_id, json.dumps(source_sections), sections_sha256(source_sections)),
            )
            source_version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_versions
                       (estimate_id,sections_json,sections_sha256)
                     VALUES (%s,%s,%s) RETURNING id""",
                (target_estimate_id, json.dumps(target_sections), sections_sha256(target_sections)),
            )
            target_version_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.brigade_contracts(company_id,project_id)
                     VALUES (702,%s) RETURNING id""",
                (project_id,),
            )
            contract_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.brigade_contract_items
                       (contract_id,work_package,quantity,source_type,
                        source_estimate_version_id,source_section_index,
                        source_item_index,source_item_key)
                     VALUES (%s,'Fixture',10,'estimate',%s,0,0,%s) RETURNING id""",
                (contract_id, source_version_id, marker + "-source"),
            )
            contract_item_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.work_journal(contract_item_id,quantity,status)
                     VALUES (%s,4,'Подтверждено')""",
                (contract_item_id,),
            )

        before = self._counts()
        payload = normalize_draft_payload({
            "reconciliationId": reconciliation_id,
            "entries": [{
                "sourceKind": "assignment",
                "sourceId": contract_item_id,
                "quantity": "3",
                "targetSectionIndex": 0,
                "targetItemIndex": 0,
                "targetItemKey": marker + "-target",
            }],
        })
        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        connection.set_session(autocommit=False, isolation_level="REPEATABLE READ")
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            plan = build_current_plan(cur, payload)
            self.assertEqual(plan["targetSnapshot"]["estimateVersionId"], target_version_id)
            plan_id = insert_draft(
                cur,
                plan,
                {"id": 12, "name": "Estimator", "role": "сметчик"},
            )
        connection.commit()
        connection.close()
        self.assertEqual(before, self._counts())

        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            stored = load_stored_plan(cur, plan_id, 702, for_update=True)
            self.assertEqual(stored["canonicalPlan"], plan)
            self.assertTrue(approve_plan(
                cur,
                plan_id=plan_id,
                company_id=702,
                expected_plan_sha256=plan["planSha256"],
                actor={"id": 2, "name": "Director", "role": "директор"},
            ))
        connection.commit()
        connection.close()
        self.assertEqual(before, self._counts())

        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        with self.assertRaisesRegex(psycopg2.Error, "estimate_row_transfer_entry_immutable"):
            with connection.cursor() as cur:
                cur.execute(
                    "UPDATE public.estimate_row_transfer_entries SET quantity=2 WHERE plan_id=%s",
                    (plan_id,),
                )
        connection.rollback()
        connection.close()

    def test_zz_assignment_apply_preserves_history_and_is_idempotent(self):
        fixture = self._create_approved_assignment_fixture(703, protected=True)
        protected_before = self._protected_rows_snapshot()

        first = self._apply_serializable(fixture)

        self.assertFalse(first["idempotent"])
        self.assertEqual(first["planSha256"], fixture["planSha256"])
        self.assertEqual(first["assignmentCount"], 1)
        self.assertEqual(first["transfers"][0]["quantity"], "3")
        protected_after = self._protected_rows_snapshot()
        self.assertEqual(protected_before, protected_after)

        with self.admin.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT quantity,price_smeta,price_brigade,done_quantity,status,
                          source_estimate_version_id,source_section_index,
                          source_item_index,source_item_key
                     FROM public.brigade_contract_items WHERE id=%s""",
                (fixture["sourceItemId"],),
            )
            source = dict(cur.fetchone())
            cur.execute(
                """SELECT id,quantity,price_smeta,price_brigade,done_quantity,status,
                          source_estimate_version_id,source_section_index,
                          source_item_index,source_item_key
                     FROM public.brigade_contract_items
                    WHERE contract_id=%s AND source_estimate_version_id=%s""",
                (fixture["contractId"], fixture["targetVersionId"]),
            )
            target = dict(cur.fetchone())
            cur.execute(
                "SELECT total_amount FROM public.brigade_contracts WHERE id=%s",
                (fixture["contractId"],),
            )
            contract_total = cur.fetchone()["total_amount"]
            cur.execute(
                """SELECT * FROM public.estimate_row_assignment_transfers
                    WHERE plan_id=%s""",
                (fixture["planId"],),
            )
            receipt = dict(cur.fetchone())

        self.assertEqual(source["quantity"], Decimal("7"))
        self.assertEqual(source["done_quantity"], Decimal("4"))
        self.assertEqual(source["price_smeta"], Decimal("850"))
        self.assertEqual(source["price_brigade"], Decimal("700"))
        self.assertEqual(source["status"], "В работе")
        self.assertEqual(source["source_estimate_version_id"], fixture["sourceVersionId"])
        self.assertEqual(target["quantity"], Decimal("3"))
        self.assertEqual(target["price_smeta"], Decimal("900"))
        self.assertEqual(target["price_brigade"], Decimal("700"))
        self.assertEqual(target["done_quantity"], Decimal("0"))
        self.assertEqual(target["status"], "Не начато")
        self.assertEqual(target["source_estimate_version_id"], fixture["targetVersionId"])
        self.assertEqual(contract_total, Decimal("7000"))
        self.assertEqual(receipt["source_item_id"], fixture["sourceItemId"])
        self.assertEqual(receipt["target_item_id"], target["id"])
        self.assertEqual(receipt["source_quantity_before"], Decimal("10"))
        self.assertEqual(receipt["source_quantity_after"], Decimal("7"))
        self.assertEqual(receipt["source_done_quantity"], Decimal("4"))
        self.assertEqual(receipt["confirmed_quantity"], Decimal("4"))
        self.assertEqual(receipt["transfer_quantity"], Decimal("3"))
        self.assertEqual(receipt["contract_total_before"], Decimal("7000"))
        self.assertEqual(receipt["contract_total_after"], Decimal("7000"))

        second = self._apply_serializable(fixture)
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["transfers"], first["transfers"])
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM public.brigade_contract_items WHERE contract_id=%s",
                (fixture["contractId"],),
            )
            self.assertEqual(cur.fetchone()[0], 2)
            cur.execute(
                "SELECT COUNT(*) FROM public.estimate_row_assignment_transfers WHERE plan_id=%s",
                (fixture["planId"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)
            with self.assertRaisesRegex(
                psycopg2.Error,
                "estimate_row_assignment_transfer_immutable",
            ):
                cur.execute(
                    """UPDATE public.estimate_row_assignment_transfers
                          SET applied_by_name='tampered' WHERE plan_id=%s""",
                    (fixture["planId"],),
                )

    def test_zz_supply_apply_preserves_history_and_is_idempotent(self):
        fixture = self._create_approved_supply_fixture(706)
        protected_before = self._protected_rows_snapshot()

        first = self._apply_supply_serializable(fixture)

        self.assertFalse(first["idempotent"])
        self.assertEqual(first["state"], "supply_allocated")
        self.assertEqual(first["supplyCount"], 1)
        self.assertEqual(first["allocations"][0]["quantity"], "3")
        self.assertEqual(protected_before, self._protected_rows_snapshot())
        with self.admin.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM public.estimate_row_supply_allocations WHERE plan_id=%s",
                (fixture["planId"],),
            )
            receipt = dict(cur.fetchone())
        self.assertEqual(receipt["request_id"], fixture["requestId"])
        self.assertEqual(receipt["request_item_index"], 0)
        self.assertEqual(receipt["source_estimate_id"], fixture["sourceEstimateId"])
        self.assertEqual(receipt["target_estimate_id"], fixture["targetEstimateId"])
        self.assertEqual(receipt["requested_quantity"], Decimal("10"))
        self.assertEqual(receipt["received_quantity"], Decimal("2"))
        self.assertEqual(receipt["previously_allocated_quantity"], Decimal("0"))
        self.assertEqual(receipt["allocation_quantity"], Decimal("3"))
        self.assertEqual(receipt["remaining_unallocated_quantity"], Decimal("5"))
        self.assertEqual(receipt["target_material_name"], "New mix")

        second = self._apply_supply_serializable(fixture)
        self.assertTrue(second["idempotent"])
        self.assertEqual(second["allocations"], first["allocations"])
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM public.estimate_row_supply_allocations WHERE plan_id=%s",
                (fixture["planId"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)
            with self.assertRaisesRegex(
                psycopg2.Error,
                "estimate_row_supply_allocation_immutable",
            ):
                cur.execute(
                    """UPDATE public.estimate_row_supply_allocations
                          SET applied_by_name='tampered' WHERE plan_id=%s""",
                    (fixture["planId"],),
                )

    def test_zzz_concurrent_supply_apply_never_duplicates_allocation(self):
        fixture = self._create_approved_supply_fixture(707)
        barrier = threading.Barrier(2)
        results = []
        results_lock = threading.Lock()

        def run_apply():
            barrier.wait(timeout=10)
            try:
                value = self._apply_supply_serializable(fixture)
            except (
                psycopg2.IntegrityError,
                psycopg2.errors.SerializationFailure,
                psycopg2.errors.DeadlockDetected,
                psycopg2.errors.LockNotAvailable,
            ) as exc:
                value = {"conflict": exc.pgcode or "serialization"}
            with results_lock:
                results.append(value)

        threads = [threading.Thread(target=run_apply) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 2)
        self.assertEqual(
            sum(result.get("idempotent") is False for result in results),
            1,
        )
        self.assertTrue(any(
            result.get("idempotent") is True or "conflict" in result
            for result in results
        ))
        with self.admin.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*),COALESCE(SUM(allocation_quantity),0)
                     FROM public.estimate_row_supply_allocations WHERE plan_id=%s""",
                (fixture["planId"],),
            )
            self.assertEqual(cur.fetchone(), (1, Decimal("3")))

    def test_zzzz_supply_delivery_drift_rolls_back_allocation(self):
        fixture = self._create_approved_supply_fixture(708)
        with self.admin.cursor() as cur:
            cur.execute(
                "UPDATE public.supply_deliveries SET received_quantity=3 WHERE id=%s",
                (fixture["deliveryId"],),
            )
        protected_before = self._protected_rows_snapshot()

        with self.assertRaisesRegex(SupplyApplyError, "supply_plan_stale"):
            self._apply_supply_serializable(fixture)

        self.assertEqual(protected_before, self._protected_rows_snapshot())
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM public.estimate_row_supply_allocations WHERE plan_id=%s",
                (fixture["planId"],),
            )
            self.assertEqual(cur.fetchone()[0], 0)

    def test_zzz_concurrent_apply_never_duplicates_the_split(self):
        fixture = self._create_approved_assignment_fixture(704)
        barrier = threading.Barrier(2)
        results = []
        results_lock = threading.Lock()

        def run_apply():
            barrier.wait(timeout=10)
            try:
                value = self._apply_serializable(fixture)
            except (
                psycopg2.errors.SerializationFailure,
                psycopg2.errors.DeadlockDetected,
                psycopg2.errors.LockNotAvailable,
            ) as exc:
                value = {"conflict": exc.pgcode or "serialization"}
            with results_lock:
                results.append(value)

        threads = [threading.Thread(target=run_apply) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 2)
        self.assertEqual(
            sum(result.get("idempotent") is False for result in results),
            1,
        )
        self.assertTrue(
            any(
                result.get("idempotent") is True or "conflict" in result
                for result in results
            )
        )
        with self.admin.cursor() as cur:
            cur.execute(
                """SELECT quantity FROM public.brigade_contract_items
                    WHERE id=%s""",
                (fixture["sourceItemId"],),
            )
            self.assertEqual(cur.fetchone()[0], Decimal("7"))
            cur.execute(
                """SELECT COUNT(*),COALESCE(SUM(quantity),0)
                     FROM public.brigade_contract_items
                    WHERE contract_id=%s AND source_estimate_version_id=%s""",
                (fixture["contractId"], fixture["targetVersionId"]),
            )
            self.assertEqual(cur.fetchone(), (1, Decimal("3")))
            cur.execute(
                """SELECT COUNT(*) FROM public.estimate_row_assignment_transfers
                    WHERE plan_id=%s""",
                (fixture["planId"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)

    def test_zzzz_stale_confirmed_quantity_rolls_back_every_apply_write(self):
        fixture = self._create_approved_assignment_fixture(705)
        with self.admin.cursor() as cur:
            cur.execute(
                "UPDATE public.work_journal SET quantity=5 WHERE id=%s",
                (fixture["workJournalId"],),
            )
        protected_before = self._protected_rows_snapshot()

        with self.assertRaisesRegex(AssignmentApplyError, "assignment_plan_stale"):
            self._apply_serializable(fixture)

        self.assertEqual(protected_before, self._protected_rows_snapshot())
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT quantity FROM public.brigade_contract_items WHERE id=%s",
                (fixture["sourceItemId"],),
            )
            self.assertEqual(cur.fetchone()[0], Decimal("10"))
            cur.execute(
                "SELECT COUNT(*) FROM public.brigade_contract_items WHERE contract_id=%s",
                (fixture["contractId"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute(
                "SELECT total_amount FROM public.brigade_contracts WHERE id=%s",
                (fixture["contractId"],),
            )
            self.assertEqual(cur.fetchone()[0], Decimal("7000"))
            cur.execute(
                "SELECT COUNT(*) FROM public.estimate_row_assignment_transfers WHERE plan_id=%s",
                (fixture["planId"],),
            )
            self.assertEqual(cur.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
