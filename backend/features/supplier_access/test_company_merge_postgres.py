"""Real company merge HTTP checks in a disposable database."""
import os
import unittest
from ..invite_codes import test_supplier_registration_postgres as base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CompanyMergePostgresTests(unittest.TestCase):
    sql = base.SupplierRegistrationPostgresTests.sql
    api = base.SupplierRegistrationPostgresTests.api

    @classmethod
    def setUpClass(cls):
        base.SupplierRegistrationPostgresTests.setUpClass.__func__(cls)

    def seed(self,cabinet=False):
        source = self.sql("INSERT INTO suppliers(name) VALUES('Synthetic receipt card') RETURNING id")[0][0]
        owner = self.fixture['users']['supplier']['id']
        target = self.sql("INSERT INTO suppliers(name,user_id,inn,registered_at) VALUES('Synthetic registered card',%s,'7799998877',NOW()) RETURNING id", (owner if cabinet else None,))[0][0]
        for sid in (source, target):
            self.sql("INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id,profile) VALUES(2,%s,1,'{}')", (sid,))
        invoice = self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,project_name,amount,paid_amount,status) VALUES(2,%s,%s,200,50,'На утверждении') RETURNING id", (source, self.fixture['project']))[0][0]
        return source, target, invoice, owner

    def review(self, source, target, **kwargs):
        return self.api('director', 'POST', f'/suppliers/{target}/merge-preview', {'sourceId':source,'companyId':2}, **kwargs)

    def merge(self, review, **kwargs):
        body = {key:review[key] for key in ('sourceId','targetVersion','sourceVersion')}
        return self.api('director', 'POST', f"/suppliers/{review['targetId']}/merge", {**body,'companyId':2,'confirmed':True,'expectedReview':review['reviewVersion']}, **kwargs)

    def test_preview_then_merge_without_cabinet_preserves_original_documents(self):
        source, target, invoice, owner = self.seed()
        before = self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,))
        review = self.review(source, target)
        self.assertEqual(review['documents']['supplier_invoices'], 1)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,)), [(None,)])
        self.assertTrue(self.merge(review)['ok'])
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,)), before)
        self.assertEqual(self.sql('SELECT user_id,inn FROM suppliers WHERE id=%s', (source,)), [(None,None)])
        rows = self.api('director', 'GET', '/suppliers', **{'X-Company-Id':'2'})
        for sid in (source, target):
            row = next(r for r in rows if r['id'] == sid)
            self.assertEqual(row['canonicalSupplierId'], target)
            self.assertEqual(row['relatedSupplierIds'], [source,target])
        self.merge(review, expected=409)

    def test_legacy_merge_cannot_grant_history_to_an_existing_cabinet(self):
        source,target,invoice,owner=self.seed(cabinet=True)
        self.merge(self.review(source,target),expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_changed_card_blocks_stale_confirmation(self):
        source, target, invoice, owner = self.seed()
        review = self.review(source, target)
        self.sql('UPDATE company_supplier_links SET version=version+1 WHERE supplier_id=%s', (source,))
        self.merge(review, expected=409)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,)), [(None,)])

    def test_other_company_link_or_document_blocks_without_claim(self):
        for kind in ('link','document'):
            source, target, invoice, owner = self.seed()
            if kind == 'link':
                self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(3,%s,1)', (source,))
            else:
                self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(3,%s,100,0)', (source,))
            self.review(source, target, expected=409)
            self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,)), [(None,)])

    def test_conflicting_identity_and_existing_owner_are_not_merged(self):
        source, target, invoice, owner = self.seed()
        self.sql("UPDATE suppliers SET inn='7788887766' WHERE id=%s", (source,))
        self.review(source, target, expected=409)
        self.sql('UPDATE suppliers SET inn=NULL,user_id=%s WHERE id=%s', (owner,source))
        self.review(source, target, expected=409)

    def test_foreign_actor_cannot_preview_or_merge(self):
        source, target, invoice, owner = self.seed()
        self.api('stranger','POST',f'/suppliers/{target}/merge-preview',{'sourceId':source,'companyId':2},expected=403,**{'X-Company-Id':'2'})
        self.api('foreman','POST',f'/suppliers/{target}/merge-preview',{'sourceId':source,'companyId':2},expected=403,**{'X-Company-Id':'2'})

    def test_merge_before_registration_claims_entire_history(self):
        source, target, invoice, owner = self.seed()
        self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s', (target,))
        self.merge(self.review(source, target))
        invite = self.api('director', 'POST', '/invite-codes',
                          {'role':'поставщик','supplierId':target,'expiresInDays':1},
                          **{'X-Company-Id':'2'})
        payload = base.SupplierRegistrationPostgresTests.registration(self, invite, inn='7799998877')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        new_owner = self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],))[0][0]
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=ANY(%s) ORDER BY id', ([source,target],)), [(new_owner,), (new_owner,)])
        self.assertEqual(self.sql('SELECT supplier_id,amount,paid_amount FROM supplier_invoices WHERE id=%s', (invoice,)), [(source,200,50)])
        self.client.cookies.clear()

    def test_merged_legal_key_cannot_create_another_card(self):
        source, target, invoice, owner = self.seed()
        self.sql("UPDATE suppliers SET inn='7788776655' WHERE id=%s", (source,))
        self.sql('UPDATE suppliers SET inn=NULL WHERE id=%s', (target,))
        self.merge(self.review(source, target))
        count = self.sql('SELECT count(*) FROM suppliers')
        self.api('director','POST','/suppliers',{'name':'Another receipt','inn':'7788776655'},
                 expected=409, **{'X-Company-Id':'2'})
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers'), count)

    def test_explicit_invite_cannot_claim_another_existing_legal_identity(self):
        source, target, invoice, owner = self.seed(cabinet=True)
        invite = self.api('director','POST','/invite-codes',
                          {'role':'поставщик','supplierId':source,'expiresInDays':1},
                          **{'X-Company-Id':'2'})
        payload = base.SupplierRegistrationPostgresTests.registration(self, invite, inn='7799998877')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s',(payload['email'],)),[])
        self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s',(invite['id'],)),[(False,)])

    def test_actual_receipt_card_is_invited_without_another_identity(self):
        import secrets
        name = 'Synthetic receipt to registration ' + secrets.token_hex(6)
        inn = '7799110000'
        result = self.api('director','POST','/warehouse-invoices',
                          dict(companyId=2,location='Основной склад',warehouseTarget='main',
                               supplierName=name,supplierInn=inn,number=name,date='2026-10-12',vat='Без НДС',
                               items=[dict(name=name+' material',unit='шт',quantity=2,price=100)],syncSupplierInvoice=True),
                          **{'X-Company-Id':'2'})
        self.assertNotIn('accountingWarning',result)
        supplier_id = self.sql('SELECT supplier_id FROM warehouse_invoices WHERE id=%s',(result['id'],))[0][0]
        self.assertIsNotNone(supplier_id)
        rows = self.api('director','GET','/suppliers',**{'X-Company-Id':'2'})
        self.assertIn(supplier_id,[row['id'] for row in rows])
        before = self.sql('SELECT to_jsonb(w) FROM warehouse_invoices w WHERE id=%s',(result['id'],))
        invite = self.api('director','POST','/invite-codes',{'role':'поставщик','expiresInDays':1},**{'X-Company-Id':'2'})
        payload = base.SupplierRegistrationPostgresTests.registration(self,invite,inn=inn)
        response = self.client.post('/register',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers WHERE inn=%s',(inn,)),[(1,)])
        self.assertEqual(self.sql('SELECT to_jsonb(w) FROM warehouse_invoices w WHERE id=%s',(result['id'],)),before)
        self.assertEqual(self.sql('SELECT supplier_id FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s',(supplier_id,)),[(supplier_id,)])
        self.client.cookies.clear()

    def test_simultaneous_receipt_and_signup_create_one_supplier(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from fastapi.testclient import TestClient
        import secrets
        inn = '7799220000'
        name = 'Synthetic concurrent receipt ' + secrets.token_hex(6)
        invite = self.api('director','POST','/invite-codes',{'role':'поставщик','expiresInDays':1},**{'X-Company-Id':'2'})
        payload = base.SupplierRegistrationPostgresTests.registration(self,invite,inn=inn)
        token = self.main.create_auth_token(self.fixture['users']['director'],two_factor_passed=True)
        barrier = Barrier(2)
        def request(path, body, headers=None):
            with TestClient(self.main.app) as client:
                barrier.wait(timeout=10)
                return client.post(path,json=body,headers=headers or {})
        receipt = dict(companyId=2,location='Основной склад',warehouseTarget='main',supplierName=name,supplierInn=inn,
                       number=name,date='2026-10-12',vat='Без НДС',syncSupplierInvoice=True,
                       items=[dict(name=name+' material',unit='шт',quantity=2,price=100)])
        with ThreadPoolExecutor(max_workers=2) as pool:
            signup = pool.submit(request,'/register',payload)
            delivery = pool.submit(request,'/warehouse-invoices',receipt,{'Authorization':'Bearer '+token,'X-Company-Id':'2'})
            signup_result, delivery_result = signup.result(timeout=30), delivery.result(timeout=30)
        self.assertEqual(signup_result.status_code,200,signup_result.text)
        self.assertEqual(delivery_result.status_code,200,delivery_result.text)
        self.assertNotIn('accountingWarning',delivery_result.json())
        rows = self.sql('SELECT id,user_id FROM suppliers WHERE inn=%s',(inn,))
        self.assertEqual(len(rows),1)
        self.assertIsNotNone(rows[0][1])
        self.assertEqual(self.sql('SELECT supplier_id FROM warehouse_invoices WHERE id=%s',(delivery_result.json()['id'],)),[(rows[0][0],)])

    def test_preview_fingerprint_required_and_same_count_document_edit_rejected(self):
        source, target, invoice, owner = self.seed()
        review = self.review(source, target)
        body = {key: review[key] for key in ('sourceId', 'targetVersion', 'sourceVersion')}
        self.api('director', 'POST', f'/suppliers/{target}/merge',
                 {**body, 'companyId': 2, 'confirmed': True}, expected=409)
        self.sql('UPDATE supplier_invoices SET amount=201 WHERE id=%s', (invoice,))
        self.merge(review, expected=409)
        self.assertEqual(self.sql("SELECT profile->>'mergedIntoSupplierId' FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s", (source,)), [(None,)])
        self.assertTrue(self.merge(self.review(source, target))['ok'])

    def test_invite_created_before_merge_follows_canonical_without_rewriting_invoice(self):
        source, target, invoice, owner = self.seed()
        self.sql("UPDATE suppliers SET inn='7799400001' WHERE id=%s", (source,))
        self.sql('UPDATE suppliers SET inn=NULL WHERE id=%s', (target,))
        invite = self.api('director', 'POST', '/invite-codes',
                          {'role': 'поставщик', 'supplierId': source}, **{'X-Company-Id': '2'})
        before = self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,))
        self.merge(self.review(source, target))
        payload = base.SupplierRegistrationPostgresTests.registration(self, invite, inn='7799400001')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        new_owner = self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],))[0][0]
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=ANY(%s) ORDER BY id', ([source, target],)), [(new_owner,), (new_owner,)])
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,)), before)
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers WHERE inn=%s', ('7799400001',)), [(2,)])
        again = self.client.post('/register', json=base.SupplierRegistrationPostgresTests.registration(self, invite, inn='7799400001'))
        self.assertEqual(again.status_code, 400, again.text)
        self.client.cookies.clear()

    def test_generic_invite_follows_legal_key_on_merged_source(self):
        source, target, invoice, owner = self.seed()
        self.sql("UPDATE suppliers SET inn='77 9940-0002' WHERE id=%s", (source,))
        self.sql('UPDATE suppliers SET inn=NULL WHERE id=%s', (target,))
        self.merge(self.review(source, target))
        count = self.sql('SELECT count(*) FROM suppliers')
        invite = self.api('director', 'POST', '/invite-codes', {'role': 'поставщик'}, **{'X-Company-Id': '2'})
        payload = base.SupplierRegistrationPostgresTests.registration(self, invite, inn='7799400002')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.sql('SELECT count(*) FROM suppliers'), count)
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (source,)), [('77 9940-0002',)])
        self.assertEqual(self.sql('SELECT inn FROM suppliers WHERE id=%s', (target,)), [('7799400002',)])
        self.client.cookies.clear()

    def test_merged_invite_never_crosses_company_or_claims_existing_account(self):
        for registered in (False, True):
            source, target, invoice, owner = self.seed()
            invite = self.api('director', 'POST', '/invite-codes',
                              {'role': 'поставщик', 'supplierId': source}, **{'X-Company-Id': '2'})
            self.merge(self.review(source, target))
            if registered:
                self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s', (owner, target))
            else:
                self.sql('DELETE FROM company_supplier_links WHERE company_id=2 AND supplier_id=%s', (target,))
                self.sql('INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id) VALUES(3,%s,1)', (target,))
            payload = base.SupplierRegistrationPostgresTests.registration(self, invite)
            response = self.client.post('/register', json=payload)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s', (payload['email'],)), [])
            self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s', (invite['id'],)), [(False,)])
            self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,)), [(None,)])
