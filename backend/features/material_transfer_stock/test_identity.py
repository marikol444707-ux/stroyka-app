"""Actual extracted handlers on SQLite; auth/estimate/document boundaries mocked.

SQL adapters strip FOR UPDATE only here. This is not PostgreSQL locking or HTTP
end-to-end proof. The separately opted-in PG suite uses unmodified PostgreSQL SQL.
"""
import ast
import json
import math
from pathlib import Path
import re
import sqlite3
import unittest
from unittest.mock import patch
import psycopg2.extras
from fastapi import HTTPException

PATH=Path(__file__).resolve().parents[2]/'main.py'
NAMES={'_norm_key_text','_norm_base_unit','_positive_int_or_none','_row_value',
       '_material_control_key','_material_control_key_resolved','_stock_row_by_material_key',
       '_material_return_stock','_require_unambiguous_legacy_material_person',
       '_personal_material_quantity','_personal_material_balance','_parse_materials_used',
       '_restore_material_work_writeoff','_float_or_zero','_sql_norm_unit',
       'create_material_transfer','return_material_from_master','delete_material_transfer'}
DDL='''
CREATE TABLE materials(id INTEGER PRIMARY KEY,company_id INTEGER,name TEXT,unit TEXT,
 quantity REAL,project TEXT,work_package TEXT);
CREATE TABLE warehouse_main(id INTEGER PRIMARY KEY,company_id INTEGER,name TEXT,unit TEXT,quantity REAL);
CREATE TABLE users(id INTEGER PRIMARY KEY,company_id INTEGER,name TEXT,active BOOLEAN);
CREATE TABLE user_company_roles(user_id INTEGER,company_id INTEGER,role TEXT,active BOOLEAN,
 assigned_projects TEXT,assigned_packages TEXT);
CREATE TABLE material_transfers(id INTEGER PRIMARY KEY,company_id INTEGER,project_id INTEGER,
 project_name TEXT,from_location TEXT,to_user_id INTEGER,to_person TEXT,to_person_role TEXT,
 work_package TEXT,material_name TEXT,quantity REAL,unit TEXT,transfer_date TEXT,notes TEXT,
 created_by TEXT,invoice_id INTEGER,invoice_line_key TEXT,invoice_line_index INTEGER,
 invoice_number TEXT,source_stock_id INTEGER,signed BOOLEAN DEFAULT FALSE,status TEXT,
 cancelled_at TEXT,cancelled_by TEXT,cancel_reason TEXT);
CREATE TABLE warehouse_history(id INTEGER PRIMARY KEY,company_id INTEGER,material TEXT,type TEXT,
 quantity REAL,unit TEXT,date TEXT,project TEXT,issued_to TEXT,issued_by TEXT,work_package TEXT,
 date_time TEXT,source_type TEXT,source_id INTEGER,source_invoice_id INTEGER,source_invoice_line_index INTEGER);
CREATE TABLE work_journal(id INTEGER PRIMARY KEY,company_id INTEGER,project TEXT,master_id INTEGER,
 master_name TEXT,work_package TEXT,materials_used TEXT,material_accounting_version INTEGER,status TEXT);
INSERT INTO users VALUES(7,1,'Петр',TRUE);
INSERT INTO user_company_roles VALUES(7,1,'мастер',TRUE,'["Объект"]','["Основная"]');
'''


def load(ns):
    for node in ast.parse(PATH.read_text()).body:
        if isinstance(node,ast.FunctionDef) and node.name in NAMES:
            node.decorator_list=[]
            if node.name in ('create_material_transfer','return_material_from_master','delete_material_transfer'):
                for arg in node.args.args:arg.annotation=None
                node.args.defaults=[ast.Constant(None) for _ in node.args.defaults]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(PATH),'exec'),ns)
    return ns


class Cursor:
    def __init__(self,conn):self.conn=conn;self.cur=conn.db.cursor()
    def execute(self,sql,params=()):
        self.conn.calls.append((sql,params))
        if self.conn.fail_history and 'INSERT INTO warehouse_history' in sql:raise RuntimeError('injected history failure')
        sql=sql.replace('FOR UPDATE','').replace('NOW()','CURRENT_TIMESTAMP')
        sql=sql.replace('issued_by=ANY(%s)','array_contains(%s,issued_by)').replace('%s','?')
        self.cur.execute(sql,[json.dumps(v) if isinstance(v,list) else v for v in params])
    def fetchall(self):return [dict(row) for row in self.cur.fetchall()]
    def fetchone(self):
        row=self.cur.fetchone();return dict(row) if row is not None else None
    @property
    def rowcount(self):return self.cur.rowcount
    def close(self):self.cur.close()


class SQLiteConnection:
    def __init__(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.calls=[];self.fail_history=False
        self.db.create_function('array_contains',2,lambda values,value:value in json.loads(values))
        self.db.executescript(DDL)
    def cursor(self,**kwargs):return Cursor(self)
    def commit(self):self.db.commit()
    def rollback(self):self.db.rollback()
    def close(self):pass


class Harness:
    def configure(self):
        self.actor={'id':1,'companyId':1,'role':'директор','name':'Директор'}
        self.ns=load(dict(math=math,re=re,psycopg2=psycopg2,HTTPException=HTTPException,
            get_db=self.connection,_resolve_material_alias=lambda *a,**k:None,
            _resolve_work_company_context=lambda *a,**k:{},effective_company_actors=lambda user,context:[user],
            WAREHOUSE_ROLES=('директор',),SUPPLY_INTERNAL_ROLES=('директор',),WORKER_EXECUTION_ROLES=('мастер',),
            PACKAGE_LIMIT_ROLES=('мастер',),has_package_access=lambda *a:True,
            require_project_or_warehouse_access=lambda *a:None,_safe_project_list=lambda raw:json.loads(raw),
            _attach_supply_estimate_control=lambda *a,**k:None,_enforce_supply_estimate_control=lambda *a,**k:None,
            _supply_work_package=lambda v:v,_run_project_ai_control_safely=lambda *a:None))
        for target,value in (
            ('backend.features.project_access.service.resolve_project_parent',{'id':1,'name':'Объект','companyId':1}),
            ('backend.features.material_transfer_access.service.resolve_material_transfer_parent',{'companyId':1}),
            ('backend.features.material_traceability.guards.lock_distribution_compatible_stock',None),
            ('backend.features.material_transfer_documents.storage.freeze_material_transfer_issue',None)):
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)
    def stock(self,id=1,name='Цемент портланд',quantity=10,company=1,project='Объект',package='Основная',unit='кг'):
        self.query('INSERT INTO materials(id,company_id,name,unit,quantity,project,work_package) VALUES(%s,%s,%s,%s,%s,%s,%s)',(id,company,name,unit,quantity,project,package))
    def transfer(self,id=1,source=1,signed=False,name='Цемент портланд',quantity=5,company=1,package='Основная',location='Объект'):
        self.query('''INSERT INTO material_transfers(id,company_id,project_id,project_name,from_location,
            to_user_id,to_person,work_package,material_name,quantity,unit,signed,source_stock_id)
            VALUES(%s,%s,1,'Объект',%s,7,'Петр',%s,%s,%s,'кг',%s,%s)''',
            (id,company,location,package,name,quantity,signed,source))
    def select(self,**kw):
        conn=self.connection()
        try:
            return self.ns['_stock_row_by_material_key'](conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor),
                company_id=kw.pop('company_id',1),project='Объект',material_name='Цемент портланд',
                unit='кг',work_package='Основная',**kw)
        finally:conn.rollback();conn.close()
    def cancel(self):return self.ns['delete_material_transfer'](1,current_user=self.actor)
    def returned(self,quantity=5):
        return self.ns['return_material_from_master'](dict(projectName='Объект',materialName='Цемент портланд',
            quantity=quantity,unit='кг',workPackage='Основная',fromPersonId=7),current_user=self.actor)
    def balances(self):return self.query('SELECT id,quantity FROM materials ORDER BY id')
    def issue(self,source=None):
        return self.ns['create_material_transfer'](dict(materialName='Цемент портланд',quantity=5,unit='кг',
            projectName='Объект',fromLocation='Объект',workPackage='Основная',toPerson='Петр',
            toUserId=7,toPersonRole='мастер',sourceStockId=source),current_user=self.actor)


class StockIdentityTests(Harness,unittest.TestCase):
    def setUp(self):
        self.conn=SQLiteConnection();self.addCleanup(self.conn.db.close);self.configure()
        self.conn.db.create_function('norm_unit',1,self.ns['_norm_base_unit'])
        self.ns['_sql_norm_unit']=lambda col:'norm_unit('+col+')'
    def connection(self):return self.conn
    def query(self,sql,params=()):
        cur=self.conn.db.execute(sql.replace('%s','?'),params)
        result=[tuple(row) for row in cur.fetchall()] if cur.description else []
        self.conn.db.commit();return result
    def test_older_exact_beats_newer_similar(self):
        self.stock();self.stock(2,name='Цемент портланд М500');self.assertEqual(self.select()['id'],1)
    def test_no_fuzzy_cross_package_company_unit_or_project(self):
        self.stock(1,name='Цемент портланд М500');self.stock(2,package='Отделка')
        self.stock(3,company=2);self.stock(4,unit='шт');self.stock(5,project='Другой')
        self.assertIsNone(self.select())
    def test_missing_company_rejected(self):
        self.stock()
        with self.assertRaises(HTTPException):self.select(company_id=None)
    def test_duplicate_requires_source_id(self):
        self.stock();self.stock(2)
        with self.assertRaises(HTTPException):self.select()
        self.assertEqual(self.select(source_stock_id=1)['id'],1)
    def test_foreign_changed_or_invalid_source_rejected(self):
        self.stock(company=2);self.stock(2,package='Отделка');self.stock(3,name='Цемент портланд М500')
        for id in (1,2,3,99,True,1.5,'1.0'):
            with self.subTest(id=id),self.assertRaises(HTTPException):self.select(source_stock_id=id)
    def test_issue_persists_id_cancel_restores_one_row_once(self):
        self.stock();self.stock(2);self.issue(2)
        self.assertEqual(self.balances(),[(1,10),(2,5)])
        self.assertEqual(self.query('SELECT source_stock_id FROM material_transfers'),[(2,)])
        self.cancel();self.cancel();self.assertEqual(self.balances(),[(1,10),(2,10)])
        self.assertEqual(self.query("SELECT count(*) FROM warehouse_history WHERE type='отмена передачи'"),[(1,)])
    def test_legacy_duplicate_cancel_rejected_without_credit(self):
        self.stock();self.stock(2,quantity=5);self.transfer(source=None)
        with self.assertRaises(HTTPException):self.cancel()
        self.assertEqual(self.balances(),[(1,10),(2,5)]);self.assertEqual(self.query('SELECT status FROM material_transfers'),[(None,)])
    def test_legacy_unique_cancel_once(self):
        self.stock(quantity=5);self.transfer(source=None);self.cancel();self.cancel()
        self.assertEqual(self.balances(),[(1,10)])
    def test_cancel_rollback_after_credit(self):
        self.stock(quantity=5);self.transfer();self.conn.fail_history=True
        with self.assertRaises(HTTPException):self.cancel()
        self.assertEqual(self.balances(),[(1,5)]);self.assertEqual(self.query('SELECT status FROM material_transfers'),[(None,)])
    def test_return_original_name_reduces_balance_and_repeat_fails(self):
        self.stock(quantity=0);self.stock(2,name='Цемент портланд М500',quantity=0);self.transfer(signed=True)
        self.returned();self.assertEqual(self.balances(),[(1,5),(2,0)])
        self.assertEqual(self.query('SELECT material FROM warehouse_history'),[('Цемент портланд',)])
        with self.assertRaises(HTTPException) as err:self.returned()
        self.assertEqual(err.exception.status_code,400);self.assertEqual(self.balances(),[(1,5),(2,0)])
    def test_return_exact_source_disambiguates_duplicate_stock(self):
        self.stock(quantity=0);self.stock(2,quantity=0);self.transfer(signed=True);self.returned()
        self.assertEqual(self.balances(),[(1,5),(2,0)])
    def test_return_ambiguous_legacy_or_multiple_sources_rejected(self):
        self.stock(quantity=0);self.stock(2,quantity=0);self.transfer(signed=True,source=None)
        with self.assertRaises(HTTPException):self.returned()
        self.query('UPDATE material_transfers SET source_stock_id=1');self.transfer(id=2,source=2,signed=True)
        with self.assertRaises(HTTPException):self.returned()
        self.assertEqual(self.balances(),[(1,0),(2,0)])
    def test_missing_return_source_rejected(self):
        self.stock(2,name='Цемент портланд М500',quantity=0);self.transfer(signed=True)
        with self.assertRaises(HTTPException):self.returned()
        self.assertEqual(self.balances(),[(2,0)])
    def test_return_history_failure_rolls_back(self):
        self.stock(quantity=0);self.transfer(signed=True);self.conn.fail_history=True
        with self.assertRaises(HTTPException):self.returned()
        self.assertEqual(self.balances(),[(1,0)]);self.conn.fail_history=False;self.returned()
        self.assertEqual(self.balances(),[(1,5)])
    def test_signed_cannot_cancel(self):
        self.stock(quantity=5);self.transfer(signed=True)
        with self.assertRaises(HTTPException):self.cancel()
        self.assertEqual(self.balances(),[(1,5)])
    def test_return_locks_before_balance(self):
        self.stock(quantity=0);self.transfer(signed=True);self.returned()
        calls=[sql for sql,_ in self.conn.calls]
        lock=next(i for i,s in enumerate(calls) if 'FROM material_transfers' in s and 'FOR UPDATE' in s)
        balance=next(i for i,s in enumerate(calls) if 'SELECT material_name, quantity, unit' in s)
        self.assertLess(lock,balance)
    def test_main_warehouse_cancel_one_source(self):
        self.query("INSERT INTO warehouse_main VALUES(1,1,'Цемент портланд','кг',5)")
        self.query("INSERT INTO warehouse_main VALUES(2,1,'Цемент портланд','кг',10)")
        self.transfer(location='Основной склад');self.cancel();self.cancel()
        self.assertEqual(self.query('SELECT id,quantity FROM warehouse_main ORDER BY id'),[(1,10),(2,10)])
    def test_legacy_work_restore_exact_not_similar(self):
        self.stock(quantity=0);self.stock(2,name='Цемент портланд М500',quantity=0)
        self.ns['_restore_material_work_writeoff'](self.conn.cursor(),'Объект',dict(name='Цемент портланд',quantity=5,unit='кг',workPackage='Основная'),dict(company_id=1,master_id=7,master_name='Петр'),None)
        self.assertEqual(self.balances(),[(1,5),(2,0)])
    def test_alias_merged_issued_names_require_review(self):
        self.stock(quantity=0);self.stock(2,name='Цемент портланд М500',quantity=0)
        self.transfer(signed=True);self.transfer(id=2,source=2,signed=True,name='Цемент портланд М500')
        self.ns['_resolve_material_alias']=lambda *a,**k:dict(canonicalName='Цемент',canonicalUnit='кг')
        with self.assertRaises(HTTPException):self.returned(10)
        self.assertEqual(self.balances(),[(1,0),(2,0)])
    def test_estimate_cannot_change_selected_source_package(self):
        self.stock()
        def changed(cur,project,items,**kw):
            if kw.get('exclude_stock_by_key'):items[0]['workPackage']='Отделка'
        self.ns['_attach_supply_estimate_control']=changed
        with self.assertRaises(HTTPException):self.issue()
        self.assertEqual(self.balances(),[(1,10)]);self.assertEqual(self.query('SELECT count(*) FROM material_transfers'),[(0,)])
    def test_main_warehouse_cancel_missing_or_foreign_source_leaves_stock(self):
        self.query("INSERT INTO warehouse_main VALUES(1,2,'Цемент портланд','кг',5)")
        self.query("INSERT INTO warehouse_main VALUES(2,1,'Цемент портланд','кг',10)")
        self.transfer(location='Основной склад')
        for source in (1,99):
            self.query('UPDATE material_transfers SET source_stock_id=%s',(source,))
            with self.subTest(source=source),self.assertRaises(HTTPException):self.cancel()
            self.assertEqual(self.query('SELECT id,quantity FROM warehouse_main ORDER BY id'),[(1,5),(2,10)])
            self.assertEqual(self.query('SELECT status FROM material_transfers'),[(None,)])
        self.assertEqual(self.query('SELECT count(*) FROM warehouse_history'),[(0,)])
    def test_legacy_main_warehouse_personal_return_requires_reconciliation(self):
        self.stock(quantity=0)
        self.query("INSERT INTO warehouse_main VALUES(1,1,'Цемент портланд','кг',5)")
        self.transfer(signed=True,location='Основной склад')
        with self.assertRaises(HTTPException):self.returned()
        self.assertEqual(self.balances(),[(1,0)])
        self.assertEqual(self.query('SELECT quantity FROM warehouse_main'),[(5,)])
        self.assertEqual(self.query('SELECT count(*) FROM warehouse_history'),[(0,)])
