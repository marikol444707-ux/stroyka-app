"""Real SQL ownership checks; actors below represent already verified memberships."""
import importlib
import os
import unittest
from fastapi import HTTPException
from backend.features.prescriptions.routes import register_prescriptions_module
from backend.features.prescriptions.test_routes import FakeApp
from backend.features.customer_cabinet.record_scope import RecordScope

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class PrescriptionPostgresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        from backend.features.supplier_access.test_postgres_chain_support import connection_settings, _assert_empty_database
        cls.settings=connection_settings(os.environ)
        cls.connect=staticmethod(lambda:psycopg2.connect(**cls.settings))
        conn=cls.connect();_assert_empty_database(conn,cls.settings)
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE projects(id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, name TEXT, UNIQUE(id,company_id)); CREATE TABLE users(id INTEGER PRIMARY KEY)')
            cur.execute('''CREATE TABLE prescriptions(id SERIAL PRIMARY KEY,project_name TEXT,number TEXT,
                issued_by TEXT,issued_by_role TEXT,violation TEXT,deadline TEXT,responsible TEXT,status TEXT,
                photo_url TEXT,fix_photo_url TEXT,fix_notes TEXT)''')
            cur.execute('''CREATE TABLE warranty_defects(id SERIAL PRIMARY KEY,project_name TEXT,description TEXT,
                found_at DATE,reported_by TEXT,reporter_phone TEXT,status TEXT,assigned_to TEXT,fix_notes TEXT,
                fixed_at DATE,photo_url TEXT,severity TEXT,created_at TIMESTAMP DEFAULT NOW())''')
            cur.execute('CREATE TABLE project_documents(id SERIAL PRIMARY KEY,project_name TEXT,side TEXT,\n                doc_type TEXT,number TEXT,doc_date DATE,counterparty TEXT,sign_status TEXT,scan_url TEXT,\n                amount NUMERIC,notes TEXT,uploaded_by TEXT,created_at TIMESTAMP DEFAULT NOW());\n                CREATE TABLE project_letters(id SERIAL PRIMARY KEY,project_name TEXT,side TEXT,direction TEXT,\n                subject TEXT,body TEXT,counterparty TEXT,letter_date DATE,file_url TEXT,author TEXT,status TEXT,\n                created_at TIMESTAMP DEFAULT NOW())')
            cur.execute(importlib.import_module('migrations.versions.0040_customer_record_owners').SCHEMA_SQL)
            cur.execute("INSERT INTO projects VALUES(1,1,'Лицей'),(2,2,'Лицей'),(3,1,'Лицей'); INSERT INTO users VALUES(10),(11),(12)")
        conn.commit();conn.close()

    def setUp(self):
        self.customer={'id':10,'companyId':1,'role':'заказчик','name':'Клиент','projectId':1,'assignedProjects':['Лицей']}
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('TRUNCATE prescriptions,warranty_defects,project_documents,project_letters RESTART IDENTITY')
            for company,project,author,text in [(1,1,10,'Моё'),(1,1,11,'Другой заказчик'),(2,2,12,'Другая компания'),(1,3,10,'Другой объект')]:
                cur.execute("INSERT INTO prescriptions(project_name,company_id,project_id,created_by_user_id,violation,status,fix_notes) VALUES('Лицей',%s,%s,%s,%s,'Открыто','Ответ подрядчика')",(company,project,author,text))
        conn.commit();conn.close()
        scope=RecordScope(self.connect,lambda cur,user,*args,**kwargs:user,
                          lambda user,context:[context],lambda actor:None if actor.get('role')=='директор' else actor.get('assignedProjects',[]))
        self.scope=scope
        self.app=FakeApp()
        register_prescriptions_module(self.app,{'require_roles':lambda *roles:lambda:None, 'get_current_user':lambda:self.customer,
            'read_roles':('заказчик','директор','мастер'), 'write_roles':('директор',),
            'worker_execution_roles':('мастер',), 'record_scope':scope})

    def call(self, method,path,**kwargs):
        return self.app.routes[(method,path)](current_user=self.customer,**kwargs)

    def test_only_own_author_project_and_company_are_visible(self):
        result=self.call('GET','/prescriptions')
        self.assertEqual([row['violation'] for row in result],['Моё'])
        self.assertEqual((result[0]['companyId'],result[0]['projectId']),(1,1))

    def test_create_forces_owner_actor_and_initial_state(self):
        result=self.call('POST','/prescriptions',data={'projectId':1,'projectName':'Лицей','companyId':2,
            'violation':'Новое','createdByUserId':12,'issuedBy':'Чужой','status':'Закрыто','responsible':'Назначен'})
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('SELECT company_id,project_id,created_by_user_id,issued_by,status,responsible FROM prescriptions WHERE id=%s',(result['id'],))
            self.assertEqual(cur.fetchone(),(1,1,10,'Клиент','Открыто',''))
        conn.close()

    def test_customer_cannot_mutate_same_role_other_author(self):
        with self.assertRaises(HTTPException) as error:
            self.call('PUT','/prescriptions/{id}',id=2,data={'status':'Закрыто'})
        self.assertEqual(error.exception.status_code,403)

    def test_direct_ids_cannot_cross_company_or_project(self):
        for record_id in (3,4):
            with self.assertRaises(HTTPException) as error:
                self.call('PUT','/prescriptions/{id}',id=record_id,data={'status':'Закрыто'})
            self.assertEqual(error.exception.status_code,404)

    def test_customer_status_update_preserves_contractor_evidence(self):
        self.call('PUT','/prescriptions/{id}',id=1,data={'status':'Закрыто'})
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('SELECT status,fix_notes FROM prescriptions WHERE id=1')
            self.assertEqual(cur.fetchone(),('Закрыто','Ответ подрядчика'))
        conn.close()
        with self.assertRaises(HTTPException):
            self.call('PUT','/prescriptions/{id}',id=1,data={'status':'Открыто','fixNotes':'Подмена'})

    def test_revoked_assignment_cannot_read_or_create(self):
        self.customer['assignedProjects']=[]
        self.assertEqual(self.call('GET','/prescriptions'),[])
        with self.assertRaises(HTTPException):
            self.call('POST','/prescriptions',data={'projectId':1,'violation':'Новое'})

    def test_ambiguous_legacy_name_does_not_grant_both_projects(self):
        del self.customer['projectId']
        self.assertEqual(self.call('GET','/prescriptions'),[])
        with self.assertRaises(HTTPException):
            self.call('POST','/prescriptions',data={'projectName':'Лицей','violation':'Новое'})

    def warranty_app(self):
        from backend.features.warranty_defects.routes import register_warranty_defects_module
        app=FakeApp()
        register_warranty_defects_module(app,{'get_db':self.connect, 'require_roles':lambda *roles:lambda:None, 'get_current_user':lambda:self.customer,
            'read_roles':('заказчик','директор'), 'write_roles':('директор',),'leadership_roles':('директор',),
            'record_scope':self.scope, 'visible_project_names':lambda user:user.get('assignedProjects',[]),
            'user_project_names':lambda user:user.get('assignedProjects',[]),
            'require_project_access':lambda *args:None, 'require_row_project_access':lambda *args:None})
        return app

    def test_warranty_creation_cannot_self_approve_or_spoof_author(self):
        app=self.warranty_app()
        result=app.routes[('POST','/warranty-defects')](data={'projectId':1,'projectName':'Лицей',
            'description':'Трещина','reportedBy':'Чужой','status':'Устранён','assignedTo':'Другой','companyId':2},current_user=self.customer)
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('SELECT company_id,project_id,created_by_user_id,reported_by,status,assigned_to FROM warranty_defects WHERE id=%s',(result['id'],))
            self.assertEqual(cur.fetchone(),(1,1,10,'Клиент','Открыт',''))
        conn.close()

    def test_warranty_same_name_does_not_expose_other_owners(self):
        conn=self.connect()
        with conn.cursor() as cur:
            for company,project,author in [(1,1,10),(1,1,11),(2,2,12),(1,3,10)]:
                cur.execute("INSERT INTO warranty_defects(project_name,company_id,project_id,created_by_user_id,description) VALUES('Лицей',%s,%s,%s,'Трещина')",(company,project,author))
        conn.commit();conn.close()
        result=self.warranty_app().routes[('GET','/warranty-defects')](current_user=self.customer)
        self.assertEqual(len(result),1)
        self.assertEqual((result[0]['companyId'],result[0]['projectId']),(1,1))

    def documents_app(self):
        from backend.features.project_records.owned_routes import register_owned_record_routes
        app=FakeApp()
        register_owned_record_routes(app,{'require_roles':lambda *roles:lambda:None, 'get_current_user':lambda:self.customer,
            'read_roles':('заказчик','директор'),'write_roles':('директор',),
            'worker_execution_roles':('мастер',),'record_scope':self.scope})
        return app

    def test_documents_and_letters_scope_company_project_and_customer_side(self):
        conn=self.connect()
        with conn.cursor() as cur:
            for company,project,side in [(1,1,'customer'),(2,2,'customer'),(1,3,'customer'),(1,1,'contractor')]:
                cur.execute("INSERT INTO project_documents(project_name,company_id,project_id,side,notes) VALUES('Лицей',%s,%s,%s,'Внутренняя заметка')",(company,project,side))
                cur.execute("INSERT INTO project_letters(project_name,company_id,project_id,side,body) VALUES('Лицей',%s,%s,%s,'Письмо')",(company,project,side))
            cur.execute("INSERT INTO project_documents(project_name,side) VALUES('Лицей','customer')")
        conn.commit();conn.close()
        app=self.documents_app()
        for path in ('/project-documents','/project-letters'):
            result=app.routes[('GET',path)](_current_user=self.customer)
            self.assertEqual(len(result),1)
            self.assertEqual((result[0]['companyId'],result[0]['projectId']),(1,1))
            self.assertNotIn('notes',result[0])

    def test_document_writer_cannot_mutate_other_company_direct_id(self):
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO project_documents(company_id,project_id,project_name) VALUES(2,2,'Лицей') RETURNING id")
            record_id=cur.fetchone()[0]
        conn.commit();conn.close()
        actor=dict(self.customer,role='директор')
        with self.assertRaises(HTTPException) as error:
            self.documents_app().routes[('PUT','/project-documents/{id}')](id=record_id,data={'notes':'Подмена'},_current_user=actor)
        self.assertEqual(error.exception.status_code,404)

    def test_document_creation_stamps_canonical_owner_and_actor(self):
        actor=dict(self.customer,role='директор')
        result=self.documents_app().routes[('POST','/project-documents')](
            data={'projectId':1,'projectName':'Лицей','companyId':2,'uploadedBy':'Чужой'},_current_user=actor)
        conn=self.connect()
        with conn.cursor() as cur:
            cur.execute('SELECT company_id,project_id,created_by_user_id,uploaded_by FROM project_documents WHERE id=%s',(result['id'],))
            self.assertEqual(cur.fetchone(),(1,1,10,'Клиент'))
        conn.close()

    def test_http_uses_selected_membership_instead_of_default_role(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from backend.features.project_records.owned_routes import register_owned_record_routes
        from backend.features.prescriptions.routes import register_prescriptions_module
        from backend.features.warranty_defects.routes import register_warranty_defects_module
        def raw_role_dependency(*roles):
            def dependency():
                if self.customer['role'] not in roles:
                    raise HTTPException(status_code=403,detail='Wrong default role')
                return self.customer
            return dependency
        def resolve(cur,user,*args,**kwargs):
            company=int(kwargs.get('x_company_id') or 1)
            return dict(user,companyId=company,projectId=company,
                        role='директор' if company==1 else 'заказчик')
        scope=RecordScope(self.connect,resolve,lambda user,context:[context],
                          lambda actor:None if actor['role']=='директор' else actor['assignedProjects'])
        app=FastAPI()
        deps={'require_roles':raw_role_dependency,'get_current_user':lambda:self.customer,
              'read_roles':('заказчик','директор'),'write_roles':('директор',),
              'worker_execution_roles':(),'leadership_roles':('директор',),'record_scope':scope}
        register_owned_record_routes(app,deps)
        register_prescriptions_module(app,deps)
        register_warranty_defects_module(app,deps)
        with TestClient(app) as client:
            response=client.post('/project-documents',headers={'X-Company-Id':'1'},json={'projectId':1})
            self.assertEqual(response.status_code,200,response.text)
            # Same authenticated person, selected company role does not permit document writing.
            response=client.post('/project-documents',headers={'X-Company-Id':'2'},json={'projectId':2})
            self.assertEqual(response.status_code,403,response.text)
            # Do not let a privileged default role override a customer membership either.
            self.customer['role']='директор'
            response=client.post('/project-documents',headers={'X-Company-Id':'2'},json={'projectId':2})
            self.assertEqual(response.status_code,403,response.text)

    def test_crm_document_target_does_not_guess_between_duplicate_names(self):
        from backend.features.crm.document_transfer import document_transfer_project
        conn=self.connect()
        try:
            with conn.cursor() as cur:
                with self.assertRaises(HTTPException):
                    document_transfer_project(cur,{'companyId':1},{},{'projectName':'Лицей'})
                parent=document_transfer_project(cur,{'companyId':1,'projectId':1},{},{'projectName':'Лицей'})
                self.assertEqual(parent['id'],1)
                with self.assertRaises(HTTPException):
                    document_transfer_project(cur,{'companyId':1,'projectId':1},{},{'projectId':3})
                with self.assertRaises(HTTPException):
                    document_transfer_project(cur,{'companyId':1},{},{'projectId':2})
        finally:
            conn.rollback();conn.close()
