import os
import json
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from .routes import register_counterparty_document_archive


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cur = self.conn.cursor.return_value
        self.cur.fetchall.return_value = []
        self.context = {'mode':'company','companyId':1}
        self.actor = {'companyId':1,'role':'директор'}
        app = FastAPI()
        register_counterparty_document_archive(app, {
            'get_db':lambda:self.conn,'get_current_user':lambda:{'role':'директор'},
            'resolve_work_company_context':lambda *a,**kw:self.context,
            'effective_company_actors':lambda *a:[self.actor]})
        self.client = TestClient(app)

    def test_all_company_mode_has_no_combined_archive(self):
        self.context={'mode':'all_companies'}
        self.assertTrue(self.client.get('/company-document-archive').json()['requiresCompanySelection'])
        self.cur.execute.assert_not_called()

    def test_effective_role_controls_access(self):
        self.actor['role']='поставщик'
        self.assertEqual(self.client.get('/company-document-archive').status_code,403)
        self.cur.execute.assert_not_called()

    def test_scope_and_search_are_parameters(self):
        response=self.client.get('/company-document-archive',params={'q':"' OR TRUE --"})
        self.assertEqual(response.status_code,200)
        sql,args=self.cur.execute.call_args.args
        self.assertNotIn("' OR TRUE --",sql)
        self.assertEqual(args[:3],(1,"' OR TRUE --","' OR TRUE --"))
        self.assertEqual(sql.count('d.company_id=%s'),8)

    def test_unsafe_links_are_withheld_and_missing_file_is_distinct(self):
        self.cur.fetchall.side_effect=[[
            ('company',1,1,'Charter','Устав',None,{'file_url':'/tenant-files/8/content'}),
            ('supplier',1,1,'Invoice','Счёт',None,{'file_url':'https://private.invalid/file'}),
            ('supplier',2,1,'Without file','Счёт',None,{})], [(8,None)]]
        items=self.client.get('/company-document-archive').json()['items']
        self.assertEqual([r['fileStatus'] for r in items],['available','needs_review','not_attached'])
        self.assertEqual(items[0]['fileUrl'],'/tenant-files/8/content')
        self.assertNotIn('private.invalid',str(items))
        self.assertNotEqual(items[0]['id'],items[1]['id'])

    def test_pagination_and_section_validation(self):
        self.cur.fetchall.return_value=[('company',i,1,'x','Устав',None,{}) for i in range(2)]
        data=self.client.get('/company-document-archive?section=company&limit=1').json()
        self.assertTrue(data['hasMore'])
        self.assertEqual(data['nextOffset'],1)
        self.assertEqual(len(data['items']),1)
        self.assertNotIn('supplier_documents',self.cur.execute.call_args.args[0])
        self.assertEqual(self.client.get('/company-document-archive?limit=1000').status_code,422)
        self.assertEqual(self.client.get('/company-document-archive?section=foreign').status_code,422)

    def test_supplier_section_includes_procurement_but_not_company_documents(self):
        response=self.client.get('/company-document-archive?section=supplier')
        self.assertEqual(response.status_code,200)
        sql=self.cur.execute.call_args.args[0]
        for table in ('supplier_offers','supplier_invoices','supply_deliveries','warehouse_invoices'):
            self.assertIn(table,sql)
        self.assertNotIn('FROM company_documents',sql)

    def test_multiple_pages_deduplicated_and_foreign_files_not_returned(self):
        self.cur.fetchall.side_effect=[[
            ('warehouse',4,1,'Pages','Накладная',None,{
                'photo_url':'/tenant-files/8/content',
                'photo_urls':'["/tenant-files/8/content","/tenant-files/9/content","/tenant-files/10/content"]'})],[(8,None),(9,None)]]
        item=self.client.get('/company-document-archive').json()['items'][0]
        self.assertEqual(len(item['attachments']),2)
        self.assertEqual(item['unavailableAttachments'],1)
        self.assertEqual(item['fileStatus'],'needs_review')
        sql,args=self.cur.execute.call_args.args
        self.assertIn('company_id=%s',sql)
        self.assertIn('SELECT id,project_id',sql)
        self.assertEqual(args[0],1)
        self.assertNotIn('/tenant-files/10/content',str(item))

    def test_project_files_require_exact_parent_access_and_cache_per_project(self):
        self.cur.fetchall.side_effect=[[
            ('warehouse',4,1,'Pages','Накладная',None,{
                'photo_urls':'["/tenant-files/8/content","/tenant-files/9/content","/tenant-files/10/content"]'})],[(8,44),(9,44),(10,55)]]
        with patch('backend.features.counterparty_documents.routes.resolve_project_parent') as resolve, patch('backend.features.counterparty_documents.routes.require_project_parent_access') as authorize:
            resolve.side_effect=[{'id':44,'companyId':1}, HTTPException(404,'Foreign or missing')]
            item=self.client.get('/company-document-archive').json()['items'][0]
            self.assertEqual(resolve.call_count,2)
            authorize.assert_called_once()
            self.assertEqual([f['fileId'] for f in item['attachments']],[8,9])
            self.assertEqual(item['unavailableAttachments'],1)

    def test_denied_project_never_exposes_file(self):
        self.cur.fetchall.side_effect=[[
            ('offer',1,1,'Offer','КП',None,{'pdf_url':'/tenant-files/8/content'})],[(8,44)]]
        with patch('backend.features.counterparty_documents.routes.resolve_project_parent',return_value={'id':44}), patch('backend.features.counterparty_documents.routes.require_project_parent_access',side_effect=HTTPException(403,'Denied')):
            item=self.client.get('/company-document-archive').json()['items'][0]
            self.assertEqual(item['attachments'],[])
            self.assertIsNone(item['fileUrl'])
            self.assertEqual(item['fileStatus'],'needs_review')

    def test_customer_section_requires_exact_project_company_and_side(self):
        self.client.get('/company-document-archive?section=customer')
        query=self.cur.execute.call_args.args[0]
        self.assertIn("d.side='customer'",query)
        self.assertIn('p.id=d.project_id AND p.company_id=d.company_id',query)
        self.assertNotIn('FROM supplier_invoices',query)

    def test_customer_document_cannot_open_a_different_project_attachment(self):
        self.cur.fetchall.side_effect=[[
            ('customer',4,1,'Contract','Договор',None,{'scan_url':'/tenant-files/8/content','project_id':44})],[(8,55)]]
        with patch('backend.features.counterparty_documents.routes.resolve_project_parent',return_value={'id':55}), patch('backend.features.counterparty_documents.routes.require_project_parent_access'):
            item=self.client.get('/company-document-archive?section=customer').json()['items'][0]
            self.assertEqual(item['attachments'],[])
            self.assertEqual(item['fileStatus'],'needs_review')

    def test_contract_original_and_verified_invoice_relationships(self):
        self.cur.fetchall.side_effect = [[
            ('contract',9,1,'Договор №362 · версия 1','Договор',None,
             {'file_url':'/tenant-files/88/content','offer_id':71}),
            ('invoice',161,1,'Счёт №В-1','Счёт',None,
             {'offer_id':71,'contract_number':'362','contract_version':1})],[(88,None)]]
        response=self.client.get('/company-document-archive?section=supplier')
        self.assertEqual(response.status_code,200,response.text)
        contract,invoice=response.json()['items']
        self.assertEqual(contract['fileUrl'],'/tenant-files/88/content')
        self.assertEqual(contract['offerId'],71)
        self.assertEqual(invoice['contractNumber'],'362')
        self.assertEqual(invoice['contractVersion'],1)
        sql=self.cur.execute.call_args_list[0].args[0]
        self.assertIn('c.company_id=d.company_id AND c.offer_id=d.offer_id',sql)
        self.assertIn('o.id=d.offer_id AND o.company_id=d.company_id',sql)

    def test_exact_document_lookup_is_scoped_and_parameterized(self):
        response=self.client.get('/company-document-archive?source=contract&recordId=9')
        self.assertEqual(response.status_code,200,response.text)
        sql,args=self.cur.execute.call_args.args
        self.assertIn('WHERE source=%s AND id=%s',sql)
        self.assertEqual(args[-4:],('contract',9,51,0))
        self.assertEqual(sql.count('d.company_id=%s'),8)
        self.assertEqual(response.json()['items'],[])

    def test_incomplete_or_invalid_lookup_is_rejected(self):
        for query in ('source=contract','recordId=9','source=unknown&recordId=9','source=contract&recordId=-1'):
            self.assertEqual(self.client.get('/company-document-archive?'+query).status_code,422)
        self.cur.execute.assert_not_called()

    def test_contract_invoice_filter_requires_exact_owner_offer_and_version(self):
        response=self.client.get('/company-document-archive?contractId=9&offset=30&limit=30')
        self.assertEqual(response.status_code,200,response.text)
        sql,args=self.cur.execute.call_args.args
        self.assertEqual(args,(1,'','',9,31,30))
        self.assertIn('c.id=%s AND c.id=d.contract_version_id AND c.company_id=d.company_id AND c.offer_id=d.offer_id',sql)
        self.assertNotIn('UNION ALL',sql)
        self.assertEqual(response.json()['items'],[])

    def test_contract_invoice_filter_rejects_conflicting_modes(self):
        for query in ('contractId=9&source=contract&recordId=9','contractId=9&section=company','contractId=0'):
            self.assertEqual(self.client.get('/company-document-archive?'+query).status_code,422)
        self.cur.execute.assert_not_called()

    def test_reused_contract_exposes_only_verified_source_relationship(self):
        self.cur.fetchall.return_value = [
            ('contract',10,1,'Повторный договор','Договор',None,{'origin_contract_id':9}),
            ('contract',11,1,'Без связи','Договор',None,{}),
            ('invoice',12,1,'Счёт','Счёт',None,{'origin_contract_id':9})]
        response=self.client.get('/company-document-archive?section=supplier')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual([i['originContractId'] for i in response.json()['items']],[9,None,None])
        sql=self.cur.execute.call_args.args[0]
        for predicate in ("c.id::text=d.snapshot_json #>> '{reusedFrom,contractId}'",
                          'c.company_id=d.company_id AND c.id<>d.id',
                          'c.source_file_id=d.source_file_id',
                          "c.snapshot_hash=d.snapshot_json #>> '{reusedFrom,snapshotHash}'",
                          "c.offer_id::text IS NOT DISTINCT FROM (d.snapshot_json #>> '{reusedFrom,offerId}')",
                          "c.version::text=d.snapshot_json #>> '{reusedFrom,version}'",
                          'o.id=c.offer_id AND o.company_id=c.company_id'):
            self.assertIn(predicate,sql)

    @unittest.skipUnless(os.environ.get('RUN_SUPPLIER_DEAL_PG_TESTS') == '1', 'isolated PostgreSQL only')
    def test_reuse_lineage_in_postgresql(self):
        import psycopg2
        self.client.get('/company-document-archive?category=contract')
        sql,args=self.cur.execute.call_args.args
        conn=psycopg2.connect(host=os.environ['DB_HOST'],port=os.environ['DB_PORT'],
                              dbname=os.environ['DB_NAME'],user=os.environ['DB_USER'])
        try:
            with conn.cursor() as cur:
                cur.execute('CREATE TEMP TABLE supplier_contract_publications (contract_version_id int,company_id int,snapshot_hash text)')
                cur.execute('CREATE TEMP TABLE projects (id int, company_id int, name text)')
                cur.execute('CREATE TEMP TABLE supplier_contract_registry (id BIGINT,company_id INTEGER,archived BOOLEAN,state_version INTEGER)')
                cur.execute('CREATE TEMP TABLE supplier_contract_registry_versions (contract_version_id int, registry_id int, company_id int)')
                cur.execute('CREATE TEMP TABLE supplier_offers (id int, company_id int)')
                cur.execute('CREATE TEMP TABLE supplier_contract_versions (id int, company_id int, offer_id int, version int, source_file_id int, snapshot_hash text, snapshot_json jsonb, reviewed_at timestamp)')
                cur.execute('INSERT INTO supplier_offers VALUES (71,1),(72,1)')
                cur.execute("INSERT INTO supplier_contract_versions VALUES (9,1,71,2,88,'saved-hash','{}',NULL),(10,1,72,1,88,'new-hash','{}',NULL)")
                valid={'contractId':9,'offerId':71,'version':2,'snapshotHash':'saved-hash'}
                def origin(lineage):
                    cur.execute('UPDATE supplier_contract_versions SET snapshot_json=%s WHERE id=10',
                                (json.dumps({'reusedFrom':lineage}),))
                    cur.execute(sql,args)
                    return next(r[6]['origin_contract_id'] for r in cur.fetchall() if r[1]==10)
                self.assertEqual(origin(valid),9)
                for field,value in (('contractId','invalid'),('contractId',999),('contractId',10),
                                    ('offerId',999),('version',1),('snapshotHash','changed')):
                    self.assertIsNone(origin({**valid,field:value}),field)
                self.assertIsNone(origin(None))
                cur.execute('UPDATE supplier_contract_versions SET company_id=2 WHERE id=9')
                self.assertIsNone(origin(valid))
                cur.execute('UPDATE supplier_contract_versions SET company_id=1,source_file_id=99 WHERE id=9')
                self.assertIsNone(origin(valid))
                cur.execute('UPDATE supplier_contract_versions SET source_file_id=88 WHERE id=9')
                cur.execute('UPDATE supplier_offers SET company_id=2 WHERE id=71')
                self.assertIsNone(origin(valid))
                cur.execute('INSERT INTO supplier_contract_registry_versions VALUES (9,7,1),(10,7,1)')
                cur.execute('INSERT INTO supplier_offers VALUES (73,2)')
                cur.execute("INSERT INTO supplier_contract_versions VALUES (11,2,73,1,88,'foreign','{}',NULL)")
                cur.execute('INSERT INTO supplier_contract_registry_versions VALUES (11,7,2)')
                self.client.get('/company-document-archive?registryId=7')
                registry_sql,registry_args=self.cur.execute.call_args.args
                cur.execute(registry_sql,registry_args)
                rows=cur.fetchall()
                # Offer71 was deliberately made foreign above, so only the authorized
                # remaining version10 is visible even with a corrupted foreign link.
                self.assertEqual([row[1] for row in rows],[10])
                self.assertEqual(rows[0][6]['registry_id'],7)
        finally:
            conn.rollback()
            conn.close()

    def test_category_filters_before_pagination_with_company_scope(self):
        from .routes import SOURCES
        for category,(_,table,*_) in SOURCES.items():
            response=self.client.get('/company-document-archive',params={'category':category,'q':'362','offset':30,'limit':30})
            self.assertEqual(response.status_code,200,response.text)
            sql,args=self.cur.execute.call_args.args
            self.assertEqual(args,(1,'362','362',31,30))
            self.assertIn('FROM '+table+' d',sql)
            self.assertNotIn('UNION ALL',sql)
            self.assertEqual(sql.count('d.company_id=%s'),1)

    def test_invalid_category_or_conflicting_lookup_rejected(self):
        for query in ('category=unknown','category=invoice&section=company',
                      'category=invoice&section=customer','category=invoice&contractId=9',
                      'category=invoice&source=contract&recordId=9'):
            self.assertEqual(self.client.get('/company-document-archive?'+query).status_code,422,query)
        self.cur.execute.assert_not_called()

    def test_registry_history_is_company_scoped_and_parameterized(self):
        response=self.client.get('/company-document-archive?registryId=7&offset=30&limit=30')
        self.assertEqual(response.status_code,200,response.text)
        sql,args=self.cur.execute.call_args.args
        self.assertEqual(args,(1,'','',7,31,30))
        self.assertIn('m.contract_version_id=d.id AND m.company_id=d.company_id AND m.registry_id=%s',sql)
        self.assertNotIn('UNION ALL',sql)

    def test_registry_history_rejects_mixed_filters(self):
        for query in ('registryId=0','registryId=7&category=contract','registryId=7&contractId=1',
                      'registryId=7&source=contract&recordId=9','registryId=7&section=customer'):
            self.assertEqual(self.client.get('/company-document-archive?'+query).status_code,422,query)
        self.cur.execute.assert_not_called()
