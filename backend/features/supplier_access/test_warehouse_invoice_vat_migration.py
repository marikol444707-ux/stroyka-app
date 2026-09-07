"""VAT schema contracts; PostgreSQL checks require an explicit isolated DSN."""

import importlib.util
import os
from pathlib import Path
import re
import sys
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations/versions/0007_warehouse_invoice_vat_labels.py"
POSTGRES_DSN = os.getenv("VAT_SCHEMA_TEST_DSN", "")


def _load_migration(execute):
    spec = importlib.util.spec_from_file_location("warehouse_invoice_vat_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    alembic = types.ModuleType("alembic")
    alembic.op = types.SimpleNamespace(execute=execute)
    with mock.patch.dict(sys.modules, {"alembic": alembic}):
        spec.loader.exec_module(module)
    return module


def _fresh_table_sql():
    source = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    return re.search(
        r"CREATE TABLE IF NOT EXISTS warehouse_invoices\s*\(.*?\n        \);",
        source, re.S,
    ).group(0)


class WarehouseInvoiceVatMigrationContractTests(unittest.TestCase):
    def test_fresh_bootstrap_uses_vat_labels(self):
        self.assertIn("vat TEXT DEFAULT 'Без НДС'", _fresh_table_sql())

    def test_revision_follows_staff_links_and_never_updates_totals(self):
        statements = []
        migration = _load_migration(statements.append)
        migration.upgrade()

        self.assertEqual("0007_warehouse_vat_labels", migration.revision)
        self.assertLessEqual(len(migration.revision), 32)
        self.assertEqual("0006_user_company_staff_links", migration.down_revision)
        self.assertTrue(statements)
        combined = "\n".join(statements)
        self.assertNotRegex(combined, r"(?i)\b(UPDATE|DELETE|TRUNCATE|INSERT)\b")
        self.assertNotIn("total_", combined)

    def test_downgrade_does_not_discard_business_labels_or_rates(self):
        statements = []
        _load_migration(statements.append).downgrade()
        self.assertEqual([], statements)


@unittest.skipUnless(POSTGRES_DSN, "set VAT_SCHEMA_TEST_DSN for the isolated chain_vat_test database")
class WarehouseInvoiceVatMigrationPostgresTests(unittest.TestCase):
    def setUp(self):
        import psycopg2

        params = psycopg2.extensions.parse_dsn(POSTGRES_DSN)
        if (
            params.get("dbname") != "chain_vat_test"
            or params.get("user") != "chain_test"
            or not params.get("host", "").startswith(("/private/tmp/", "/tmp/"))
            or not params.get("port")
            or set(params) - {"dbname", "user", "host", "port", "password"}
        ):
            raise RuntimeError("VAT tests require an explicit local chain_vat_test Unix-socket DSN")
        self.conn = psycopg2.connect(**params, connect_timeout=5)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor()
        self.addCleanup(self.cur.close)
        self.cur.execute("SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='1s'")
        self.cur.execute("SELECT current_database(), current_user, inet_server_addr()")
        self.assertEqual(("chain_vat_test", "chain_test", None), self.cur.fetchone())
        self.cur.execute("SELECT to_regclass('public.warehouse_invoices')")
        self.assertIsNone(self.cur.fetchone()[0], "Refuse to modify an existing warehouse table")
        self.migration = _load_migration(self.cur.execute)

    def create_table(self, vat_type):
        self.cur.execute(f"""CREATE TABLE public.warehouse_invoices (
            id INTEGER PRIMARY KEY, vat {vat_type},
            total_base NUMERIC(14,2), total_vat NUMERIC(14,2), total_with_vat NUMERIC(14,2)
        )""")

    def metadata(self):
        self.cur.execute("""SELECT data_type, column_default, is_nullable, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='warehouse_invoices' AND column_name='vat'""")
        return self.cur.fetchone()

    def rows(self):
        self.cur.execute("SELECT * FROM public.warehouse_invoices ORDER BY id")
        return self.cur.fetchall()

    def test_boolean_conversion_preserves_flags_nulls_and_every_amount(self):
        self.create_table("BOOLEAN DEFAULT FALSE")
        self.cur.execute("""INSERT INTO public.warehouse_invoices VALUES
            (1,FALSE,100,0,100), (2,TRUE,100,22,122), (3,NULL,250,50,300)""")
        before = self.rows()

        self.migration.upgrade()

        self.assertEqual(("text", "'Без НДС'::text", "YES", None), self.metadata())
        expected_labels = ["Без НДС", "С НДС", None]
        self.assertEqual([(row[0], label, *row[2:]) for row, label in zip(before, expected_labels)], self.rows())
        self.cur.execute("INSERT INTO public.warehouse_invoices(id) VALUES (4) RETURNING vat")
        self.assertEqual(("Без НДС",), self.cur.fetchone())
        self.cur.execute("INSERT INTO public.warehouse_invoices(id,vat) VALUES (5,'Без НДС')")

    def test_existing_text_and_varchar_keep_labels_defaults_and_constraints(self):
        for vat_type in ("TEXT DEFAULT 'С НДС 22%' NOT NULL", "VARCHAR(80) DEFAULT 'Особая метка' NOT NULL"):
            with self.subTest(vat_type=vat_type):
                self.cur.execute("SAVEPOINT text_fixture")
                self.create_table(vat_type)
                self.cur.execute("""INSERT INTO public.warehouse_invoices VALUES
                    (1,'С НДС 20%',100,20,120), (2,'С НДС 22%',100,22,122),
                    (3,'  НДС по документу  ',250,50,300)""")
                before = (self.metadata(), self.rows())

                self.migration.upgrade()
                self.migration.downgrade()

                self.assertEqual(before, (self.metadata(), self.rows()))
                self.cur.execute("ROLLBACK TO SAVEPOINT text_fixture")

    def test_repeated_upgrade_is_idempotent_and_downgrade_keeps_new_rates(self):
        self.create_table("BOOLEAN DEFAULT FALSE")
        self.migration.upgrade()
        self.cur.execute("INSERT INTO public.warehouse_invoices VALUES (1,'С НДС 22%',100,22,122)")
        before = (self.metadata(), self.rows())

        self.migration.upgrade()
        self.migration.downgrade()

        self.assertEqual(before, (self.metadata(), self.rows()))

    def test_unsupported_type_fails_without_changing_data(self):
        import psycopg2

        self.create_table("INTEGER DEFAULT 0")
        self.cur.execute("INSERT INTO public.warehouse_invoices VALUES (1,22,100,22,122)")
        before = (self.metadata(), self.rows())
        self.cur.execute("SAVEPOINT unsupported_type")
        with self.assertRaises(psycopg2.errors.RaiseException):
            self.migration.upgrade()
        self.cur.execute("ROLLBACK TO SAVEPOINT unsupported_type")
        self.assertEqual(before, (self.metadata(), self.rows()))

    def test_missing_table_or_column_fails_explicitly(self):
        import psycopg2

        for missing_table in (True, False):
            with self.subTest(missing_table=missing_table):
                self.cur.execute("SAVEPOINT missing_schema")
                if not missing_table:
                    self.cur.execute("CREATE TABLE public.warehouse_invoices(id INTEGER)")
                with self.assertRaises(psycopg2.errors.RaiseException):
                    self.migration.upgrade()
                self.cur.execute("ROLLBACK TO SAVEPOINT missing_schema")

    def test_fresh_bootstrap_accepts_real_receipt_label(self):
        self.cur.execute(_fresh_table_sql())
        self.cur.execute("""INSERT INTO public.warehouse_invoices(number,vat)
            VALUES ('LOCAL VAT receipt','Без НДС') RETURNING vat""")
        self.assertEqual(("Без НДС",), self.cur.fetchone())


if __name__ == "__main__":
    unittest.main()
