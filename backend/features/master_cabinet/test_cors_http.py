"""The local browser must be able to read the journal ownership proof."""
import unittest
import urllib.request
from backend.features.master_cabinet import test_profile_http as support

@unittest.skipUnless(support.RUN, 'Requires the owned local audit API')
class JournalCorsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.MasterProfileHttpTests.setUpClass.__func__(cls)

    def test_allowed_browser_origin_can_read_owned_snapshot_header(self):
        from backend.auth import create_auth_token
        actor = self.users['foreman']
        request = urllib.request.Request('http://127.0.0.1:8001/material-inspection', headers={
            'Origin': 'http://localhost:4187',
            'Authorization': 'Bearer ' + create_auth_token(actor, two_factor_passed=True),
            'X-Company-Mode': 'company', 'X-Company-Id': str(actor['company_id']),
        })
        with urllib.request.urlopen(request, timeout=10) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get('X-Quality-Journal-Snapshot'), 'owned-v1')
            self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'http://localhost:4187')
            self.assertIn('x-quality-journal-snapshot', response.headers.get('Access-Control-Expose-Headers', '').lower())
