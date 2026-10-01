"""Real PostgreSQL checks for immutable RFQ requester snapshots.

The suite runs only in a fresh, explicit Unix-socket test database created by
scripts/run_supplier_catalog_postgres_tests.py.
"""

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
class RfqRequesterSnapshotPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = connection_settings(os.environ)
        cls.connection = psycopg2.connect(**cls.settings)
        cls.connection.autocommit = False
        with cls.connection, cls.connection.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE supply_requests (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    project TEXT NOT NULL
                )"""
            )
        migration_path = (
            Path(__file__).resolve().parents[3]
            / "migrations/versions/0073_rfq_requester_snapshots.py"
        )
        spec = importlib.util.spec_from_file_location("rfq_snapshot_migration", migration_path)
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
            cursor.execute("TRUNCATE supply_requests RESTART IDENTITY")

    def _insert_frozen(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO supply_requests(company_id,project,delivery_address,requester_snapshot_json)
                   VALUES(2,'Лицей №4','Старый адрес',%s::jsonb) RETURNING id""",
                ('{"version": 1, "companyId": 2}',),
            )
            return cursor.fetchone()[0]

    def test_snapshot_scope_and_delivery_are_immutable_after_freeze(self):
        request_id = self._insert_frozen()
        for column, value in (
            ("requester_snapshot_json", "'{\"version\": 2}'::jsonb"),
            ("company_id", "3"),
            ("project", "'Другой объект'"),
            ("delivery_address", "'Новый адрес'"),
        ):
            with self.subTest(column=column):
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    with self.connection, self.connection.cursor() as cursor:
                        cursor.execute(
                            f"UPDATE supply_requests SET {column}={value} WHERE id=%s",
                            (request_id,),
                        )

    def test_unfrozen_request_can_be_edited_and_frozen_once(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO supply_requests(company_id,project,delivery_address)
                   VALUES(2,'Лицей №4','Первый адрес') RETURNING id"""
            )
            request_id = cursor.fetchone()[0]
            cursor.execute(
                """UPDATE supply_requests
                      SET delivery_address='Итоговый адрес', requester_snapshot_json=%s::jsonb
                    WHERE id=%s""",
                ('{"version": 1, "companyId": 2}', request_id),
            )
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                "SELECT delivery_address,requester_snapshot_json->>'version' FROM supply_requests WHERE id=%s",
                (request_id,),
            )
            self.assertEqual(cursor.fetchone(), ("Итоговый адрес", "1"))

    def test_downgrade_refuses_to_discard_frozen_history(self):
        self._insert_frozen()
        with self.assertRaises(psycopg2.errors.RaiseException):
            with self.connection, self.connection.cursor() as cursor:
                with patch.object(self.migration, "op", SimpleNamespace(execute=cursor.execute)):
                    self.migration.downgrade()

    def test_downgrade_refuses_to_discard_draft_delivery_address(self):
        with self.connection, self.connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO supply_requests(company_id,project,delivery_address)
                   VALUES(2,'Лицей №4','Адрес черновика')"""
            )
        with self.assertRaises(psycopg2.errors.RaiseException):
            with self.connection, self.connection.cursor() as cursor:
                with patch.object(self.migration, "op", SimpleNamespace(execute=cursor.execute)):
                    self.migration.downgrade()


if __name__ == "__main__":
    unittest.main()
