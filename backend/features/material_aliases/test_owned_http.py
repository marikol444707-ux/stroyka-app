"""HTTP contract and boundary tests without ambient application configuration."""
import os
import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


class OwnedAliasHttpTests(unittest.TestCase):
    def setUp(self):
        from backend.features.material_aliases.owned_routes import register_owned_aliases
        self.db = Mock()
        app = FastAPI()
        register_owned_aliases(app, {'get_db': self.db, 'get_current_user': lambda: {'id': 1},
            'read_roles': ('директор',), 'write_roles': ('директор',), 'full_project_roles': ('директор',)})
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.flag = patch.dict(os.environ, {'COMPANY_MATERIAL_ALIASES_ENABLED': '1'})
        self.flag.start()
        self.addCleanup(self.flag.stop)

    def test_disabled_returns_404_without_database(self):
        with patch.dict(os.environ, {'COMPANY_MATERIAL_ALIASES_ENABLED': '0'}):
            response = self.client.get('/company-material-aliases?companyId=2')
        self.assertEqual(response.status_code, 404)
        self.db.assert_not_called()

    def test_strict_body_rejects_spoofed_fields_and_invalid_ids(self):
        valid = dict(companyId=2, aliasName='Brand', canonicalName='Cement', expectedAliasId=None)
        for changes in ({'companyId': True}, {'projectId': '2'}, {'createdById': 99},
                        {'aliasName': ''}, {'canonicalName': 'X'*501}, {'expectedAliasId': '1'}):
            with self.subTest(changes=changes):
                response = self.client.post('/company-material-aliases', json={**valid, **changes})
                self.assertEqual(response.status_code, 422, response.text)
        without_version = dict(valid)
        del without_version['expectedAliasId']
        self.assertEqual(self.client.post('/company-material-aliases', json=without_version).status_code, 422)
        self.db.assert_not_called()

    def test_bare_legacy_id_cannot_target_owned_delete(self):
        for value in ('1', 'cma:0', 'cma:01', 'cma:9223372036854775808'):
            response = self.client.delete('/company-material-aliases/'+value+'?companyId=2')
            self.assertEqual(response.status_code, 422, response.text)
        self.db.assert_not_called()

    def test_aggregate_mode_is_explicitly_rejected_before_database(self):
        response = self.client.get('/company-material-aliases?companyId=2', headers={'X-Company-Mode': 'all_companies'})
        self.assertEqual(response.status_code, 400)
        self.db.assert_not_called()
