"""Contract API and migration exercised only on isolated local temporary tables."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from .contracts import register_supplier_contracts_module
from .test_contracts import payload
from . import test_postgres as parties_tests


def statements(method):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions/0043_supplier_contract_versions.py'
    spec = importlib.util.spec_from_file_location('contract_migration', path)
    module = importlib.util.module_from_spec(spec)
    result = []
    fake = types.ModuleType('alembic')
    fake.op = types.SimpleNamespace(execute=result.append)
    with patch.dict(sys.modules, {'alembic': fake}):
        spec.loader.exec_module(module)
    getattr(module, method)()
    return result


@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS') == '1', 'local PostgreSQL opt-in')
class ContractPostgresTest(unittest.TestCase):
    # Reuse fixture setup, not the parent test methods.
    setUp_parties = parties_tests.PartiesPostgresTest.setUp
    put = parties_tests.PartiesPostgresTest.put

    def setUp(self):
        self.setUp_parties()
        with self.conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE company_requisites (company_id INTEGER PRIMARY KEY, inn TEXT, full_name TEXT)')
            cur.execute("INSERT INTO company_requisites VALUES (12,'7701234567','Компания А'),(99,'7707654321','Компания Б')")
            cur.execute('CREATE TEMP TABLE suppliers (id INTEGER PRIMARY KEY, inn TEXT, name TEXT)')
            cur.execute("INSERT INTO suppliers VALUES (5,'7709876543','Поставщик')")
            cur.execute('CREATE TEMP TABLE projects (id INTEGER PRIMARY KEY, company_id INTEGER, name TEXT)')
            cur.execute("INSERT INTO projects VALUES (44,12,'Object A'),(45,12,'Other object')")
            cur.execute('''CREATE TEMP TABLE file_ownership (id INTEGER PRIMARY KEY,
                company_id INTEGER, project_id INTEGER, deletion_status TEXT DEFAULT 'active')''')
            cur.execute("""INSERT INTO file_ownership VALUES (31,12,NULL,'active'),
                (32,99,NULL,'active'),(33,12,45,'active'),(34,12,NULL,'deleting'),(35,12,44,'active')""")
            for statement in statements('upgrade'):
                cur.execute(statement.replace('public.', 'pg_temp.'))
        self.assertEqual(self.put().status_code, 200)
        app = FastAPI()
        register_supplier_contracts_module(app, self.deps)
        self.contract_client = TestClient(app)

    def review(self, **changes):
        return self.contract_client.post('/supplier-offers/40/contracts', json={**payload(), **changes})

    def history(self, query=''):
        return self.contract_client.get('/supplier-offers/40/contracts' + query)

    def test_snapshot_survives_profile_change_and_retains_source(self):
        response = self.review()
        self.assertEqual(response.status_code, 200, response.text)
        original = response.json()
        with self.conn.cursor() as cur:
            cur.execute("UPDATE company_requisites SET inn='7700000000' WHERE company_id=12")
            cur.execute('SELECT retained_at IS NOT NULL FROM file_ownership WHERE id=31')
            self.assertTrue(cur.fetchone()[0])
        saved = self.history().json()['items'][0]
        self.assertEqual(saved, original)
        self.assertEqual(saved['snapshot']['buyer']['inn'], '7701234567')
        self.assertEqual(saved['snapshot']['signatureStatus'], 'not_verified')

    def test_foreign_wrong_project_and_deleting_files_rejected(self):
        for file_id in (32,33,34):
            with self.subTest(file_id=file_id):
                self.assertEqual(self.review(sourceFileId=file_id).status_code, 403)
        self.assertEqual(self.review(sourceFileId=35).status_code, 200)

    def test_inn_mismatch_and_stale_party_version_leave_no_contract(self):
        wrong = {**payload()['buyer'], 'inn':'7700000000'}
        self.assertEqual(self.review(buyer=wrong).status_code, 409)
        self.assertEqual(self.put(1).status_code, 200)
        self.assertEqual(self.review().status_code, 409)
        self.assertEqual(self.history().json()['items'], [])
        with self.conn.cursor() as cur:
            cur.execute('SELECT retained_at FROM file_ownership WHERE id=31')
            self.assertIsNone(cur.fetchone()[0])

    def test_versions_are_append_only_and_paginated(self):
        self.assertEqual(self.review().status_code, 200)
        self.assertEqual(self.review().status_code, 409)
        self.assertEqual(self.review(expectedVersion=1, number='ДП-2').status_code, 200)
        recent = self.history('?limit=1').json()
        self.assertEqual(recent['nextBeforeVersion'], 2)
        self.assertEqual(recent['items'][0]['snapshot']['number'], 'ДП-2')
        old = self.history('?beforeVersion=2').json()
        self.assertEqual(old['items'][0]['snapshot']['number'], 'ДП-1')

    def test_payer_only_membership_cannot_read_or_review_owner_contract(self):
        self.user = {**self.user, 'id':9, 'companyId':99}
        self.assertEqual(self.history().status_code, 403)
        self.assertEqual(self.review().status_code, 403)

    def test_schema_prevents_foreign_file_and_destructive_downgrade(self):
        self.assertEqual(self.review().status_code, 200)
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                cur.execute('UPDATE supplier_contract_versions SET source_file_id=32')
            with self.assertRaises(psycopg2.errors.RaiseException):
                cur.execute(statements('downgrade')[0].replace('public.', 'pg_temp.'))

    def test_supplier_cannot_confirm_customer_requisites(self):
        self.user = {**self.user, 'role':'поставщик'}
        self.assertEqual(self.review().status_code, 403)
        with self.conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM supplier_contract_versions')
            self.assertEqual(cur.fetchone()[0], 0)

    def test_empty_migration_downgrade_and_upgrade(self):
        with self.conn.cursor() as cur:
            for statement in statements('downgrade') + statements('upgrade'):
                cur.execute(statement.replace('public.', 'pg_temp.'))
        self.assertEqual(self.review().status_code, 200)

    def test_review_context_checks_all_parties_and_returns_current_versions(self):
        response = self.contract_client.get('/supplier-offers/40/contract-review-context')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data['partyVersion'], data['expectedVersion']), (1,0))
        self.assertEqual(data['payer']['companyId'], 99)
        self.assertEqual(data['buyer']['inn'], '7701234567')
        self.assertNotIn('basis', data['buyer'])
        self.assertEqual(self.review().status_code, 200)
        self.assertEqual(self.contract_client.get('/supplier-offers/40/contract-review-context').json()['expectedVersion'], 1)

    def test_review_context_rejects_supplier_and_missing_payer_authority(self):
        with self.conn.cursor() as cur:
            cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=8 AND company_id=99')
        self.assertEqual(self.contract_client.get('/supplier-offers/40/contract-review-context').status_code, 403)
        self.user = {**self.user, 'role':'поставщик'}
        self.assertEqual(self.contract_client.get('/supplier-offers/40/contract-review-context').status_code, 403)

    def test_review_context_requires_configured_parties_and_legal_identity(self):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE company_requisites SET inn='' WHERE company_id=99")
        self.assertEqual(self.contract_client.get('/supplier-offers/40/contract-review-context').status_code, 409)
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM supplier_deal_parties')
        self.assertEqual(self.contract_client.get('/supplier-offers/40/contract-review-context').status_code, 409)
