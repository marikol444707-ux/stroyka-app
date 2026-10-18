"""Opt-in disposable Unix-socket PG test. Never loads application DB configuration.

Exercises real route transaction + command SQL with synthetic stock worker;
not a full stock/traceability/authentication end-to-end test.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Event
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import Mock
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from fastapi import HTTPException

from backend.features.material_traceability.test_movement_transaction import load_route
from backend.features.warehouse_distribution.test_postgres_support import connection_settings
from backend.features.warehouse_movements.idempotency import SCHEMA_SQL


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
            'Requires explicitly configured disposable Unix-socket PostgreSQL; no live DB fallback')
class MovementCommandPostgresTests(TestCase):
    def setUp(self):
        self.settings = connection_settings(os.environ)
        self.schema = 'movement_retry_' + uuid4().hex
        self.control = psycopg2.connect(**self.settings)
        self.control.autocommit = True
        with self.control.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
            cur.execute('CREATE TABLE companies(id integer PRIMARY KEY)')
            cur.execute('INSERT INTO companies VALUES(2)')
            cur.execute(SCHEMA_SQL)
            cur.execute('CREATE TABLE stock(quantity integer NOT NULL)')
            cur.execute('INSERT INTO stock VALUES(10)')
            cur.execute('CREATE TABLE moves(id serial PRIMARY KEY)')
        self.addCleanup(self.cleanup_schema)
        self.model = SimpleNamespace(commandId=str(uuid4()), materialName='Cable', fromLocation='Основной склад',
            toLocation='School', workPackage='', quantity=2, unit='m', date='2026-10-18', createdBy='Test',
            notes='', invoiceId=None, invoiceLineIndex=None)

    def cleanup_schema(self):
        with self.control.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.control.close()

    def get_db(self):
        conn = psycopg2.connect(**self.settings)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
            cur.execute("SET statement_timeout='10s'")
        return conn

    def route(self, worker):
        return load_route(dict(get_db=self.get_db, psycopg2=psycopg2,
            os=SimpleNamespace(getenv=lambda *args: None), HTTPException=HTTPException,
            PACKAGE_LIMIT_ROLES=(), MAIN_WAREHOUSE_WRITE_ROLES=('директор',),
            require_project_or_warehouse_access=Mock(), _project_company_id=lambda *_: 2,
            _positive_int_or_none=lambda value: value, _resolve_work_company_context=lambda *a, **k: {'companyId': 2},
            _apply_warehouse_movement=worker,
            _create_warehouse_movement_review_task_safely=Mock(return_value={}), _run_project_ai_control_safely=Mock()))

    def worker(self, cur, model, *_):
        cur.execute('UPDATE stock SET quantity=quantity-%s', (model.quantity,))
        cur.execute('INSERT INTO moves DEFAULT VALUES RETURNING id')
        return dict(cur.fetchone())

    def call(self, route):
        return route(self.model, _current_user={'role':'директор'})

    def test_concurrent_duplicate_has_one_stock_write_and_same_response(self):
        entered, release = Event(), Event()
        def blocked_worker(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timeout')
            return self.worker(*args)
        route = self.route(blocked_worker)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.call, route)
            self.assertTrue(entered.wait(5))
            second = pool.submit(self.call, route)
            release.set()
            self.assertEqual(first.result(timeout=10), second.result(timeout=10))
        with self.control.cursor() as cur:
            cur.execute('SELECT quantity FROM stock')
            self.assertEqual(cur.fetchone()[0], 8)
            cur.execute('SELECT count(*) FROM moves')
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute('SELECT count(*) FROM warehouse_movement_commands')
            self.assertEqual(cur.fetchone()[0], 1)

    def test_stock_failure_rolls_back_command_and_stock_then_retry_succeeds(self):
        def fail(*args):
            self.worker(*args)
            raise ValueError('rollback after stock write')
        with self.assertRaises(ValueError):
            self.call(self.route(fail))
        with self.control.cursor() as cur:
            cur.execute('SELECT quantity FROM stock')
            self.assertEqual(cur.fetchone()[0], 10)
            cur.execute('SELECT count(*) FROM warehouse_movement_commands')
            self.assertEqual(cur.fetchone()[0], 0)
        self.call(self.route(self.worker))
        with self.control.cursor() as cur:
            cur.execute('SELECT quantity FROM stock')
            self.assertEqual(cur.fetchone()[0], 8)
