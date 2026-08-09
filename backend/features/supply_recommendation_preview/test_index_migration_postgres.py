import json
import os
import re
import unittest
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor

from backend.features.supply_recommendation_preview import index_migration
from backend.features.supply_recommendation_preview.index_migration import (
    APPLY_CONFIRMATION,
    INDEX_NAME,
    ROLLBACK_SQL,
    SupplierReviewIndexMigrationError,
    run_supplier_user_index_migration,
)
from backend.features.supply_recommendation_preview.supplier_eligibility import (
    _has_supporting_index,
)


RUN_POSTGRES = os.getenv("A8_3A_RUN_POSTGRES_INTEGRATION") == "1"
TEST_DATABASE_URL = os.getenv("A8_3A_TEST_DATABASE_URL", "")


@unittest.skipUnless(
    RUN_POSTGRES and TEST_DATABASE_URL,
    "set A8_3A_RUN_POSTGRES_INTEGRATION=1 and a dedicated database URL",
)
class SupplierUserIndexPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = parse_dsn(TEST_DATABASE_URL).get("dbname", "")
        if not re.fullmatch(r"a8_3a_[a-z0-9_]+", configured):
            raise RuntimeError(
                "A8.3a PostgreSQL tests require a dedicated a8_3a_* database"
            )
        cls.connection = psycopg2.connect(TEST_DATABASE_URL)
        cls.connection.autocommit = True
        with cls.connection.cursor() as cur:
            cur.execute("SELECT pg_catalog.current_database()")
            actual = cur.fetchone()[0]
            if actual != configured:
                raise RuntimeError("dedicated database identity changed")
            cur.execute("DROP TABLE IF EXISTS public.suppliers CASCADE")
            cur.execute(
                "DROP OPERATOR CLASS IF EXISTS public.a8_int4_ops USING btree"
            )
            cur.execute(
                "DROP OPERATOR IF EXISTS public.===(integer,integer)"
            )
            cur.execute(
                """CREATE TABLE public.suppliers (
                     id SERIAL PRIMARY KEY,
                     user_id INTEGER,
                     status TEXT
                   )"""
            )

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "connection"):
            with cls.connection.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS public.suppliers CASCADE")
                cur.execute(
                    "DROP OPERATOR CLASS IF EXISTS "
                    "public.a8_int4_ops USING btree"
                )
                cur.execute(
                    "DROP OPERATOR IF EXISTS public.===(integer,integer)"
                )
            cls.connection.close()

    def get_db(self):
        connection = psycopg2.connect(TEST_DATABASE_URL)
        connection.autocommit = True
        return connection

    def index_exists(self, name=INDEX_NAME):
        with self.connection.cursor() as cur:
            cur.execute(
                """SELECT EXISTS(
                     SELECT 1
                       FROM pg_catalog.pg_class relation
                       JOIN pg_catalog.pg_namespace namespace
                         ON namespace.oid=relation.relnamespace
                      WHERE namespace.nspname=%s
                        AND relation.relname=%s
                        AND relation.relkind='i'
                      LIMIT 1
                   )""",
                ("public", name),
            )
            return cur.fetchone()[0]

    def runtime_gate(self):
        with self.connection.cursor(cursor_factory=RealDictCursor) as cur:
            return _has_supporting_index(
                cur,
                "suppliers",
                "user_id",
                "id",
            )

    def test_transactional_apply_catalog_semantics_repeat_and_rollback(self):
        dry_run = run_supplier_user_index_migration(self.get_db)
        self.assertTrue(dry_run["readyForApply"])
        self.assertEqual(dry_run["changeCount"], 1)
        self.assertFalse(self.index_exists())
        self.assertFalse(self.runtime_gate())

        with self.connection.cursor() as cur:
            cur.execute(
                """CREATE OPERATOR public.=== (
                     LEFTARG=integer,
                     RIGHTARG=integer,
                     FUNCTION=pg_catalog.int4eq,
                     COMMUTATOR=OPERATOR(public.===),
                     RESTRICT=pg_catalog.eqsel,
                     JOIN=pg_catalog.eqjoinsel
                   )"""
            )
            cur.execute(
                """CREATE OPERATOR CLASS public.a8_int4_ops
                     FOR TYPE integer USING btree AS
                     OPERATOR 1 < (integer,integer),
                     OPERATOR 2 <= (integer,integer),
                     OPERATOR 3 public.=== (integer,integer),
                     OPERATOR 4 >= (integer,integer),
                     OPERATOR 5 > (integer,integer),
                     FUNCTION 1 pg_catalog.btint4cmp(integer,integer)"""
            )
            cur.execute(
                """CREATE INDEX idx_a8_3a_custom_opclass
                     ON public.suppliers USING btree
                     (user_id public.a8_int4_ops,
                      id public.a8_int4_ops)"""
            )
            cur.execute(
                """INSERT INTO public.suppliers(user_id,status)
                     SELECT value%100,NULL
                       FROM pg_catalog.generate_series(1,10000) AS value"""
            )
            cur.execute("ANALYZE public.suppliers")
            cur.execute(
                """EXPLAIN (FORMAT JSON,COSTS OFF)
                     SELECT id AS supplier_id,user_id AS supplier_user_id
                       FROM public.suppliers
                      WHERE user_id=ANY(ARRAY[1])
                      ORDER BY user_id
                      LIMIT 101"""
            )
            explain = cur.fetchone()[0]
        self.assertIn("Seq Scan", json.dumps(explain, sort_keys=True))
        custom = run_supplier_user_index_migration(self.get_db)
        self.assertTrue(custom["readyForApply"])
        self.assertIsNone(custom["matchingIndex"])
        self.assertFalse(self.runtime_gate())
        with self.connection.cursor() as cur:
            cur.execute("DROP INDEX public.idx_a8_3a_custom_opclass")
            cur.execute(
                "DROP OPERATOR CLASS public.a8_int4_ops USING btree"
            )
            cur.execute("DROP OPERATOR public.===(integer,integer)")

        real_collect = index_migration._collect_catalog
        calls = 0

        def fail_only_postcheck(cur):
            nonlocal calls
            calls += 1
            facts = real_collect(cur)
            if calls == 2:
                facts["canonicalNameHolder"] = {
                    "exists": False,
                    "oid": None,
                    "relkind": None,
                }
                facts["indexes"] = []
            return facts

        with patch(
            "backend.features.supply_recommendation_preview.index_migration._collect_catalog",
            side_effect=fail_only_postcheck,
        ):
            with self.assertRaises(SupplierReviewIndexMigrationError) as error:
                run_supplier_user_index_migration(
                    self.get_db,
                    apply=True,
                    confirm=APPLY_CONFIRMATION,
                    expected_change_count=1,
                    expected_plan_sha256=dry_run["planSha256"],
                )
        self.assertEqual(
            error.exception.code,
            "supplier_index_postcheck_failed",
        )
        self.assertFalse(self.index_exists())
        self.assertFalse(self.runtime_gate())

        applied = run_supplier_user_index_migration(
            self.get_db,
            apply=True,
            confirm=APPLY_CONFIRMATION,
            expected_change_count=1,
            expected_plan_sha256=dry_run["planSha256"],
        )
        self.assertTrue(applied["committed"])
        self.assertEqual(applied["schemaWritesAttempted"], 1)
        self.assertTrue(self.index_exists())
        self.assertTrue(self.runtime_gate())

        complete = run_supplier_user_index_migration(self.get_db)
        repeat = run_supplier_user_index_migration(
            self.get_db,
            apply=True,
            confirm=APPLY_CONFIRMATION,
            expected_change_count=0,
            expected_plan_sha256=complete["planSha256"],
        )
        self.assertTrue(repeat["complete"])
        self.assertEqual(repeat["schemaWritesAttempted"], 0)

        with self.connection.cursor() as cur:
            cur.execute(ROLLBACK_SQL)
            cur.execute(
                """CREATE INDEX idx_a8_3a_partial
                     ON public.suppliers USING btree (user_id,id)
                     WHERE user_id IS NOT NULL"""
            )
        partial = run_supplier_user_index_migration(self.get_db)
        self.assertTrue(partial["readyForApply"])
        self.assertEqual(partial["matchingIndex"], None)
        with self.connection.cursor() as cur:
            cur.execute("DROP INDEX public.idx_a8_3a_partial")
            cur.execute(
                """CREATE INDEX idx_a8_3a_equivalent
                     ON public.suppliers USING btree (user_id,id)"""
            )
        equivalent = run_supplier_user_index_migration(self.get_db)
        self.assertTrue(equivalent["complete"])
        self.assertEqual(
            equivalent["matchingIndex"],
            "idx_a8_3a_equivalent",
        )
        with self.connection.cursor() as cur:
            cur.execute("DROP INDEX public.idx_a8_3a_equivalent")
            cur.execute(
                """CREATE INDEX idx_suppliers_user_id_id
                     ON public.suppliers USING btree (id,user_id)"""
            )
        conflict = run_supplier_user_index_migration(self.get_db)
        self.assertFalse(conflict["schemaReady"])
        self.assertEqual(
            conflict["blockers"],
            ["supplier_index_name_conflict"],
        )
        with self.connection.cursor() as cur:
            cur.execute("DROP INDEX public.idx_suppliers_user_id_id")
            cur.execute(
                """CREATE INDEX idx_suppliers_user_id_id
                     ON public.suppliers USING btree (user_id DESC,id)"""
            )
        descending = run_supplier_user_index_migration(self.get_db)
        self.assertFalse(descending["schemaReady"])
        self.assertEqual(
            descending["blockers"],
            ["supplier_index_name_conflict"],
        )


if __name__ == "__main__":
    unittest.main()
