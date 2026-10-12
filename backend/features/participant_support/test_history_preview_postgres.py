"""Exact company history is diagnosis, never permission to claim an archive."""
import os
import unittest
import uuid
from unittest.mock import patch

from .test_postgres import ParticipantSupportPostgresTests as Base


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupplierHistoryPreviewPostgresTests(unittest.TestCase):
    sql, api = Base.sql, Base.api

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)
        patch.dict(os.environ, PARTICIPANT_HISTORY_PREVIEW_ENABLED='1').start()
        from ..supplier_deal_parties.test_migration import migration_statements
        from ..supplier_deal_parties.test_contract_postgres import statements
        for statement in (migration_statements('upgrade')+statements('upgrade')+
                          statements('upgrade','0064_supplier_contract_registry.py')+
                          statements('upgrade','0067_supplier_contract_originals.py')):
            cls.sql(cls,statement)

    def pair(self):
        inn = '77'+str(uuid.uuid4().int % 10**8).zfill(8)
        source = self.sql('INSERT INTO suppliers(name,inn) VALUES(%s,%s) RETURNING id', ('Synthetic receipt',inn))[0][0]
        target = self.sql('INSERT INTO suppliers(name,inn,user_id) VALUES(%s,%s,%s) RETURNING id',
                          ('Synthetic cabinet',inn,self.fixture['users']['supplier']['id']))[0][0]
        for sid in (source,target):
            self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(2,1,%s)',(sid,))
        return source,target

    def path(self,source,target,company=2,category='invoices',offset=0):
        return f'/system/companies/{company}/participants/{source}/history-preview?targetSupplierId={target}&category={category}&offset={offset}'

    def test_exact_ids_pagination_and_no_account_or_history_write(self):
        source,target=self.pair()
        ids=[]
        for _ in range(27):
            ids.append(self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,200,50) RETURNING id',(source,))[0][0])
        before={table:self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id') for table in
                ('suppliers','supplier_invoices','company_supplier_links','users','audit_log')}
        plan=self.api('admin','GET',self.path(source,target))
        self.assertFalse(plan['canApply'])
        self.assertEqual(plan['companyId'],2)
        self.assertEqual(plan['summary']['invoices'],27)
        self.assertEqual([r['id'] for r in plan['items']],ids[:25])
        self.assertTrue(plan['hasMore'])
        self.assertTrue(all(r['currentSupplierAccess']=='unavailable' for r in plan['items']))
        page=self.api('admin','GET',self.path(source,target,offset=25))
        self.assertEqual([r['id'] for r in page['items']],ids[25:])
        self.assertFalse(page['hasMore'])
        self.assertNotIn('amount',str(plan));self.assertNotIn('password',str(plan))
        for table,rows in before.items():self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))

    def test_foreign_company_or_forged_target_never_returns_history(self):
        source,target=self.pair()
        self.api('director','GET',self.path(source,target),expected=403)
        self.api('admin','GET',self.path(source,target,company=3),expected=404)
        foreign=self.sql("INSERT INTO suppliers(name,inn,user_id) VALUES('Synthetic foreign cabinet','7700009999',%s) RETURNING id",
                         (self.fixture['users']['supplier']['id'],))[0][0]
        self.api('admin','GET',self.path(source,foreign),expected=404)
        self.api('admin','GET',self.path(source,target,category='users'),expected=422)
        with patch.dict(os.environ,PARTICIPANT_HISTORY_PREVIEW_ENABLED='0'):
            self.api('admin','GET',self.path(source,target),expected=503)

    def test_read_only_history_transaction_cannot_change_ownership(self):
        from psycopg2.errors import ReadOnlySqlTransaction
        source,target=self.pair()
        def unexpected_writer(cur,company,supplier_id):
            cur.execute('UPDATE suppliers SET user_id=%s WHERE id=%s',
                        (self.fixture['users']['supplier']['id'],supplier_id))
        with patch('backend.features.participant_support.history_preview.diagnose',side_effect=unexpected_writer):
            with self.assertRaises(ReadOnlySqlTransaction):self.api('admin','GET',self.path(source,target))
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])

    def test_shared_source_blocks_merge_and_returns_only_selected_company_ids(self):
        source,target=self.pair()
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(3,1,%s)',(source,))
        foreign=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(3,%s,777) RETURNING id',(source,))[0][0]
        own=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(2,%s,100) RETURNING id',(source,))[0][0]
        plan=self.api('admin','GET',self.path(source,target))
        self.assertEqual([r['id'] for r in plan['items']],[own])
        self.assertNotIn(foreign,[r['id'] for r in plan['items']])
        self.assertIn('SHARED_SOURCE_CARD',[b['code'] for b in plan['blockers']])
        self.assertFalse(plan['canApply'])

    def test_legacy_link_commands_cannot_clear_merged_owner_or_claim_another_card(self):
        source,target=self.pair()
        owner=self.fixture['users']['supplier']['id']
        self.sql('UPDATE suppliers SET user_id=%s WHERE id=%s',(owner,source))
        before=self.sql('SELECT to_jsonb(s) FROM suppliers s ORDER BY id')
        for endpoint,payload in (('link-user',{'userId':owner}),('link-duplicate',{'duplicateSupplierId':source})):
            result=self.api('admin','POST',f'/suppliers/{target}/{endpoint}',payload,expected=409)
            self.assertIn('организац',result['detail'].lower())
        self.assertEqual(before,self.sql('SELECT to_jsonb(s) FROM suppliers s ORDER BY id'))

    def test_contract_versions_and_registered_originals_remain_separate_from_access(self):
        source,target=self.pair()
        own=self.sql("INSERT INTO file_ownership(company_id,file_url) VALUES(2,%s) RETURNING id",('/uploads/synthetic-'+str(uuid.uuid4())+'.pdf',))[0][0]
        foreign=self.sql("INSERT INTO file_ownership(company_id,file_url) VALUES(3,%s) RETURNING id",('/uploads/synthetic-'+str(uuid.uuid4())+'.pdf',))[0][0]
        self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,amount,file_url) VALUES(2,%s,100,%s),(2,%s,100,%s)",
                 (source,f'/tenant-files/{own}/content',source,f'/tenant-files/{foreign}/content'))
        registry=self.sql('INSERT INTO supplier_contract_registry(company_id,supplier_id,buyer_company_id,payer_company_id) VALUES(2,%s,2,2) RETURNING id',(source,))[0][0]
        version=self.sql('''INSERT INTO supplier_contract_versions(company_id,version,source_file_id,snapshot_json,snapshot_hash,
            reason,reviewed_by_id,reviewed_by) VALUES(2,1,%s,%s,%s,'Synthetic review',%s,'Synthetic reviewer') RETURNING id''',
            (own,'{"supplier":{"supplierId":'+str(source)+'}}','0'*64,self.fixture['users']['director']['id']))[0][0]
        self.sql('INSERT INTO supplier_contract_registry_versions(registry_id,contract_version_id,company_id) VALUES(%s,%s,2)',(registry,version))
        before=self.sql('SELECT to_jsonb(v) FROM supplier_contract_versions v ORDER BY id')
        contracts=self.api('admin','GET',self.path(source,target,category='contracts'))
        self.assertEqual([r['id'] for r in contracts['items']],[version])
        self.assertEqual(contracts['summary']['contracts'],1)
        self.assertEqual(contracts['summary']['files'],1)
        self.assertEqual(contracts['unresolvedPrimaryFiles'],1)
        self.assertIn('FILE_REFERENCE_REVIEW_REQUIRED',[b['code'] for b in contracts['blockers']])
        files=self.api('admin','GET',self.path(source,target,category='files'))
        self.assertEqual([r['id'] for r in files['items']],[own])
        self.assertNotIn(foreign,[r['id'] for r in files['items']])
        self.assertNotIn('file_url',str(files));self.assertNotIn('snapshot_json',str(contracts))
        self.assertEqual(before,self.sql('SELECT to_jsonb(v) FROM supplier_contract_versions v ORDER BY id'))

    def test_fifty_buyers_keep_exact_history_of_one_existing_cabinet(self):
        source,target=self.pair()
        inn=self.sql('SELECT inn FROM suppliers WHERE id=%s',(target,))[0][0]
        self.sql("INSERT INTO platform_accounts(id,name,plan,status) VALUES(199,'Synthetic history buyers','pro','active')")
        for cid in range(700,750):
            account=1 if cid<725 else 199
            self.sql("INSERT INTO companies(id,name,platform_account_id,active,plan) VALUES(%s,'Synthetic history buyer',%s,TRUE,'pro')",(cid,account))
            card=self.sql("INSERT INTO suppliers(name,inn) VALUES('Synthetic company receipt',%s) RETURNING id",(inn,))[0][0]
            for sid in (card,target):
                self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(%s,%s,%s)',(cid,account,sid))
            invoice=self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(%s,%s,100) RETURNING id',(cid,card))[0][0]
            plan=self.api('admin','GET',self.path(card,target,company=cid))
            self.assertEqual([r['id'] for r in plan['items']],[invoice])
            self.assertEqual(plan['platformAccountId'],account)
            self.assertFalse(plan['canApply'])
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(source,)),[(None,)])
