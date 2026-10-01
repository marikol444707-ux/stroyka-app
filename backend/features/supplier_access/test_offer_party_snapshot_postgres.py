"""Real PostgreSQL immutability checks for quotation party snapshots."""

import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import psycopg2

from backend.features.supplier_access.test_postgres_chain_support import connection_settings


@unittest.skipUnless(
    os.environ.get("SUPPLY_CHAIN_RUN_POSTGRES") == "1",
    "Fresh isolated PostgreSQL required",
)
class OfferPartySnapshotPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connection = psycopg2.connect(**connection_settings(os.environ))
        cls.connection.autocommit = False
        with cls.connection, cls.connection.cursor() as cursor:
            cursor.execute("""CREATE TABLE supplier_offers (
                id SERIAL PRIMARY KEY,
                request_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                supplier_id INTEGER NOT NULL
            )""")
        path = Path(__file__).resolve().parents[3] / "migrations/versions/0074_offer_party_snapshots.py"
        spec = importlib.util.spec_from_file_location("offer_party_snapshot_migration", path)
        cls.migration = importlib.util.module_from_spec(spec)
        alembic = ModuleType("alembic")
        alembic.op = None
        with patch.dict(sys.modules, {"alembic": alembic}):
            spec.loader.exec_module(cls.migration)
        with cls.connection, cls.connection.cursor() as cursor:
            with patch.object(cls.migration, "op", SimpleNamespace(execute=cursor.execute)):
                cls.migration.upgrade()

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()

    def setUp(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute("TRUNCATE supplier_offers RESTART IDENTITY")

    def _insert_frozen(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute("""INSERT INTO supplier_offers(request_id,company_id,supplier_id,party_snapshot_json)
                VALUES(31,2,9,%s::jsonb) RETURNING id""", ('{"version":1}',))
            return cursor.fetchone()[0]

    def test_snapshot_and_party_scope_are_immutable_after_first_response(self):
        offer_id = self._insert_frozen()
        for column, value in (
            ("party_snapshot_json", "'{\"version\":2}'::jsonb"),
            ("company_id", "3"),
            ("request_id", "32"),
            ("supplier_id", "10"),
        ):
            with self.subTest(column=column):
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    with self.connection, self.connection.cursor() as cursor:
                        cursor.execute(f"UPDATE supplier_offers SET {column}={value} WHERE id=%s", (offer_id,))

    def test_unanswered_offer_can_be_scoped_and_frozen_once(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO supplier_offers(request_id,company_id,supplier_id) VALUES(31,2,9) RETURNING id")
            offer_id = cursor.fetchone()[0]
            cursor.execute("UPDATE supplier_offers SET supplier_id=10,party_snapshot_json=%s::jsonb WHERE id=%s",
                           ('{"version":1}', offer_id))
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute("SELECT supplier_id,party_snapshot_json->>'version' FROM supplier_offers WHERE id=%s", (offer_id,))
            self.assertEqual(cursor.fetchone(), (10, "1"))

    def test_downgrade_refuses_to_discard_history(self):
        self._insert_frozen()
        with self.assertRaises(psycopg2.errors.RaiseException):
            with self.connection, self.connection.cursor() as cursor:
                with patch.object(self.migration, "op", SimpleNamespace(execute=cursor.execute)):
                    self.migration.downgrade()


if __name__ == "__main__":
    unittest.main()
