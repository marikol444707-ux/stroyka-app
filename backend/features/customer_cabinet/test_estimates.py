import copy
import unittest
from backend.features.customer_cabinet.estimates import customer_estimate_sections

class CustomerEstimateTest(unittest.TestCase):
    def test_internal_and_unknown_metadata_are_not_published(self):
        source = [{'id': 7, 'name': 'Отделка', 'internalNotes':'secret', 'items': [{
            'id': 9, 'name':'Стены','quantity':10,'unit':'м2','priceWork':100,'priceMaterial':20,
            'executionPricePerUnit':40,'internalPricePerUnit':30,'masterPricePerUnit':25,
            'priceBrigade':10,'futureInternalField':{'secret':123},'notes':'internal',
        }]}]
        original=copy.deepcopy(source)
        self.assertEqual(customer_estimate_sections(source), [{'id':7,'name':'Отделка','items':[{
            'id':9,'name':'Стены','quantity':10,'unit':'м2','priceWork':100,'priceMaterial':20}]}])
        self.assertEqual(source,original)

    def test_imported_customer_totals_and_adjustments_survive(self):
        rows=[{'name':'Импорт','items':[
            {'name':'Работа','type':'work','isImported':True,'totalWork':1000,'totalMaterial':300,'quantity':2},
            {'name':'Коррекция','type':'adjustment','itemType':'adjustment','isImported':True,'lineTotal':-50},
        ]}]
        self.assertEqual(customer_estimate_sections(rows),rows)

    def test_unexpected_nested_data_in_public_field_is_not_a_bypass(self):
        self.assertEqual(customer_estimate_sections([{'name':{'secret':2},'items':[
            None, 'invalid', {'name':'Работа','priceWork':{'secret':1}, 'quantity':[10]}]}]),
            [{'items':[{'name':'Работа'}]}])
        self.assertEqual(customer_estimate_sections(None),[])

class CustomerEstimateRouteTest(unittest.TestCase):
    """Execute the real list/detail bodies with controlled repository rows."""
    @classmethod
    def setUpClass(cls):
        import ast
        from pathlib import Path
        cls.path=Path(__file__).resolve().parents[2]/'main.py'
        cls.tree=ast.parse(cls.path.read_text())

    def response(self, name, role):
        import ast
        import json
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from backend.features.estimate_access import service
        sections=[{'name':'Отделка','items':[{'name':'Стена','quantity':10,'priceWork':100,'priceMaterial':20,'executionPricePerUnit':40,'internalNotes':'private'}]}]
        row=(7,1,'Лицей','Смета','1',json.dumps(sections),'Заказчик','Основная',False,'Активная',None,0,None,1)
        cur=Mock(); cur.fetchall.return_value=[row];cur.fetchone.return_value=row
        conn=Mock();conn.cursor.return_value=cur
        actor={'companyId':1,'role':role}
        names=[name,'_estimate_response_payload_from_row','_estimate_sections_total_for_summary','_estimate_item_total_for_summary']
        functions=[]
        for original in self.tree.body:
            if isinstance(original,ast.FunctionDef) and original.name in names:
                node=copy.deepcopy(original);node.decorator_list=[];node.returns=None
                for arg in node.args.args+node.args.kwonlyargs: arg.annotation=None
                if node.name==name:
                    node.args.defaults=[ast.Constant(None) for _ in node.args.defaults]
                functions.append(node)
        namespace={
            'get_db':lambda:conn,'psycopg2':SimpleNamespace(extras=SimpleNamespace(RealDictCursor=object)),
            '_resolve_work_company_context':lambda *a,**kw:{},'effective_company_actors':lambda *a:[actor],
            'PACKAGE_LIMIT_ROLES':(), 'WORKER_EXECUTION_ROLES':('мастер',),
            '_normalize_estimate_adjustment_rows':lambda value:(value,False),
            '_safe_float':lambda value:float(value or 0),
        }
        exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),str(self.path),'exec'),namespace)
        with patch.object(service,'estimate_visibility_filter',return_value=('TRUE',[])), patch.object(service,'resolve_estimate_parent',return_value={'id':1,'companyId':1}):
            kwargs={'current_user':actor}
            if name=='get_estimate_detail': kwargs['id']=7
            else: kwargs['summary']=False
            result=namespace[name](**kwargs)
        return result[0] if isinstance(result,list) else result

    def test_customer_list_and_detail_exclude_internal_rates_preserve_total(self):
        for name in ('get_estimates','get_estimate_detail'):
            with self.subTest(route=name):
                result=self.response(name,'заказчик')
                item=result['sections'][0]['items'][0]
                self.assertNotIn('executionPricePerUnit',item)
                self.assertNotIn('internalNotes',item)
                self.assertEqual(result['total'],1200)

    def test_director_internal_rates_are_preserved(self):
        for name in ('get_estimates','get_estimate_detail'):
            with self.subTest(route=name):
                result=self.response(name,'директор')
                self.assertEqual(result['sections'][0]['items'][0]['executionPricePerUnit'],40)
                self.assertEqual(result['total'],1200)
