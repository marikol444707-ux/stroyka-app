"""Opt-in real PG handler transactions; auth/estimate/document boundaries mocked.

Explicit disposable Unix socket only. No main/config/.env or production schema.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from threading import Barrier
import unittest
from uuid import uuid4
import psycopg2
from fastapi import HTTPException
from . import test_identity as support
from backend.features.warehouse_distribution.test_postgres_support import connection_settings


@unittest.skipUnless(os.environ.get('SUPPLY_CHAIN_RUN_POSTGRES')=='1','Explicit disposable PostgreSQL required')
class TransferIdentityPostgresTests(support.Harness,unittest.TestCase):
    def setUp(self):
        self.settings=connection_settings(os.environ)
        self.settings.update(password='',passfile='/nonexistent-test-passfile',sslmode='disable')
        self.schema='transfer_identity_'+uuid4().hex
        self.admin=psycopg2.connect(**self.settings);self.admin.autocommit=True
        self.addCleanup(self.admin.close)
        self.query('CREATE SCHEMA '+self.schema)
        self.addCleanup(lambda:self.query('DROP SCHEMA '+self.schema+' CASCADE'))
        self.query('SET search_path TO '+self.schema)
        self.query(support.DDL.replace('INTEGER PRIMARY KEY','SERIAL PRIMARY KEY'))
        self.configure()
    def connection(self):return psycopg2.connect(**self.settings,options='-c search_path='+self.schema)
    def query(self,sql,params=()):
        with self.admin.cursor() as cur:
            cur.execute(sql,params)
            return cur.fetchall() if cur.description else []
    test_issue_and_cancel_exact_source_once=support.StockIdentityTests.test_issue_persists_id_cancel_restores_one_row_once
    test_legacy_duplicate_cancel_no_mutation=support.StockIdentityTests.test_legacy_duplicate_cancel_rejected_without_credit
    test_return_identity_and_repeat=support.StockIdentityTests.test_return_original_name_reduces_balance_and_repeat_fails
    def test_concurrent_cancellations_credit_once(self):
        self.stock(quantity=5);self.stock(2);self.transfer();barrier=Barrier(2)
        def run(_):barrier.wait(timeout=5);return self.cancel()
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,range(2)))
        self.assertEqual(result,[{'ok':True},{'ok':True}]);self.assertEqual(self.balances(),[(1,10),(2,10)])
        self.assertEqual(self.query('SELECT count(*) FROM warehouse_history'),[(1,)])
    def test_concurrent_returns_exhaust_once(self):
        self.stock(quantity=0);self.stock(2,quantity=0);self.transfer(signed=True);barrier=Barrier(2)
        def run(_):
            barrier.wait(timeout=5)
            try:self.returned();return 200
            except HTTPException as error:return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(run,range(2)))
        self.assertEqual(sorted(result),[200,400]);self.assertEqual(self.balances(),[(1,5),(2,0)])
        self.assertEqual(self.query('SELECT count(*) FROM warehouse_history'),[(1,)])
    def test_history_failure_rolls_back_credit_and_status(self):
        self.stock(quantity=5);self.transfer()
        self.query("ALTER TABLE warehouse_history ADD CONSTRAINT reject_cancel CHECK(type<>'отмена передачи')")
        with self.assertRaises(HTTPException):self.cancel()
        self.assertEqual(self.balances(),[(1,5)]);self.assertEqual(self.query('SELECT status FROM material_transfers'),[(None,)])
