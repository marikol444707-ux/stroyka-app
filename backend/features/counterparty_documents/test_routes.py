import unittest
from unittest.mock import MagicMock
from fastapi import FastAPI
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
        self.assertEqual(sql.count('d.company_id=%s'),2)
        self.assertIn('f.company_id=d.company_id',sql)

    def test_unsafe_links_are_withheld_and_missing_file_is_distinct(self):
        self.cur.fetchall.return_value=[
            ('company',1,1,'Charter','Устав',None,'/tenant-files/8/content',8),
            ('supplier',1,1,'Invoice','Счёт',None,'https://private.invalid/file',None),
            ('supplier',2,1,'Without file','Счёт',None,'',None)]
        items=self.client.get('/company-document-archive').json()['items']
        self.assertEqual([r['fileStatus'] for r in items],['available','needs_review','not_attached'])
        self.assertEqual(items[0]['fileUrl'],'/tenant-files/8/content')
        self.assertNotIn('private.invalid',str(items))
        self.assertNotEqual(items[0]['id'],items[1]['id'])

    def test_pagination_and_section_validation(self):
        self.cur.fetchall.return_value=[('company',i,1,'x','Устав',None,'',None) for i in range(2)]
        data=self.client.get('/company-document-archive?section=company&limit=1').json()
        self.assertTrue(data['hasMore'])
        self.assertEqual(data['nextOffset'],1)
        self.assertEqual(len(data['items']),1)
        self.assertNotIn('supplier_documents',self.cur.execute.call_args.args[0])
        self.assertEqual(self.client.get('/company-document-archive?limit=1000').status_code,422)
        self.assertEqual(self.client.get('/company-document-archive?section=foreign').status_code,422)
