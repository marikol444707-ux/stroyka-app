"""Real authenticated OCR/template regressions; disposable socket-only PostgreSQL."""
import json
import os
import unittest
from unittest.mock import patch
from backend.features.supplier_access.test_postgres_chain import PostgresSupplyChainTests

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class InvoiceScanIsolationTests(unittest.TestCase):
    api = PostgresSupplyChainTests.api
    sql = PostgresSupplyChainTests.sql

    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        import importlib
        with cls.main.get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO supplier_invoice_templates(supplier_key,supplier_name,sample_json) VALUES('legacy','LEGACY PRIVATE','{}') RETURNING id")
                cls.legacy_id = cur.fetchone()[0]
                cur.execute(importlib.import_module('migrations.versions.0117_invoice_template_owners').SCHEMA_SQL)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def learn(self, actor='director', **overrides):
        return self.api(actor, 'POST', '/supplier-invoice-templates/learn', dict(
            supplierName='SCAN private supplier', supplierId=self.fixture['supplierId'],
            number='PRIVATE-A', date='2026-11-10', documentType='waybill',
            items=[dict(name='PRIVATE-A material',quantity=2,price=10)], **overrides))

    def scan(self, actor, payload):
        with patch.object(self.main, 'generate_yandex_parts', return_value=json.dumps(payload)) as model:
            response=self.api(actor,'POST','/scan-invoice',{'images':[{'data':'aGVsbG8=','mimeType':'image/png'}]})
        return response,model

    def test_a_private_template_is_not_read_or_sent_to_model_by_another_company(self):
        saved=self.learn()
        self.assertNotIn(saved['template']['id'],[r['id'] for r in self.api('stranger','GET','/supplier-invoice-templates')])
        result,model=self.scan('stranger',dict(supplier='Unknown',items=[]))
        self.assertTrue(result['ok'],result)
        self.assertNotIn('PRIVATE-A material',str(model.call_args))

    def test_b_ocr_is_read_only_and_does_not_complete_supplier_requisites(self):
        sid=self.fixture['supplierId']
        self.sql("UPDATE suppliers SET kpp='',inn='7702222222' WHERE id=%s",(sid,))
        before=self.sql('SELECT to_jsonb(s) FROM suppliers s ORDER BY id')
        aliases=self.sql('SELECT to_jsonb(a) FROM supplier_aliases a ORDER BY id')
        result,_=self.scan('director',dict(supplier='OCR proposed name',supplierInn='7702222222',supplierKpp='770201001',items=[]))
        self.assertTrue(result['ok'],result)
        self.assertEqual(self.sql('SELECT to_jsonb(s) FROM suppliers s ORDER BY id'),before)
        self.assertEqual(self.sql('SELECT to_jsonb(a) FROM supplier_aliases a ORDER BY id'),aliases)
        self.assertEqual(result['data']['supplier'],'OCR proposed name')

    def test_c_learning_cannot_reference_supplier_outside_company(self):
        sid=self.sql("INSERT INTO suppliers(name,inn) VALUES('FOREIGN ONLY','7709999999') RETURNING id")[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id) VALUES(3,%s)',(sid,))
        before=self.sql('SELECT count(*) FROM supplier_invoice_templates')
        self.api('director','POST','/supplier-invoice-templates/learn',dict(supplierId=sid,supplierName='FOREIGN ONLY',items=[]),expected=403)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_invoice_templates'),before)

    def test_d_unowned_legacy_template_is_hidden(self):
        tid=self.legacy_id
        for actor in ('director','stranger'):
            self.assertNotIn(tid,[r['id'] for r in self.api(actor,'GET','/supplier-invoice-templates')])

    def test_e_model_ids_names_and_conflicting_inn_never_select_supplier(self):
        sid=self.fixture['supplierId']
        self.sql("UPDATE suppliers SET inn='7702222222' WHERE id=%s",(sid,))
        for payload in (dict(supplier='SCAN private supplier',supplierId=sid),
                        dict(supplier='SCAN private supplier',supplierId=sid,supplierInn='7700000000')):
            result,_=self.scan('director',dict(payload,items=[]))
            self.assertEqual(result['data']['recognition']['supplierId'],0)
            self.assertIsNone(result['data']['recognition']['templateId'])
        # The fixture supplier is legitimately shared; use a company-private identity.
        private=self.sql("INSERT INTO suppliers(name,inn) VALUES('Private legal supplier','7708888888') RETURNING id")[0][0]
        self.sql('INSERT INTO company_supplier_links(company_id,supplier_id) VALUES(2,%s)',(private,))
        result,_=self.scan('stranger',dict(supplier='Private legal supplier',supplierInn='7708888888',items=[]))
        self.assertEqual(result['data']['recognition']['supplierId'],0)

    def test_f_scoped_exact_inn_reuses_template_without_changing_any_template(self):
        saved=self.learn()
        self.sql("UPDATE suppliers SET inn='7702222222' WHERE id=%s",(self.fixture['supplierId'],))
        before=self.sql('SELECT to_jsonb(t) FROM supplier_invoice_templates t ORDER BY id')
        result,_=self.scan('director',dict(supplier='SCAN private supplier',supplierInn='7702222222',documentType='waybill',items=[]))
        self.assertEqual(result['data']['recognition']['templateId'],saved['template']['id'])
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM supplier_invoice_templates t ORDER BY id'),before)

    def test_g_forbidden_company_and_supplier_roles_never_invoke_model(self):
        with patch.object(self.main,'generate_yandex_parts') as model:
            self.api('director','POST','/scan-invoice',{'companyId':3,'image':'abc'},expected=403)
            self.api('director','POST','/scan-invoice',{'image':'abc'},expected=403,**{'X-Company-Id':'3'})
            self.api('supplier','POST','/scan-invoice',{'image':'abc'},expected=403)
            self.api('supplier','GET','/supplier-invoice-templates',expected=403)
            model.assert_not_called()

    def test_h_too_many_files_are_rejected_before_model(self):
        with patch.object(self.main,'generate_yandex_parts') as model:
            self.api('director','POST','/scan-invoice',{'images':['abc']*9},expected=422)
            model.assert_not_called()

    def test_i_company_templates_with_same_name_are_independent(self):
        first=self.learn()
        second=self.api('stranger','POST','/supplier-invoice-templates/learn',{
            'supplierName':'SCAN private supplier','documentType':'waybill','items':[{'name':'PRIVATE-B material'}]})
        self.assertNotEqual(first['template']['id'],second['template']['id'])
        again=self.learn()
        self.assertEqual(first['template']['id'],again['template']['id'])
        self.assertNotIn(second['template']['id'],[x['id'] for x in self.api('director','GET','/supplier-invoice-templates')])

    def test_j_migration_preserves_legacy_but_blocks_old_unscoped_writer(self):
        import psycopg2
        self.assertEqual(self.sql('SELECT company_id,supplier_name FROM supplier_invoice_templates WHERE id=%s',(self.legacy_id,)),[(None,'LEGACY PRIVATE')])
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql("INSERT INTO supplier_invoice_templates(supplier_key,supplier_name) VALUES('old-client','Old')")
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.sql('UPDATE supplier_invoice_templates SET usage_count=1 WHERE id=%s',(self.legacy_id,))

    def test_k_two_concurrent_learns_create_one_company_template(self):
        from concurrent.futures import ThreadPoolExecutor
        def learn(n):
            return self.api('director','POST','/supplier-invoice-templates/learn',{
                'supplierName':'Concurrent template','documentType':'waybill','number':str(n),'items':[]})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(learn,(1,2)))
        self.assertEqual(results[0]['template']['id'],results[1]['template']['id'])
        self.assertEqual(self.sql("SELECT count(*) FROM supplier_invoice_templates WHERE company_id=2 AND supplier_name='Concurrent template'"),[(1,)])

    def test_l_company_selection_checks_effective_role_and_owns_template(self):
        uid=self.fixture['users']['director']['id']
        self.sql("INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default) VALUES(%s,3,1,'мастер',TRUE,FALSE)",(uid,))
        try:
            self.api('director','GET','/supplier-invoice-templates',expected=403,**{'X-Company-Id':'3'})
            self.sql("UPDATE user_company_roles SET role='директор' WHERE user_id=%s AND company_id=3",(uid,))
            data=self.api('director','GET','/supplier-invoice-templates',**{'X-Company-Id':'3'})
            self.assertNotIn('PRIVATE-A material',str(data))
            self.assertIn('PRIVATE-B material',str(data))
        finally:
            self.sql('DELETE FROM user_company_roles WHERE user_id=%s AND company_id=3',(uid,))
