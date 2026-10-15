"""Read-only connection diagnosis through real authentication and disposable PG."""
import os
import importlib
import time
from statistics import median
import unittest
from unittest.mock import patch
from psycopg2.errors import ForeignKeyViolation

from . import test_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupplierConnectionPreviewPostgresTests(unittest.TestCase):
    sql, api = support.ParticipantSupportPostgresTests.sql, support.ParticipantSupportPostgresTests.api

    @classmethod
    def setUpClass(cls):
        support.ParticipantSupportPostgresTests.setUpClass.__func__(cls)
        cls.sql(cls,importlib.import_module('migrations.versions.0038_supplier_customer_team').SCHEMA_SQL)

    def card(self, inn, *, owned=False, company=2, account=1):
        sid = self.sql('INSERT INTO suppliers(name,inn,user_id) VALUES(%s,%s,%s) RETURNING id',
                       ('Synthetic connection '+inn,inn,self.fixture['users']['supplier']['id'] if owned else None))[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)',
                 (company,account,sid))
        return sid

    def preview(self, sid, **kwargs):
        return self.api('admin','GET',f'/system/companies/2/participants/{sid}/connection-preview',**kwargs)

    def test_existing_cabinet_is_not_another_registration_and_reads_exact_history(self):
        sid=self.card('7700010001',owned=True)
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(2,%s,100),(3,%s,900)',(sid,sid))
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(3,1,%s)',(sid,))
        result=self.preview(sid)
        self.assertEqual(result['scenario'],'already_connected')
        self.assertEqual(result['cabinet']['supplierId'],sid)
        self.assertEqual(result['history']['invoices'],1)
        self.assertEqual(result['currentVisibility']['invoices'],1)
        self.assertEqual(result['blockers'],[])
        self.assertFalse(result['canApply'])

    def test_exact_legal_candidate_outside_buyer_never_grants_or_moves_history(self):
        source=self.card('7700010002')
        target=self.card('7700010002',owned=True,company=3)
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,200,50)',(source,))
        before={table:self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id')
                for table in ('suppliers','company_supplier_links','supplier_invoices','invite_codes','audit_log')}
        result=self.preview(source)
        self.assertEqual(result['scenario'],'connect_existing')
        self.assertEqual(result['cabinet']['supplierId'],target)
        self.assertFalse(result['cabinet']['hasBuyerRelationship'])
        self.assertIn('OWNER_VERIFICATION_REQUIRED',[b['code'] for b in result['blockers']])
        self.assertIn('HISTORY_REVIEW_REQUIRED',[b['code'] for b in result['blockers']])
        self.assertIsNone(result['currentVisibility'])
        for table,rows in before.items():
            self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))
        self.assertNotIn('900',str(result))
        self.assertNotIn('email',str(result))
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(2,1,%s)',(target,))
        result=self.preview(source)
        self.assertEqual(result['scenario'],'merge_cards')
        self.assertIsInstance(result['cabinet']['relationshipVersion'],int)

    def test_fifty_independent_buyers_share_one_cabinet_without_history_disclosure(self):
        sid=self.card('7700010050',owned=True)
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(199,'Synthetic independent buyer account','pro','active')")
        for cid in range(500,550):
            account=1 if cid<525 else 199
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,'Synthetic preview buyer',%s,TRUE,'pro')",(cid,account))
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)',(cid,account,sid))
            self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(%s,%s,%s)',(cid,sid,cid))
        before=self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE supplier_id=%s ORDER BY id',(sid,))
        for cid in range(500,550):
            result=self.api('admin','GET',f'/system/companies/{cid}/participants/{sid}/connection-preview')
            self.assertEqual(result['companyId'],cid)
            self.assertEqual(result['cabinet']['supplierId'],sid)
            self.assertEqual(result['history']['invoices'],1)
            self.assertEqual(result['currentVisibility']['invoices'],1)
            self.assertEqual(result['blockers'],[])
            self.assertNotIn('amount',str(result))
        self.assertEqual(before,self.sql('SELECT to_jsonb(i) FROM supplier_invoices i WHERE supplier_id=%s ORDER BY id',(sid,)))
        values=[]
        for _ in range(20):
            start=time.perf_counter()
            self.api('admin','GET',f'/system/companies/549/participants/{sid}/connection-preview')
            values.append((time.perf_counter()-start)*1000)
        values.sort()
        print('CONNECTION_PREVIEW synthetic=50_buyers/2_accounts samples=20 median_ms=%.2f p95_ms=%.2f' % (median(values),values[18]))

    def test_two_cabinets_missing_keys_and_conflicting_legal_keys_are_not_guessed(self):
        source=self.card('7700010003')
        self.card('7700010003',owned=True,company=3)
        self.card('7700010003',owned=True,company=3)
        result=self.preview(source)
        self.assertEqual(result['scenario'],'ambiguous')
        self.assertIsNone(result['cabinet'])
        self.assertIn('MULTIPLE_CABINETS',[b['code'] for b in result['blockers']])
        blank=self.card('')
        self.assertIn('LEGAL_IDENTITY_REQUIRED',[b['code'] for b in self.preview(blank)['blockers']])
        source=self.card('7700010004')
        target=self.card('7700010004',owned=True,company=3)
        self.sql("UPDATE suppliers SET ogrn='1100000000001' WHERE id=%s",(source,))
        self.sql("UPDATE suppliers SET ogrn='1100000000002' WHERE id=%s",(target,))
        self.assertIn('LEGAL_IDENTITY_CONFLICT',[b['code'] for b in self.preview(source)['blockers']])

    def test_shared_source_unknown_document_owner_and_merged_card_block_repair(self):
        source=self.card('7700010005')
        self.card('7700010005',owned=True)
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(3,1,%s)',(source,))
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(NULL,%s,1)',(source,))
        result=self.preview(source)
        codes=[b['code'] for b in result['blockers']]
        self.assertEqual(result['scenario'],'merge_cards')
        self.assertIn('SHARED_SOURCE_CARD',codes)
        self.assertIn('DOCUMENT_OWNER_REVIEW',codes)
        self.assertEqual(result['history']['invoices'],0)
        self.sql("UPDATE company_supplier_links SET profile=jsonb_build_object('mergedIntoSupplierId',99999) WHERE company_id=2 AND supplier_id=%s",(source,))
        self.assertIn('SOURCE_CARD_MERGED',[b['code'] for b in self.preview(source)['blockers']])

    def test_owner_revocation_and_company_account_boundary_are_checked_again(self):
        sid=self.card('7700010006',owned=True)
        owner=self.fixture['users']['supplier']['id']
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(owner,))
        try:
            result=self.preview(sid)
            self.assertEqual(result['cabinet']['accountState'],'disabled')
            self.assertIsNone(result['currentVisibility'])
            self.assertIn('CABINET_ACCOUNT_DISABLED',[b['code'] for b in result['blockers']])
        finally:self.sql('UPDATE users SET active=TRUE WHERE id=%s',(owner,))
        foreign=self.card('7700010007',company=3)
        self.preview(foreign,expected=404)
        with self.assertRaises(ForeignKeyViolation):
            self.sql('UPDATE company_supplier_links SET platform_account_id=999 WHERE supplier_id=%s',(sid,))
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(99,'Synthetic separate account','pro','active')")
        self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(99,'Synthetic separate buyer',99,TRUE,'pro')")
        foreign=self.card('7700010009',company=99,account=99)
        self.preview(foreign,expected=404)

    def test_auth_flags_input_and_no_write_route(self):
        sid=self.card('7700010008')
        path=f'/system/companies/2/participants/{sid}/connection-preview'
        self.api('director','GET',path,expected=403)
        self.api('admin','POST',path,{},expected=405)
        self.api('admin','GET',path.replace(str(sid)+'/','0/'),expected=422)
        self.api('admin','GET',f'/system/companies/2/participants/{2**100}/connection-preview',expected=422)
        self.assertEqual(self.client.get(path).status_code,401)
        with patch.dict(os.environ,PARTICIPANT_SUPPORT_ENABLED='0'):
            self.preview(sid,expected=503)

    def test_name_contact_and_team_membership_are_not_a_cabinet_match(self):
        source=self.card('7700010010')
        target=self.card('7700010011',owned=True,company=3)
        self.sql("UPDATE suppliers SET name='Same brand',email='same@local.invalid' WHERE id=ANY(%s)",([source,target],))
        self.sql("INSERT INTO supplier_team_members(supplier_id,user_id,role,active) VALUES(%s,%s,'leader',TRUE)",
                 (source,self.fixture['users']['supplier']['id']))
        result=self.preview(source)
        self.assertIsNone(result['cabinet'])
        self.assertEqual(result['scenario'],'review')
        self.assertIn('SOURCE_TEAM_EXISTS',[b['code'] for b in result['blockers']])
        self.assertNotIn('same@local.invalid',str(result))

    def test_visibility_uses_recipient_policy_not_all_buyer_documents(self):
        sid=self.card('7700010012',owned=True)
        request=self.sql("INSERT INTO supply_requests(company_id,material_name,status,selected_suppliers) VALUES(2,'Synthetic hidden request','Новая',%s) RETURNING id",([sid],))[0][0]
        offer=self.sql('INSERT INTO supplier_offers(company_id,supplier_id,request_id) VALUES(2,%s,%s) RETURNING id',(sid,request))[0][0]
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,offer_id) VALUES(2,%s,%s)',(sid,offer))
        result=self.preview(sid)
        self.assertEqual(result['history']['offers'],1)
        self.assertEqual(result['history']['invoices'],1)
        self.assertEqual(result['currentVisibility'],{'invoices':0,'offers':0})
        with patch.dict(os.environ,SUPPLIER_TEAM_ENABLED='1',SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED='1'):
            self.assertEqual(self.preview(sid)['currentVisibility'],{'invoices':0,'offers':0})

    def test_inactive_relationship_and_wrong_role_do_not_claim_operational_access(self):
        sid=self.card('7700010013',owned=True)
        owner=self.fixture['users']['supplier']['id']
        self.sql("UPDATE company_supplier_links SET status='Неактивный' WHERE company_id=2 AND supplier_id=%s",(sid,))
        self.assertIn('NEW_OPERATIONS_PAUSED',[b['code'] for b in self.preview(sid)['blockers']])
        self.sql("UPDATE users SET role='мастер' WHERE id=%s",(owner,))
        try:
            result=self.preview(sid)
            self.assertEqual(result['cabinet']['accountState'],'wrong_role')
            self.assertIsNone(result['currentVisibility'])
        finally:self.sql("UPDATE users SET role='поставщик' WHERE id=%s",(owner,))
