"""Local HTTP checks for leadership review; requires the owned master-audit fixture."""
import importlib.util
import os
from pathlib import Path
import unittest

from backend.features.master_cabinet.test_profile_http import require_owned_fixture

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(os.environ.get('MASTER_CABINET_HTTP_TESTS') == '1', 'Requires the owned local audit API')
class LeadershipReviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_owned_fixture()
        spec = importlib.util.spec_from_file_location('leadership_audit_api', ROOT / 'tmp/master-audit/api_support.py')
        helper = importlib.util.module_from_spec(spec)
        environment, exists = dict(os.environ), os.path.exists
        try:
            spec.loader.exec_module(helper)
        finally:
            os.environ.clear()
            os.environ.update(environment)
            os.path.exists = exists
        cls.request = staticmethod(helper.request)
        cls.fixture = helper.FIXTURE
        if 'deputy' not in cls.fixture['users']:
            raise RuntimeError('Create the synthetic deputy in the owned fixture first')

    def journal(self, role):
        status, rows = self.request(role, '/work-journal')
        self.assertEqual(status, 200, rows)
        return rows

    def test_both_leaders_see_master_volumes_photos_and_accepted_results(self):
        master_id = self.fixture['users']['master']['id']
        master = {r['id']: r for r in self.journal('master')}
        for role in ('director', 'deputy'):
            with self.subTest(role=role):
                own = [r for r in self.journal(role) if r['masterId'] == master_id]
                self.assertTrue(own)
                self.assertEqual({r['id'] for r in own}, set(master))
                self.assertTrue(any(r['status'] == 'Подтверждено' for r in own))
                for row in own:
                    self.assertEqual(row['companyId'], self.fixture['users'][role]['company_id'])
                    for key in ('quantity', 'status', 'roomId', 'executionTotal', 'photoUrl'):
                        self.assertEqual(row[key], master[row['id']][key])
                photo = next(r['photoUrl'].split(',')[0] for r in own if r['photoUrl'])
                self.assertTrue(photo.startswith('/tenant-files/'))
                status, _ = self.request(role, photo)
                self.assertEqual(status, 200)

    def test_other_company_cannot_read_or_confirm_master_report(self):
        row = self.journal('master')[0]
        self.assertNotIn(row['id'], [r['id'] for r in self.journal('stranger')])
        status, _ = self.request('stranger', '/work-journal/' + str(row['id']), 'PUT', {'status': 'Подтверждено'})
        self.assertIn(status, (403, 404))
        self.assertEqual(next(r for r in self.journal('master') if r['id'] == row['id']), row)

    def test_master_and_accountant_cannot_confirm_pending_report(self):
        row = next(r for r in self.journal('master') if r['status'] == 'На проверке')
        for role in ('master', 'accountant'):
            with self.subTest(role=role):
                status, _ = self.request(role, '/work-journal/' + str(row['id']), 'PUT', {'status': 'Подтверждено'})
                self.assertEqual(status, 403)
        self.assertEqual(next(r for r in self.journal('master') if r['id'] == row['id']), row)

    def test_repeat_confirmation_keeps_journal_and_daily_acts_unchanged(self):
        for role in ('director', 'deputy'):
            with self.subTest(role=role):
                row = next(r for r in self.journal('master') if r['status'] == 'Подтверждено')
                status, before = self.request('master', '/interim-acts')
                self.assertEqual(status, 200)
                status, body = self.request(role, '/work-journal/' + str(row['id']), 'PUT', {'status': 'Подтверждено', 'quantity': row['quantity']})
                self.assertEqual(status, 409, body)
                status, after = self.request('master', '/interim-acts')
                self.assertEqual(status, 200)
                self.assertEqual(after, before)
                self.assertEqual(next(r for r in self.journal('master') if r['id'] == row['id']), row)
