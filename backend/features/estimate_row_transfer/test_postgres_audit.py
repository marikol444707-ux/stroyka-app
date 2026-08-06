import json
import os
import unittest
import uuid

import psycopg2
import psycopg2.extras

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.audit import run_impact_audit
from backend.features.estimate_row_transfer.plan import normalize_draft_payload
from backend.features.estimate_row_transfer.schema import run_schema_migration
from backend.features.estimate_row_transfer.service import build_current_plan
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
                    id SERIAL PRIMARY KEY, company_id INTEGER, project_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS public.brigade_contract_items (
                    id SERIAL PRIMARY KEY, contract_id INTEGER, work_package TEXT,
                    quantity DOUBLE PRECISION, source_type TEXT,
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
            cur.execute("DROP TABLE IF EXISTS public.estimate_row_transfer_entries CASCADE")
            cur.execute("DROP TABLE IF EXISTS public.estimate_row_transfer_plans CASCADE")
            cur.execute("DROP FUNCTION IF EXISTS public.reject_estimate_row_transfer_entry_mutation()")
            cur.execute("DROP FUNCTION IF EXISTS public.guard_estimate_row_transfer_plan_mutation()")

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


if __name__ == "__main__":
    unittest.main()
