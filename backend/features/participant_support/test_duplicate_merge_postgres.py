"""Company-local admin consolidation on disposable PostgreSQL."""
import importlib
import os
import unittest
from unittest.mock import patch
from .test_postgres import ParticipantSupportPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class AdminDuplicateMergePostgresTests(unittest.TestCase):
    sql,api,seed=Base.sql,Base.api,Base.seed

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)
        for migration in ('0038_supplier_customer_team','0095_supplier_buyer_connections','0096_supplier_history_merge_plans'):
            cls.sql(cls,importlib.import_module('migrations.versions.'+migration).SCHEMA_SQL)

    def duplicate_review(self, source, target, **kwargs):
        return self.api('admin','POST',f'/system/companies/2/participants/{source}/duplicate-preview',
                        {'targetSupplierId':target},**kwargs)

    def duplicate_confirm(self, source, review, **kwargs):
        return self.api('admin','POST',f'/system/companies/2/participants/{source}/duplicate-merge',
                        {'targetSupplierId':review['targetId'],'expectedReview':review['reviewVersion'],
                         'confirmed':True,'reason':'Проверены исходные документы поставщика'},**kwargs)

    def test_admin_duplicate_merge_preserves_invoice_and_requires_current_review(self):
        source,target=self.seed(),self.seed()
        invoice=self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,200,50) RETURNING id",(source,))[0][0]
        before=self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s',(invoice,))
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            review=self.duplicate_review(source,target)
            self.assertEqual(review['documents']['supplier_invoices'],1)
            self.assertTrue(self.duplicate_confirm(source,review)['ok'])
            self.duplicate_confirm(source,review,expected=409)
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s',(invoice,)),before)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.sql("SELECT profile->>'mergedIntoSupplierId' FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s",(source,)),[(str(target),)])
        self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_cards_merged' AND entity_id=%s AND company_id=2",(source,)),[(1,)])

    def test_admin_duplicate_merge_cannot_bypass_registered_history_flow(self):
        source,target=self.seed(),self.seed(owned=True)
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            review=self.duplicate_review(source,target)
            self.assertTrue(review['hasSupplierAccount'])
            self.duplicate_confirm(source,review,expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_admin_duplicate_merge_rechecks_scope_identity_and_freshness(self):
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            source,target=self.seed(),self.seed()
            review=self.duplicate_review(source,target)
            self.sql('UPDATE company_supplier_links SET version=version+1 WHERE supplier_id=%s',(source,))
            self.duplicate_confirm(source,review,expected=409)
            self.sql("UPDATE suppliers SET inn='2635045921' WHERE id=%s",(source,))
            self.sql("UPDATE suppliers SET inn='2312254452' WHERE id=%s",(target,))
            self.duplicate_review(source,target,expected=409)
            self.duplicate_review(self.seed(shared=True),self.seed(),expected=409)
            foreign=self.sql("INSERT INTO suppliers(name) VALUES('Foreign') RETURNING id")[0][0]
            self.duplicate_review(self.seed(),foreign,expected=404)
            self.api('director','POST',f'/system/companies/2/participants/{source}/duplicate-preview',{'targetSupplierId':target},expected=403)
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='0'):
            self.duplicate_review(source,target,expected=503)

    def test_changed_document_count_and_new_cabinet_require_new_review(self):
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            source,target=self.seed(),self.seed()
            review=self.duplicate_review(source,target)
            self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,100,0)',(source,))
            self.duplicate_confirm(source,review,expected=409)
            review=self.duplicate_review(source,target)
            self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(self.fixture['users']['supplier']['id'],target))
            self.duplicate_confirm(source,review,expected=409)
            self.assertEqual(self.sql("SELECT profile->>'mergedIntoSupplierId' FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s",(source,)),[(None,)])

    def test_database_role_revocation_rejects_an_old_admin_token(self):
        source,target=self.seed(),self.seed()
        from fastapi.testclient import TestClient
        user=self.fixture['users']['admin']
        token=self.main.create_auth_token(user,two_factor_passed=True)
        self.sql("UPDATE users SET role='мастер' WHERE id=%s",(user['id'],))
        try:
            with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'),TestClient(self.main.app) as client:
                result=client.post(f'/system/companies/2/participants/{source}/duplicate-preview',
                    json={'targetSupplierId':target},headers={'Authorization':'Bearer '+token})
                self.assertIn(result.status_code,(401,403),result.text)
        finally:
            self.sql("UPDATE users SET role='system_owner' WHERE id=%s",(user['id'],))

    def test_two_confirmations_apply_once_and_audit_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from fastapi.testclient import TestClient
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            source,target=self.seed(),self.seed()
            review=self.duplicate_review(source,target)
            token=self.main.create_auth_token(self.fixture['users']['admin'],two_factor_passed=True)
            def send(_):
                with TestClient(self.main.app) as client:
                    return client.post(f'/system/companies/2/participants/{source}/duplicate-merge',
                        json=dict(targetSupplierId=target,expectedReview=review['reviewVersion'],confirmed=True,reason='Сверены исходные документы'),
                        headers={'Authorization':'Bearer '+token}).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(send,range(2))),[200,409])
            self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_cards_merged' AND entity_id=%s AND company_id=2",(source,)),[(1,)])

    def complete_inn(self,source,review,**kwargs):
        return self.api('admin','POST',f'/system/companies/2/participants/{source}/duplicate-complete-inn',
                        dict(targetSupplierId=review['targetId'],expectedReview=review['reviewVersion'],confirmed=True,
                             reason='ИНН подтверждён по счёту зарегистрированного кабинета'),**kwargs)

    def test_missing_cabinet_inn_can_be_confirmed_without_granting_history(self):
        source,target=self.seed(),self.seed(owned=True)
        self.sql("UPDATE suppliers SET inn='2312254452' WHERE id=%s",(source,))
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            review=self.duplicate_review(source,target)
            self.assertTrue(review['canCompleteInn'])
            before=self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,))
            self.assertTrue(self.complete_inn(source,review)['ok'])
            self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),before)
            self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s',(target,)),[('2312254452',)])
            self.assertEqual(self.sql("SELECT count(*) FROM audit_log WHERE action='supplier_missing_inn_completed' AND entity_id=%s",(target,)),[(1,)])
            self.complete_inn(source,review,expected=409)

    def test_missing_inn_completion_rejects_changes_and_shared_target(self):
        with patch.dict(os.environ,PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            source,target=self.seed(),self.seed(owned=True)
            self.sql("UPDATE suppliers SET inn='2312254452' WHERE id=%s",(source,))
            review=self.duplicate_review(source,target)
            self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(3,%s,1)',(target,))
            self.complete_inn(source,review,expected=409)
            self.sql('DELETE FROM company_supplier_links WHERE company_id=3 AND supplier_id=%s',(target,))
            review=self.duplicate_review(source,target)
            self.sql("UPDATE suppliers SET inn='2635045921' WHERE id=%s",(target,))
            self.complete_inn(source,review,expected=409)
            self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s',(target,)),[('2635045921',)])

    def test_formatted_inn_completion_checks_all_existing_cabinets(self):
        from secrets import randbelow
        inn = '71' + str(randbelow(10**8)).zfill(8)
        source, target, competitor = self.seed(), self.seed(owned=True), self.seed(owned=True)
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, source))
        formatted = inn[:2] + '- ' + inn[2:]
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (formatted, competitor))
        with patch.dict(os.environ, PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            review = self.duplicate_review(source, target)
            self.complete_inn(source, review, expected=409)
        self.assertEqual(self.sql("SELECT COALESCE(inn,'') FROM suppliers WHERE id=%s", (target,)), [('',)])
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (competitor,)), [(formatted,)])

    def test_formatted_source_can_complete_without_rewriting_source_or_documents(self):
        from secrets import randbelow
        inn = '72' + str(randbelow(10**8)).zfill(8)
        source, target = self.seed(), self.seed(owned=True)
        formatted = inn[:3] + '\u00a0-' + inn[3:]
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (formatted, source))
        invoice = self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,500,123) RETURNING id', (source,))[0][0]
        before = self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,))
        with patch.dict(os.environ, PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            review = self.duplicate_review(source, target)
            self.assertTrue(review['canCompleteInn'])
            self.complete_inn(source, review)
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (target,)), [(inn,)])
        self.assertEqual(self.sql('SELECT inn,user_id FROM suppliers WHERE id=%s', (source,)), [(formatted, None)])
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,)), before)

    def test_concurrent_profile_write_and_completion_create_only_one_cabinet_identity(self):
        from secrets import randbelow
        from concurrent.futures import ThreadPoolExecutor
        from fastapi.testclient import TestClient
        inn = '73' + str(randbelow(10**8)).zfill(8)
        source, target, competitor = self.seed(), self.seed(owned=True), self.seed(owned=True)
        self.sql('UPDATE suppliers SET inn=%s WHERE id=%s', (inn, source))
        with patch.dict(os.environ, PARTICIPANT_HISTORY_MERGE_ENABLED='1'):
            review = self.duplicate_review(source, target)
            token = self.main.create_auth_token(self.fixture['users']['admin'], two_factor_passed=True)
            def send(operation):
                with TestClient(self.main.app) as client:
                    headers = {'Authorization': 'Bearer ' + token}
                    if operation == 'complete':
                        return client.post(f'/system/companies/2/participants/{source}/duplicate-complete-inn',
                            json=dict(targetSupplierId=target, expectedReview=review['reviewVersion'], confirmed=True,
                                      reason='ИНН проверен по исходному документу'), headers=headers).status_code
                    return client.put(f'/suppliers/{competitor}/requisites',
                                      json={'inn': inn[:2] + '-' + inn[2:]}, headers=headers).status_code
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(send, ('complete', 'profile'))), [200, 409])
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers WHERE id=ANY(%s) AND inn=%s',
                                 ([target, competitor], inn)), [(1,)])
