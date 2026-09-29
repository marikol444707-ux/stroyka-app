"""Socket-only PG regressions; use an empty UTF-8 DB and SUPPLY_CHAIN_* settings.

Uses synthetic base DDL plus migration 0012, not production bootstrap/auth.
Only two exact public-schema guard probes are redirected to the fixture schema.
The real guard SQL, locks, UPDATEs, commit and rollback run on PostgreSQL.
"""
import ast
import os
from pathlib import Path
from typing import Optional
from unittest import TestCase, skipUnless

import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException

from backend.features.materials.routes import MaterialModel, register_materials_module
from backend.features.warehouse_distribution.test_postgres_support import Fixture


class GuardCursor:
    def __init__(self, raw, owner):
        self.raw, self.owner = raw, owner

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def execute(self, statement, params=None):
        for table in ('warehouse_distribution_operations', 'warehouse_receipt_lots'):
            probe = f"SELECT to_regclass('public.{table}') IS NOT NULL AS present"
            if statement == probe:
                statement = 'SELECT to_regclass(%s) IS NOT NULL AS present'
                params = (f'{self.owner.schema}.{table}',)
                break
        result = self.raw.execute(statement, params)
        if statement.lstrip().startswith('UPDATE '):
            self.owner.updated = True
            if self.owner.fail_after_update:
                raise HTTPException(409, 'Synthetic rejection after real UPDATE')
        return result


class ObservedConnection:
    """Delegate all transaction behavior; observe cleanup without mocking PG."""
    def __init__(self, raw, schema, fail_after_update):
        self.raw, self.schema = raw, schema
        self.fail_after_update = fail_after_update
        self.commits = self.rollbacks = 0
        self.updated = False
        self.cursors = []

    @property
    def autocommit(self):
        return self.raw.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self.raw.autocommit = value

    def cursor(self, **kwargs):
        cursor = GuardCursor(self.raw.cursor(**kwargs), self)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.commits += 1
        self.raw.commit()

    def rollback(self):
        self.rollbacks += 1
        self.raw.rollback()

    def close(self):
        self.raw.close()


def warehouse_handler(get_db):
    """Compile only this handler, with its body unchanged; never import main."""
    path = Path(__file__).resolve().parents[2] / 'main.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == 'update_warehouse_main']
    if len(selected) != 1:
        raise AssertionError('Expected exactly one warehouse metadata handler')
    selected[0].decorator_list = []
    namespace = dict(
        Optional=Optional, Header=Header, Depends=Depends, HTTPException=HTTPException,
        WarehouseMainModel=MaterialModel, psycopg2=psycopg2, get_db=get_db,
        get_current_user=lambda: {}, _norm_base_unit=lambda value: value,
        resolve_resource_company_actor=lambda *args, **kwargs: ({}, {}),
        MAIN_WAREHOUSE_WRITE_ROLES=(), PLATFORM_STAFF_ROLES=(), CLIENT_ACCOUNT_ROLES=(),
    )
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['update_warehouse_main']


@skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES') == '1',
            'Explicit isolated PostgreSQL opt-in required')
class MetadataTransactionTests(TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.close)
        self.fixture.query("""INSERT INTO materials
            (company_id,name,unit,quantity,project,work_package)
            VALUES(2,'Cement','кг',10,'Alpha','Основная')""")
        self.connections = []
        self.fail_after_update = False
        app = FastAPI()
        noop = lambda *args, **kwargs: None
        register_materials_module(app, dict(
            resolve_work_company_context=lambda *args, **kwargs: {
                'mode': 'company', 'companyId': 2, 'membershipId': 1,
                'source': 'membership', 'active': True, 'companyActive': True},
            effective_company_actors=lambda *args: [{'companyId': 2, 'role': 'директор'}],
            main_warehouse_write_roles=('директор',),
            get_db=self.get_db, get_current_user=lambda: {}, require_roles=lambda *roles: noop,
            user_project_names=noop, package_access_filter=noop, can_see_warehouse_data=noop,
            require_project_or_warehouse_access=noop, has_package_access=lambda *args: True,
            limit_offset_sql=noop, norm_base_unit=lambda value: value, log_audit=noop,
        ))
        self.material = next(route.endpoint for route in app.routes
                             if getattr(route, 'path', '') == '/materials/{id}'
                             and 'PUT' in route.methods)
        self.warehouse = warehouse_handler(self.get_db)

    def get_db(self):
        raw = self.fixture.get_db()
        # Fixture's setup is committed; reproduce production's initial mode.
        raw.autocommit = True
        self.assertTrue(raw.autocommit)
        conn = ObservedConnection(raw, self.fixture.schema, self.fail_after_update)
        self.connections.append(conn)
        return conn

    def snapshot(self):
        return {table: self.fixture.query(f'SELECT * FROM {table} ORDER BY id')
                for table in ('materials', 'warehouse_main', 'warehouse_receipt_lots',
                              'warehouse_distribution_operations', 'warehouse_movements',
                              'warehouse_history')}

    def invoke(self, kind, **changes):
        data = dict(name='Cement', unit='кг', quantity=10, price=17,
                    minQuantity=3, category='Metadata', workPackage='Основная',
                    project='Alpha' if kind == 'material' else '')
        data.update(changes)
        user = dict(id=1, company_id=2, role='директор')
        if kind == 'material':
            return self.material(1, MaterialModel(**data), user)
        return self.warehouse(1, MaterialModel(**data), None, None, user)

    def assert_closed(self, *, commits, rollbacks):
        conn = self.connections[-1]
        self.assertEqual((conn.commits, conn.rollbacks), (commits, rollbacks))
        self.assertTrue(conn.raw.closed)
        self.assertTrue(conn.cursors)
        self.assertTrue(all(cursor.closed for cursor in conn.cursors))

    def assert_success(self, kind):
        before = self.snapshot()
        self.assertEqual(self.invoke(kind), {'ok': True})
        self.assert_closed(commits=1, rollbacks=0)
        # A separate connection observes committed metadata and unchanged stock.
        after = self.snapshot()
        table = 'materials' if kind == 'material' else 'warehouse_main'
        row = after[table][0]
        self.assertEqual((row['price'], row['min_quantity'], row['category']),
                         (17, 3, 'Metadata'))
        expected = before[table][0].copy()
        expected.update(price=17, min_quantity=3, category='Metadata')
        before[table][0] = expected
        self.assertEqual(after, before)

    def test_material_metadata_commits_from_autocommit_connection(self):
        self.assert_success('material')

    def test_warehouse_metadata_commits_from_autocommit_connection(self):
        self.assert_success('warehouse')

    def test_material_stock_or_project_change_rejected_and_closed(self):
        for change in ({'quantity': 9}, {'project': 'Beta'}):
            with self.subTest(change=change):
                before = self.snapshot()
                with self.assertRaises(HTTPException) as error:
                    self.invoke('material', **change)
                self.assertEqual(error.exception.status_code, 400)
                self.assert_closed(commits=0, rollbacks=1)
                self.assertEqual(self.snapshot(), before)

    def test_tracked_warehouse_identity_or_stock_change_rejected_and_closed(self):
        for change in ({'quantity': 9}, {'name': 'Other'}, {'unit': 'шт'}):
            with self.subTest(change=change):
                before = self.snapshot()
                with self.assertRaises(HTTPException) as error:
                    self.invoke('warehouse', **change)
                self.assertEqual(error.exception.status_code, 409)
                self.assert_closed(commits=0, rollbacks=1)
                self.assertEqual(self.snapshot(), before)

    def test_rejection_after_real_update_rolls_back_metadata(self):
        self.fail_after_update = True
        for kind in ('material', 'warehouse'):
            with self.subTest(kind=kind):
                before = self.snapshot()
                with self.assertRaises(HTTPException) as error:
                    self.invoke(kind)
                self.assertEqual(error.exception.detail, 'Synthetic rejection after real UPDATE')
                self.assertTrue(self.connections[-1].updated)
                self.assert_closed(commits=0, rollbacks=1)
                self.assertEqual(self.snapshot(), before)
