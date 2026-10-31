"""Regression tests with SQL recording doubles only; no HTTP or database."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from backend.features.customer_cabinet.record_scope import project_visibility
from .scope import owned_query, require_record
from .user_scope import user_visibility, require_user
from backend.features.document_versions.routes import visible_snapshot
from backend.features.supplier_access.subscription_scope import is_owned_supplier_profile_mutation

class Scope:
    def visible(self,actors,roles):
        return project_visibility(actors,roles,lambda actor:None)
class Cursor:
    def __init__(self,row=None): self.row=row;self.calls=[]
    def execute(self,sql,params): self.calls.append((sql,params))
    def fetchone(self): return self.row

class OwnedScopeTests(unittest.TestCase):
    def test_fixed_identity_join_and_company_parameter(self):
        query,params=owned_query(Scope(),[{'companyId':7,'role':'директор'}],['директор'],'contracts','r.id',record_id=10,lock=True)
        self.assertIn('p.id=r.project_id AND p.company_id=r.company_id',query)
        self.assertIn('p.company_id=%s',query)
        self.assertEqual(params,[7,10])
        self.assertIn('FOR UPDATE OF r,p',query)
    def test_missing_owned_record_stops_before_mutation(self):
        cur=Cursor()
        with self.assertRaises(HTTPException) as raised:
            require_record(cur,Scope(),[{'companyId':7,'role':'директор'}],['директор'],'supervisor_acts',10)
        self.assertEqual(raised.exception.status_code,404)
        self.assertEqual(len(cur.calls),1)
    def test_owned_record_positive_control(self):
        cur=Cursor((10,))
        require_record(cur,Scope(),[{'companyId':7,'role':'директор'}],['директор'],'supervisor_acts',10)
        self.assertEqual(cur.calls[0][1],[7,10])
    def test_missing_membership_never_generates_broad_query(self):
        query,params=owned_query(Scope(),[],['директор'],'contracts','r.id')
        self.assertIn('WHERE FALSE',query);self.assertEqual(params,[])
    def test_user_visibility_never_falls_back_after_revocation(self):
        query,params=user_visibility([{'companyId':7}])
        self.assertIn('m.company_id=%s',query)
        self.assertIn('COALESCE(m.active,TRUE)',query)
        self.assertIn('NOT EXISTS (SELECT 1 FROM user_company_roles any_membership',query)
        self.assertEqual(params,[7,7])
    def test_foreign_user_blocks_before_upsert(self):
        cur=Cursor()
        with self.assertRaises(HTTPException) as error: require_user(cur,[{'companyId':7}],99)
        self.assertEqual(error.exception.status_code,404)
        self.assertEqual(len(cur.calls),1)
    def test_external_snapshot_excludes_private_and_nested_fields(self):
        snapshot={'workName':'Тест','amount':900,'passport':'secret','description':{'amount':900}}
        self.assertEqual(visible_snapshot(snapshot,True),{'workName':'Тест'})
        self.assertEqual(visible_snapshot(snapshot,False),snapshot)
    def test_supplier_private_archive_exemption_has_exact_methods_and_paths(self):
        supplier={'role':'поставщик'}
        self.assertTrue(is_owned_supplier_profile_mutation(None,supplier,'POST','/supplier-documents'))
        self.assertTrue(is_owned_supplier_profile_mutation(None,supplier,'DELETE','/supplier-documents/9'))
        self.assertFalse(is_owned_supplier_profile_mutation(None,{'role':'мастер'},'DELETE','/supplier-documents/9'))
        self.assertFalse(is_owned_supplier_profile_mutation(None,supplier,'DELETE','/supplier-documents/9/files'))
    def test_forward_guard_retains_credit_refund_and_date_semantics(self):
        path=Path(__file__).resolve().parents[3]/'migrations/versions/0105_settlement_cash_guard.py'
        spec=importlib.util.spec_from_file_location('guard_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        statements=[]
        with patch.object(module.op,'execute',side_effect=statements.append): module.upgrade()
        sql=' '.join(statements)
        self.assertIn('supplier_settlement_cash(NEW.kind,NEW.amount,original.kind)',sql)
        self.assertIn("original.kind NOT IN ('payment','refund','credit')",sql)
        self.assertIn('payment.date::DATE',sql)
        self.assertIn('Credit must not create cash',sql)

class RoutesOwnershipTests(unittest.TestCase):
    def test_supervisor_update_denied_before_write_and_positive_control(self):
        from backend.features.supervisor_acts.routes import register_supervisor_acts_module
        from backend.features.rooms.test_routes import FakeApp, FakeCursor, FakeConnection
        from .testing import FakeScope
        for allowed in (False,True):
            cursor=FakeCursor(fetchone_results=[(9,)] if allowed else [])
            connection=FakeConnection(cursor)
            app=FakeApp()
            register_supervisor_acts_module(app,{'record_scope':FakeScope(cursor,connection),'get_current_user':lambda:{},
                'get_db':lambda:connection,'require_roles':lambda *args:lambda:None,'read_roles':['директор'],'write_roles':['директор'],
                'visible_project_names':lambda actor:None,'require_project_access':lambda *args:None,'require_row_project_access':lambda *args:None})
            call=lambda:app.routes[('PUT','/supervisor-acts/{id}')](9,{'status':'Закрыт'},current_user={})
            if allowed:
                call();self.assertTrue(connection.committed)
                self.assertTrue(cursor.calls[-1][0].startswith('UPDATE supervisor_acts'))
            else:
                with self.assertRaises(HTTPException):call()
                self.assertEqual(len(cursor.calls),1);self.assertFalse(connection.committed)
    def test_contract_create_binds_project_and_checks_user_before_insert(self):
        from backend.features.contracts.routes import register_contracts_module, ContractModel
        from backend.features.rooms.test_routes import FakeApp, FakeCursor, FakeConnection
        from .testing import FakeScope
        for allowed in (False,True):
            cursor=FakeCursor(fetchone_results=[(5,),(9,'Активен')] if allowed else [])
            connection=FakeConnection(cursor);app=FakeApp()
            register_contracts_module(app,{'record_scope':FakeScope(cursor,connection),'get_current_user':lambda:{},
                'contract_roles':['директор'],'create_roles':['директор'],'delete_roles':['директор'],'worker_execution_roles':['мастер']})
            call=lambda:app.routes[('POST','/contracts')](ContractModel(masterId=5,masterName='Тест',contractNumber='1',project='Учебный объект'),_current_user={})
            if allowed:
                result=call();self.assertEqual(result['company_id'],3);self.assertEqual(result['status'],'Активен')
                self.assertEqual(cursor.calls[-1][1][:2],(3,7));self.assertTrue(connection.committed)
            else:
                with self.assertRaises(HTTPException):call()
                self.assertEqual(len(cursor.calls),1);self.assertFalse(connection.committed)
