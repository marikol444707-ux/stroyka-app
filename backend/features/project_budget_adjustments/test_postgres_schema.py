import hashlib
import json
import os
import threading
import unittest
import uuid
from decimal import Decimal

import psycopg2
import psycopg2.extras
from psycopg2 import sql

from backend.features.project_budget_adjustments.approval import (
    BudgetAdjustmentApprovalError,
    apply_budget_adjustment,
)
from backend.features.project_budget_adjustments.preview_service import (
    build_budget_adjustment_preview,
)
from backend.features.project_budget_adjustments.schema import (
    SchemaMigrationError,
    run_schema_migration,
)


POSTGRES_TEST_DSN = os.getenv("E6_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    os.getenv("E6_RUN_POSTGRES_INTEGRATION") == "1" and POSTGRES_TEST_DSN,
    "set E6_RUN_POSTGRES_INTEGRATION=1 and E6_TEST_DATABASE_URL for PostgreSQL fixture",
)
class BudgetAdjustmentSchemaPostgresTests(unittest.TestCase):
    PAYLOAD_HISTORY_TABLES = (
        "project_payments", "expenses", "accountable_payments",
        "accountable_expenses", "work_journal", "hidden_works_acts",
        "brigade_acts", "brigade_payments", "supply_requests",
        "supply_deliveries", "supplier_offers", "supplier_invoices",
        "warehouse_main", "warehouse_movements", "warehouse_invoices",
        "warehouse_history", "estimate_versions",
        "estimate_reconciliation_items", "project_documents",
    )
    PROTECTED_HISTORY_TABLES = PAYLOAD_HISTORY_TABLES + (
        "estimates", "estimate_reconciliations",
    )

    @classmethod
    def setUpClass(cls):
        cls.admin = psycopg2.connect(POSTGRES_TEST_DSN)
        cls.admin.autocommit = True
        with cls.admin.cursor() as cur:
            cur.execute("SELECT current_database()")
            database_name = cur.fetchone()[0]
            if not str(database_name).startswith("e6_"):
                raise RuntimeError(
                    "E6 integration fixture requires a dedicated e6_* database"
                )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.projects (
                  id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL,
                  name TEXT, budget DOUBLE PRECISION DEFAULT 0
                );
                ALTER TABLE public.projects
                  ADD COLUMN IF NOT EXISTS company_id INTEGER,
                  ADD COLUMN IF NOT EXISTS budget DOUBLE PRECISION DEFAULT 0;
                CREATE TABLE IF NOT EXISTS public.estimates (
                  id SERIAL PRIMARY KEY, company_id INTEGER, project_id INTEGER,
                  status TEXT, smeta_type TEXT, work_package TEXT,
                  total NUMERIC(14,2), sections_json TEXT
                );
                ALTER TABLE public.estimates
                  ADD COLUMN IF NOT EXISTS company_id INTEGER,
                  ADD COLUMN IF NOT EXISTS project_id INTEGER,
                  ADD COLUMN IF NOT EXISTS status TEXT,
                  ADD COLUMN IF NOT EXISTS smeta_type TEXT,
                  ADD COLUMN IF NOT EXISTS work_package TEXT,
                  ADD COLUMN IF NOT EXISTS total NUMERIC(14,2),
                  ADD COLUMN IF NOT EXISTS sections_json TEXT;
                CREATE TABLE IF NOT EXISTS public.estimate_reconciliations (
                  id SERIAL PRIMARY KEY, base_estimate_id INTEGER,
                  next_estimate_id INTEGER, status TEXT, smeta_type TEXT,
                  work_package TEXT, base_total NUMERIC(14,2),
                  next_total NUMERIC(14,2)
                );
                ALTER TABLE public.estimate_reconciliations
                  ADD COLUMN IF NOT EXISTS base_estimate_id INTEGER,
                  ADD COLUMN IF NOT EXISTS next_estimate_id INTEGER,
                  ADD COLUMN IF NOT EXISTS status TEXT,
                  ADD COLUMN IF NOT EXISTS smeta_type TEXT,
                  ADD COLUMN IF NOT EXISTS work_package TEXT,
                  ADD COLUMN IF NOT EXISTS base_total NUMERIC(14,2),
                  ADD COLUMN IF NOT EXISTS next_total NUMERIC(14,2);
                CREATE TABLE IF NOT EXISTS public.users (
                  id SERIAL PRIMARY KEY, name TEXT, email TEXT UNIQUE,
                  role TEXT
                );
                CREATE TABLE IF NOT EXISTS public.user_company_roles (
                  id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL,
                  company_id INTEGER NOT NULL, role TEXT NOT NULL,
                  active BOOLEAN DEFAULT TRUE
                );
                ALTER TABLE public.user_company_roles
                  ADD COLUMN IF NOT EXISTS user_id INTEGER,
                  ADD COLUMN IF NOT EXISTS company_id INTEGER,
                  ADD COLUMN IF NOT EXISTS role TEXT,
                  ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
                CREATE TABLE IF NOT EXISTS public.project_payments
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.expenses
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.accountable_payments
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.accountable_expenses
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.work_journal
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.hidden_works_acts
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.brigade_acts
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.brigade_payments
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.supply_requests
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.supply_deliveries
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.supplier_offers
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.supplier_invoices
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.warehouse_main
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.warehouse_movements
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.warehouse_invoices
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.warehouse_history
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.estimate_versions
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.estimate_reconciliation_items
                  (id SERIAL PRIMARY KEY,payload TEXT);
                CREATE TABLE IF NOT EXISTS public.project_documents
                  (id SERIAL PRIMARY KEY,payload TEXT);
            """)

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    @staticmethod
    def _sections(total):
        return json.dumps([{"name": "Fixture", "items": [{
            "quantity": "1",
            "priceWork": str(total),
            "priceMaterial": "0",
        }]}])

    def _create_approval_fixture(self):
        marker = uuid.uuid4().hex
        company_id = 930000 + int(marker[:5], 16)
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(company_id,name,budget) "
                "VALUES (%s,%s,%s) RETURNING id",
                (company_id, "e6-approval-" + marker, Decimal("1000.00")),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.users(name,email,role) "
                "VALUES (%s,%s,'директор') RETURNING id",
                ("E6 Director", "e6-approval-" + marker + "@example.invalid"),
            )
            user_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.user_company_roles"
                "(user_id,company_id,role,active) VALUES (%s,%s,'директор',TRUE)",
                (user_id, company_id),
            )
            cur.execute(
                """INSERT INTO public.estimates
                     (company_id,project_id,status,smeta_type,work_package,total,
                      sections_json)
                   VALUES (%s,%s,'Неактивная','Заказчик','Fixture',%s,%s)
                   RETURNING id""",
                (company_id, project_id, Decimal("250.00"), self._sections("250.00")),
            )
            base_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimates
                     (company_id,project_id,status,smeta_type,work_package,total,
                      sections_json)
                   VALUES (%s,%s,'Активная','Заказчик','Fixture',%s,%s)
                   RETURNING id""",
                (company_id, project_id, Decimal("275.50"), self._sections("275.50")),
            )
            next_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO public.estimate_reconciliations
                     (base_estimate_id,next_estimate_id,status,smeta_type,
                      work_package,base_total,next_total)
                   VALUES (%s,%s,'Утверждена','Заказчик','Fixture',%s,%s)
                   RETURNING id""",
                (base_id, next_id, Decimal("250.00"), Decimal("275.50")),
            )
            reconciliation_id = cur.fetchone()[0]
        with self.admin.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            preview = build_budget_adjustment_preview(
                cur, reconciliation_id, company_id
            )
        return {
            "companyId": company_id,
            "projectId": project_id,
            "reconciliationId": reconciliation_id,
            "nextEstimateId": next_id,
            "userId": user_id,
            "planSha256": preview["planSha256"],
        }

    def _apply_fixture(
        self,
        fixture,
        *,
        expected_plan_sha256=None,
        update_budget=None,
    ):
        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        connection.set_session(autocommit=False, isolation_level="SERIALIZABLE")
        try:
            with connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                kwargs = dict(
                    reconciliation_id=fixture["reconciliationId"],
                    company_id=fixture["companyId"],
                    expected_plan_sha256=(
                        expected_plan_sha256 or fixture["planSha256"]
                    ),
                    actor={
                        "id": fixture["userId"],
                        "companyId": fixture["companyId"],
                        "name": "E6 Director",
                        "role": "директор",
                    },
                )
                if update_budget is not None:
                    kwargs["update_budget"] = update_budget
                result = apply_budget_adjustment(cur, **kwargs)
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _seed_and_hash_protected_history(self):
        marker = "e6-protected-" + uuid.uuid4().hex
        with self.admin.cursor() as cur:
            for table in self.PAYLOAD_HISTORY_TABLES:
                cur.execute(
                    sql.SQL("INSERT INTO {}(payload) VALUES (%s)").format(
                        sql.Identifier(table)
                    ),
                    (marker + "-" + table,),
                )
        return self._protected_history_sha256()

    def _protected_history_sha256(self):
        snapshot = {}
        with self.admin.cursor() as cur:
            for table in self.PROTECTED_HISTORY_TABLES:
                cur.execute(
                    sql.SQL(
                        "SELECT COALESCE(jsonb_agg(to_jsonb(item) ORDER BY id),"
                        "'[]'::jsonb)::text FROM {} item"
                    ).format(sql.Identifier(table))
                )
                snapshot[table] = cur.fetchone()[0]
        payload = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def test_lossless_apply_repeat_source_guard_and_immutability(self):
        with self.admin.cursor() as cur:
            cur.execute("""
                SELECT data_type
                  FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='projects'
                   AND column_name='budget'
            """)
            budget_type = cur.fetchone()[0]

        if budget_type == "double precision":
            with self.admin.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.projects(company_id,name,budget) "
                    "VALUES (%s,%s,%s) RETURNING id",
                    (920001, "e6-unsafe-" + uuid.uuid4().hex, 10.001),
                )
                unsafe_id = cur.fetchone()[0]
            blocked = run_schema_migration(
                lambda: psycopg2.connect(POSTGRES_TEST_DSN)
            )
            self.assertFalse(blocked["readyForApply"])
            self.assertEqual(
                blocked["blockers"], ["project_budget_conversion_unsafe"]
            )
            with self.assertRaisesRegex(
                SchemaMigrationError, "schema_catalog_blocked"
            ):
                run_schema_migration(
                    lambda: psycopg2.connect(POSTGRES_TEST_DSN),
                    apply=True,
                    expected_change_count=blocked["changeCount"],
                    expected_plan_sha256=blocked["planSha256"],
                )
            with self.admin.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.projects WHERE id=%s", (unsafe_id,)
                )

        dry_run = run_schema_migration(
            lambda: psycopg2.connect(POSTGRES_TEST_DSN)
        )
        if dry_run["changeCount"]:
            applied = run_schema_migration(
                lambda: psycopg2.connect(POSTGRES_TEST_DSN),
                apply=True,
                expected_change_count=dry_run["changeCount"],
                expected_plan_sha256=dry_run["planSha256"],
            )
            self.assertTrue(applied["schemaReady"])

        repeat = run_schema_migration(
            lambda: psycopg2.connect(POSTGRES_TEST_DSN)
        )
        self.assertTrue(repeat["schemaReady"])
        self.assertEqual(repeat["changeCount"], 0)
        self.assertEqual(repeat["writesAttempted"], 0)

        marker = uuid.uuid4().hex
        company_id = 920002
        with self.admin.cursor() as cur:
            cur.execute(
                "INSERT INTO public.projects(company_id,name,budget) "
                "VALUES (%s,%s,%s) RETURNING id",
                (company_id, "e6-project-" + marker, Decimal("1000.00")),
            )
            project_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.users(name,email,role) "
                "VALUES (%s,%s,'директор') RETURNING id",
                ("E6 fixture", "e6-" + marker + "@example.invalid"),
            )
            user_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.user_company_roles"
                "(user_id,company_id,role,active) VALUES (%s,%s,'директор',TRUE)",
                (user_id, company_id),
            )
            cur.execute(
                "INSERT INTO public.estimates"
                "(company_id,project_id,status,smeta_type,work_package,total) "
                "VALUES (%s,%s,'Неактивная','Заказчик','Fixture',%s) RETURNING id",
                (company_id, project_id, Decimal("100.00")),
            )
            base_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.estimates"
                "(company_id,project_id,status,smeta_type,work_package,total) "
                "VALUES (%s,%s,'Активная','Заказчик','Fixture',%s) RETURNING id",
                (company_id, project_id, Decimal("125.00")),
            )
            next_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO public.estimate_reconciliations"
                "(base_estimate_id,next_estimate_id,status,smeta_type,work_package,"
                "base_total,next_total) VALUES "
                "(%s,%s,'Утверждена','Заказчик','Fixture',%s,%s) RETURNING id",
                (base_id, next_id, Decimal("100.00"), Decimal("125.00")),
            )
            reconciliation_id = cur.fetchone()[0]

        connection = psycopg2.connect(POSTGRES_TEST_DSN)
        try:
            with connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.project_budget_adjustments
                      (company_id,project_id,reconciliation_id,base_estimate_id,
                       next_estimate_id,project_budget_before,estimate_base_total,
                       estimate_next_total,adjustment_amount,project_budget_after,
                       plan_sha256,approved_by_user_id,approved_by_name,
                       approved_by_role,approved_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                    RETURNING id
                    """,
                    (
                        company_id, project_id, reconciliation_id, base_id,
                        next_id, Decimal("1000.00"), Decimal("100.00"),
                        Decimal("125.00"), Decimal("25.00"),
                        Decimal("1025.00"), marker + ("0" * (64 - len(marker))),
                        user_id, "E6 fixture", "директор",
                    ),
                )
                receipt_id = cur.fetchone()[0]
                cur.execute(
                    "UPDATE public.projects SET budget=%s WHERE id=%s",
                    (Decimal("1025.00"), project_id),
                )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaisesRegex(
            psycopg2.Error, "project_budget_adjustment_immutable"
        ):
            with self.admin.cursor() as cur:
                cur.execute(
                    "UPDATE public.project_budget_adjustments "
                    "SET approved_by_name='tampered' WHERE id=%s",
                    (receipt_id,),
                )
        with self.assertRaisesRegex(
            psycopg2.Error, "project_budget_adjustment_immutable"
        ):
            with self.admin.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.project_budget_adjustments WHERE id=%s",
                    (receipt_id,),
                )

    def test_transactional_kernel_applies_delta_once_and_is_idempotent(self):
        fixture = self._create_approval_fixture()

        first = self._apply_fixture(fixture)
        second = self._apply_fixture(fixture)

        self.assertFalse(first["idempotent"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["planSha256"], fixture["planSha256"])
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT budget FROM public.projects WHERE id=%s",
                (fixture["projectId"],),
            )
            self.assertEqual(cur.fetchone()[0], Decimal("1025.50"))
            cur.execute(
                "SELECT COUNT(*) FROM public.project_budget_adjustments "
                "WHERE reconciliation_id=%s",
                (fixture["reconciliationId"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)

    def test_stale_hash_and_source_drift_roll_back_without_receipt(self):
        stale = self._create_approval_fixture()
        with self.assertRaises(BudgetAdjustmentApprovalError) as raised:
            self._apply_fixture(stale, expected_plan_sha256="0" * 64)
        self.assertEqual(raised.exception.code, "budget_adjustment_plan_stale")

        drifted = self._create_approval_fixture()
        with self.admin.cursor() as cur:
            cur.execute(
                "UPDATE public.estimates SET sections_json=%s WHERE id=%s",
                (self._sections("275.51"), drifted["nextEstimateId"]),
            )
        with self.assertRaises(BudgetAdjustmentApprovalError) as raised:
            self._apply_fixture(drifted)
        self.assertEqual(raised.exception.code, "budget_adjustment_source_drift")

        with self.admin.cursor() as cur:
            for fixture in (stale, drifted):
                cur.execute(
                    "SELECT budget FROM public.projects WHERE id=%s",
                    (fixture["projectId"],),
                )
                self.assertEqual(cur.fetchone()[0], Decimal("1000.00"))
                cur.execute(
                    "SELECT COUNT(*) FROM public.project_budget_adjustments "
                    "WHERE reconciliation_id=%s",
                    (fixture["reconciliationId"],),
                )
                self.assertEqual(cur.fetchone()[0], 0)

    def test_budget_conflict_after_receipt_insert_rolls_back_both_writes(self):
        fixture = self._create_approval_fixture()

        with self.assertRaises(BudgetAdjustmentApprovalError) as raised:
            self._apply_fixture(fixture, update_budget=lambda _cur, _plan: False)

        self.assertEqual(
            raised.exception.code,
            "budget_adjustment_budget_update_conflict",
        )
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT budget FROM public.projects WHERE id=%s",
                (fixture["projectId"],),
            )
            self.assertEqual(cur.fetchone()[0], Decimal("1000.00"))
            cur.execute(
                "SELECT COUNT(*) FROM public.project_budget_adjustments "
                "WHERE reconciliation_id=%s",
                (fixture["reconciliationId"],),
            )
            self.assertEqual(cur.fetchone()[0], 0)

    def test_apply_preserves_protected_history_byte_for_byte(self):
        fixture = self._create_approval_fixture()
        protected_before = self._seed_and_hash_protected_history()

        result = self._apply_fixture(fixture)

        self.assertFalse(result["idempotent"])
        self.assertEqual(protected_before, self._protected_history_sha256())

    def test_concurrent_double_approval_changes_budget_once(self):
        fixture = self._create_approval_fixture()
        barrier = threading.Barrier(2)
        results = []
        result_lock = threading.Lock()

        def run_apply():
            barrier.wait(timeout=10)
            try:
                value = self._apply_fixture(fixture)
            except (
                psycopg2.IntegrityError,
                psycopg2.errors.SerializationFailure,
                psycopg2.errors.DeadlockDetected,
                psycopg2.errors.LockNotAvailable,
            ) as exc:
                value = {"conflict": exc.pgcode or "serialization"}
            with result_lock:
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
                "SELECT budget FROM public.projects WHERE id=%s",
                (fixture["projectId"],),
            )
            self.assertEqual(cur.fetchone()[0], Decimal("1025.50"))
            cur.execute(
                "SELECT COUNT(*) FROM public.project_budget_adjustments "
                "WHERE reconciliation_id=%s",
                (fixture["reconciliationId"],),
            )
            self.assertEqual(cur.fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
