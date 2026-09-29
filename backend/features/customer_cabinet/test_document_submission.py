import os
import unittest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from .record_scope import RecordScope
from .document_submission import register_customer_file_submission
from ..supplier_deal_parties.test_postgres import PartiesPostgresTest

@unittest.skipUnless(os.getenv('RUN_SUPPLIER_DEAL_PG_TESTS')=='1','isolated local PostgreSQL required')
class CustomerFileSubmissionTest(unittest.TestCase):
    def setUp(self):
        PartiesPostgresTest.setUp(self)
        with self.conn.cursor() as cur:
            cur.execute('CREATE TEMP TABLE projects(id INT PRIMARY KEY,company_id INT,name TEXT)')
            cur.execute("INSERT INTO projects VALUES(1,12,'Same name'),(2,99,'Same name'),(3,12,'Same name')")
            cur.execute('''CREATE TEMP TABLE file_ownership(id INT PRIMARY KEY,company_id INT,project_id INT,
                uploaded_by_id INT,context TEXT,deletion_status TEXT,retained_at TIMESTAMPTZ)''')
            cur.execute("""INSERT INTO file_ownership VALUES(1,12,1,8,'customer-request','active',NULL),
                (2,99,2,8,'customer-request','active',NULL),(3,12,1,9,'customer-request','active',NULL),
                (4,12,3,8,'customer-request','active',NULL),(5,12,1,8,'general','active',NULL),
                (6,12,1,8,'customer-request','deleted',NULL)""")
            cur.execute('''CREATE TEMP TABLE project_letters(id SERIAL PRIMARY KEY,project_name TEXT,company_id INT,
                project_id INT,created_by_user_id INT,side TEXT,direction TEXT,subject TEXT,body TEXT,
                counterparty TEXT,letter_date DATE,file_url TEXT,author TEXT,status TEXT,created_at TIMESTAMPTZ DEFAULT NOW())''')
        self.user.update(role='заказчик',projectId=1,assignedProjects=['Same name'])
        def context(cur,user,*args,**kwargs):
            if kwargs.get('x_company_id') != str(user['companyId']):raise HTTPException(403,'Company mismatch')
            return user
        scope=RecordScope(self.deps['get_db'],context,lambda user,ctx:[ctx],lambda actor:None if actor.get('role')=='директор' else actor.get('assignedProjects',[]))
        app=FastAPI();register_customer_file_submission(app,scope,lambda:self.user)
        from ..project_records.owned_routes import register_owned_record_routes
        register_owned_record_routes(app,{'record_scope':scope,'get_current_user':lambda:self.user,
            'read_roles':('директор','заказчик'),'write_roles':('директор',),'worker_execution_roles':()})
        self.client=TestClient(app)
        self.body={'projectId':1,'fileId':1,'subject':'Чертёж','body':'Комментарий'}

    def send(self,**changes):
        return self.client.post('/customer-files/send',json={**self.body,**changes},headers={'X-Company-Id':'12','X-Company-Mode':'company'})

    def test_publishes_incoming_once_and_retains_original(self):
        first=self.send();self.assertEqual(first.status_code,200,first.text)
        second=self.send();self.assertEqual(second.json(),first.json())
        with self.conn.cursor() as cur:
            cur.execute('SELECT side,direction,status,file_url,company_id,project_id FROM project_letters')
            self.assertEqual(cur.fetchall(),[('customer','incoming','Получено','/tenant-files/1/content',12,1)])
            cur.execute('SELECT retained_at IS NOT NULL FROM file_ownership WHERE id=1');self.assertTrue(cur.fetchone()[0])
        self.assertEqual(self.send(subject='Changed').status_code,409)

    def test_sent_file_appears_in_both_project_libraries(self):
        record=self.send().json()
        def letters():return self.client.get('/project-letters',headers={'X-Company-Id':str(self.user['companyId'])}).json()
        self.assertEqual([row['id'] for row in letters()],[record['id']])
        self.user.update(role='директор')
        rows=letters();self.assertEqual(rows[0]['fileUrl'],'/tenant-files/1/content')
        self.assertEqual(rows[0]['direction'],'incoming')
        self.user.update(companyId=99,projectId=2)
        self.assertEqual(letters(),[])

    def test_foreign_other_author_other_project_private_deleted_file_denied(self):
        for file_id in (2,3,4,5,6,999):
            response=self.send(fileId=file_id);self.assertEqual(response.status_code,403,response.text)
        with self.conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM project_letters');self.assertEqual(cur.fetchone()[0],0)

    def test_scope_role_and_assignment_enforced(self):
        self.assertEqual(self.send(projectId=2).status_code,404)
        self.assertEqual(self.send(projectId=3,fileId=4).status_code,403)
        self.assertEqual(self.client.post('/customer-files/send',json=self.body,headers={'X-Company-Id':'99'}).status_code,403)
        self.user['role']='директор';self.assertEqual(self.send().status_code,403)

    def test_no_financial_or_status_fields_and_empty_subject(self):
        for changes in ({'subject':'  '},{'status':'Подписан'},{'amount':100},{'companyId':99},{'fileId':True}):
            response=self.send(**changes);self.assertEqual(response.status_code,422,response.text)
