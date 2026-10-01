import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import HTTPException

from backend.features.project_records.owned_routes import register_owned_record_routes


class App:
    def __init__(self): self.routes = {}
    def get(self, path): return self._route('GET', path)
    def post(self, path): return self._route('POST', path)
    def put(self, path): return self._route('PUT', path)
    def delete(self, path): return self._route('DELETE', path)
    def _route(self, method, path):
        def register(handler): self.routes[(method, path)] = handler; return handler
        return register


class Cursor:
    def __init__(self, fetchone=()): self.rows=list(fetchone); self.calls=[]
    def execute(self, sql, params=()): self.calls.append((' '.join(sql.split()), tuple(params)))
    def fetchone(self): return self.rows.pop(0) if self.rows else None


class Scope:
    def __init__(self, cursor): self.cursor=cursor
    @contextmanager
    def transaction(self, *_args, **_kwargs):
        yield self.cursor, [{'id':5,'companyId':3,'role':'директор','name':'Директор'}]
    def parent(self, *_args): return {'id':17,'companyId':3,'name':'Лицей'}
    def record(self, *_args): return (17,3,5)
    def visible(self, *_args): return ('p.company_id=%s',[3])


DOCUMENT=(40,3,17,'customer','Договор','15','2026-10-01','/tenant-files/77/content',
          'Подписан',1,None,None,None,'Лицей',8)
COMPANY=(3,'ООО Исполнитель','2611008712','261101001','1234567890123','Ставрополь','',
         '+7','office@example.test','Петров П.П.','Директор','Устава','Банк','044525104',
         '40702810309500007753','30101810745374525104')
CUSTOMER=(8,3,'ООО Заказчик','+7','client@example.test','2632090186','263201001',
          '1092632000001','Пятигорск','','Иванов И.И.','Директор','Устава','Банк 2',
          '044525411','40702810415590000143','30101810145250000411')
FILE=(77,3,17,'active')


def build(cursor):
    app=App()
    register_owned_record_routes(app,{
        'record_scope':Scope(cursor),'get_current_user':lambda:{},
        'read_roles':('директор',),'write_roles':('директор',),'worker_execution_roles':(),
    })
    return app


class CustomerContractOwnedRoutesTest(unittest.TestCase):
    def test_signed_contract_create_freezes_parties_in_same_transaction(self):
        cursor=Cursor([(40,),DOCUMENT,FILE,COMPANY,CUSTOMER])
        app=build(cursor)
        result=app.routes[('POST','/project-documents')]({
            'projectId':17,'side':'customer','docType':'Договор','number':'15',
            'docDate':'2026-10-01','counterparty':'ООО Заказчик','signStatus':'Подписан',
            'scanUrl':'/tenant-files/77/content',
        },_current_user={},request=SimpleNamespace(headers={}))
        self.assertEqual(result,{'ok':True,'id':40})
        self.assertTrue(any('party_snapshot_json=%s::jsonb' in sql for sql,_ in cursor.calls))

    def test_frozen_contract_requires_a_new_version_for_party_changes(self):
        cursor=Cursor([({'schemaVersion':1},)])
        app=build(cursor)
        with self.assertRaises(HTTPException) as raised:
            app.routes[('PUT','/project-documents/{id}')](
                40,{'counterparty':'Другое лицо'},_current_user={},request=SimpleNamespace(headers={}))
        self.assertEqual(raised.exception.status_code,409)
        self.assertIn('новую версию',raised.exception.detail)

    def test_new_version_keeps_contract_identity_and_increments_version(self):
        source={
            'project_id':17,'company_id':3,'side':'customer','doc_type':'Договор',
            'number':'15','counterparty':'ООО Заказчик','contract_version':1,
            'party_snapshot_json':{'schemaVersion':1},'customer_client_id':8,'project_client_id':8,
        }
        draft=(41,3,17,'customer','Договор','15','2026-10-02','',
               'Не подписан',2,40,None,None,'Лицей',8)
        cursor=Cursor([source,(41,),draft])
        app=build(cursor)
        result=app.routes[('POST','/project-documents')]({
            'projectId':17,'revisesDocumentId':40,'side':'customer','docType':'Подмена',
            'number':'ДРУГОЙ','docDate':'2026-10-02','counterparty':'Подмена',
            'signStatus':'Не подписан','scanUrl':'',
        },_current_user={},request=SimpleNamespace(headers={}))
        self.assertEqual(result,{'ok':True,'id':41})
        insert=next(call for call in cursor.calls if call[0].startswith('INSERT INTO project_documents'))
        self.assertEqual(insert[1][-2:],(2,40))
        self.assertIn('Договор',insert[1])
        self.assertNotIn('ДРУГОЙ',insert[1])


if __name__=='__main__': unittest.main()
