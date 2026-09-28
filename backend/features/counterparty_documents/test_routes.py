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
        self.assertEqual(sql.count('d.company_id=%s'),7)

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
