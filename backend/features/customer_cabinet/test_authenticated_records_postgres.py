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
