import json
import os
import unittest
import uuid

import psycopg2

from backend.features.material_control_ownership.readiness_report import (
    run_readiness_report,
)


POSTGRES_TEST_DSN = os.getenv("E5_TEST_DATABASE_URL", "")


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
                    smeta_type TEXT,
                    work_package TEXT,
                    status TEXT,
                    is_template BOOLEAN DEFAULT FALSE
                );
                """
            )

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.estimates,public.projects RESTART IDENTITY"
            )

    def tearDown(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "TRUNCATE public.estimates,public.projects RESTART IDENTITY"
            )

    def _snapshot(self):
        with self.admin.cursor() as cur:
            cur.execute(
                "SELECT id,company_id,name,archived FROM public.projects ORDER BY id"
            )
            projects = cur.fetchall()
            cur.execute(
                """SELECT id,company_id,project_id,project_name,smeta_type,
                          work_package,status,is_template
                     FROM public.estimates ORDER BY id"""
            )
            estimates = cur.fetchall()
        return projects, estimates

    def test_same_name_cross_company_fixture_is_ready_and_unchanged(self):
        collision_name = "e5-collision-" + uuid.uuid4().hex
        with self.admin.cursor() as cur:
            cur.execute(
                """INSERT INTO public.projects(company_id,name,archived)
                     VALUES (10,%s,FALSE),(20,%s,FALSE)
                     RETURNING id,company_id""",
                (collision_name, collision_name),
            )
            owners = cur.fetchall()
            for project_id, company_id in owners:
                cur.execute(
                    """INSERT INTO public.estimates(
                           company_id,project_id,project_name,smeta_type,
                           work_package,status,is_template
                       ) VALUES (%s,%s,%s,'Заказчик','Основная','Активная',FALSE)""",
                    (company_id, project_id, collision_name),
                )
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
        self.assertEqual(
            report["dataAudit"]["summary"]["nameCollisionGroups"], 1
        )
        self.assertEqual(before, self._snapshot())
        self.assertNotIn(collision_name, json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
