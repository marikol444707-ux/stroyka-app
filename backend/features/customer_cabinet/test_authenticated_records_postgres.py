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
        self.api(director,'POST','/project-letters',{'projectId':project_id,'side':'customer','body':'Согласование'})
        self.assertEqual(len(self.api(self.customer,'GET','/project-letters')),1)

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
        self.api(self.customer,'DELETE',uploaded['metadataUrl'],expected=403)
