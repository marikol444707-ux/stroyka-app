"""Socket-only PG regression; never import main/config or read .env.

The old protocol is a minimal SQL reproduction of create/return's stock
SELECT FOR UPDATE followed by UPDATE, not a claim that delete has that cycle.
The handler tests execute real AST-extracted entry points only up to their
parent callback, then real synthetic stock SQL versus the distribution API.
They prove the early transaction lock boundary, NOT full transfer semantics,
authentication, personal balance accounting or transfer journals.
"""
import ast
import math
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
from threading import Event
import time
from unittest import TestCase, skipUnless
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import psycopg2

from backend.features.material_traceability.guards import lock_distribution_compatible_stock
from backend.features.warehouse_distribution.test_postgres_support import Fixture


class BoundaryDone(BaseException):
    """Stop before untested business code without being translated to HTTP 500."""


class SchemaProbeCursor:
    """Only adapt public-schema presence probe to Fixture's isolated schema."""
    def __init__(self, cur):
        self.cur = cur

    def execute(self, statement, args=()):
        if "to_regclass('public.warehouse_distribution_operations')" in statement:
            statement = "SELECT to_regclass('warehouse_distribution_operations') IS NOT NULL AS present"
        return self.cur.execute(statement, args)

    def fetchone(self):
        return self.cur.fetchone()


def extracted_handler(name, get_db):
    path = Path(__file__).resolve().parents[2] / 'main.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    for arg in node.args.args:
        arg.annotation = None
    node.args.defaults = [ast.Constant(None)] * len(node.args.defaults)
    namespace = dict(
        get_db=get_db, psycopg2=psycopg2, math=math, HTTPException=HTTPException,
        _norm_base_unit=lambda value: value,
        _resolve_work_company_context=lambda *a, **k: {},
        effective_company_actors=lambda user, context: [user],
        WAREHOUSE_ROLES=('директор',), SUPPLY_INTERNAL_ROLES=('директор',),
        WORKER_EXECUTION_ROLES=('мастер',),
        lock_distribution_compatible_stock=compatible_lock,
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(path), 'exec'), namespace)
    return namespace[name]


def compatible_lock(cur):
    lock_distribution_compatible_stock(SchemaProbeCursor(cur))


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
            'Explicit isolated PostgreSQL opt-in required')
class TransferLockPostgresTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.assertEqual(self.fixture.query('SHOW server_encoding')[0]['server_encoding'], 'UTF8')
        self.fixture.query("""INSERT INTO materials
            (company_id,name,unit,quantity,project,work_package)
            VALUES(2,'Cement','кг',10,'Alpha','Synthetic package')""")

    def test_legacy_stock_lock_conflict_is_bounded_and_rollback_safe(self):
        blocker = self.fixture.get_db()
        waiter = self.fixture.get_db()
        try:
            with blocker.cursor() as cur:
                cur.execute('LOCK TABLE materials IN SHARE ROW EXCLUSIVE MODE')
            with waiter.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='500ms'")
                started = time.monotonic()
                with self.assertRaises(HTTPException) as error:
                    compatible_lock(cur)
                self.assertEqual(error.exception.status_code, 409)
                self.assertLess(time.monotonic() - started, 8)
            waiter.rollback()
            self.assertEqual(self.fixture.query('SELECT quantity FROM materials WHERE company_id=2')[0]['quantity'], 10)
        finally:
            waiter.rollback(); waiter.close()
            blocker.rollback(); blocker.close()

    def wait_blocked(self, waiting_pid, blocking_pid):
        deadline = time.monotonic() + 3
        with self.fixture.control.cursor() as cur:
            while time.monotonic() < deadline:
                cur.execute('SELECT %s = ANY(pg_blocking_pids(%s))', (blocking_pid, waiting_pid))
                if cur.fetchone()[0]:
                    return
                time.sleep(.01)
        self.fail(f'Backend {waiting_pid} did not wait on {blocking_pid}')

    def test_old_stock_row_then_update_protocol_really_deadlocks(self):
        """RowShare is compatible with SRX; the later RowExclusive upgrade is not."""
        legacy, distribution = self.fixture.get_db(), self.fixture.get_db()
        try:
            with legacy.cursor() as cur:
                cur.execute('SELECT id FROM materials WHERE id=1 FOR UPDATE')
            # This succeeds despite the row lock: do not assume RowShare conflicts.
            with distribution.cursor() as cur:
                cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')

            def operation(conn, statement):
                try:
                    with conn, conn.cursor() as cur:
                        cur.execute(statement)
                    return 'committed'
                except psycopg2.Error as error:
                    return error.pgcode

            with ThreadPoolExecutor(max_workers=2) as pool:
                waiter = pool.submit(operation, distribution,
                    'SELECT id FROM materials WHERE id=1 FOR UPDATE')
                self.wait_blocked(distribution.get_backend_pid(), legacy.get_backend_pid())
                upgrade = pool.submit(operation, legacy,
                    'UPDATE materials SET quantity=quantity-1 WHERE id=1')
                outcomes = [waiter.result(timeout=8), upgrade.result(timeout=8)]
            self.assertCountEqual(outcomes, ['40P01', 'committed'])
        finally:
            legacy.close()
            distribution.close()

    def check_handler_boundary(self, name, delta):
        """Hold the handler at parent access, prove API waits, then release SQL."""
        reached, release = Event(), Event()
        legacy = self.fixture.get_db()
        legacy_pid = legacy.get_backend_pid()
        distribution = self.fixture.get_db()
        distribution_pid = distribution.get_backend_pid()
        handler = extracted_handler(name, lambda: legacy)
        target = ('backend.features.material_transfer_access.service.resolve_material_transfer_parent'
                  if name == 'delete_material_transfer'
                  else 'backend.features.project_access.service.resolve_project_parent')

        def parent(cur, *args, **kwargs):
            cur.execute("""SELECT c.relname FROM pg_locks l
                JOIN pg_class c ON c.oid=l.relation
                WHERE l.pid=pg_backend_pid() AND l.granted
                AND l.mode='ShareRowExclusiveLock'
                AND c.relnamespace=current_schema()::regnamespace""")
            self.assertEqual({r['relname'] for r in cur.fetchall()},
                             {'materials', 'warehouse_main', 'projects'})
            reached.set()
            if not release.wait(6):
                raise AssertionError('Parent boundary release timed out')
            cur.execute('SELECT id FROM materials WHERE id=1 FOR UPDATE')
            cur.execute('UPDATE materials SET quantity=quantity+%s WHERE id=1', (delta,))
            cur.connection.commit()
            raise BoundaryDone()

        def invoke():
            data = dict(materialName='Cement', quantity=1, unit='кг', projectName='Alpha',
                        fromLocation='Alpha', workPackage='Synthetic package', toPersonRole='мастер')
            try:
                handler(1 if name == 'delete_material_transfer' else data,
                        current_user=dict(id=1, companyId=2, role='директор'))
            except BoundaryDone:
                return 'boundary committed'

        # Route dependencies captured get_db at registration; return the prepared
        # real connection so the observer knows its backend PID before it waits.
        # Existing registered endpoints expose their injected dependencies via
        # closure; avoid rebuilding auth scaffolding by using their get_db cell.
        endpoint = next(r.endpoint for r in self.fixture.app.routes
                        if r.path == '/warehouse-distributions' and 'POST' in r.methods)
        candidates = [c.cell_contents for c in endpoint.__closure__ or ()
                      if isinstance(c.cell_contents, dict) and 'get_db' in c.cell_contents]
        self.assertEqual(len(candidates), 1, 'Distribution endpoint dependency closure changed')
        deps = candidates[0]
        body = dict(companyId=2, requestId=str(uuid4()), reason='Concurrent boundary check',
                    rows=[dict(lotId=1, projectId=1, quantity='2')])

        def issue():
            with TestClient(self.fixture.app) as client:
                return client.post('/warehouse-distributions', json=body)

        try:
            with patch(target, side_effect=parent), patch(
                'backend.features.material_traceability.guards.lock_distribution_compatible_stock',
                side_effect=compatible_lock), patch.dict(deps, get_db=lambda: distribution):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(invoke)
                    try:
                        deadline = time.monotonic() + 3
                        while not reached.wait(.01):
                            if first.done():
                                first.result()  # Surface missing lock immediately (RED).
                            self.assertLess(time.monotonic(), deadline, 'Handler did not reach parent')
                        second = pool.submit(issue)
                        self.wait_blocked(distribution_pid, legacy_pid)
                    finally:
                        release.set()
                    self.assertEqual(first.result(timeout=8), 'boundary committed')
                    response = second.result(timeout=8)
                    self.assertEqual(response.status_code, 200, response.text)
        finally:
            legacy.close()
            distribution.close()
        self.assertEqual(self.fixture.query('SELECT quantity FROM materials WHERE id=1')[0]['quantity'],
                         12 + delta)
        self.assertEqual(self.fixture.query('SELECT quantity FROM warehouse_main WHERE id=1')[0]['quantity'], 8)
        self.assertEqual(self.fixture.query('SELECT available_quantity FROM warehouse_receipt_lots WHERE id=1')[0]['available_quantity'], 8)
        self.assertEqual(self.fixture.query('SELECT count(*) n FROM warehouse_distribution_allocations')[0]['n'], 1)

    def test_create_boundary_serializes_distribution(self):
        self.check_handler_boundary('create_material_transfer', -1)

    def test_return_boundary_serializes_distribution(self):
        self.check_handler_boundary('return_material_from_master', 1)

    def test_delete_boundary_serializes_distribution(self):
        self.check_handler_boundary('delete_material_transfer', 1)
