import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from .routes import register_company_documents_module


class CompanyDocumentScopeTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cur = self.conn.cursor.return_value
        self.context = {'mode': 'company', 'companyId': 1}
        self.actor = {'companyId': 1, 'role': 'директор', 'name': 'Verified actor'}
        app = FastAPI()
        register_company_documents_module(app, {
            'get_db': lambda: self.conn,
            'get_current_user': lambda: {'role': 'директор'},
            'finance_roles': ['директор'],
            'resolve_work_company_context': lambda *a, **kw: self.context,
            'effective_company_actors': lambda *a: [self.actor],
        })
        self.client = TestClient(app)

    def test_list_scopes_query(self):
        self.cur.fetchall.return_value = [(3, 1, 'Charter', 'Устав', '', '', '')]
        response = self.client.get('/company-documents')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]['companyId'], 1)
        sql, args = self.cur.execute.call_args.args
        self.assertIn('WHERE company_id=%s', sql)
        self.assertEqual(args, (1,))

    def test_all_companies_returns_no_archive(self):
        self.context = {'mode': 'all'}
        self.assertEqual(self.client.get('/company-documents').json(), [])
        self.cur.execute.assert_not_called()
        self.assertEqual(self.client.post('/company-documents', json={}).status_code, 409)

    def test_effective_role_required(self):
        self.actor['role'] = 'прораб'
        self.assertEqual(self.client.get('/company-documents').status_code, 403)
        self.cur.execute.assert_not_called()

    def test_claimed_foreign_company_rejected(self):
        self.assertEqual(self.client.post('/company-documents', json={'companyId': 2}).status_code, 409)
        self.cur.execute.assert_not_called()

    def test_foreign_missing_and_project_files_rejected(self):
        for owner, status in [(None, 403), ((2, None), 403), ((1, 99), 409)]:
            with self.subTest(owner=owner):
                self.cur.fetchone.return_value = owner
                response = self.client.post('/company-documents', json={'fileUrl': '/tenant-files/9/content'})
                self.assertEqual(response.status_code, status)
        self.conn.commit.assert_not_called()

    def test_raw_file_url_rejected(self):
        response = self.client.post('/company-documents', json={'fileUrl': '/uploads/file.pdf'})
        self.assertEqual(response.status_code, 409)
        self.cur.execute.assert_not_called()

    def test_create_uses_server_owner_and_author(self):
        self.cur.fetchone.side_effect = [(1, None), (77,)]
        response = self.client.post('/company-documents', json={
            'fileUrl': '/tenant-files/9/content', 'uploadedBy': 'Forged'})
        self.assertEqual(response.status_code, 200)
        params = self.cur.execute.call_args.args[1]
        self.assertEqual(params[0], 1)
        self.assertEqual(params[-1], 'Verified actor')
        self.conn.commit.assert_called_once()

    def test_delete_foreign_or_unassigned_document_not_found(self):
        self.cur.fetchone.return_value = None
        self.assertEqual(self.client.delete('/company-documents/99').status_code, 404)
        sql, args = self.cur.execute.call_args.args
        self.assertIn('AND company_id=%s', sql)
        self.assertEqual(args, (99, 1))
        self.conn.commit.assert_not_called()
        self.conn.rollback.assert_called_once()


if __name__ == '__main__':
    unittest.main()
