"""Real PostgreSQL races, using actual PUT function bodies without app startup.

The launcher creates a new cluster; importing backend.main/config/db is forbidden.
The route harness stubs external AI/normalization work, but uses the real estimate
owner resolver, revision guard, SQL, version history and transaction owner.
"""
import ast
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
import re
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from typing import Optional
import unittest
from unittest.mock import patch

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
import psycopg2
import psycopg2.extras

ROOT = Path(__file__).resolve().parents[3]
RUN = os.environ.get('ESTIMATE_CONCURRENCY_RUN_POSTGRES') == '1'


def load_migration():
    path = ROOT / 'migrations/versions/0107_estimate_revisions.py'
    spec = importlib.util.spec_from_file_location('estimate_revision_test_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(RUN, 'Run scripts/run_estimate_concurrency_tests.py for an isolated database.')
class EstimateConcurrencyPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = os.environ.get('ESTIMATE_CONCURRENCY_TEST_ROOT', '')
        if not raw:
            raise RuntimeError('Missing launcher-owned test fixture.')
        work = Path(raw).resolve()
        if work.parent != (ROOT / 'tmp').resolve() or not work.name.startswith('er-'):
            raise RuntimeError('Refusing a database outside the repo-local disposable fixture.')
        marker = json.loads((work / 'fixture.json').read_text(encoding='utf-8'))
        expected = {'kind': 'estimate-concurrency-fixture-v1',
                    'database': 'estimate_concurrency_test', 'user': 'estimate_test',
                    'port': '6549', 'root': str(work)}
        if marker != expected:
            raise RuntimeError('Invalid test cluster marker.')
        pid_lines = (work / 'data/postmaster.pid').read_text().splitlines()
        if Path(pid_lines[1]).resolve() != work / 'data' or pid_lines[3] != '6549':
            raise RuntimeError('Postmaster does not belong to the isolated fixture.')
        cls.connection_args = {'host': str(work), 'port': 6549, 'user': 'estimate_test',
                               'dbname': 'estimate_concurrency_test', 'connect_timeout': 5}
        cls.migration = load_migration()
        from backend.features.estimate_concurrency.service import (
            require_estimate_revision, read_estimate_revision,
        )
        cls.require_revision = staticmethod(require_estimate_revision)
        cls.read_revision = staticmethod(read_estimate_revision)
        with cls.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT current_database(),current_user,current_setting('listen_addresses')")
            if cur.fetchone() != ('estimate_concurrency_test', 'estimate_test', ''):
                raise RuntimeError('Not the intended socket-only test database.')
            cur.execute('''CREATE TABLE projects (id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,name TEXT);
            CREATE TABLE estimates (
                id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL, project_id INTEGER,
                project_name TEXT NOT NULL DEFAULT '', name TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1.0', sections_json TEXT NOT NULL DEFAULT '[]',
                smeta_type TEXT NOT NULL DEFAULT 'Заказчик', status TEXT NOT NULL DEFAULT 'Черновик',
                work_package TEXT NOT NULL DEFAULT 'Основная', is_template BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ); CREATE TABLE work_journal (
                id SERIAL PRIMARY KEY, company_id INTEGER, estimate_id INTEGER, quantity NUMERIC,
                status TEXT, estimate_item_key TEXT, section_name TEXT, estimate_item_name TEXT, description TEXT
            ); CREATE TABLE estimate_versions (
                id SERIAL PRIMARY KEY, estimate_id INTEGER NOT NULL,
                version_label TEXT, sections_json TEXT, total NUMERIC, comment TEXT, created_by TEXT
            ); CREATE TABLE unexpected_works (
                id INTEGER PRIMARY KEY, company_id INTEGER, project_id INTEGER, estimate_id INTEGER,
                description TEXT, unit TEXT, quantity NUMERIC, price NUMERIC, total NUMERIC,
                change_type TEXT, section_name TEXT, estimate_item_name TEXT, base_quantity NUMERIC,
                new_required_quantity NUMERIC, delta_quantity NUMERIC, reason TEXT, status TEXT,
                included_in_estimate_id INTEGER, approved_by TEXT, approved_at TEXT
            ); CREATE TABLE work_material_operations (
                id SERIAL PRIMARY KEY, company_id INTEGER NOT NULL, actor_id INTEGER NOT NULL,
                request_id UUID NOT NULL, kind TEXT NOT NULL, payload_hash TEXT NOT NULL, result JSONB,
                UNIQUE(company_id,actor_id,request_id)
            ); ALTER SEQUENCE estimates_id_seq RESTART WITH 100;''')
            cur.execute(cls.migration.UPGRADE_SQL)
        cls.routes = cls.make_routes()
        cls.route = staticmethod(cls.routes["update_estimate"])

    @classmethod
    def connect(cls):
        conn = psycopg2.connect(**cls.connection_args)
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout='10s'; SET lock_timeout='8s'")
        conn.commit()
        return conn

    @classmethod
    def route_connect(cls):
        # Production get_db defaults to autocommit: handlers must own their transaction.
        conn = cls.connect()
        conn.autocommit = True
        return conn

    @classmethod
    def make_routes(cls):
        from backend.features.estimate_access.service import resolve_estimate_parent

        def resolve_actor(conn, actor, estimate_id, allowed_roles, **kwargs):
            if actor.get('role') not in allowed_roles:
                raise HTTPException(403, detail='Forbidden')
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                estimate = resolve_estimate_parent(cur, actor, estimate_id, for_update=True,
                                                   allow_template=True, allow_unbound=True)
            return actor, estimate

        namespace = {
            'HTTPException': HTTPException, 'Optional': Optional,
            'Depends': Depends, 'Header': Header, 'get_current_user': lambda: None,
            'BackgroundTasks': BackgroundTasks, 'psycopg2': psycopg2,
            '_resolve_work_company_context': lambda cur, user, *args, **kwargs: user,
            'effective_company_actors': lambda user, context: [user],
            'log_audit': lambda **kwargs: None,
            '_estimate_item_type_backend': lambda item, section: item.get('itemType', 'work'),
            'try_local_hidden_works_canary': lambda **kwargs: None,
            'YANDEX_API_KEY': '', 'YANDEX_FOLDER_ID': '',
            '_detect_hidden_by_keywords': lambda name: True,
            '_positive_int_or_none': lambda value: int(value) if value else None,
            '_refresh_open_supply_controls_for_estimate': lambda *args: {},
            'ensure_active_estimate_snapshot': lambda *args, **kwargs: None,
            'get_db': cls.route_connect, 'json': json,
            '_resolve_estimate_mutation_actor': resolve_actor,
            'require_estimate_revision': cls.require_revision,
            'read_estimate_revision': cls.read_revision,
            '_normalize_estimate_adjustment_rows': lambda rows: (rows, []),
            '_safe_float': lambda value: float(value or 0),
            '_float_or_zero': lambda value: float(value or 0),
            'ESTIMATE_WRITE_ROLES': ('директор',), 'WORKER_EXECUTION_ROLES': (),
            'PACKAGE_LIMIT_ROLES': (), 'LEADERSHIP_ROLES': ('директор',),
            'work_material_runtime': SimpleNamespace(enabled=lambda: False),
            'handoff_estimate_activation_transition': lambda **kwargs: None,
            'handoff_estimate_revision_impact_transition': lambda **kwargs: None,
            '_run_project_ai_control_safely': lambda *args: None,
            '_refresh_open_supply_controls_after_estimate_change': lambda *args: None,
            'require_project_access': lambda *args: None,
        }
        tree = ast.parse((ROOT / 'backend/main.py').read_text(encoding='utf-8'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('update_estimate', '_update_estimate_with_connection',
                                       'create_estimate', 'update_estimate_status', 'toggle_estimate_template',
                                       'delete_estimate', 'ai_detect_hidden_works', '_startup_num',
                                       '_startup_repair_saved_estimate_adjustments',
                                       '_recalculate_estimate_item_done_from_work_journal',
                                       '_estimate_item_key_candidates')]
        if len(functions) != 11:
            raise RuntimeError('PUT transaction owner functions not found.')
        for function in functions:
            function.decorator_list = []
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'backend/main.py', 'exec'), namespace)
        from backend.features.project_access.service import (
            resolve_project_parent, require_project_parent_access, require_project_write_actor,
        )
        namespace.update({
            'copy': copy, 're': re, 'time': time, 'leadership_roles': ('директор',),
            'full_view_roles': ('директор',), 'approved_statuses': {'Утверждено'},
            'resolve_work_company_context': namespace['_resolve_work_company_context'],
            'resolve_estimate_parent': resolve_estimate_parent,
            'resolve_project_parent': resolve_project_parent,
            'require_project_parent_access': require_project_parent_access,
            'require_project_write_actor': require_project_write_actor,
        })
        changes_tree = ast.parse((ROOT / 'backend/features/estimate_changes/routes.py').read_text())
        names = {'_positive_int', '_row_id', '_row_value', '_change_ids', '_number',
                 '_assert_same_project', 'estimate_mutation_scope', 'load_estimate_for_change',
                 'load_changes_for_estimate', 'include_estimate_changes'}
        changes = [node for node in ast.walk(changes_tree)
                   if isinstance(node, ast.FunctionDef) and node.name in names]
        if len(changes) != len(names):
            raise RuntimeError('Include-changes transaction functions not found.')
        for function in changes:
            function.decorator_list = []
        exec(compile(ast.Module(body=changes, type_ignores=[]),
                     'backend/features/estimate_changes/routes.py', 'exec'), namespace)
        return namespace

    def setUp(self):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute('TRUNCATE estimate_versions, estimates, projects, work_journal, unexpected_works, work_material_operations RESTART IDENTITY')
            cur.execute('ALTER SEQUENCE estimates_id_seq RESTART WITH 100')
            cur.execute("INSERT INTO estimates(id,company_id,name) VALUES (7,1,'A'),(8,2,'B')")
            cur.execute("INSERT INTO projects(id,company_id,name) VALUES (11,1,'School'),(22,2,'School')")

    def sql(self, sql, params=()):
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None

    def put(self, name='changed', expected=1, company=1, estimate_id=7, **payload):
        return self.route(estimate_id, dict(name=name, expectedRevision=expected, sections=[], **payload),
                          x_company_id=str(company), x_company_mode='company',
                          current_user={'id': 10, 'companyId': company, 'role': 'директор', 'name': 'Test'})

    def snapshot(self):
        return (self.sql('SELECT row_to_json(e)::text FROM estimates e ORDER BY id'),
                self.sql('SELECT row_to_json(v)::text FROM estimate_versions v ORDER BY id'))

    def prepare_include(self):
        self.sql("UPDATE estimates SET project_id=11,project_name='School',status='Активная' WHERE id=7")
        self.sql("""INSERT INTO unexpected_works
            (id,company_id,project_id,estimate_id,description,unit,quantity,price,status)
            VALUES (21,1,11,7,'New work','шт',2,100,'Утверждено'),
                   (22,2,22,8,'Foreign work','шт',3,200,'Утверждено')""")

    def include(self, expected=2, company=1, change_ids=None):
        return self.routes['include_estimate_changes'](
            7, {'expectedRevision': expected, 'changeIds': change_ids or [21]},
            x_company_id=str(company), x_company_mode='company',
            current_user={'id': 10, 'companyId': company, 'role': 'директор', 'name': 'Test'})

    def include_snapshot(self):
        return self.snapshot(), self.sql('SELECT row_to_json(w)::text FROM unexpected_works w ORDER BY id')

    def test_include_changes_creates_revision_one_and_invalidates_archived_base(self):
        self.prepare_include()
        foreign = self.sql('SELECT row_to_json(e)::text FROM estimates e WHERE id=8')
        result = self.include()
        self.assertEqual(result['estimate']['revision'], 1)
        self.assertEqual(result['includedChangeIds'], [21])
        self.assertEqual(self.sql('SELECT status,revision FROM estimates WHERE id=7'), [('Архив', 3)])
        self.assertEqual(self.sql('SELECT revision,company_id FROM estimates WHERE id=%s',
                                 (result['id'],)), [(1, 1)])
        self.assertEqual(self.sql('SELECT included_in_estimate_id FROM unexpected_works WHERE id=21'),
                         [(result['id'],)])
        self.assertEqual(self.sql('SELECT included_in_estimate_id FROM unexpected_works WHERE id=22'), [(None,)])
        self.assertEqual(self.sql('SELECT row_to_json(e)::text FROM estimates e WHERE id=8'), foreign)
        before = self.include_snapshot()
        with self.assertRaises(HTTPException) as caught:
            self.put('stale', expected=2)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.include_snapshot(), before)

    def test_include_changes_stale_and_foreign_requests_have_no_side_effects(self):
        self.prepare_include()
        before = self.include_snapshot()
        for args, status in [({'expected': 1}, 409), ({'expected': None}, 428),
                             ({'company': 2}, 404), ({'change_ids': [22]}, 403)]:
            with self.subTest(args=args), self.assertRaises(HTTPException) as caught:
                self.include(**args)
            self.assertEqual(caught.exception.status_code, status)
            self.assertEqual(self.include_snapshot(), before)

    def test_include_changes_rolls_back_all_writes_with_initial_autocommit_enabled(self):
        self.prepare_include()
        before = self.include_snapshot()

        def fail_after_writes(cur, **kwargs):
            cur.execute('INSERT INTO estimate_versions(estimate_id) VALUES (%s)', (kwargs['estimate_id'],))
            raise RuntimeError('Injected failure after archival, creation and change linking')

        with patch.dict(self.routes, {'ensure_active_estimate_snapshot': fail_after_writes}):
            with self.assertRaisesRegex(RuntimeError, 'Injected failure'):
                self.include()
        self.assertEqual(self.include_snapshot(), before)

    def test_include_changes_holds_base_lock_until_commit_with_initial_autocommit_enabled(self):
        self.prepare_include()
        load_changes = self.routes['load_changes_for_estimate']
        pending = []
        with ThreadPoolExecutor(max_workers=1) as executor:
            def concurrent_save(cur, **kwargs):
                pending.append(executor.submit(self.put, 'waiting stale save', expected=2))
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")[0][0]:
                        break
                    if pending[0].done():
                        self.fail('Competing save finished before include-changes released its base lock.')
                    time.sleep(0.01)
                else:
                    self.fail('Competing save never waited on the include-changes base lock.')
                return load_changes(cur, **kwargs)

            with patch.dict(self.routes, {'load_changes_for_estimate': concurrent_save}):
                result = self.include()
            with self.assertRaises(HTTPException) as caught:
                pending[0].result(timeout=10)
            self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(result['estimate']['revision'], 1)
        self.assertEqual(self.sql('SELECT name,revision FROM estimates WHERE id=7'), [('A', 3)])

    def test_put_returns_new_revision_and_old_revision_conflicts_without_history(self):
        result = self.put('newer')
        self.assertEqual(result['revision'], 2)
        self.assertEqual(self.sql('SELECT name,revision FROM estimates WHERE id=7'), [('newer', 2)])
        before = self.snapshot()
        with self.assertRaises(HTTPException) as caught:
            self.put('older', expected=1)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.detail['code'], 'estimate_revision_conflict')
        self.assertEqual(caught.exception.detail['expectedRevision'], 1)
        self.assertEqual(caught.exception.detail['currentRevision'], 2)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.sql('SELECT count(*) FROM estimate_versions'), [(1,)])

    def test_material_v2_replay_precedes_revision_check_and_performs_no_new_writes(self):
        from backend.features.work_material_accounting import runtime
        actor = {'id': 10, 'companyId': 1, 'role': 'мастер', 'name': 'Test'}
        payload = {'materialAccountingVersion': 2, 'requestId': '00000000-0000-4000-8000-000000000001',
                   'expectedRevision': 1, 'name': 'original', 'sections': []}
        original_response = {'ok': True, 'revision': 2, 'journalEntries': 1,
                             'hiddenWorkActs': 0, 'brigadeItemsSynced': 0,
                             'supplyControlRefresh': {'scanned': 0, 'updated': 0}}
        # Seed a committed operation through the real idempotency runtime. The full
        # material stock/journal success workflow is outside this minimal schema.
        with self.connect() as conn, conn.cursor() as cur:
            operation_id, replay = runtime.begin_operation(
                cur, actor, payload['requestId'], 'estimate-work', {'estimateId': 7, 'data': payload})
            self.assertIsNone(replay)
            cur.execute("UPDATE estimates SET name='original' WHERE id=7")
            runtime.finish_operation(cur, operation_id, original_response)
        self.sql("UPDATE estimates SET name='subsequent save' WHERE id=7")
        before = self.include_snapshot(), self.sql('SELECT row_to_json(w)::text FROM work_material_operations w')

        def unexpected_revision_check(*args):
            self.fail('A completed operation replay must return before checking its old revision.')

        with patch.dict(os.environ, {'WORK_MATERIAL_ACCOUNTING_ENABLED': '1'}), patch.dict(self.routes, {
            'work_material_runtime': runtime, 'WORKER_EXECUTION_ROLES': ('мастер',),
            'require_estimate_revision': unexpected_revision_check,
        }):
            replay = self.route(7, payload, x_company_id='1', x_company_mode='company', current_user=actor)
        self.assertEqual(replay, original_response)
        self.assertEqual(replay['revision'], 2)
        self.assertEqual((self.include_snapshot(), self.sql('SELECT row_to_json(w)::text FROM work_material_operations w')), before)
        self.assertEqual(self.sql('SELECT name,revision FROM estimates WHERE id=7'), [('subsequent save', 3)])

    def test_new_material_v2_stale_or_missing_revision_rolls_back_operation_before_effects(self):
        from backend.features.work_material_accounting import runtime
        self.sql("UPDATE estimates SET name='newer' WHERE id=7")
        before = self.include_snapshot(), self.sql('SELECT row_to_json(w)::text FROM work_journal w')

        def unexpected_effect(*args, **kwargs):
            self.fail('Rejected revision reached snapshot normalization or material effects.')

        with patch.dict(os.environ, {'WORK_MATERIAL_ACCOUNTING_ENABLED': '1'}), patch.dict(self.routes, {
            'work_material_runtime': runtime, 'WORKER_EXECUTION_ROLES': ('мастер',),
            '_normalize_estimate_adjustment_rows': unexpected_effect,
            'work_material_service': SimpleNamespace(prepare=unexpected_effect, post=unexpected_effect),
        }):
            for expected, status in [(1, 409), (None, 428)]:
                with self.subTest(expected=expected):
                    payload = {'materialAccountingVersion': 2,
                               'requestId': '00000000-0000-4000-8000-000000000002',
                               'name': 'old', 'sections': []}
                    if expected is not None:
                        payload['expectedRevision'] = expected
                    with self.assertRaises(HTTPException) as caught:
                        self.route(7, payload, x_company_id='1', x_company_mode='company', current_user={
                            'id': 10, 'companyId': 1, 'role': 'мастер', 'name': 'Test'})
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(self.sql('SELECT count(*) FROM work_material_operations'), [(0,)])
                    self.assertEqual((self.include_snapshot(), self.sql('SELECT row_to_json(w)::text FROM work_journal w')), before)

    def test_material_v2_commit_tail_persists_final_revision_for_exact_replay(self):
        """Execute actual final persistence statements, without the broad stock workflow."""
        from backend.features.work_material_accounting import runtime
        tree = ast.parse((ROOT / 'backend/main.py').read_text())
        route = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == '_update_estimate_with_connection')
        final_try = next(node for node in route.body if isinstance(node, ast.Try)
                         and any(isinstance(child, ast.Assign)
                                 and any(isinstance(target, ast.Name) and target.id == 'saved_revision'
                                         for target in child.targets) for child in node.body))
        start = next(index for index, node in enumerate(final_try.body) if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == 'saved_revision' for target in node.targets))
        actor = {'id': 10, 'companyId': 1}
        payload = {'estimateId': 7, 'data': {'expectedRevision': 1}}
        key = '00000000-0000-4000-8000-000000000003'
        with self.connect() as conn, conn.cursor() as cur:
            operation_id, _ = runtime.begin_operation(cur, actor, key, 'estimate-work', payload)
            cur.execute("UPDATE estimates SET name='saved' WHERE id=7")
            # Model a later journal recalculation in the same transaction.
            cur.execute("UPDATE estimates SET sections_json='[]' WHERE id=7")
            namespace = {'conn': conn, 'cur': cur, 'id': 7, 'estimate_scope': {'companyId': 1},
                         'read_estimate_revision': self.read_revision, 'use_material_v2': True,
                         'journal_added': 1, 'acts_added': 0, 'brigade_synced': 0,
                         'work_journal_materials': {'work': []}, 'matched_material_keys': {'work'},
                         'work_material_runtime': runtime, 'material_operation_id': operation_id,
                         'supply_refresh': {'scanned': 0, 'updated': 0}, 'HTTPException': HTTPException}
            exec(compile(ast.Module(body=final_try.body[start:], type_ignores=[]),
                         'backend/main.py', 'exec'), namespace)
        with self.connect() as conn, conn.cursor() as cur:
            _, replay = runtime.begin_operation(cur, actor, key, 'estimate-work', payload)
        self.assertEqual(replay, {'ok': True, 'revision': 3, 'journalEntries': 1,
                                 'hiddenWorkActs': 0, 'brigadeItemsSynced': 0,
                                 'supplyControlRefresh': {'scanned': 0, 'updated': 0}})

    def test_http_contract_returns_conflict_and_requires_expected_revision(self):
        app = FastAPI()
        app.put('/estimates/{id}')(self.routes['update_estimate'])
        app.dependency_overrides[self.routes['get_current_user']] = lambda: {
            'id': 10, 'companyId': 1, 'role': 'директор', 'name': 'Test'}
        with TestClient(app) as client:
            first = client.put('/estimates/7', json={'name': 'new', 'sections': [], 'expectedRevision': 1})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.json()['revision'], 2)
            before = self.snapshot()
            stale = client.put('/estimates/7', json={'name': 'old', 'sections': [], 'expectedRevision': 1})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(stale.json()['detail']['code'], 'estimate_revision_conflict')
            self.assertEqual(stale.json()['detail']['currentRevision'], 2)
            missing = client.put('/estimates/7', json={'name': 'missing', 'sections': []})
            self.assertEqual(missing.status_code, 428)
            invalid = client.put('/estimates/7', json={'name': 'invalid', 'sections': [], 'expectedRevision': True})
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(self.snapshot(), before)

    def test_two_real_puts_with_same_expected_revision_only_one_commits(self):
        start = threading.Barrier(2)

        def write(name):
            start.wait(timeout=5)
            try:
                return ('ok', name, self.put(name)['revision'])
            except HTTPException as error:
                return ('error', name, error.status_code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(write, name) for name in ('first', 'second')]
            results = [future.result(timeout=15) for future in futures]
        winners = [row for row in results if row[0] == 'ok']
        losers = [row for row in results if row[0] == 'error']
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(winners[0][2], 2)
        self.assertEqual(len(losers), 1, results)
        self.assertEqual(losers[0][2], 409)
        self.assertEqual(self.sql('SELECT name,revision FROM estimates WHERE id=7'), [(winners[0][1], 2)])
        self.assertEqual(self.sql('SELECT count(*) FROM estimate_versions'), [(1,)])

    def test_waiting_old_put_sees_revision_committed_by_lock_holder(self):
        with self.connect() as winner:
            with winner.cursor() as cur:
                self.require_revision(cur, 7, 1, {'expectedRevision': 1})
                cur.execute("UPDATE estimates SET name='winner' WHERE id=7 AND company_id=1 AND revision=1 RETURNING revision")
                self.assertEqual(cur.fetchone(), (2,))
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.put, 'loser')
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    waits = self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock'")
                    if waits[0][0]:
                        break
                    time.sleep(0.01)
                else:
                    self.fail('The competing PUT never waited on the held estimate lock.')
                winner.commit()
                with self.assertRaises(HTTPException) as caught:
                    future.result(timeout=10)
                self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.sql('SELECT name,revision FROM estimates WHERE id=7'), [('winner', 2)])
        self.assertEqual(self.sql('SELECT count(*) FROM estimate_versions'), [(0,)])

    def test_missing_and_invalid_expectations_leave_data_and_history_unchanged(self):
        before = self.snapshot()
        for value, status in [(None, 428), (True, 422), (False, 422), (0, 422), (-1, 422),
                              ('1', 422), (1.0, 422), ({}, 422), (9007199254740992, 422)]:
            with self.subTest(expected=value):
                with self.assertRaises(HTTPException) as caught:
                    self.put(expected=value)
                self.assertEqual(caught.exception.status_code, status)
                self.assertEqual(self.snapshot(), before)

    def test_foreign_company_cannot_read_revision_or_mutate_even_with_valid_expectation(self):
        before = self.snapshot()
        for expected in (None, 1, 2):
            with self.subTest(expected=expected):
                with self.assertRaises(HTTPException) as caught:
                    self.put(expected=expected, company=2)
                self.assertEqual(caught.exception.status_code, 404)
                self.assertNotIn('currentRevision', str(caught.exception.detail))
        with self.connect() as conn, conn.cursor() as cur:
            with self.assertRaises(HTTPException) as caught:
                self.read_revision(cur, 7, 2)
            self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.put(company=2, estimate_id=8)['revision'], 2)
        self.assertEqual(self.sql('SELECT revision FROM estimates WHERE id=7'), [(1,)])

    def test_indirect_writers_increment_revision_and_invalidate_old_snapshot(self):
        for statement in ("name='indirect'", "status='Черновик'", "is_template=TRUE",
                          "sections_json='[]'", 'revision=100'):
            with self.subTest(statement=statement):
                before_revision = self.sql('SELECT revision FROM estimates WHERE id=7')[0][0]
                self.sql('UPDATE estimates SET ' + statement + ' WHERE id=7 AND company_id=1')
                self.assertEqual(self.sql('SELECT revision FROM estimates WHERE id=7'), [(before_revision + 1,)])
                before = self.snapshot()
                with self.assertRaises(HTTPException) as caught:
                    self.put(expected=before_revision)
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(self.snapshot(), before)

    def test_rolled_back_write_does_not_consume_revision(self):
        before = self.snapshot()
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                self.require_revision(cur, 7, 1, {'expectedRevision': 1})
                cur.execute("UPDATE estimates SET name='not committed' WHERE id=7 RETURNING revision")
                self.assertEqual(cur.fetchone(), (2,))
            conn.rollback()
        finally:
            conn.close()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.put()['revision'], 2)

    def mutate(self, operation, *, expected=1, company=1, estimate_id=7):
        actor = {'id': 10, 'companyId': company, 'role': 'директор', 'name': 'Test'}
        kwargs = dict(x_company_id=str(company), x_company_mode='company')
        if operation == 'status':
            return self.routes['update_estimate_status'](estimate_id,
                {'expectedRevision': expected, 'status': 'Черновик'}, BackgroundTasks(),
                current_user=actor, **kwargs)
        if operation == 'template':
            return self.routes['toggle_estimate_template'](estimate_id,
                {'expectedRevision': expected}, current_user=actor, **kwargs)
        if operation == 'hidden':
            return self.routes['ai_detect_hidden_works'](estimate_id,
                {'expectedRevision': expected}, _current_user=actor, **kwargs)
        if operation == 'delete':
            return self.routes['delete_estimate'](estimate_id, hard=True,
                expectedRevision=expected, current_user=actor, **kwargs)
        raise AssertionError(operation)

    def test_other_routes_reject_missing_stale_and_foreign_revisions_without_writes(self):
        self.put('latest')
        before = self.snapshot()
        for operation in ('status', 'template', 'hidden', 'delete'):
            for expected, company, status in ((None, 1, 428), (1, 1, 409), (2, 2, 404)):
                with self.subTest(operation=operation, expected=expected, company=company):
                    with self.assertRaises(HTTPException) as caught:
                        self.mutate(operation, expected=expected, company=company)
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(self.snapshot(), before)

    def test_status_and_template_changes_return_new_revision_and_invalidate_put(self):
        for operation in ('status', 'template'):
            with self.subTest(operation=operation):
                previous = self.sql('SELECT revision FROM estimates WHERE id=7')[0][0]
                result = self.mutate(operation, expected=previous)
                self.assertEqual(result['revision'], previous + 1)
                before = self.snapshot()
                with self.assertRaises(HTTPException) as caught:
                    self.put(expected=previous)
                self.assertEqual(caught.exception.status_code, 409)
                self.assertEqual(self.snapshot(), before)

    def test_activation_invalidates_other_estimate_in_same_company_only(self):
        self.sql("UPDATE estimates SET project_id=11,project_name='School' WHERE id=7")
        self.sql("INSERT INTO estimates(id,company_id,project_id,project_name,name,status) VALUES (9,1,11,'School','previous','Активная'),(10,2,22,'School','foreign','Активная')")
        result = self.routes['update_estimate_status'](7,
            {'expectedRevision': 2, 'status': 'Активная'}, BackgroundTasks(),
            x_company_id='1', x_company_mode='company',
            current_user={'id': 10, 'companyId': 1, 'role': 'директор'})
        self.assertEqual(result['revision'], 3)
        self.assertEqual(sorted(result['affectedEstimates'], key=lambda item: item['id']),
                         [{'id': 7, 'revision': 3, 'previousRevision': 2, 'status': 'Активная'},
                          {'id': 9, 'revision': 2, 'previousRevision': 1, 'status': 'Черновик'}])
        self.assertEqual(self.sql('SELECT id,status,revision FROM estimates WHERE id IN (9,10) ORDER BY id'),
                         [(9, 'Черновик', 2), (10, 'Активная', 1)])
        with self.assertRaises(HTTPException) as caught:
            self.put(estimate_id=9, expected=1)
        self.assertEqual(caught.exception.status_code, 409)

    def test_failed_active_creation_rolls_back_previous_activation_and_closes_connection(self):
        self.sql("UPDATE estimates SET project_id=11,project_name='School',status='Активная' WHERE id=7")
        before = self.snapshot()
        conn = self.route_connect()
        def fail_snapshot(*args, **kwargs):
            raise RuntimeError('snapshot unavailable')
        try:
            with patch.dict(self.routes, get_db=lambda: conn, ensure_active_estimate_snapshot=fail_snapshot):
                with self.assertRaisesRegex(RuntimeError, 'snapshot unavailable'):
                    self.routes['create_estimate'](
                        {'name': 'Failed active', 'projectId': 11, 'status': 'Активная'}, BackgroundTasks(),
                        x_company_id='1', x_company_mode='company',
                        current_user={'id': 10, 'companyId': 1, 'role': 'директор'})
            self.assertTrue(conn.closed, 'Failed activation must release its transaction and locks')
            self.assertEqual(self.snapshot(), before)
        finally:
            if not conn.closed:
                conn.rollback()
                conn.close()

    def test_new_active_estimate_reports_previous_revisions_in_same_company(self):
        self.sql("UPDATE estimates SET project_id=11,project_name='School',status='Активная' WHERE id=7")
        self.sql("UPDATE estimates SET project_id=22,project_name='School',status='Активная' WHERE id=8")
        result = self.routes['create_estimate'](
            {'name': 'New active', 'projectId': 11, 'status': 'Активная'}, BackgroundTasks(),
            x_company_id='1', x_company_mode='company',
            current_user={'id': 10, 'companyId': 1, 'role': 'директор'})
        self.assertEqual(result['affectedEstimates'],
                         [{'id': 7, 'revision': 3, 'previousRevision': 2, 'status': 'Черновик'}])
        self.assertEqual(self.sql('SELECT revision,status FROM estimates WHERE id=8'), [(2, 'Активная')])
        self.assertEqual(self.sql('SELECT revision,status FROM estimates WHERE id=%s', (result['id'],)), [(1, 'Активная')])

    def test_hidden_detection_rejects_concurrent_save_after_inference_started(self):
        sections = [{'name': 'Section', 'items': [{'name': 'Cable', 'itemType': 'work'}]}]
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=7', (json.dumps(sections),))
        def concurrent_save(**kwargs):
            self.put('newer while detecting', expected=2)
            return SimpleNamespace(hidden_names=['Cable'], method='test')
        with patch.dict(self.routes, try_local_hidden_works_canary=concurrent_save):
            with self.assertRaises(HTTPException) as caught:
                self.mutate('hidden', expected=2)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.sql('SELECT name,sections_json,revision FROM estimates WHERE id=7'),
                         [('newer while detecting', '[]', 3)])
        self.assertEqual(self.sql('SELECT count(*) FROM estimate_versions'), [(1,)])

    def test_hidden_detection_updates_sections_and_revision_when_current(self):
        sections = [{'name': 'Section', 'items': [{'name': 'Cable', 'itemType': 'work'}]}]
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=7', (json.dumps(sections),))
        result = self.mutate('hidden', expected=2)
        self.assertEqual(result['revision'], 3)
        self.assertTrue(result['sections'][0]['items'][0]['hiddenWork'])
        self.assertEqual(self.sql('SELECT revision FROM estimates WHERE id=8'), [(1,)])

    def test_delete_current_draft_uses_revision_before_dependency_cleanup(self):
        with patch('backend.features.estimate_deletion.service.find_estimate_delete_blockers', return_value=[]), \
                patch('backend.features.estimate_deletion.service.delete_estimate_technical_records') as cleanup:
            result = self.mutate('delete')
        self.assertEqual(result, {'ok': True, 'id': 7})
        cleanup.assert_called_once()
        self.assertEqual(self.sql('SELECT id,revision FROM estimates ORDER BY id'), [(8, 1)])

    def test_failed_actual_put_rolls_back_snapshot_and_revision(self):
        before = self.snapshot()
        self.sql("""CREATE FUNCTION fail_estimate_test_save() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.name='reject-write' THEN RAISE EXCEPTION 'test write failure'; END IF; RETURN NEW; END;
            $$; CREATE TRIGGER test_reject_estimate_write AFTER UPDATE ON estimates
                FOR EACH ROW EXECUTE FUNCTION fail_estimate_test_save();""")
        try:
            with self.assertRaises(psycopg2.Error):
                self.put('reject-write')
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('DROP TRIGGER test_reject_estimate_write ON estimates; DROP FUNCTION fail_estimate_test_save()')

    def test_startup_repair_skips_snapshot_changed_since_scan(self):
        sections = [{'name': 'Section', 'items': [{'name': 'Resource', 'itemType': 'material', 'quantity': -1}]}]
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=7', (json.dumps(sections),))
        test_case = self
        with self.connect() as conn, conn.cursor() as cur:
            class RacingCursor:
                def execute(self, *args):
                    return cur.execute(*args)
                def fetchall(self):
                    rows = cur.fetchall()
                    test_case.put('saved after repair scan', expected=2)
                    return rows
                @property
                def rowcount(self):
                    return cur.rowcount
            repaired = self.routes['_startup_repair_saved_estimate_adjustments'](RacingCursor())
        self.assertEqual(repaired, 0)
        self.assertEqual(self.sql('SELECT name,sections_json,revision FROM estimates WHERE id=7'),
                         [('saved after repair scan', '[]', 3)])

    def test_startup_repair_applies_current_snapshot_and_increments_revision(self):
        sections = [{'name': 'Section', 'items': [{'name': 'Resource', 'itemType': 'material', 'quantity': -1}]}]
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=7', (json.dumps(sections),))
        with self.connect() as conn, conn.cursor() as cur:
            repaired = self.routes['_startup_repair_saved_estimate_adjustments'](cur)
        self.assertEqual(repaired, 1)
        stored, revision = self.sql('SELECT sections_json,revision FROM estimates WHERE id=7')[0]
        self.assertEqual(json.loads(stored)[0]['items'][0]['itemType'], 'adjustment')
        self.assertEqual(revision, 3)
        self.assertEqual(self.sql('SELECT revision FROM estimates WHERE id=8'), [(1,)])

    def test_journal_recalculation_rejects_missing_owner_and_foreign_legacy_link(self):
        before = self.snapshot()
        for company in (None, 0, -1, True, '1', 2):
            with self.subTest(company=company):
                with self.connect() as conn, conn.cursor() as cur:
                    changed = self.routes['_recalculate_estimate_item_done_from_work_journal'](
                        cur, {'company_id': company, 'estimate_id': 7, 'estimate_item_key': '7:0:0'})
                self.assertFalse(changed)
                self.assertEqual(self.snapshot(), before)

    def test_journal_recalculation_excludes_foreign_company_totals_and_bumps_revision(self):
        sections = [{'name': 'Section', 'items': [{'name': 'Work', 'quantity': 20, 'doneQuantity': 0}]}]
        self.sql('UPDATE estimates SET sections_json=%s WHERE id=7', (json.dumps(sections),))
        self.sql("""INSERT INTO work_journal(company_id,estimate_id,quantity,status,estimate_item_key)
                    VALUES (1,7,3,'Подтверждено','7:0:0'),(2,7,5,'Подтверждено','7:0:0')""")
        with self.connect() as conn, conn.cursor() as cur:
            changed = self.routes['_recalculate_estimate_item_done_from_work_journal'](
                cur, {'company_id': 1, 'estimate_id': 7, 'estimate_item_key': '7:0:0'}, strict_key=True)
        self.assertTrue(changed)
        stored, revision = self.sql('SELECT sections_json,revision FROM estimates WHERE id=7')[0]
        self.assertEqual(json.loads(stored)[0]['items'][0]['doneQuantity'], 3)
        self.assertEqual(revision, 3)
        with self.assertRaises(HTTPException) as caught:
            self.put(expected=2)
        self.assertEqual(caught.exception.status_code, 409)

    def test_migration_downgrade_and_upgrade_preserve_existing_records(self):
        self.put('saved')
        before = self.sql('SELECT id,company_id,name,sections_json FROM estimates ORDER BY id')
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(self.migration.DOWNGRADE_SQL)
            cur.execute(self.migration.UPGRADE_SQL)
        self.assertEqual(self.sql('SELECT id,company_id,name,sections_json FROM estimates ORDER BY id'), before)
        self.assertEqual(self.sql('SELECT revision FROM estimates ORDER BY id'), [(1,), (1,)])
        self.assertEqual(self.put()['revision'], 2)


if __name__ == '__main__':
    unittest.main()
