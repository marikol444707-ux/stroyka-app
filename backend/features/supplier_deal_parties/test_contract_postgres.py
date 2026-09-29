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


def statements(method, filename='0043_supplier_contract_versions.py'):
    path = Path(__file__).resolve().parents[3] / 'migrations/versions' / filename
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
            for statement in statements('upgrade') + statements('upgrade','0064_supplier_contract_registry.py') + statements('upgrade','0065_contract_archive.py') + statements('upgrade','0066_contract_publications.py'):
                cur.execute(statement.replace('public.', 'pg_temp.'))
        # Historical split-payer contract fixture: new API requests cannot create it.
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO supplier_deal_parties
                (offer_id,company_id,request_id,supplier_id,buyer_company_id,payer_company_id,
                 version,reason,created_by_id,created_by)
                VALUES (40,12,20,5,12,99,1,'Historical fixture',8,'Test')""")
        app = FastAPI()
        register_supplier_contracts_module(app, self.deps)
        self.contract_client = TestClient(app)

    def review(self, **changes):
        return self.contract_client.post('/supplier-offers/40/contracts', json={**payload(), **changes})

    def history(self, query=''):
        return self.contract_client.get('/supplier-offers/40/contracts' + query)

    def test_reviewed_original_reused_for_second_offer_without_new_file(self):
        applicability={'scope':'company','term':'open_ended','startsOn':'2020-01-01','projectId':None,'endsOn':None}
        original = self.review(applicability=applicability)
        self.assertEqual(original.status_code, 200, original.text)
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO supplier_offers VALUES (41,12,20,5,'Утверждено')")
            cur.execute("""INSERT INTO supplier_deal_parties
                (offer_id,company_id,request_id,supplier_id,buyer_company_id,payer_company_id,
                 version,reason,created_by_id,created_by)
                VALUES (41,12,20,5,12,99,1,'Historical pair',8,'Test')""")
            cur.execute('SELECT COUNT(*) FROM file_ownership')
            before_files = cur.fetchone()[0]
        context = self.contract_client.get('/supplier-offers/41/contract-review-context')
        self.assertEqual(context.status_code, 200, context.text)
        candidates = context.json()['reusableContracts']
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['sourceFileId'], 31)
        for change in ({'reusedFromContractId': 999999},
                       {'reusedFromContractId': original.json()['id'], 'sourceFileId': 35}):
            rejected = self.contract_client.post('/supplier-offers/41/contracts', json={**payload(), **change})
            self.assertEqual(rejected.status_code, 409, rejected.text)
        saved = self.contract_client.post('/supplier-offers/41/contracts', json={**payload(), 'applicability':applicability, 'reusedFromContractId':original.json()['id']})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['sourceFileId'], original.json()['sourceFileId'])
        self.assertEqual(saved.json()['snapshot']['reusedFrom']['contractId'], original.json()['id'])
        self.assertEqual(saved.json()['snapshot']['reusedFrom']['snapshotHash'], original.json()['snapshotHash'])
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM file_ownership')
            self.assertEqual(cur.fetchone()[0], before_files)
            cur.execute("UPDATE file_ownership SET deletion_status='deleting' WHERE id=31")
        self.assertEqual(self.contract_client.get('/supplier-offers/41/contract-review-context').json()['reusableContracts'], [])

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
            for statement in (statements('downgrade','0066_contract_publications.py') + statements('downgrade','0065_contract_archive.py') + statements('downgrade','0064_supplier_contract_registry.py') + statements('downgrade')
                              + statements('upgrade') + statements('upgrade','0064_supplier_contract_registry.py') + statements('upgrade','0065_contract_archive.py') + statements('upgrade','0066_contract_publications.py')):
                cur.execute(statement.replace('public.', 'pg_temp.'))
        self.assertEqual(self.review().status_code, 200)

    def test_review_context_checks_all_parties_and_returns_current_versions(self):
        response = self.contract_client.get('/supplier-offers/40/contract-review-context')
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data['partyVersion'], data['expectedVersion']), (1,0))
        self.assertEqual(data['payer']['companyId'], 99)
        self.assertEqual(data['buyer']['inn'], '7701234567')
        self.assertEqual(data['buyer']['basis'], '')
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

    def test_new_unified_deal_rejects_conflicting_bank_and_freezes_snapshot(self):
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM supplier_deal_parties')
        self.assertEqual(self.put(payer=99).status_code, 409)
        self.assertEqual(self.put(payer=12).status_code, 200)
        buyer = {**payload()['buyer'], 'bankName':'Original bank'}
        conflict = {**buyer, 'bankName':'Other bank'}
        self.assertEqual(self.review(buyer=buyer, payer=conflict).status_code, 409)
        response = self.review(buyer=buyer, payer=buyer)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        with self.conn.cursor() as cur:
            cur.execute("UPDATE company_requisites SET full_name='Updated company' WHERE company_id=12")
        history = self.contract_client.get('/supplier-offers/40/contracts').json()['items']
        self.assertEqual(history[0]['snapshot'], saved['snapshot'])
        self.assertEqual(history[0]['snapshot']['buyer']['bankName'], 'Original bank')

    def second_offer(self):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO supplier_offers VALUES (41,12,20,5,'Утверждено')")
            cur.execute("""INSERT INTO supplier_deal_parties
                (offer_id,company_id,request_id,supplier_id,buyer_company_id,payer_company_id,
                 version,reason,created_by_id,created_by)
                VALUES (41,12,20,5,12,99,1,'Historical pair',8,'Test')""")

    def test_project_original_reusable_only_for_exact_scope_and_dates_immutable(self):
        applicability={'scope':'project','projectId':44,'term':'open_ended','startsOn':'2020-01-01','endsOn':None}
        first=self.review(sourceFileId=35,applicability=applicability)
        self.assertEqual(first.status_code,200,first.text)
        self.second_offer()
        context=self.contract_client.get('/supplier-offers/41/contract-review-context').json()
        self.assertEqual(context['project']['id'],44)
        self.assertEqual(len(context['reusableContracts']),1)
        body={**payload(),'sourceFileId':35,'applicability':applicability,'reusedFromContractId':first.json()['id']}
        for change in ({'projectId':45},{'startsOn':'2020-02-01'}):
            rejected=self.contract_client.post('/supplier-offers/41/contracts',json={**body,'applicability':{**applicability,**change}})
            self.assertEqual(rejected.status_code,422,rejected.text)
        saved=self.contract_client.post('/supplier-offers/41/contracts',json=body)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(saved.json()['snapshot']['applicability'],applicability)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE supply_requests SET project='Other object' WHERE id=20")
        self.assertEqual(self.contract_client.get('/supplier-offers/41/contract-review-context').json()['reusableContracts'],[])
        self.assertEqual(self.history().json()['items'][0]['snapshot']['applicability'],applicability)

    def test_expired_and_unknown_contracts_not_reused(self):
        expired={'scope':'company','term':'fixed','startsOn':'2020-01-01','endsOn':'2020-01-02','projectId':None}
        original=self.review(applicability=expired)
        self.assertEqual(original.status_code,200,original.text)
        self.second_offer()
        self.assertEqual(self.contract_client.get('/supplier-offers/41/contract-review-context').json()['reusableContracts'],[])
        rejected=self.contract_client.post('/supplier-offers/41/contracts',json={**payload(),'applicability':expired,'reusedFromContractId':original.json()['id']})
        self.assertEqual(rejected.status_code,422,rejected.text)
        unknown=self.review(expectedVersion=1)
        self.assertEqual(unknown.status_code,200,unknown.text)
        self.assertNotIn('applicability',unknown.json()['snapshot'])
        self.assertEqual(self.contract_client.get('/supplier-offers/41/contract-review-context').json()['reusableContracts'],[])

    def test_project_scope_rejects_foreign_ambiguous_and_company_scope_file(self):
        base={'scope':'project','projectId':45,'term':'open_ended','startsOn':'2020-01-01'}
        self.assertEqual(self.review(applicability=base).status_code,422)
        self.assertEqual(self.review(sourceFileId=35,applicability={**base,'scope':'company','projectId':None}).status_code,422)
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO projects VALUES (46,12,'Object A')")
        self.assertEqual(self.review(applicability={**base,'projectId':44}).status_code,422)

    def test_existing_original_can_be_reviewed_without_upload(self):
        original=self.review()
        self.assertEqual(original.status_code,200,original.text)
        context=self.contract_client.get('/supplier-offers/40/contract-review-context').json()
        self.assertEqual(context['existingOriginal']['sourceFileId'],31)
        self.assertIsNone(context['existingOriginal']['applicability'])
        conditions={'scope':'company','term':'open_ended','startsOn':'2020-01-01'}
        saved=self.review(expectedVersion=1,applicability=conditions,revisesContractId=original.json()['id'])
        self.assertEqual(saved.status_code,200,saved.text)
        history=self.history().json()['items']
        self.assertEqual(len(history),2)
        self.assertNotIn('applicability',history[1]['snapshot'])
        self.assertEqual(history[0]['sourceFileId'],history[1]['sourceFileId'])
        with self.conn.cursor() as cur:
            cur.execute("UPDATE file_ownership SET deletion_status='deleting' WHERE id=31")
        self.assertIsNone(self.contract_client.get('/supplier-offers/40/contract-review-context').json()['existingOriginal'])

    def test_registry_groups_explicit_reuse_and_revision_and_rejects_stale_source(self):
        conditions={'scope':'company','term':'open_ended','startsOn':'2020-01-01','projectId':None,'endsOn':None}
        first=self.review(applicability=conditions).json()
        self.second_offer()
        second=self.contract_client.post('/supplier-offers/41/contracts',json={**payload(),'applicability':conditions,'reusedFromContractId':first['id']})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json()['registryId'],first['registryId'])
        third=self.contract_client.post('/supplier-offers/41/contracts',json={**payload(),'expectedVersion':1,'applicability':conditions,'revisesContractId':second.json()['id']})
        self.assertEqual(third.status_code,200,third.text)
        self.assertEqual(third.json()['registryId'],first['registryId'])
        self.assertEqual(third.json()['snapshot']['revises']['contractId'],second.json()['id'])
        stale=self.review(expectedVersion=1,applicability=conditions,revisesContractId=first['id'])
        self.assertEqual(stale.status_code,422,stale.text)
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_contract_registry')
            self.assertEqual(cur.fetchone()[0],1)
            cur.execute('SELECT COUNT(*) FROM supplier_contract_registry_versions')
            self.assertEqual(cur.fetchone()[0],3)
            cur.execute('SELECT COUNT(*) FROM supplier_contract_versions')
            self.assertEqual(cur.fetchone()[0],3)
        # The latest global version is offered, not an older copy from another CP.
        candidates=self.contract_client.get('/supplier-offers/40/contract-review-context').json()['reusableContracts']
        self.assertEqual([c['id'] for c in candidates],[third.json()['id']])

    def test_same_number_does_not_implicitly_merge_contracts(self):
        first=self.review().json()
        second=self.review(expectedVersion=1).json()
        self.assertNotEqual(first['registryId'],second['registryId'])
        self.assertEqual(first['snapshot']['number'],second['snapshot']['number'])

    def test_registry_constraints_and_downgrade_protect_history(self):
        first=self.review().json()
        with self.conn.cursor() as cur:
            with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                cur.execute('UPDATE supplier_contract_registry_versions SET company_id=99')
            with self.assertRaises(psycopg2.errors.RaiseException):
                cur.execute(statements('downgrade','0064_supplier_contract_registry.py')[0].replace('public.','pg_temp.'))
        rejected=self.review(expectedVersion=1,revisesContractId=999999)
        self.assertEqual(rejected.status_code,422)
        self.assertEqual(self.history().json()['items'][0]['registryId'],first['registryId'])

    def test_legacy_source_is_linked_only_on_explicit_review(self):
        first=self.review().json()
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM supplier_contract_registry_versions')
            cur.execute('DELETE FROM supplier_contract_registry')
        revised=self.review(expectedVersion=1,revisesContractId=first['id'])
        self.assertEqual(revised.status_code,200,revised.text)
        history=self.history().json()['items']
        self.assertEqual(history[0]['registryId'],history[1]['registryId'])
        self.assertEqual(history[1]['snapshot'],first['snapshot'])

    def archive_client(self):
        from ..counterparty_documents.contract_archive import register_contract_archive
        from ..company_context.service import resolve_request_company_context, effective_company_actors
        app=FastAPI()
        register_contract_archive(app,{**self.deps,
            'resolve_work_company_context':resolve_request_company_context,
            'effective_company_actors':effective_company_actors})
        return TestClient(app)

    def test_archive_restore_preserves_snapshots_and_blocks_stale_review(self):
        conditions={'scope':'company','term':'open_ended','startsOn':'2020-01-01'}
        first=self.review(applicability=conditions).json()
        self.second_offer()
        with self.conn.cursor() as cur:
            cur.execute("UPDATE user_company_roles SET role='директор' WHERE user_id=8 AND company_id=12")
        client=self.archive_client()
        url=f"/supplier-contract-registry/{first['registryId']}/archive"
        headers={'X-Company-Id':'12','X-Company-Mode':'company'}
        archived=client.put(url,headers=headers,json={'archived':True,'expectedVersion':0})
        self.assertEqual(archived.status_code,200,archived.text)
        self.assertEqual(archived.json()['stateVersion'],1)
        self.assertEqual(self.history().json()['items'][0],first)
        context=self.contract_client.get('/supplier-offers/41/contract-review-context').json()
        self.assertEqual(context['reusableContracts'],[])
        self.assertTrue(self.contract_client.get('/supplier-offers/40/contract-review-context').json()['existingOriginal']['archived'])
        rejected=self.review(expectedVersion=1,revisesContractId=first['id'])
        self.assertEqual(rejected.status_code,422,rejected.text)
        rejected=self.contract_client.post('/supplier-offers/41/contracts',json={**payload(),'applicability':conditions,'reusedFromContractId':first['id']})
        self.assertEqual(rejected.status_code,422,rejected.text)
        self.assertEqual(len(self.history().json()['items']),1)
        # An uncertain/repeated old command never reverses a newer decision.
        self.assertEqual(client.put(url,headers=headers,json={'archived':False,'expectedVersion':0}).status_code,409)
        self.assertEqual(client.put(url,headers=headers,json={'archived':False,'expectedVersion':1}).status_code,200)
        self.assertEqual(client.put(url,headers=headers,json={'archived':True,'expectedVersion':0}).status_code,409)
        self.assertEqual(len(self.contract_client.get('/supplier-offers/41/contract-review-context').json()['reusableContracts']),1)
        with self.conn.cursor() as cur:
            cur.execute('SELECT version,archived,actor_id,company_id FROM supplier_contract_registry_events ORDER BY version')
            self.assertEqual(cur.fetchall(),[(1,True,8,12),(2,False,8,12)])
            with self.assertRaises(psycopg2.errors.RaiseException):
                cur.execute(statements('downgrade','0065_contract_archive.py')[0].replace('public.','pg_temp.'))

    def test_archive_checks_effective_role_owner_and_input(self):
        first=self.review().json()
        client=self.archive_client()
        url=f"/supplier-contract-registry/{first['registryId']}/archive"
        body={'archived':True,'expectedVersion':0}
        self.assertEqual(client.put(url,json=body).status_code,403)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE user_company_roles SET role='директор' WHERE user_id=8")
        self.assertEqual(client.put(url,headers={'X-Company-Id':'99'},json=body).status_code,404)
        self.assertEqual(client.put(url,headers={'X-Company-Id':'101'},json=body).status_code,403)
        self.assertEqual(client.put(url,headers={'X-Company-Mode':'all_companies'},json=body).status_code,400)
        for invalid in ({**body,'expectedVersion':True},{**body,'archived':'true'},{**body,'extra':1}):
            self.assertEqual(client.put(url,json=invalid).status_code,422)
        with self.conn.cursor() as cur:
            cur.execute('SELECT archived,state_version FROM supplier_contract_registry')
            self.assertEqual(cur.fetchone(),(False,0))
            cur.execute('SELECT COUNT(*) FROM supplier_contract_registry_events')
            self.assertEqual(cur.fetchone()[0],0)

    def test_addendum_creates_new_snapshot_keeps_original_and_reuses_full_chain(self):
        conditions={'scope':'company','term':'open_ended','startsOn':'2020-01-01'}
        first=self.review(applicability=conditions).json()
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO file_ownership (id,company_id) VALUES (36,12),(37,12)")
        supplement={'sourceFileId':36,'number':'1','date':'2026-09-20'}
        second=self.review(expectedVersion=1,revisesContractId=first['id'],addendum=supplement,applicability=conditions)
        self.assertEqual(second.status_code,200,second.text)
        second=second.json()
        self.assertEqual(second['sourceFileId'],31)
        self.assertEqual(second['registryId'],first['registryId'])
        self.assertEqual(second['snapshot']['addenda'],[supplement])
        third=self.review(expectedVersion=2,revisesContractId=second['id'],addendum={**supplement,'sourceFileId':37,'number':'2'},applicability=conditions)
        self.assertEqual(third.status_code,200,third.text)
        self.assertEqual(len(third.json()['snapshot']['addenda']),2)
        self.assertEqual(self.history().json()['items'][-1],first)
        self.second_offer()
        reused=self.contract_client.post('/supplier-offers/41/contracts',json={**payload(),'applicability':conditions,'reusedFromContractId':third.json()['id']})
        self.assertEqual(reused.status_code,200,reused.text)
        self.assertEqual(reused.json()['snapshot']['addenda'],third.json()['snapshot']['addenda'])
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM file_ownership WHERE id IN (31,36,37) AND retained_at IS NOT NULL')
            self.assertEqual(cur.fetchone()[0],3)

    def test_addendum_rejects_foreign_project_duplicate_and_stale_files_atomically(self):
        first=self.review().json()
        supplement={'sourceFileId':32,'number':'1','date':'2026-09-20'}
        for file_id,code in ((32,403),(33,422),(34,403),(31,422),(99999,403)):
            response=self.review(expectedVersion=1,revisesContractId=first['id'],addendum={**supplement,'sourceFileId':file_id})
            self.assertEqual(response.status_code,code,response.text)
        self.assertEqual(self.review(expectedVersion=1,addendum=supplement).status_code,422)
        self.assertEqual(self.review(expectedVersion=1,revisesContractId=first['id'],number='OTHER',addendum=supplement).status_code,422)
        self.assertEqual(self.review(expectedVersion=1,revisesContractId=first['id'],addendum={**supplement,'date':'2020-01-01'}).status_code,422)
        self.assertEqual(self.history().json()['items'],[first])
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM file_ownership WHERE id<>31 AND retained_at IS NOT NULL')
            self.assertEqual(cur.fetchone()[0],0)

    def test_addendum_preserves_existing_payment_schedule(self):
        schedule={'schemaVersion':1,'stages':[{'title':'Оплата','percentBasisPoints':10000,'event':'after_acceptance','daysAfter':5}]}
        with patch.dict(os.environ,{'SUPPLIER_PAYMENT_SCHEDULES_ENABLED':'1','SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED':'1'}):
            response=self.review(paymentSchedule=schedule)
        self.assertEqual(response.status_code,200,response.text)
        first=response.json()
        with self.conn.cursor() as cur:
            cur.execute('INSERT INTO file_ownership (id,company_id) VALUES (36,12)')
        response=self.review(expectedVersion=1,revisesContractId=first['id'],addendum={'sourceFileId':36,'number':'1','date':'2026-09-20'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['snapshot']['paymentSchedule'],schedule)
        self.assertEqual(self.history().json()['items'][-1],first)

    def publication_scope(self):
        with self.conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE supplier_invoices (id INT,company_id INT,offer_id INT,supplier_id INT,contract_version_id BIGINT)')
            cur.execute('ALTER TABLE suppliers ADD COLUMN user_id INT')
            cur.execute('UPDATE suppliers SET user_id=13')
            cur.execute('CREATE TEMP TABLE users (id INT,role TEXT,active BOOLEAN)')
            cur.execute("INSERT INTO users VALUES (13,'поставщик',TRUE),(14,'поставщик',TRUE),(15,'поставщик',TRUE)")
            cur.execute('CREATE TEMP TABLE supplier_team_members (id INT,supplier_id INT,user_id INT,active BOOLEAN,role TEXT)')
            cur.execute("INSERT INTO supplier_team_members VALUES (1,5,14,TRUE,'manager')")
            cur.execute('CREATE TEMP TABLE supplier_customer_assignments (supplier_id INT,company_id INT,member_id INT)')
            cur.execute('INSERT INTO supplier_customer_assignments VALUES (5,12,1)')
            cur.execute('ALTER TABLE supply_requests ADD COLUMN prorab_confirmed_at TIMESTAMPTZ, ADD COLUMN director_approved_at TIMESTAMPTZ, ADD COLUMN selected_suppliers INT[]')
            cur.execute('UPDATE supply_requests SET prorab_confirmed_at=NOW(),director_approved_at=NOW(),selected_suppliers=ARRAY[5]')
            cur.execute('CREATE TEMP TABLE supply_request_recipients (request_id INT,company_id INT,visible_to_supplier BOOLEAN,target_supplier_id INT,supplier_id INT,supplier_group_ids INT[],supplier_user_id INT)')
        self.deps['current_supplier_ids']=lambda cur,user:[6] if user['id']==15 else [5]
        flags=patch.dict(os.environ,{'SUPPLIER_TEAM_ENABLED':'1','SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED':'1'})
        flags.start();self.addCleanup(flags.stop)

    def test_supplier_publication_version_files_and_manager_revocation(self):
        from ..supplier_access.contract_files import supplier_contract_file_visible
        self.publication_scope()
        first=self.review().json()
        with self.conn.cursor() as cur:
            cur.execute('INSERT INTO file_ownership (id,company_id) VALUES (36,12)')
        second=self.review(expectedVersion=1,revisesContractId=first['id'],addendum={'sourceFileId':36,'number':'1','date':'2026-09-20'}).json()
        publisher=dict(self.user)
        def file_visible(file_id):
            with self.conn.cursor() as cur:
                return supplier_contract_file_visible(cur,self.user,{'id':file_id,'company_id':12,'project_id':None},self.deps['current_supplier_ids'](cur,self.user))
        self.user={'id':14,'role':'поставщик'}
        self.assertEqual([r['id'] for r in self.history().json()['items']],[second['id'],first['id']])
        self.assertTrue(file_visible(31));self.assertTrue(file_visible(36))
        self.assertEqual(self.contract_client.post(f"/supplier-offers/40/contracts/{second['id']}/publish",json={'confirmed':True}).status_code,403)
        self.user=publisher
        path=f"/supplier-offers/40/contracts/{second['id']}/publish"
        self.assertEqual(self.contract_client.post(path,json={'confirmed':False}).status_code,422)
        self.assertEqual(self.contract_client.post(path,headers={'X-Company-Id':'99'},json={'confirmed':True}).status_code,409)
        for _ in range(2):
            response=self.contract_client.post(path,json={'confirmed':True})
            self.assertEqual(response.status_code,200,response.text)
        self.user={'id':14,'role':'поставщик'}
        self.assertEqual([r['id'] for r in self.history().json()['items']],[second['id'],first['id']])
        self.assertTrue(file_visible(31));self.assertTrue(file_visible(36));self.assertFalse(file_visible(32))
        self.user=publisher
        third=self.review(expectedVersion=2,revisesContractId=second['id']).json()
        self.user={'id':14,'role':'поставщик'}
        self.assertEqual([r['id'] for r in self.history().json()['items']],[third['id'],second['id'],first['id']])
        with self.conn.cursor() as cur:
            cur.execute('DELETE FROM supplier_customer_assignments')
        self.assertEqual(self.history().status_code,403)
        self.assertFalse(file_visible(31));self.assertFalse(file_visible(36))
        self.user={'id':13,'role':'поставщик'}
        self.assertTrue(file_visible(36))
        self.user={'id':15,'role':'поставщик'}
        self.assertFalse(file_visible(36))
        self.assertEqual(self.history().status_code,403)
        self.user=publisher
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_contract_publications')
            self.assertEqual(cur.fetchone()[0],1)
            with self.assertRaises(psycopg2.errors.RaiseException):
                cur.execute(statements('downgrade','0066_contract_publications.py')[0].replace('public.','pg_temp.'))

    def test_bound_invoice_keeps_exact_contract_available_without_publication(self):
        self.publication_scope()
        first=self.review().json()
        second=self.review(expectedVersion=1).json()
        with self.conn.cursor() as cur:
            cur.execute('INSERT INTO supplier_invoices VALUES (1,12,40,5,%s)',(first['id'],))
        self.user={'id':13,'role':'поставщик'}
        self.assertEqual([r['id'] for r in self.history().json()['items']],[second['id'],first['id']])
        with self.conn.cursor() as cur:
            cur.execute('UPDATE supplier_invoices SET company_id=99')
        self.assertEqual([r['id'] for r in self.history().json()['items']],[second['id'],first['id']])

    def test_publication_rejects_archived_stale_and_unavailable_original(self):
        first=self.review().json()
        second=self.review(expectedVersion=1,revisesContractId=first['id']).json()
        path=lambda row:f"/supplier-offers/40/contracts/{row['id']}/publish"
        self.assertEqual(self.contract_client.post(path(first),json={'confirmed':True}).status_code,409)
        with self.conn.cursor() as cur:
            cur.execute('UPDATE supplier_contract_registry SET archived=TRUE')
        self.assertEqual(self.contract_client.post(path(second),json={'confirmed':True}).status_code,422)
        with self.conn.cursor() as cur:
            cur.execute('UPDATE supplier_contract_registry SET archived=FALSE')
            cur.execute("UPDATE file_ownership SET deletion_status='deleting' WHERE id=31")
        self.assertEqual(self.contract_client.post(path(second),json={'confirmed':True}).status_code,403)
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM supplier_contract_publications')
            self.assertEqual(cur.fetchone()[0],0)

    def test_publication_cannot_follow_offer_reassigned_to_another_supplier(self):
        from .publication import supplier_version_visible
        self.publication_scope()
        first=self.review().json()
        response=self.contract_client.post(f"/supplier-offers/40/contracts/{first['id']}/publish",json={'confirmed':True})
        self.assertEqual(response.status_code,200,response.text)
        with self.conn.cursor() as cur:
            cur.execute('SELECT v.id FROM supplier_contract_versions v WHERE '+supplier_version_visible('v'))
            self.assertEqual(cur.fetchall(),[(first['id'],)])
            with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                cur.execute('UPDATE supplier_offers SET supplier_id=6')
            # Deliberately corrupt only the temporary fixture to exercise read defense.
            cur.execute('ALTER TABLE supplier_deal_parties DROP CONSTRAINT fk_supplier_deal_parties_offer')
            cur.execute('UPDATE supplier_offers SET supplier_id=6')
            cur.execute('SELECT v.id FROM supplier_contract_versions v WHERE '+supplier_version_visible('v'))
            self.assertEqual(cur.fetchall(),[])
