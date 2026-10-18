"""Opt-in, empty, Unix-socket PostgreSQL fixture for unified receipt tests.

No backend.main/config import, .env loading, database creation, or migration runner.
The receipt-originals schema SQL is installed only in this disposable schema;
no production schema or migrations are applied.
The schema is synthetic. The real confirmation/resolver/company-context code is
used, but the writer below is deliberately a stock/invoice/proof/claim SQL stand-in:
these tests do NOT establish integration with the production accounting writer.

Run against an already provisioned EMPTY disposable database, never a user DB:
  WAREHOUSE_RECEIPTS_RUN_POSTGRES=1 \
  WAREHOUSE_RECEIPTS_TEST_DSN='host=/tmp/receipt-pg port=55432 dbname=warehouse_receipts_test_local user=receipt_test' \
  python -m unittest backend.features.warehouse_receipts.test_confirmation_postgres -v

Missing opt-in/DSN skips the PostgreSQL cases. An unsafe DSN, nonempty database,
or unavailable explicitly selected server fails setup rather than passing.
"""
import copy
import os
import re
import threading
import time
import unittest
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from fastapi import HTTPException
from psycopg2 import sql
from psycopg2.extensions import connection, parse_dsn
from psycopg2.extras import Json, RealDictCursor

from backend.features.company_context.service import (
    effective_company_actors, resolve_request_company_context,
    resolve_resource_company_actor,
)
from backend.features.supplier_access.fulfilment import internal_fulfilment_filter
from backend.features.supplier_access.offer_party_snapshot import build_offer_party_snapshot
from backend.features.supplier_access.rfq_requester_snapshot import build_rfq_requester_snapshot
from .receipt_originals_schema import SCHEMA_SQL as RECEIPT_ORIGINALS_SCHEMA_SQL


RUN_POSTGRES = (os.getenv('WAREHOUSE_RECEIPTS_RUN_POSTGRES') == '1'
                and bool(os.getenv('WAREHOUSE_RECEIPTS_TEST_DSN')))
SKIP_REASON = ('requires WAREHOUSE_RECEIPTS_RUN_POSTGRES=1 and an explicit '
               'WAREHOUSE_RECEIPTS_TEST_DSN for an empty disposable Unix-socket database')


def connection_settings(environ):
    """Validate every destination value before psycopg2 may open a connection."""
    if environ.get('WAREHOUSE_RECEIPTS_RUN_POSTGRES') != '1':
        raise ValueError('Explicit warehouse receipts PostgreSQL opt-in required')
    value = environ.get('WAREHOUSE_RECEIPTS_TEST_DSN')
    if not value:
        raise ValueError('Explicit dedicated test DSN required')
    settings = parse_dsn(value)
    if set(settings) != {'host', 'port', 'dbname', 'user'}:
        raise ValueError('Test DSN must contain only explicit host, port, dbname, and user')
    host = settings['host']
    if not host.startswith('/') or ',' in host or '\x00' in host:
        raise ValueError('A single absolute Unix socket directory is required')
    if not re.fullmatch(r'[0-9]{1,5}', settings['port']) or not 1 <= int(settings['port']) <= 65535:
        raise ValueError('Explicit valid test port required')
    if not re.fullmatch(r'warehouse_receipts_test_[a-z0-9_]+', settings['dbname']):
        raise ValueError('A dedicated warehouse_receipts_test_* database is required')
    if settings['user'] != 'receipt_test':
        raise ValueError('The dedicated receipt_test role is required')
    return {**settings, 'password': '', 'passfile': '/nonexistent-receipt-test-passfile',
            'connect_timeout': 5, 'application_name': 'warehouse_receipts_regression'}


class RecordingCursor(RealDictCursor):
    def execute(self, statement, params=None):
        text = statement if isinstance(statement, str) else statement.as_string(self)
        self.connection.statements.append(text)
        if text.startswith('LOCK TABLE'):
            self.connection.stock_lock_requested.set()
        if 'pg_advisory_xact_lock' in text and params:
            if str(params[0]).startswith('physical-receipt-batch:'):
                self.connection.batch_lock_requested.set()
            if str(params[0]).startswith('physical-receipt-document:'):
                self.connection.document_lock_requested.set()
        return super().execute(statement, params)


class RecordingConnection(connection):
    """Count real commit/rollback calls without replacing PostgreSQL behavior."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commits = 0
        self.rollbacks = 0
        self.statements = []
        self.stock_lock_requested = threading.Event()
        self.batch_lock_requested = threading.Event()
        self.document_lock_requested = threading.Event()
        self.backend_pid = self.get_backend_pid()

    def cursor(self, *args, **kwargs):
        kwargs['cursor_factory'] = RecordingCursor
        return super().cursor(*args, **kwargs)

    def commit(self):
        super().commit()
        self.commits += 1

    def rollback(self):
        super().rollback()
        self.rollbacks += 1


DDL = '''
CREATE TABLE companies(id integer PRIMARY KEY, name text, short_name text,
    active boolean DEFAULT TRUE, platform_account_id integer,
    plan text DEFAULT 'pro', trial_until date, plan_expires_at date,
    payment_status text DEFAULT 'active', suspended_at timestamp);
CREATE TABLE user_company_roles(id serial PRIMARY KEY, user_id integer,
    company_id integer REFERENCES companies(id), staff_id integer,
    platform_account_id integer, role text, assigned_projects jsonb,
    assigned_packages jsonb, active boolean DEFAULT TRUE, is_default boolean DEFAULT TRUE);
CREATE TABLE projects(id integer PRIMARY KEY, company_id integer, name text);
CREATE TABLE file_ownership(id integer PRIMARY KEY, company_id integer,
    project_id integer, deletion_status text DEFAULT 'active', retained_at timestamptz);
CREATE TABLE supply_requests(id integer PRIMARY KEY, company_id integer,
    project text, requester_snapshot_json jsonb);
CREATE TABLE supplier_offers(id integer PRIMARY KEY, company_id integer,
    supplier_id integer, request_id integer, party_snapshot_json jsonb);
CREATE TABLE supplier_invoices(id integer PRIMARY KEY, company_id integer,
    supplier_id integer, offer_id integer, request_id integer,
    contract_version_id bigint, status text, invoice_number text, invoice_date date);
CREATE TABLE supplier_contract_versions(id bigint PRIMARY KEY, company_id integer,
    offer_id integer, snapshot_json jsonb, snapshot_hash text);
CREATE TABLE supply_deliveries(id integer PRIMARY KEY, company_id integer,
    supplier_id integer, offer_id integer, request_id integer, project text,
    work_package text, material_name text, unit text, shipped_quantity numeric,
    received_quantity numeric DEFAULT 0, received_at timestamptz, status text DEFAULT 'В пути',
    quality_status text, waybill_number text, waybill_date date,
    source_supplier_invoice_id integer, contract_version_id bigint,
    receipt_original_urls jsonb, claim_id integer);
CREATE TABLE supplier_shipment_batches(id integer PRIMARY KEY, company_id integer,
    offer_id integer, delivery_ids integer[]);
CREATE TABLE warehouse_invoices(id serial PRIMARY KEY, company_id integer,
    supply_delivery_id integer, photo_urls jsonb, pages_count integer,
    number text, date date, supplier_id integer, project text,
    items jsonb DEFAULT '[]', total_with_vat numeric, supplier_invoice_id integer,
    source_type text DEFAULT 'supply_delivery', status text DEFAULT 'Принята',
    UNIQUE(company_id,supply_delivery_id));
CREATE TABLE materials(id serial PRIMARY KEY);
CREATE TABLE warehouse_main(company_id integer, material_name text, unit text,
    quantity numeric DEFAULT 0, PRIMARY KEY(company_id,material_name,unit));
CREATE TABLE warehouse_history_standin(id serial PRIMARY KEY, company_id integer,
    delivery_id integer, quantity numeric);
CREATE TABLE receipt_line_proofs_standin(id serial PRIMARY KEY, company_id integer,
    delivery_id integer UNIQUE, invoice_id integer REFERENCES warehouse_invoices(id),
    quantity numeric);
-- Minimal claim stand-in: this does not exercise the production claim endpoint.
CREATE TABLE supply_claims(id serial PRIMARY KEY,
    delivery_id integer UNIQUE REFERENCES supply_deliveries(id), photo_url text,
    received_quantity numeric, shortage_quantity numeric);
CREATE TABLE resource_limits_standin(delivery_id integer PRIMARY KEY, max_quantity numeric);
'''


class ReceiptPostgresFixture:
    def __init__(self):
        self.settings = connection_settings(os.environ)
        self.schema = 'receipt_regression_' + uuid4().hex
        self.connections = []
        self.confirmation_connections = []
        self.written_lines = []
        self.callbacks = []
        self.before_write = None
        self.after_write = None
        self.created = False
        self.control = None
        # libpq must not acquire a different host/service/password from PG* env.
        clean_environment = {key: value for key, value in os.environ.items()
                             if not key.startswith('PG')}
        clean_environment['SUPPLIER_PARTIAL_RECEIPTS_ENABLED'] = '0'
        self.environment = patch.dict(os.environ, clean_environment, clear=True)
        self.environment.start()
        try:
            self.control = psycopg2.connect(**self.settings,
                options='-c search_path=pg_catalog -c statement_timeout=15000 -c lock_timeout=8000')
            self.control.autocommit = True
            with self.control.cursor() as cur:
                cur.execute('SELECT current_database(),current_user,inet_server_addr(),inet_server_port()')
                if cur.fetchone() != (self.settings['dbname'], 'receipt_test', None, None):
                    raise RuntimeError('Unexpected PostgreSQL test database identity')
                cur.execute("""SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%%' AND n.nspname NOT LIKE 'pg_temp_%%'
                      AND c.relkind IN ('r','p','v','m','S','f')""")
                if cur.fetchone()[0]:
                    raise RuntimeError('Refusing a nonempty database; an empty disposable database is required')
                cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
                self.created = True
                cur.execute(sql.SQL('SET search_path TO {},pg_catalog').format(sql.Identifier(self.schema)))
                cur.execute(DDL)
                # Exact feature DDL in the newly created synthetic schema only.
                # This exercises the real readiness/shape/immutability guards.
                cur.execute(RECEIPT_ORIGINALS_SCHEMA_SQL)
            self.seed()
            self.user = {'id': 1, 'company_id': 2, 'role': 'директор', 'name': 'Synthetic operator'}
            self.headers = {'x_company_id': '2', 'x_company_mode': 'company'}
            self.data = {
                'companyId': 2, 'project': 'School', 'projectId': 11,
                'document': {'documentType': 'waybill', 'waybillNumber': 'A-12',
                    'waybillDate': '2026-10-17', 'supplierInn': '1234567890', 'buyerInn': '9876543210',
                    'lines': [{'materialName': name, 'unit': 'шт', 'quantity': '10'}
                              for name in ('Brick', 'Cement')]},
                'originalUrls': ['/tenant-files/77/content', '/tenant-files/78/content',
                                 '/tenant-files/77/content'],
                'physicalReceiptConfirmed': True,
                'actualLines': [{'deliveryId': identity, 'receivedQuantity': '8', 'qualityStatus': 'Недостача'}
                                for identity in (31, 32)],
            }
            self.deps = {'get_db': self.get_db, 'lock_stock': self.lock_stock,
                # Isolate the adapter/document-lock path from legacy DDL by
                # default. A dedicated case installs the real NOWAIT guard.
                'prepare_receipt_transaction': lambda cur: None,
                'receive_delivery': self.receive_standin,
                'resolve_work_company_context': resolve_request_company_context,
                'effective_company_actors': effective_company_actors,
                'warehouse_roles': ('директор', 'кладовщик'),
                'fulfilment_visibility': self.visibility,
                'require_project_or_warehouse_access': self.require_project}
        except BaseException:
            self.close()
            raise

    def seed(self):
        self.query("INSERT INTO companies(id,name) VALUES(2,'Synthetic buyer'),(3,'Other company')")
        self.query("""INSERT INTO user_company_roles(user_id,company_id,role,assigned_projects,assigned_packages)
            VALUES(1,2,'кладовщик','["School"]','["Main"]')""")
        self.query("INSERT INTO projects VALUES(11,2,'School'),(12,2,'Private'),(13,3,'School')")
        self.query("INSERT INTO file_ownership(id,company_id,project_id) VALUES(77,2,11),(78,2,11),(79,3,13),(80,2,12)")
        requester = build_rfq_requester_snapshot(request_id=9, company_id=2, project_id=11,
            project_name='School', delivery_address='Synthetic address', company={'name': 'Synthetic buyer'},
            actor={'id': 1}, frozen_at='2026-10-17T10:00:00Z')
        parties = build_offer_party_snapshot(offer_id=8, request_id=9, company_id=2, supplier_id=7,
            buyer={'fullName': 'Synthetic buyer', 'inn': '9876543210'},
            supplier={'fullName': 'Synthetic supplier', 'inn': '1234567890'},
            actor={'id': 10}, frozen_at='2026-10-17T10:00:00Z')
        self.query('INSERT INTO supply_requests VALUES(9,2,%s,%s)', ('School', Json(requester)))
        self.query('INSERT INTO supplier_offers VALUES(8,2,7,9,%s)', (Json(parties),))
        for identity, name in ((31, 'Brick'), (32, 'Cement')):
            self.query('''INSERT INTO supply_deliveries(id,company_id,supplier_id,offer_id,request_id,
                project,work_package,material_name,unit,shipped_quantity,waybill_number,waybill_date)
                VALUES(%s,2,7,8,9,'School','Main',%s,'шт',10,'A-12','2026-10-17')''', (identity, name))
            self.query('INSERT INTO warehouse_main VALUES(2,%s,%s,0)', (name, 'шт'))
            self.query('INSERT INTO resource_limits_standin VALUES(%s,10)', (identity,))
        self.query('INSERT INTO supplier_shipment_batches VALUES(4,2,8,ARRAY[31,32])')
        self.query("INSERT INTO warehouse_main VALUES(3,'Brick','шт',100)")

    def connect(self, *, tracked=False):
        kwargs = dict(self.settings, options='-c search_path=' + self.schema +
                      ',pg_catalog -c statement_timeout=15000 -c lock_timeout=8000')
        if tracked:
            kwargs['connection_factory'] = RecordingConnection
        conn = psycopg2.connect(**kwargs)
        self.connections.append(conn)
        return conn

    def add_duplicate_batch(self):
        """Another persisted batch of the same legal waybill, never new stock."""
        self.query('''INSERT INTO supply_deliveries(id,company_id,supplier_id,offer_id,request_id,
            project,work_package,material_name,unit,shipped_quantity,waybill_number,waybill_date)
            SELECT id+10,company_id,supplier_id,offer_id,request_id,project,work_package,
                material_name,unit,shipped_quantity,waybill_number,waybill_date
            FROM supply_deliveries WHERE id IN (31,32)''')
        self.query('INSERT INTO supplier_shipment_batches VALUES(5,2,8,ARRAY[41,42])')
        self.query('INSERT INTO resource_limits_standin VALUES(41,10),(42,10)')

    def hide_duplicate_batch(self):
        """Give duplicate lines a valid frozen chain in an unauthorized project."""
        requester = build_rfq_requester_snapshot(request_id=19, company_id=2, project_id=12,
            project_name='Private', delivery_address='Private synthetic address',
            company={'name': 'Synthetic buyer'}, actor={'id': 1}, frozen_at='2026-10-17T10:00:00Z')
        parties = build_offer_party_snapshot(offer_id=18, request_id=19, company_id=2, supplier_id=7,
            buyer={'fullName': 'Synthetic buyer', 'inn': '9876543210'},
            supplier={'fullName': 'Synthetic supplier', 'inn': '1234567890'},
            actor={'id': 10}, frozen_at='2026-10-17T10:00:00Z')
        self.query('INSERT INTO supply_requests VALUES(19,2,%s,%s)', ('Private', Json(requester)))
        self.query('INSERT INTO supplier_offers VALUES(18,2,7,19,%s)', (Json(parties),))
        self.query("""UPDATE supply_deliveries SET offer_id=18,request_id=19,
            project='Private',work_package='Private' WHERE id IN (41,42)""")
        self.query('UPDATE supplier_shipment_batches SET offer_id=18 WHERE id=5')

    def get_db(self):
        conn = self.connect(tracked=True)
        self.confirmation_connections.append(conn)
        return conn

    def query(self, statement, params=None):
        with self.control.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(statement, params)
            return [dict(row) for row in cur.fetchall()] if cur.description else []

    @staticmethod
    def lock_stock(cur):
        # Same physical table-lock order as the production compatibility guard.
        # The public-schema presence probe is intentionally not enabled here.
        cur.execute('LOCK TABLE materials, warehouse_main, projects IN SHARE ROW EXCLUSIVE MODE')

    @staticmethod
    def require_project(actor, project):
        if actor['role'] != 'директор' and project not in actor['assignedProjects']:
            raise HTTPException(403, 'Synthetic project assignment denied')

    @staticmethod
    def visibility(cur, user, company, project, package, company_id, mode):
        context = resolve_request_company_context(cur, user, company_id,
            x_company_id=company_id, x_company_mode=mode)
        # Real SQL composition and persisted memberships, with small synthetic
        # project/package policy dependencies rather than importing backend.main.
        return internal_fulfilment_filter(effective_company_actors(user, context),
            company_column=company, project_column=project, package_column=package,
            deps={'can_see_all_company_data': lambda actor: actor['role'] == 'директор',
                  'scoped_project_filter': lambda actor, column:
                      (' AND ' + column + '=ANY(%s)', [actor['assignedProjects']]),
                  'package_access_filter': lambda actor, column:
                      (' AND ' + column + '=ANY(%s)', [actor['assignedPackages']]),
                  'worker_execution_roles': ()})

    def receive_standin(self, delivery_id, payload, *, connection, after_commit,
                        _current_user, x_company_id, x_company_mode):
        """Real SQL mutations; NOT the production stock/payment/claim writer."""
        from .confirmation import ReceiptTransaction
        if not isinstance(connection, ReceiptTransaction):
            raise AssertionError('The adapter must supply its shared transaction')
        if self.before_write:
            self.before_write(delivery_id, connection)
        with connection.cursor() as cur:
            cur.execute('SELECT * FROM supply_deliveries WHERE id=%s FOR UPDATE', (delivery_id,))
            delivery = cur.fetchone()
            _, actor = resolve_resource_company_actor(cur, _current_user, delivery['company_id'],
                x_company_id=x_company_id, x_company_mode=x_company_mode,
                allowed_roles=('директор', 'кладовщик'))
            self.require_project(actor, delivery['project'])
            if delivery['work_package'] not in actor['assignedPackages']:
                raise HTTPException(403, 'Synthetic package assignment denied')
            quantity = Decimal(payload['receivedQuantity'])
            cur.execute('SELECT max_quantity FROM resource_limits_standin WHERE delivery_id=%s FOR UPDATE',
                        (delivery_id,))
            if quantity > cur.fetchone()['max_quantity']:
                raise HTTPException(409, 'Synthetic resource limit rejected receipt')
            invoice_id = None
            if quantity > 0:
                cur.execute('''INSERT INTO warehouse_invoices(company_id,supply_delivery_id,photo_urls,pages_count)
                    VALUES(%s,%s,%s,1) RETURNING id''',
                    (delivery['company_id'], delivery_id, Json([payload['photoUrl']])))
                invoice_id = cur.fetchone()['id']
                cur.execute('''UPDATE warehouse_main SET quantity=quantity+%s
                    WHERE company_id=%s AND material_name=%s AND unit=%s''',
                    (quantity, delivery['company_id'], delivery['material_name'], delivery['unit']))
                if cur.rowcount != 1:
                    raise HTTPException(409, 'Synthetic stock resource missing')
                cur.execute('''INSERT INTO receipt_line_proofs_standin(company_id,delivery_id,invoice_id,quantity)
                    VALUES(%s,%s,%s,%s)''', (delivery['company_id'], delivery_id, invoice_id, quantity))
            cur.execute('INSERT INTO warehouse_history_standin(company_id,delivery_id,quantity) VALUES(%s,%s,%s)',
                        (delivery['company_id'], delivery_id, quantity))
            claim_id = None
            if quantity < delivery['shipped_quantity']:
                cur.execute('''INSERT INTO supply_claims(delivery_id,photo_url,received_quantity,shortage_quantity)
                    VALUES(%s,%s,%s,%s) RETURNING id''',
                    (delivery_id, payload['photoUrl'], quantity, delivery['shipped_quantity'] - quantity))
                claim_id = cur.fetchone()['id']
            cur.execute("""UPDATE supply_deliveries SET received_quantity=%s,received_at=NOW(),
                status='Проблема',quality_status=%s,claim_id=%s WHERE id=%s""",
                        (quantity, payload['qualityStatus'], claim_id, delivery_id))
            # receipt_original_urls is deliberately not written by this stand-in.
            # Only the real confirmation helper may establish durable originals.
        self.written_lines.append(delivery_id)
        connection.commit()  # Suppressed by the real ReceiptTransaction.
        connection.close()   # Suppressed by the real ReceiptTransaction.
        after_commit.append(lambda: self.callbacks.append((delivery_id, self.snapshot())))
        if self.after_write:
            self.after_write(delivery_id, connection)
        return {'ok': True, 'invoiceId': invoice_id, 'claimId': claim_id}

    def snapshot(self):
        return {table: self.query('SELECT * FROM ' + table + ' ORDER BY 1,2') for table in (
            'warehouse_main', 'warehouse_invoices', 'warehouse_history_standin',
            'receipt_line_proofs_standin', 'supply_deliveries', 'file_ownership', 'supply_claims')}

    def confirm(self, data=None):
        from .confirmation import confirm_receipt
        return confirm_receipt(copy.deepcopy(self.data if data is None else data),
                               self.user, self.headers, self.deps)

    def resolve(self, data=None):
        from .resolver import resolve_receipt
        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SET TRANSACTION READ ONLY')
                return resolve_receipt(cur, copy.deepcopy(self.data if data is None else data),
                                       self.user, self.headers, self.deps)
        finally:
            conn.rollback()
            conn.close()

    def wait_for_blocked(self, conn, blocker_pid, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            row = self.query('SELECT %s=ANY(pg_blocking_pids(%s)) AS blocked',
                             (blocker_pid, conn.backend_pid))[0]
            if row['blocked']:
                return
            time.sleep(.01)
        raise AssertionError('Expected PostgreSQL lock wait was not observed')

    def close(self):
        for conn in self.connections:
            if not conn.closed:
                conn.close()
        try:
            if self.control is not None and not self.control.closed:
                try:
                    if self.created:
                        with self.control.cursor() as cur:
                            cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
                finally:
                    self.control.close()
        finally:
            self.environment.stop()


class IsolatedDatabaseSettingsTests(unittest.TestCase):
    def settings(self, dsn=None, **changes):
        environ = {'WAREHOUSE_RECEIPTS_RUN_POSTGRES': '1',
                   'WAREHOUSE_RECEIPTS_TEST_DSN': dsn or
                   'host=/tmp/receipt-pg port=55432 dbname=warehouse_receipts_test_local user=receipt_test'}
        environ.update(changes)
        return connection_settings(environ)

    def test_explicit_unix_socket_dedicated_database_allowed(self):
        self.assertEqual(self.settings()['dbname'], 'warehouse_receipts_test_local')

    def test_missing_opt_in_and_dsn_fail_before_connect(self):
        for environ in ({}, {'WAREHOUSE_RECEIPTS_RUN_POSTGRES': '1'},
                        {'WAREHOUSE_RECEIPTS_TEST_DSN': 'dbname=warehouse_receipts_test_local'}):
            with self.subTest(environ=environ), patch('psycopg2.connect') as connect:
                with self.assertRaises(ValueError):
                    connection_settings(environ)
                connect.assert_not_called()

    def test_network_shared_database_and_libpq_overrides_rejected(self):
        valid = 'host=/tmp/receipt-pg port=55432 dbname=warehouse_receipts_test_local user=receipt_test'
        for dsn in (valid.replace('/tmp/receipt-pg', 'localhost'),
                    valid.replace('/tmp/receipt-pg', '/tmp/receipt-pg,/tmp/other'),
                    valid.replace('warehouse_receipts_test_local', 'postgres'),
                    valid.replace('receipt_test', 'postgres'),
                    valid.replace('55432', '0'), valid + ' hostaddr=127.0.0.1',
                    valid + ' service=production', valid + ' options=-csearch_path=public',
                    valid + ' password=secret'):
            with self.subTest(dsn=dsn), patch('psycopg2.connect') as connect:
                with self.assertRaises(ValueError):
                    self.settings(dsn)
                connect.assert_not_called()

    def assert_database_refused_without_schema_write(self, replies):
        environment = {'WAREHOUSE_RECEIPTS_RUN_POSTGRES': '1',
                       'WAREHOUSE_RECEIPTS_TEST_DSN':
                       'host=/tmp/receipt-pg port=55432 dbname=warehouse_receipts_test_local user=receipt_test'}
        with patch.dict(os.environ, environment, clear=True), patch('psycopg2.connect') as connect:
            cursor = connect.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = replies
            connect.return_value.closed = False
            with self.assertRaises(RuntimeError):
                ReceiptPostgresFixture()
            statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
            self.assertTrue(statements)
            self.assertTrue(all(statement.lstrip().startswith('SELECT') for statement in statements))
            connect.return_value.close.assert_called_once()

    def test_unexpected_connected_identity_is_refused_before_any_schema_write(self):
        self.assert_database_refused_without_schema_write([('different_database', 'receipt_test', None, None)])

    def test_nonempty_test_database_is_refused_before_any_schema_write(self):
        self.assert_database_refused_without_schema_write([
            ('warehouse_receipts_test_local', 'receipt_test', None, None), (1,)])


if __name__ == '__main__':
    unittest.main()
