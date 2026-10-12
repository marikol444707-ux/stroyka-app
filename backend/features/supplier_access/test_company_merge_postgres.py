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

    def seed(self):
        source = self.sql("INSERT INTO suppliers(name) VALUES('Synthetic receipt card') RETURNING id")[0][0]
        owner = self.fixture['users']['supplier']['id']
        target = self.sql("INSERT INTO suppliers(name,user_id,inn,registered_at) VALUES('Synthetic registered card',%s,'7799998877',NOW()) RETURNING id", (owner,))[0][0]
        for sid in (source, target):
            self.sql("INSERT INTO company_supplier_links(company_id,supplier_id,platform_account_id,profile) VALUES(2,%s,1,'{}')", (sid,))
        invoice = self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,project_name,amount,paid_amount,status) VALUES(2,%s,%s,200,50,'На утверждении') RETURNING id", (source, self.fixture['project']))[0][0]
        return source, target, invoice, owner

    def review(self, source, target, **kwargs):
        return self.api('director', 'POST', f'/suppliers/{target}/merge-preview', {'sourceId':source,'companyId':2}, **kwargs)

    def merge(self, review, **kwargs):
        body = {key:review[key] for key in ('sourceId','targetVersion','sourceVersion')}
        return self.api('director', 'POST', f"/suppliers/{review['targetId']}/merge", {**body,'companyId':2,'confirmed':True}, **kwargs)

    def test_preview_then_merge_preserves_documents_and_connects_cabinet(self):
        source, target, invoice, owner = self.seed()
        before = self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,))
        review = self.review(source, target)
        self.assertEqual(review['documents']['supplier_invoices'], 1)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s', (source,)), [(None,)])
        self.assertTrue(self.merge(review)['ok'])
        self.assertEqual(self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE id=%s', (invoice,)), before)
        self.assertEqual(self.sql('SELECT user_id,inn FROM suppliers WHERE id=%s', (source,)), [(owner,None)])
        rows = self.api('director', 'GET', '/suppliers', **{'X-Company-Id':'2'})
        for sid in (source, target):
            row = next(r for r in rows if r['id'] == sid)
            self.assertEqual(row['canonicalSupplierId'], target)
            self.assertEqual(row['relatedSupplierIds'], [source,target])
        conn = self.main.get_db()
        try:
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                ids = self.main.current_supplier_ids(cur, {'id':owner})
                self.assertLess(ids.index(target), ids.index(source))
        finally:
            conn.close()
        self.merge(review, expected=409)

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
        source, target, invoice, owner = self.seed()
        invite = self.api('director','POST','/invite-codes',
                          {'role':'поставщик','supplierId':source,'expiresInDays':1},
                          **{'X-Company-Id':'2'})
        payload = base.SupplierRegistrationPostgresTests.registration(self, invite, inn='7799998877')
        response = self.client.post('/register', json=payload)
        self.assertEqual(response.status_code,409,response.text)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
        self.assertEqual(self.sql('SELECT id FROM users WHERE email=%s',(payload['email'],)),[])
        self.assertEqual(self.sql('SELECT used FROM invite_codes WHERE id=%s',(invite['id'],)),[(False,)])
