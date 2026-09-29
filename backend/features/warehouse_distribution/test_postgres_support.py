"""Explicit Unix-socket-only empty test DB. No main/config/auth import or .env reads."""
import ast
from contextlib import ExitStack
from pathlib import Path
import os
import re
import socket
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from ..company_context.service import effective_company_actors, resolve_request_company_context
from .routes import register_warehouse_distribution_module


def connection_settings(environ):
    if environ.get('SUPPLY_CHAIN_RUN_POSTGRES') != '1':
        raise RuntimeError('Explicit SUPPLY_CHAIN_RUN_POSTGRES=1 is required')
    host = environ.get('SUPPLY_CHAIN_TEST_DB_HOST', '')
    port = environ.get('SUPPLY_CHAIN_TEST_DB_PORT', '')
    name = environ.get('SUPPLY_CHAIN_TEST_DB_NAME', '')
    if not host.startswith('/') or ',' in host or '\x00' in host:
        raise RuntimeError('Explicit Unix socket SUPPLY_CHAIN_TEST_DB_HOST required')
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise RuntimeError('Explicit valid SUPPLY_CHAIN_TEST_DB_PORT required')
    if not re.fullmatch(r'(?:supply_chain_test|dist_membership)_[a-z0-9_]+', name):
        raise RuntimeError('Dedicated supply_chain_test_* or dist_membership_* database required')
    return dict(host=host, port=port, dbname=name, user='chain_test', password='')


def migration(cur, action):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/0025_warehouse_distribution.py'
    tree = ast.parse(path.read_text())
    functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)], type_ignores=[])
    namespace = {'op': SimpleNamespace(execute=cur.execute)}
    exec(compile(functions, str(path), 'exec'), namespace)
    namespace[action]()


class MovementModel(BaseModel):
    materialName: str
    fromLocation: str
    toLocation: str
    quantity: float
    unit: str
    workPackage: str
    date: str
    createdBy: str
    notes: str
    invoiceId: object = None
    invoiceLineIndex: object = None


def extracted_movement_helper():
    """Run real stock/history helper, stubbing only estimate annotation (not stock)."""
    import datetime
    path = Path(__file__).resolve().parents[2] / 'main.py'
    tree = ast.parse(path.read_text())
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name in ('_apply_warehouse_movement', '_sql_norm_unit', '_norm_base_unit', '_norm_key_text', '_json_list_or_empty')]
    if len(selected) != 5:
        raise RuntimeError('Shared helper contract unavailable')
    def estimate_annotation(cur, project, items, company_id):
        # Synthetic estimate resolution deliberately changes package on issue.
        for item in items:
            item['workPackage'] = 'Synthetic package'
    namespace = {'psycopg2': psycopg2, 'HTTPException': HTTPException, 'dt': datetime,
                 '_supply_work_package': lambda value: value,
                 '_attach_supply_estimate_control': estimate_annotation,
                 'build_movement_estimate_control': lambda items: {'status': 'test', 'items': items}}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_apply_warehouse_movement']


DDL = '''
CREATE TABLE companies(id integer PRIMARY KEY, name text, short_name text,
    active boolean DEFAULT TRUE, platform_account_id integer, plan text DEFAULT 'demo',
    trial_until date, plan_expires_at date, payment_status text, suspended_at timestamp);
CREATE TABLE users(id integer PRIMARY KEY, company_id integer REFERENCES companies(id),
    name text, role text, active boolean DEFAULT TRUE);
CREATE TABLE user_company_roles(id serial PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id),
    company_id integer NOT NULL REFERENCES companies(id), role text NOT NULL, staff_id integer,
    platform_account_id integer, assigned_projects jsonb DEFAULT '[]', assigned_packages jsonb DEFAULT '[]',
    active boolean DEFAULT TRUE, is_default boolean DEFAULT TRUE, UNIQUE(user_id,company_id,role));
CREATE TABLE projects(id serial PRIMARY KEY, company_id integer, name text);
CREATE TABLE warehouse_invoices(id serial PRIMARY KEY, company_id integer, number text,
    supplier_name text DEFAULT 'Synthetic supplier',
    items jsonb, status text DEFAULT 'Принята', project text DEFAULT '', location text DEFAULT 'Основной склад',
    payment_status text DEFAULT 'Не оплачено');
CREATE TABLE warehouse_main(id serial PRIMARY KEY, company_id integer,name text,unit text,
    quantity double precision,price numeric DEFAULT 0,min_quantity numeric DEFAULT 0,category text DEFAULT '');
CREATE TABLE materials(id serial PRIMARY KEY, company_id integer,name text,unit text,
    quantity double precision,price numeric DEFAULT 0,min_quantity numeric DEFAULT 0,category text DEFAULT '',
    project text,work_package text);
CREATE TABLE warehouse_movements(id serial PRIMARY KEY, company_id integer,material_name text,
    from_location text,to_location text,quantity double precision,unit text,work_package text,date text,
    created_by text,notes text,source_invoice_id integer,source_invoice_line_index integer,
    estimate_control_status text,estimate_control jsonb);
CREATE TABLE warehouse_history(id serial PRIMARY KEY,company_id integer,material text,type text,
    quantity double precision,unit text,date text,project text,issued_to text,issued_by text,
    work_package text,date_time text,source_type text,source_id integer,
    source_invoice_id integer,source_invoice_line_index integer);
'''


class Fixture:
    def __init__(self):
        self.settings = connection_settings(os.environ)
        self.schema = 'distribution_test_' + uuid4().hex
        self.stack = ExitStack()
        self.connections = []
        self.stack.enter_context(patch.dict(os.environ, {
            'WAREHOUSE_DISTRIBUTION_ENABLED': '1', 'PGPASSFILE': '/nonexistent-distribution-test-passfile'
        }, clear=True))
        original_connect = socket.socket.connect
        def no_network(*args, **kwargs):
            raise RuntimeError('Network disabled in distribution tests')
        def unix_only(sock, address):
            if sock.family != socket.AF_UNIX:
                return no_network()
            return original_connect(sock, address)
        self.stack.enter_context(patch.object(socket.socket, 'connect', unix_only))
        self.stack.enter_context(patch.object(socket.socket, 'connect_ex', no_network))
        self.stack.enter_context(patch.object(socket, 'create_connection', no_network))
        try:
            self.control = psycopg2.connect(**self.settings)
            self.connections.append(self.control)
            self.control.autocommit = True
            with self.control.cursor() as cur:
                cur.execute('SELECT current_database(),current_user,inet_server_addr(),inet_server_port()')
                if cur.fetchone() != (self.settings['dbname'], 'chain_test', None, None):
                    raise RuntimeError('Unexpected test DB identity')
                cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')")
                if cur.fetchone()[0]:
                    raise RuntimeError('A completely empty dedicated test DB is required')
                cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
            conn = self.get_db()
            with conn, conn.cursor() as cur:
                cur.execute(DDL)
                migration(cur, 'upgrade')
                cur.execute("INSERT INTO companies(id,name) VALUES(2,'Company A'),(3,'Company B')")
                for company_id in (2, 3):
                    for index, role in enumerate(('директор', 'зам_директора', 'бухгалтер', 'прораб', 'поставщик', 'кладовщик', 'снабженец'), 1):
                        user_id = (company_id - 2) * 100 + index
                        cur.execute('INSERT INTO users(id,company_id,name,role) VALUES(%s,%s,%s,%s)',
                                    (user_id, company_id, 'Synthetic actor', role))
                        cur.execute('INSERT INTO user_company_roles(user_id,company_id,role) VALUES(%s,%s,%s)',
                                    (user_id, company_id, role))
                cur.execute("INSERT INTO projects(id,company_id,name) VALUES(1,2,'Alpha'),(2,2,'Beta'),(3,3,'Other')")
                cur.execute('''INSERT INTO warehouse_invoices(id,company_id,number,items)
                    VALUES(1,2,'R1','[{"name":"Cement","quantity":10,"unit":"кг"}]'),
                          (2,3,'R2','[{"name":"Cement","quantity":10,"unit":"кг"}]')''')
                cur.execute('''INSERT INTO warehouse_receipt_lots(company_id,warehouse_location,warehouse_target,
                    warehouse_invoice_id,invoice_line_index,material_name,document_quantity,document_unit,
                    received_quantity,unit,available_quantity)
                    VALUES(2,'Основной склад','main',1,0,'Cement',10,'кг',10,'кг',10),
                          (3,'Основной склад','main',2,0,'Cement',10,'кг',10,'кг',10)''')
                cur.execute("INSERT INTO warehouse_main(company_id,name,unit,quantity) VALUES(2,'Cement','кг',10),(3,'Cement','кг',10)")
            conn.close()
            self.helper = extracted_movement_helper()
            self.calls = 0
            self.fail_on_call = None
            def apply(cur, model, company_id, actor):
                assert model.invoiceId is None and model.invoiceLineIndex is None
                self.calls += 1
                result = self.helper(cur, model, company_id, actor)
                if self.calls == self.fail_on_call:
                    raise HTTPException(409, 'Synthetic failure after stock/history mutations')
                return result
            def user(request: Request):
                # Synthetic authentication only; company scope/roles use the real resolver.
                index = {'director': 1, 'deputy': 2, 'accountant': 3, 'foreman': 4,
                         'supplier': 5, 'storekeeper': 6, 'supply': 7}[request.headers.get('X-Test-Role', 'director')]
                user_id = (int(request.headers.get('X-Test-Company', '2')) - 2) * 100 + index
                rows = self.query('SELECT * FROM users WHERE id=%s AND active=TRUE', (user_id,))
                if not rows:
                    raise HTTPException(403, 'Synthetic user inactive or missing')
                return dict(rows[0])
            self.app = FastAPI()
            self.deps = dict(
                get_db=self.get_db, get_current_user=user, resolve_work_company_context=resolve_request_company_context,
                effective_company_actors=effective_company_actors,
                apply_movement=apply, movement_model=MovementModel,
                finance_roles={'директор', 'зам_директора', 'бухгалтер'})
            register_warehouse_distribution_module(self.app, self.deps)
        except BaseException:
            self.close()
            raise

    def get_db(self):
        conn = psycopg2.connect(**self.settings)
        self.connections.append(conn)
        with conn.cursor() as cur:
            cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
            cur.execute("SET statement_timeout='15s'; SET lock_timeout='5s'")
        conn.commit()
        return conn

    def query(self, statement, args=()):
        conn = self.get_db()
        try:
            with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(statement, args)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def close(self):
        for conn in self.connections:
            if not conn.closed:
                conn.close()
        if hasattr(self, 'control'):
            conn = psycopg2.connect(**self.settings)
            try:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(self.schema)))
            finally:
                conn.close()
        self.stack.close()
