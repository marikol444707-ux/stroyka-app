"""Production-shaped bootstrap at revision 0007, then the exact Alembic target."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CatalogMigrationPostgresTests(unittest.TestCase):
    def test_explicit_target_migrates_zero_links_without_payment_chain_or_guessed_ownership(self):
        from .test_postgres_chain_support import build_fixture
        from alembic import command
        from alembic.config import Config
        from sqlalchemy import create_engine
        main, fixture, cleanup = build_fixture()
        self.addCleanup(cleanup)
        root = Path(__file__).resolve().parents[3]
        config = Config(str(root / 'alembic.ini'))
        config.set_main_option('script_location', str(root / 'migrations'))
        conn = main.get_db()
        self.addCleanup(conn.close)
        with conn.cursor() as cur:
            cur.execute('DELETE FROM company_supplier_links')
            cur.execute("INSERT INTO suppliers(name,notes) SELECT 'Legacy ' || n,'Private conditions' FROM generate_series(1,26) n")
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            before = {r[0] for r in cur.fetchall()}
            cur.execute('SELECT id,notes,inn FROM suppliers ORDER BY id')
            sources = cur.fetchall()
        def connect():
            connection = main.get_db()
            connection.autocommit = False
            return connection
        engine = create_engine('postgresql+psycopg2://', creator=connect)
        self.addCleanup(engine.dispose)
        with patch('sqlalchemy.create_engine', return_value=engine):
            command.stamp(config, '0007_warehouse_vat_labels')
            command.upgrade(config, 'supplier_catalog@head')
        with conn.cursor() as cur:
            cur.execute('SELECT version_num FROM alembic_version')
            self.assertEqual(cur.fetchall(), [('0022_supplier_company_catalog',)])
            cur.execute('SELECT COUNT(*) FROM company_supplier_links')
            self.assertEqual(cur.fetchone()[0], 0)
            cur.execute('SELECT id,notes,inn FROM suppliers ORDER BY id')
            self.assertEqual(cur.fetchall(), sources)
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            self.assertEqual({r[0] for r in cur.fetchall()} - before, {'alembic_version'})
