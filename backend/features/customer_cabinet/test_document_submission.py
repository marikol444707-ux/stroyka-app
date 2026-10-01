import os
import unittest
from uuid import uuid4
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
            cur.execute('CREATE TEMP TABLE projects(id INT PRIMARY KEY,company_id INT,name TEXT,client_id INT)')
            cur.execute("INSERT INTO projects VALUES(1,12,'Same name',21),(2,99,'Same name',22),(3,12,'Same name',23)")
            cur.execute('''ALTER TABLE companies ADD COLUMN IF NOT EXISTS inn TEXT;
                ALTER TABLE companies ADD COLUMN IF NOT EXISTS kpp TEXT;
                ALTER TABLE companies ADD COLUMN IF NOT EXISTS ogrn TEXT;
                ALTER TABLE companies ADD COLUMN IF NOT EXISTS legal_address TEXT;
                ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone TEXT;
                ALTER TABLE companies ADD COLUMN IF NOT EXISTS email TEXT''')
            cur.execute("UPDATE companies SET short_name='C12',inn='1200000000' WHERE id=12")
            cur.execute("UPDATE companies SET short_name='C99',inn='9900000000' WHERE id=99")
            cur.execute('''CREATE TEMP TABLE company_requisites(id SERIAL PRIMARY KEY,company_id INT,full_name TEXT,
                short_name TEXT,inn TEXT,kpp TEXT,ogrn TEXT,legal_address TEXT,phone TEXT,email TEXT)''')
            cur.execute("INSERT INTO company_requisites(company_id,full_name,short_name,inn,email) VALUES(12,'ООО Стройка 12','Стройка 12','1212121212','office@12.test')")
            cur.execute('''CREATE TEMP TABLE clients(id INT PRIMARY KEY,company_id INT,name TEXT,phone TEXT,email TEXT,
                status TEXT,inn TEXT,kpp TEXT,ogrn TEXT,legal_address TEXT)''')
            cur.execute("INSERT INTO clients VALUES(21,12,'Лицей №4','+70000000001','client@12.test','Активен','2121212121','','','Адрес заказчика'),(22,99,'Чужой заказчик','','','Активен','','','',''),(23,12,'Другой заказчик','','','Активен','','','','')")
            cur.execute('''CREATE TEMP TABLE file_ownership(id INT PRIMARY KEY,company_id INT,project_id INT,
                uploaded_by_id INT,context TEXT,deletion_status TEXT,retained_at TIMESTAMPTZ)''')
            cur.execute("""INSERT INTO file_ownership VALUES(1,12,1,8,'customer-request','active',NULL),
                (2,99,2,8,'customer-request','active',NULL),(3,12,1,9,'customer-request','active',NULL),
                (4,12,3,8,'customer-request','active',NULL),(5,12,1,8,'general','active',NULL),
                (6,12,1,8,'customer-request','deleted',NULL),
                (11,12,1,3,'project-letters','active',NULL),(12,99,2,3,'project-letters','active',NULL),
                (13,12,1,9,'project-letters','active',NULL),(14,12,3,3,'project-letters','active',NULL),
                (15,12,1,3,'general','active',NULL),(16,12,1,3,'project-letters','deleted',NULL)""")
            cur.execute('''CREATE TEMP TABLE project_letters(id SERIAL PRIMARY KEY,project_name TEXT,company_id INT,
                project_id INT,created_by_user_id INT,side TEXT,direction TEXT,subject TEXT,body TEXT,
                counterparty TEXT,letter_date DATE,file_url TEXT,author TEXT,status TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),
                correction_reason TEXT,correction_requested_at TIMESTAMPTZ,correction_requested_by_id INT,
                correction_requested_by_name TEXT,corrected_by_letter_id INT,replaces_letter_id INT UNIQUE,
                delivery_status TEXT NOT NULL DEFAULT 'sent',published_at TIMESTAMPTZ,
                published_by_id INT,published_by_name TEXT,client_request_id UUID,
                party_snapshot_json JSONB,party_snapshot_hash CHAR(64),party_snapshot_frozen_at TIMESTAMPTZ,
                customer_client_id INT,
                UNIQUE(company_id,client_request_id))''')
        self.user.update(role='заказчик',projectId=1,assignedProjects=['Same name'])
        def context(cur,user,*args,**kwargs):
            if kwargs.get('x_company_id') != str(user['companyId']):raise HTTPException(403,'Company mismatch')
            return user
        scope=RecordScope(self.deps['get_db'],context,lambda user,ctx:[ctx],lambda actor:None if actor.get('role')=='директор' else actor.get('assignedProjects',[]))
        app=FastAPI();register_customer_file_submission(app,scope,lambda:self.user,('директор',))
        from ..project_records.owned_routes import register_owned_record_routes
        register_owned_record_routes(app,{'record_scope':scope,'get_current_user':lambda:self.user,
            'read_roles':('директор','заказчик'),'write_roles':('директор',),'worker_execution_roles':()})
        self.client=TestClient(app)
        self.body={'projectId':1,'fileId':1,'subject':'Чертёж','body':'Комментарий'}

    def send(self,**changes):
        return self.client.post('/project-letters/customer-files',json={**self.body,**changes},headers={'X-Company-Id':'12','X-Company-Mode':'company'})

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
        self.assertEqual(self.client.post('/project-letters/customer-files',json=self.body,headers={'X-Company-Id':'99'}).status_code,403)
        self.user['role']='директор';self.assertEqual(self.send().status_code,403)

    def test_no_financial_or_status_fields_and_empty_subject(self):
        for changes in ({'subject':'  '},{'status':'Подписан'},{'amount':100},{'companyId':99},{'fileId':True}):
            response=self.send(**changes);self.assertEqual(response.status_code,422,response.text)

    def test_director_requests_correction_and_customer_replaces_without_overwriting_original(self):
        original=self.send().json()['id']
        self.user.update(role='директор',id=3,name='Директор')
        requested=self.client.post(f'/project-letters/{original}/request-correction',
            json={'reason':'Загрузите подписанный лист полностью'},headers={'X-Company-Id':'12'})
        self.assertEqual(requested.status_code,200,requested.text)
        self.user.update(role='заказчик',id=8,name='Заказчик')
        listed=self.client.get('/project-letters',headers={'X-Company-Id':'12'}).json()
        self.assertEqual((listed[0]['correctionReason'],listed[0]['correctedByLetterId']),
            ('Загрузите подписанный лист полностью',None))
        replaced=self.send(fileId=7,replacesLetterId=original,subject='Чертёж — исправлено')
        self.assertEqual(replaced.status_code,403)  # The new file must still be owned and active.
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO file_ownership VALUES(7,12,1,8,'customer-request','active',NULL)")
        replaced=self.send(fileId=7,replacesLetterId=original,subject='Чертёж — исправлено')
        self.assertEqual(replaced.status_code,200,replaced.text)
        with self.conn.cursor() as cur:
            cur.execute('SELECT subject,file_url,replaces_letter_id FROM project_letters ORDER BY id')
            self.assertEqual(cur.fetchall(),[('Чертёж','/tenant-files/1/content',None),
                ('Чертёж — исправлено','/tenant-files/7/content',original)])
            cur.execute('SELECT corrected_by_letter_id FROM project_letters WHERE id=%s',(original,))
            self.assertEqual(cur.fetchone()[0],replaced.json()['id'])
        self.user.update(role='директор',id=3,name='Директор')
        self.assertEqual(self.client.delete(f'/project-letters/{original}',headers={'X-Company-Id':'12'}).status_code,409)
        self.assertEqual(self.client.delete(f'/project-letters/{replaced.json()["id"]}',headers={'X-Company-Id':'12'}).status_code,409)

    def test_customer_cannot_request_correction_and_cross_company_record_is_hidden(self):
        original=self.send().json()['id']
        denied=self.client.post(f'/project-letters/{original}/request-correction',json={'reason':'Нет'},
            headers={'X-Company-Id':'12'})
        self.assertEqual(denied.status_code,403)
        self.user.update(role='директор',id=3,name='Директор',companyId=99,projectId=2)
        hidden=self.client.post(f'/project-letters/{original}/request-correction',json={'reason':'Чужой файл'},
            headers={'X-Company-Id':'99'})
        self.assertEqual(hidden.status_code,404)

    def test_replacement_requires_an_open_request_for_the_same_customer_and_project(self):
        original=self.send().json()['id']
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO file_ownership VALUES(7,12,1,8,'customer-request','active',NULL)")
        response=self.send(fileId=7,replacesLetterId=original)
        self.assertEqual(response.status_code,409,response.text)

    def publish(self, **changes):
        body={'requestId':str(uuid4()),'projectId':1,'fileId':11,'subject':'Исполнительная схема',
              'body':'Для ознакомления'}
        body.update(changes)
        return self.client.post('/project-letters/customer-publications',json=body,
            headers={'X-Company-Id':'12','X-Company-Mode':'company'})

    def test_internal_user_publishes_one_addressed_outgoing_version(self):
        self.user.update(role='директор',id=3,name='Директор',companyId=12,projectId=1)
        sent=self.publish();self.assertEqual(sent.status_code,200,sent.text)
        with self.conn.cursor() as cur:
            cur.execute('''SELECT side,direction,status,delivery_status,file_url,company_id,project_id,
                                  published_at IS NOT NULL,published_by_id,published_by_name
                             FROM project_letters WHERE id=%s''',(sent.json()['id'],))
            self.assertEqual(cur.fetchone(),('customer','outgoing','Активно','sent','/tenant-files/11/content',
                12,1,True,3,'Директор'))
            cur.execute("""SELECT party_snapshot_json->'sender'->>'fullName',
                                  party_snapshot_json->'sender'->>'inn',
                                  party_snapshot_json->'recipient'->>'fullName',
                                  party_snapshot_json->'project'->>'name',customer_client_id,
                                  party_snapshot_hash IS NOT NULL,party_snapshot_frozen_at IS NOT NULL
                             FROM project_letters WHERE id=%s""",(sent.json()['id'],))
            self.assertEqual(cur.fetchone(),('ООО Стройка 12','1212121212','Лицей №4','Same name',21,True,True))
            cur.execute('SELECT retained_at IS NOT NULL FROM file_ownership WHERE id=11')
            self.assertTrue(cur.fetchone()[0])
        self.user.update(role='заказчик',id=8,name='Заказчик',assignedProjects=['Same name'])
        listed=self.client.get('/project-letters',headers={'X-Company-Id':'12'}).json()
        row=next(item for item in listed if item['id']==sent.json()['id'])
        self.assertEqual((row['direction'],row['deliveryStatus'],row['publishedByName']),
            ('outgoing','sent','Директор'))
        self.assertEqual(row['partySnapshot']['recipient']['clientId'],21)

    def test_outgoing_publication_keeps_the_original_parties_after_cards_change(self):
        self.user.update(role='директор',id=3,name='Директор',companyId=12,projectId=1)
        sent=self.publish();self.assertEqual(sent.status_code,200,sent.text)
        with self.conn.cursor() as cur:
            cur.execute("UPDATE company_requisites SET full_name='Новое имя компании' WHERE company_id=12")
            cur.execute("UPDATE clients SET name='Новое имя заказчика' WHERE id=21")
        listed=self.client.get('/project-letters',headers={'X-Company-Id':'12'}).json()
        snapshot=next(row for row in listed if row['id']==sent.json()['id'])['partySnapshot']
        self.assertEqual(snapshot['sender']['fullName'],'ООО Стройка 12')
        self.assertEqual(snapshot['recipient']['fullName'],'Лицей №4')

    def test_outgoing_publication_requires_an_exact_customer_card(self):
        self.user.update(role='директор',id=3,name='Директор',companyId=12,projectId=1)
        with self.conn.cursor() as cur: cur.execute('UPDATE projects SET client_id=NULL WHERE id=1')
        response=self.publish()
        self.assertEqual(response.status_code,409,response.text)
        self.assertIn('заказчика',response.json()['detail'].lower())

    def test_outgoing_publication_is_idempotent_and_immutable(self):
        self.user.update(role='директор',id=3,name='Директор',companyId=12,projectId=1)
        request_id=str(uuid4())
        first=self.publish(requestId=request_id)
        second=self.publish(requestId=request_id)
        self.assertEqual(second.json(),first.json())
        changed=self.publish(requestId=request_id,subject='Другое письмо')
        self.assertEqual(changed.status_code,409,changed.text)
        self.assertEqual(self.client.delete(f'/project-letters/{first.json()["id"]}',
            headers={'X-Company-Id':'12'}).status_code,409)

    def test_outgoing_publication_rejects_unowned_or_wrong_scope_files(self):
        self.user.update(role='директор',id=3,name='Директор',companyId=12,projectId=1)
        for file_id in (12,13,14,15,16,999):
            response=self.publish(fileId=file_id)
            self.assertEqual(response.status_code,403,response.text)
        self.user.update(role='заказчик',id=8,name='Заказчик')
        self.assertEqual(self.publish(fileId=11).status_code,403)

    def test_legacy_generic_route_cannot_publish_to_customer(self):
        self.user.update(role='директор',id=3,name='Директор',companyId=12,projectId=1)
        response=self.client.post('/project-letters',json={'projectId':1,'side':'customer',
            'direction':'outgoing','subject':'Обход адресной отправки'},headers={'X-Company-Id':'12'})
        self.assertEqual(response.status_code,409,response.text)
        with self.conn.cursor() as cur:
            cur.execute("""INSERT INTO project_letters(project_name,company_id,project_id,created_by_user_id,
                side,direction,subject,status,delivery_status) VALUES('Same name',12,1,3,'customer',
                'outgoing','Не опубликовано','Активно','sent')""")
        self.user.update(role='заказчик',id=8,name='Заказчик',assignedProjects=['Same name'])
        self.assertEqual(self.client.get('/project-letters',headers={'X-Company-Id':'12'}).json(),[])
