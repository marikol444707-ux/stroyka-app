import os
import unittest
import uuid
from decimal import Decimal

import psycopg2

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
                  total NUMERIC(14,2)
                );
                ALTER TABLE public.estimates
                  ADD COLUMN IF NOT EXISTS company_id INTEGER,
                  ADD COLUMN IF NOT EXISTS project_id INTEGER,
                  ADD COLUMN IF NOT EXISTS status TEXT,
                  ADD COLUMN IF NOT EXISTS smeta_type TEXT,
                  ADD COLUMN IF NOT EXISTS work_package TEXT,
                  ADD COLUMN IF NOT EXISTS total NUMERIC(14,2);
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
            """)

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

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


if __name__ == "__main__":
    unittest.main()
