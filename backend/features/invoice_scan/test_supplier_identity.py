import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
from .supplier_identity import native_pdf_seller, template_matches_supplier

class SupplierIdentityTest(TestCase):
    def test_explicit_pdf_seller_not_shipper_or_buyer(self):
        text='Продавец    АО Тестовый продавец (2)\nАдрес адрес\nИНН/КПП продавца 1234567890/123456789 (2б)\nГрузоотправитель подразделение\nПокупатель ООО Другой'
        result=native_pdf_seller([SimpleNamespace(kind='text',value=text)])
        self.assertEqual(native_pdf_seller([SimpleNamespace(kind='text',value=text.replace('Продавец    ', 'документ  Продавец  '))]),result)
        self.assertEqual(result,{'supplier':'АО Тестовый продавец','supplierInn':'1234567890','supplierKpp':'123456789'})
        self.assertEqual(native_pdf_seller([SimpleNamespace(kind='text',value=text),SimpleNamespace(kind='text',value=text.replace('1234567890','1234567891'))]),{})
    def test_template_requires_legal_identity_and_same_card(self):
        supplier={'id':1,'inn':'1234567890'}
        self.assertTrue(template_matches_supplier({'supplierInn':'1234567890'},supplier,{'supplierId':1}))
        for payload,card in [({'supplierInn':'1234567891'},{'supplierId':1}),({'supplierInn':'1234567890'},{'supplierId':2}),({}, {'supplierId':1})]:
            self.assertFalse(template_matches_supplier(payload,supplier,card))
    def test_wrong_template_cannot_override_seller_and_scan_is_read_only(self):
        import psycopg2.extras
        path=Path(__file__).resolve().parents[2]/'main.py'
        node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='_apply_supplier_invoice_template_metadata')
        conn=Mock();cur=conn.cursor.return_value
        ns={'psycopg2':SimpleNamespace(extras=psycopg2.extras),'get_db':lambda:conn,
            '_scan_invoice_supplier_name':lambda p:p['supplier'],'_supplier_digits':lambda v:str(v or ''),
            '_supplier_find_match':Mock(return_value={'id':1,'name':'Правильный','inn':'1234567890'}),
            '_find_supplier_invoice_template':Mock(return_value=({'score':1,'row':{}},'')),
            '_supplier_invoice_template_row':lambda row:{'id':3,'supplierId':2,'supplierName':'Неправильный','templateName':'Тест'}}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<scan identity>','exec'),ns)
        result=ns['_apply_supplier_invoice_template_metadata']({'supplier':'Правильный','supplierInn':'1234567890','supplierId':2})
        self.assertEqual(result['supplier'],'Правильный');self.assertEqual(result['recognition']['supplierId'],1)
        self.assertEqual(result['recognition']['method'],'ai_ocr');conn.commit.assert_not_called();cur.execute.assert_not_called()
        conn.set_session.assert_called_once_with(readonly=True);conn.rollback.assert_called_once();self.assertNotIn('supplierId',ns['_supplier_find_match'].call_args.args[1])
        conn.reset_mock()
        ns['_supplier_invoice_template_row'] = lambda row: {'id':3,'supplierId':1,'supplierName':'Wrong learned display name','templateName':'Test'}
        result=ns['_apply_supplier_invoice_template_metadata']({'supplier':'Document seller','supplierInn':'1234567890'})
        self.assertEqual(result['supplier'],'Document seller')
        self.assertEqual(result['recognition']['supplierName'],'Document seller')
        self.assertEqual(result['recognition']['method'],'template')
        conn.commit.assert_not_called();cur.execute.assert_not_called()

