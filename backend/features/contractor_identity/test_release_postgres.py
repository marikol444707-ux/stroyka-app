"""Real Alembic 0100 -> 0101 rehearsal on a small synthetic predecessor schema.

This is not a production clone or a rehearsal of the complete migration history.
Requires a fresh explicit socket-only supply_chain_test_* database.
"""
import importlib.util
import os
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch
from uuid import uuid4

from ..supplier_access.test_postgres_chain_support import connection_settings, _assert_empty_database

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class UnifiedReleasePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from alembic.config import Config
        from alembic import command
        from ..material_packaging.history_lock_schema import GUARD_SQL
        cls.settings = connection_settings(os.environ)
        cls.connect = staticmethod(lambda: psycopg2.connect(**cls.settings))
        cls.config = Config(str(ROOT / 'alembic.ini'))
        cls.config.set_main_option('script_location', str(ROOT / 'migrations'))
        spec = importlib.util.spec_from_file_location('release_database_check', ROOT / 'scripts/release_database_check.py')
        cls.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.checker)
        conn = cls.connect()
        try:
            _assert_empty_database(conn, cls.settings)
            with conn, conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE companies(id INTEGER PRIMARY KEY);
                    CREATE TABLE users(id INTEGER PRIMARY KEY);
                    CREATE TABLE projects(id INTEGER PRIMARY KEY,company_id INTEGER);
                    CREATE TABLE staff(id INTEGER PRIMARY KEY,company_id INTEGER,company_scope_verified BOOLEAN);
                    CREATE TABLE user_company_roles(id INTEGER PRIMARY KEY,user_id INTEGER,company_id INTEGER,
                        staff_id INTEGER,active BOOLEAN,role TEXT);
                    CREATE TABLE brigade_contracts(id INTEGER PRIMARY KEY,company_id INTEGER,project_id INTEGER,
                        contractor_id INTEGER,work_package TEXT,status TEXT,party_snapshot_json JSONB,party_snapshot_hash TEXT);
                    CREATE TABLE brigade_contract_items(id INTEGER PRIMARY KEY,contract_id INTEGER,
                        source_estimate_version_id INTEGER,price NUMERIC);
                    CREATE TABLE estimates(id INTEGER PRIMARY KEY,company_id INTEGER);
                    CREATE TABLE estimate_versions(id INTEGER PRIMARY KEY,estimate_id INTEGER);
                    CREATE TABLE suppliers(id INTEGER PRIMARY KEY);
                    CREATE TABLE company_supplier_links(id INTEGER PRIMARY KEY,company_id INTEGER,supplier_id INTEGER);
                    CREATE TABLE material_packaging_rules(id INTEGER PRIMARY KEY,supplier_id INTEGER);
                    CREATE TABLE alembic_version(version_num VARCHAR(32) PRIMARY KEY);
                    INSERT INTO alembic_version VALUES('0100_packaging_history_guard');
                    INSERT INTO companies VALUES(1),(2);
                    INSERT INTO users VALUES(1),(2);
                    INSERT INTO projects VALUES(1,1),(2,2);
                    INSERT INTO brigade_contracts VALUES(1,1,1,NULL,'Основная','Подписан',
                        '{"frozenParty":"synthetic original"}','original-snapshot-hash');
                    INSERT INTO brigade_contract_items VALUES(1,1,NULL,123.45);
                ''')
                cur.execute(GUARD_SQL)
            cls.before = cls.history(conn)
            conn.rollback()
            cls.baseline_report = cls.checker.inspect_connection(conn)
        finally:
            conn.close()
        db = ModuleType('backend.db')
        db.DB_CONFIG = cls.settings
        with patch.dict('sys.modules', {'backend.db': db}):
            command.upgrade(cls.config, cls.checker.SOURCE_REVISION)

    @staticmethod
    def history(conn):
        with conn.cursor() as cur:
            cur.execute('SELECT to_jsonb(t) FROM brigade_contracts t ORDER BY id')
            contracts = cur.fetchall()
            cur.execute('SELECT to_jsonb(t) FROM brigade_contract_items t ORDER BY id')
            return contracts, cur.fetchall()

    def test_00_real_upgrade_preserves_legacy_snapshots_prices_and_does_no_backfill(self):
        conn = self.connect()
        try:
            # This historical 0100 fixture is not the supported release source.
            self.assertEqual(self.baseline_report['status'], 'blocked')
            self.assertIn('UNEXPECTED_DATABASE_REVISION', self.baseline_report['blockers'])
            self.assertEqual(self.baseline_report['pendingMigrations'], [])
            self.assertEqual(self.before, self.history(conn))
            conn.rollback()
            report = self.checker.inspect_connection(conn)
            self.assertEqual(report['status'], 'blocked', report)
            self.assertIn('INTEGRATION_RELEASE_ACCEPTANCE_REQUIRED', report['blockers'])
            self.assertEqual(report['checks']['manualOriginCount'], 0)
        finally:
            conn.close()

    def test_01_readonly_checker_and_missing_guard_fail_closed_without_data_changes(self):
        import psycopg2
        conn = self.connect()
        try:
            report = self.checker.inspect_connection(conn)
            self.assertTrue(report['readOnly'])
            conn.set_session(readonly=True, autocommit=False)
            with conn.cursor() as cur, self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
                cur.execute('UPDATE brigade_contract_items SET price=0')
            conn.rollback()
            conn.set_session(readonly=False, autocommit=False)
            with conn, conn.cursor() as cur:
                cur.execute('ALTER TABLE brigade_contracts DISABLE TRIGGER manual_brigade_identity_guard')
            try:
                report = self.checker.inspect_connection(conn)
                self.assertIn('MANUAL_GUARD_MISSING_OR_DISABLED', report['blockers'])
            finally:
                conn.set_session(readonly=False, autocommit=False)
                with conn, conn.cursor() as cur:
                    cur.execute('ALTER TABLE brigade_contracts ENABLE TRIGGER manual_brigade_identity_guard')
            self.assertEqual(self.before, self.history(conn))
        finally:
            conn.close()

    def test_02_actual_downgrade_refuses_used_origin_and_keeps_revision_and_identity(self):
        from alembic import command
        conn = self.connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("INSERT INTO brigade_contracts VALUES(2,1,1,NULL,'Основная','Черновик',NULL,NULL)")
                cur.execute('''INSERT INTO manual_brigade_contract_origins
                    (contract_id,company_id,project_id,request_id,command_hash,created_by)
                    VALUES(2,1,1,%s,%s,1)''', (str(uuid4()), 'a' * 64))
            original = self.history(conn)
            conn.rollback()
            db = ModuleType('backend.db')
            db.DB_CONFIG = self.settings
            with patch.dict('sys.modules', {'backend.db': db}), self.assertRaises(Exception) as raised:
                command.downgrade(self.config, self.checker.BASE_REVISION)
            self.assertIn('Preserve manual contract origins', str(raised.exception))
            self.assertEqual(original, self.history(conn))
            conn.rollback()
            report = self.checker.inspect_connection(conn)
            self.assertEqual(report['status'], 'blocked', report)
            self.assertIn('INTEGRATION_RELEASE_ACCEPTANCE_REQUIRED', report['blockers'])
            self.assertEqual(report['checks']['manualOriginCount'], 1)
        finally:
            conn.close()
