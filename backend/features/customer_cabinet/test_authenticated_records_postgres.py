"""Real authentication, company context and HTTP routes on an isolated database."""
import importlib
import os
import unittest

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class AuthenticatedCustomerRecordTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.features.supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main,cls.fixture,cleanup=build_fixture()
        cls.addClassCleanup(cleanup)
        conn=cls.main.get_db()
        try:
            with conn.cursor() as cur:
                # The legacy supply fixture uses init_db, not the full Alembic chain.
                cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS quality_projects_id_company_idx ON projects(id,company_id)')
                cur.execute(importlib.import_module('migrations.versions.0040_customer_record_owners').SCHEMA_SQL)
                cur.execute(importlib.import_module('migrations.versions.0068_customer_file_corrections').SCHEMA_SQL)
                cur.execute(importlib.import_module('migrations.versions.0069_addressed_customer_publications').SCHEMA_SQL)
                cur.execute(importlib.import_module('migrations.versions.0080_outgoing_letter_parties').UPGRADE_SQL)
                cur.execute('ALTER TABLE file_ownership ADD COLUMN IF NOT EXISTS retained_at TIMESTAMPTZ')
                cur.execute("INSERT INTO clients(company_id,name,status,inn) VALUES(2,'Заказчик объекта','Активен','2600000000') RETURNING id")
                cls.customer_client_id=cur.fetchone()[0]
                cur.execute('UPDATE projects SET client_id=%s WHERE id=%s AND company_id=2',
                            (cls.customer_client_id,cls.fixture['projectId']))
                user_id=cls.fixture['users']['foreman']['id']
                cur.execute("UPDATE users SET role='заказчик' WHERE id=%s",(user_id,))
                cur.execute("UPDATE user_company_roles SET role='заказчик' WHERE user_id=%s",(user_id,))
            conn.commit()
        finally:
            conn.close()
        cls.customer=dict(cls.fixture['users']['foreman'],role='заказчик')
        cls.client=TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def api(self,user,method,path,body=None,company=2,expected=200):
        token=self.main.create_auth_token(user,two_factor_passed=True)
        response=self.client.request(method,path,json=body,headers={'Authorization':'Bearer '+token,
            'X-Company-Id':str(company),'X-Company-Mode':'company'})
        self.assertEqual(response.status_code,expected,response.text)
        return response.json()

    def test_authenticated_customer_records_and_company_header_boundary(self):
        project_id=self.fixture['projectId']
        note=self.api(self.customer,'POST','/prescriptions',{'projectId':project_id,'violation':'Проверить стык','status':'Закрыто'})
        rows=self.api(self.customer,'GET','/prescriptions')
        row=next(row for row in rows if row['id']==note['id'])
        self.assertEqual((row['companyId'],row['projectId'],row['status']),(2,project_id,'Открыто'))
        self.assertEqual(row['createdByUserId'],self.customer['id'])
        self.api(self.customer,'GET','/prescriptions',company=3,expected=403)
        self.api(self.customer,'POST','/project-documents',{'projectId':project_id},expected=403)
        defect=self.api(self.customer,'POST','/warranty-defects',{'projectId':project_id,'description':'Трещина','status':'Устранён'})
        warranty=self.api(self.customer,'GET','/warranty-defects')
        self.assertEqual(next(row for row in warranty if row['id']==defect['id'])['status'],'Открыт')
        director=self.fixture['users']['director']
        public=self.api(director,'POST','/project-documents',{'projectId':project_id,'side':'customer','notes':'Внутренняя заметка'})
        private=self.api(director,'POST','/project-documents',{'projectId':project_id,'side':'contractor'})
        documents=self.api(self.customer,'GET','/project-documents')
        self.assertIn(public['id'],[row['id'] for row in documents])
        self.assertNotIn(private['id'],[row['id'] for row in documents])
        self.assertNotIn('notes',next(row for row in documents if row['id']==public['id']))
        letter=self.api(director,'POST','/project-letters/customer-publications',{
            'requestId':'a35ad376-0e44-4821-aaaf-f4f56ad25430','projectId':project_id,
            'subject':'Согласование','body':'Согласование'})
        letters=self.api(self.customer,'GET','/project-letters')
        published=next(row for row in letters if row['id']==letter['id'])
        self.assertEqual(published['partySnapshot']['recipient']['clientId'],self.customer_client_id)

    def test_direct_file_url_requires_customer_publication(self):
        project_id=self.fixture['projectId']
        director=self.fixture['users']['director']
        conn=self.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO file_ownership(company_id,project_id,file_url,context,original_name,
                    content_type,uploaded_by_id) VALUES(2,%s,%s,'general','private.pdf','application/pdf',%s) RETURNING id''',
                    (project_id,f'/uploads/company-2-project-{project_id}-general/private.pdf',director['id']))
                file_id=cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        self.api(self.customer,'GET',f'/tenant-files/{file_id}',expected=403)
        self.api(self.customer,'GET',f'/tenant-files/{file_id}/content',expected=403)
        # Knowing an ID must not let a customer publish a private file by attaching it to a remark.
        self.api(self.customer,'POST','/prescriptions',{'projectId':project_id,
            'violation':'Подмена вложения','photoUrl':f'/tenant-files/{file_id}/content'},expected=403)
        published=self.api(director,'POST','/project-documents',{'projectId':project_id,'side':'customer',
            'scanUrl':f'/tenant-files/{file_id}/content'})
        metadata=self.api(self.customer,'GET',f'/tenant-files/{file_id}')
        self.assertEqual(metadata['projectId'],project_id)
        self.api(director,'DELETE',f'/project-documents/{published["id"]}')
        self.api(self.customer,'GET',f'/tenant-files/{file_id}',expected=403)

    def test_customer_upload_is_private_request_attachment_and_can_be_linked(self):
        import base64
        image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
        token=self.main.create_auth_token(self.customer,two_factor_passed=True)
        response=self.client.post('/upload-photo',headers={'Authorization':'Bearer '+token,'X-Company-Id':'2'},
            data={'projectId':str(self.fixture['projectId']),'context':'internal'},
            files={'file':('photo.png',image,'image/png')})
        self.assertEqual(response.status_code,200,response.text)
        uploaded=response.json()
        self.assertEqual(uploaded['context'],'customer-request')
        metadata=self.api(self.customer,'GET',uploaded['metadataUrl'])
        self.assertEqual(metadata['context'],'customer-request')
        response=self.client.get(uploaded['contentUrl'],headers={'Authorization':'Bearer '+token,'X-Company-Id':'2'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.content,image)
        request=self.api(self.customer,'POST','/warranty-defects',{'projectId':self.fixture['projectId'],
            'description':'Фото дефекта','photoUrl':uploaded['url']})
        rows=self.api(self.customer,'GET','/warranty-defects')
        self.assertEqual(next(row for row in rows if row['id']==request['id'])['photoUrl'],uploaded['contentUrl'])
        self.api(self.customer, 'PUT', f'/warranty-defects/{request["id"]}', {'status': 'Устранён'}, expected=403)
        self.api(self.fixture['users']['director'], 'PUT', f'/warranty-defects/{request["id"]}',
                 {'status': 'Устранён', 'fixNotes': 'Исправлено, результат проверен', 'fixedAt': '2026-09-20'})
        updated = next(row for row in self.api(self.customer, 'GET', '/warranty-defects') if row['id'] == request['id'])
        self.assertEqual((updated['status'], updated['fixNotes']), ('Устранён', 'Исправлено, результат проверен'))
        self.assertEqual(updated['photoUrl'], uploaded['contentUrl'])
        self.api(self.customer,'DELETE',uploaded['metadataUrl'],expected=403)

    def test_addressed_outgoing_file_is_downloadable_only_in_its_customer_project(self):
        import base64
        image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
        director=self.fixture['users']['director'];project_id=self.fixture['projectId']
        token=self.main.create_auth_token(director,two_factor_passed=True)
        upload=self.client.post('/upload-photo',headers={'Authorization':'Bearer '+token,
            'X-Company-Id':'2','X-Company-Mode':'company'},data={'projectId':str(project_id),
            'context':'project-letters'},files={'file':('letter.png',image,'image/png')})
        self.assertEqual(upload.status_code,200,upload.text)
        uploaded=upload.json();file_id=int(uploaded['contentUrl'].split('/')[2])
        sent=self.api(director,'POST','/project-letters/customer-publications',{
            'requestId':'4cb9b3b5-bc31-469c-b81d-169c1bcd0114','projectId':project_id,
            'fileId':file_id,'subject':'Исполнительная схема'})
        customer_token=self.main.create_auth_token(self.customer,two_factor_passed=True)
        content=self.client.get(uploaded['contentUrl'],headers={'Authorization':'Bearer '+customer_token,
            'X-Company-Id':'2','X-Company-Mode':'company'})
        self.assertEqual((content.status_code,content.content),(200,image))
        self.api(director,'DELETE',f'/project-letters/{sent["id"]}',expected=409)
        denied=self.client.get(uploaded['contentUrl'],headers={'Authorization':'Bearer '+customer_token,
            'X-Company-Id':'3','X-Company-Mode':'company'})
        self.assertIn(denied.status_code,(403,404,409))
