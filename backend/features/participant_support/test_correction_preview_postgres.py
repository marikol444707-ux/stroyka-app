"""Read-only impact review of one accepted connection, on disposable PostgreSQL."""
import importlib
import os
import unittest
import uuid
from unittest.mock import patch

from . import test_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class SupplierCorrectionPreviewPostgresTests(unittest.TestCase):
    sql, api = support.ParticipantSupportPostgresTests.sql, support.ParticipantSupportPostgresTests.api

    @classmethod
    def setUpClass(cls):
        support.ParticipantSupportPostgresTests.setUpClass.__func__(cls)
        for migration in ('0038_supplier_customer_team', '0095_supplier_buyer_connections'):
            cls.sql(cls, importlib.import_module('migrations.versions.'+migration).SCHEMA_SQL)
        patch.dict(os.environ, PARTICIPANT_CONNECTIONS_ENABLED='1', PARTICIPANT_CORRECTION_PREVIEW_ENABLED='1').start()

    def connection(self, accepted=True):
        inn = '77'+str(uuid.uuid4().int % 10**8).zfill(8)
        source = self.sql('INSERT INTO suppliers(name,inn) VALUES(%s,%s) RETURNING id', ('Synthetic original card', inn))[0][0]
        target = self.sql('INSERT INTO suppliers(name,inn,user_id) VALUES(%s,%s,%s) RETURNING id',
                          ('Synthetic connected cabinet', inn, self.fixture['users']['supplier']['id']))[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,platform_account_id,supplier_id) VALUES(2,1,%s),(3,1,%s)', (source,target))
        request = self.api('admin', 'POST', f'/system/companies/2/participants/{source}/connection-requests',
                           dict(targetSupplierId=target, expectedSourceVersion=1, requestId=str(uuid.uuid4()), confirmed=True))
        if accepted:
            self.api('supplier', 'POST', f"/supplier/connection-requests/{request['id']}/accept", dict(expectedVersion=1, confirmed=True))
        return source, target, request['id']

    def path(self, source, request, company=2):
        return f'/system/companies/{company}/participants/{source}/connection-requests/{request}/correction-preview'

    def review(self, source, request, **kwargs):
        return self.api('admin', 'GET', self.path(source,request), **kwargs)

    def test_exact_documents_dates_access_and_no_writes(self):
        source,target,request = self.connection()
        old = self.sql("INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount,created_at) VALUES(2,%s,200,50,NOW()-INTERVAL '1 day') RETURNING id", (source,))[0][0]
        new = self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount,paid_amount) VALUES(2,%s,400,100) RETURNING id', (target,))[0][0]
        foreign = self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,amount) VALUES(3,%s,987654) RETURNING id', (target,))[0][0]
        tables = ('users','suppliers','company_supplier_links','supplier_invoices','supplier_buyer_connection_requests','audit_log')
        before = {table:self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id') for table in tables}
        result = self.review(source,request)
        self.assertEqual(result['companyId'],2)
        self.assertEqual(result['sourceId'],source)
        self.assertEqual(result['targetId'],target)
        self.assertEqual(result['summary']['invoices'],dict(total=2,afterConnection=1,undated=0))
        self.assertEqual({item['id'] for item in result['items']},{old,new})
        items = {item['id']:item for item in result['items']}
        self.assertEqual(items[old]['currentSupplierAccess'],'unavailable')
        self.assertEqual(items[new]['currentSupplierAccess'],'available')
        self.assertFalse(items[old]['createdAfterConnection'])
        self.assertTrue(items[new]['createdAfterConnection'])
        self.assertNotIn(foreign,{item['id'] for item in result['items']})
        self.assertNotIn('987654',str(result))
        for forbidden in ('file_url','email','password','paid_amount','amount','ownerUserId'):
            self.assertNotIn(forbidden,str(result))
        self.assertFalse(result['canApply'])
        self.assertTrue(result['addressedAccessRequiresSeparateCorrection'])
        for table,rows in before.items():
            self.assertEqual(rows,self.sql('SELECT to_jsonb(t) FROM '+table+' t ORDER BY id'))

    def test_pagination_category_and_unknown_dates(self):
        source,target,request = self.connection()
        for sid in (source,target):
            self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,created_at) VALUES(2,%s,NULL)',(sid,))
        self.sql('INSERT INTO warehouse_invoices(company_id,supplier_id) VALUES(2,%s)',(source,))
        first = self.api('admin','GET',self.path(source,request)+'?limit=1')
        second = self.api('admin','GET',self.path(source,request)+'?limit=1&offset=1')
        self.assertTrue(first['hasMore'])
        self.assertFalse(second['hasMore'])
        self.assertNotEqual(first['items'][0]['id'],second['items'][0]['id'])
        self.assertEqual(first['summary']['invoices'],dict(total=2,afterConnection=0,undated=2))
        self.assertIsNone(first['items'][0]['createdAfterConnection'])
        self.assertIn('UNDATED_DOCUMENTS',[b['code'] for b in first['blockers']])
        receipts = self.api('admin','GET',self.path(source,request)+'?category=receipts')
        self.assertEqual(len(receipts['items']),1)
        self.assertEqual(receipts['items'][0]['currentSupplierAccess'],'needs_check')

    def test_no_cross_company_or_unaccepted_request_or_arbitrary_pair(self):
        source,target,request = self.connection()
        self.api('admin','GET',self.path(source,request,3),expected=404)
        self.review(target,request,expected=404)
        self.review(source,str(uuid.uuid4()),expected=404)
        pending,_,pending_request = self.connection(False)
        self.review(pending,pending_request,expected=409)
        self.api('admin','GET',self.path(source,request)+'?category=arbitrary',expected=422)
        self.api('admin','GET',self.path(source,request)+'?limit=101',expected=422)

    def test_owner_change_merge_and_missing_schema_are_explicit_not_empty_success(self):
        source,target,request = self.connection()
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id) VALUES(NULL,%s)',(source,))
        self.sql('UPDATE suppliers SET user_id=NULL WHERE id=%s',(target,))
        self.sql("UPDATE company_supplier_links SET profile=jsonb_build_object('mergedIntoSupplierId',%s) WHERE company_id=2 AND supplier_id=%s",(target,source))
        result = self.review(source,request)
        codes = {b['code'] for b in result['blockers']}
        self.assertIn('CABINET_OWNER_CHANGED',codes)
        self.assertIn('MERGE_REQUIRES_SEPARATE_CORRECTION',codes)
        self.assertIn('UNASSIGNED_DOCUMENTS',codes)
        self.assertEqual(result['summary']['invoices']['total'],0)
        self.assertEqual(result['summary']['files']['total'],0)
        self.sql('ALTER TABLE file_ownership RENAME TO correction_test_saved_files')
        try:
            missing = self.review(source,request)
            self.assertIsNone(missing['summary']['files']['total'])
            self.assertIn('HISTORY_SCHEMA_REVIEW_REQUIRED',[b['code'] for b in missing['blockers']])
            self.api('admin','GET',self.path(source,request)+'?category=files',expected=503)
        finally:
            self.sql('ALTER TABLE correction_test_saved_files RENAME TO file_ownership')

    def test_auth_revocation_default_off_and_no_mutation_endpoint(self):
        source,_,request = self.connection()
        path = self.path(source,request)
        self.assertEqual(self.client.get(path).status_code,401)
        for actor in ('director','supplier'):
            self.api(actor,'GET',path,expected=403)
        self.api('admin','POST',path,{},expected=405)
        with patch.dict(os.environ,PARTICIPANT_CORRECTION_PREVIEW_ENABLED='0'):
            self.review(source,request,expected=503)
        uid = self.fixture['users']['admin']['id']
        self.sql('UPDATE users SET active=FALSE WHERE id=%s',(uid,))
        try:
            response = self.client.get(path,headers={'Authorization':'Bearer '+self.main.create_auth_token(self.fixture['users']['admin'],two_factor_passed=True)})
            self.assertIn(response.status_code,(401,403))
        finally:
            self.sql('UPDATE users SET active=TRUE WHERE id=%s',(uid,))

    def test_read_only_transaction_rejects_an_accidental_writer(self):
        from psycopg2.errors import ReadOnlySqlTransaction
        source,target,request = self.connection()
        def writer(cur,company,source_id,target_id):
            cur.execute('UPDATE suppliers SET user_id=NULL WHERE id=%s',(target_id,))
        with patch('backend.features.participant_support.correction_preview.document_queries',side_effect=writer):
            with self.assertRaises(ReadOnlySqlTransaction):
                self.review(source,request)
        self.assertEqual(self.sql('SELECT user_id FROM suppliers WHERE id=%s',(target,)),[(self.fixture['users']['supplier']['id'],)])

    def test_registered_originals_are_deduplicated_and_foreign_files_stay_out(self):
        from ..supplier_deal_parties.test_migration import migration_statements
        from ..supplier_deal_parties.test_contract_postgres import statements
        for statement in (migration_statements('upgrade')+statements('upgrade')+
                          statements('upgrade','0064_supplier_contract_registry.py')+
                          statements('upgrade','0067_supplier_contract_originals.py')):
            self.sql(statement)
        source,target,request = self.connection()
        own = self.sql('INSERT INTO file_ownership(company_id,file_url) VALUES(2,%s) RETURNING id',('/uploads/synthetic-'+str(uuid.uuid4())+'.pdf',))[0][0]
        foreign = self.sql('INSERT INTO file_ownership(company_id,file_url) VALUES(3,%s) RETURNING id',('/uploads/synthetic-'+str(uuid.uuid4())+'.pdf',))[0][0]
        for sid in (source,target):
            self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,file_url) VALUES(2,%s,%s)',(sid,f'/tenant-files/{own}/content'))
        self.sql('INSERT INTO supplier_invoices(company_id,supplier_id,file_url) VALUES(2,%s,%s)',(target,f'/tenant-files/{foreign}/content'))
        result = self.api('admin','GET',self.path(source,request)+'?category=files')
        self.assertEqual(result['summary']['files']['total'],1)
        self.assertEqual([r['id'] for r in result['items']],[own])
        self.assertEqual(result['items'][0]['currentSupplierAccess'],'needs_check')
        self.assertIn('FILE_REFERENCE_REVIEW_REQUIRED',[b['code'] for b in result['blockers']])
        self.assertNotIn('file_url',str(result))
        registry = self.sql('INSERT INTO supplier_contract_registry(company_id,supplier_id,buyer_company_id,payer_company_id) VALUES(2,%s,2,2) RETURNING id',(source,))[0][0]
        version = self.sql('''INSERT INTO supplier_contract_versions(company_id,version,source_file_id,snapshot_json,snapshot_hash,
            reason,reviewed_by_id,reviewed_by) VALUES(2,1,%s,%s,%s,'Synthetic review',%s,'Synthetic reviewer') RETURNING id''',
            (own,'{"supplier":{"supplierId":'+str(source)+'}}','0'*64,self.fixture['users']['director']['id']))[0][0]
        self.sql('INSERT INTO supplier_contract_registry_versions(registry_id,contract_version_id,company_id) VALUES(%s,%s,2)',(registry,version))
        contracts = self.api('admin','GET',self.path(source,request)+'?category=contracts')
        self.assertEqual(contracts['summary']['contracts']['total'],1)
        self.assertEqual(contracts['summary']['files']['total'],1)
        self.assertEqual([r['id'] for r in contracts['items']],[version])
        self.assertEqual(contracts['items'][0]['currentSupplierAccess'],'needs_check')
        self.assertNotIn('snapshot_json',str(contracts))
