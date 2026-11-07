"""Audit actual API-created staff/contract records in the migrated app fixture."""
import os
import secrets
import unittest

from .report import run_audit
from ..staff import test_access_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ContractorIdentityRuntimePostgresTests(unittest.TestCase):
    sql = support.StaffAccessPostgresTests.sql
    api = support.StaffAccessPostgresTests.api

    @classmethod
    def setUpClass(cls):
        support.StaffAccessPostgresTests.setUpClass.__func__(cls)

    def test_api_created_contractor_is_a_candidate_until_membership_is_revoked(self):
        project, name = self.sql('SELECT id,name FROM projects WHERE company_id=2 ORDER BY id LIMIT 1')[0]
        director = self.fixture['users']['director']
        staff = self.api(director, 'POST', '/staff', {
            'name':'Synthetic contractor identity', 'email':'identity-audit@local.invalid',
            'password':secrets.token_urlsafe(24), 'systemRole':'субподрядчик',
            'assignedProjects':[name], 'assignedPackages':['Основная'],
        })
        user = self.sql('''SELECT user_id FROM user_company_roles
            WHERE company_id=2 AND staff_id=%s AND active''', (staff['id'],))[0][0]
        contract = self.api(director, 'POST', '/brigade-contracts', {
            'projectId':project, 'projectName':name, 'brigadeName':'Synthetic contractor identity',
            'contractorId':user, 'contractorType':'Субподрядчик', 'workPackage':'Основная',
        })
        before = self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=%s', (contract['id'],))
        report = run_audit(self.main.get_db, 2)
        entry = next(item for item in report['items'] if item['contractId'] == contract['id'])
        self.assertEqual(entry['reference'], {'type':'user','id':user})
        self.assertEqual(entry['reason'], 'CANDIDATE_USER_REFERENCE')
        self.assertFalse(report['canApply'])
        self.assertEqual(self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=%s', (contract['id'],)), before)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE company_id=2 AND user_id=%s', (user,))
        revoked = run_audit(self.main.get_db, 2)
        entry = next(item for item in revoked['items'] if item['contractId'] == contract['id'])
        self.assertEqual(entry['reason'], 'COMPANY_MEMBERSHIP_UNVERIFIED')
        self.assertIsNone(entry['reference'])
        self.assertNotEqual(report['evidenceSha256'], revoked['evidenceSha256'])
        self.assertEqual(self.sql('SELECT to_jsonb(c) FROM brigade_contracts c WHERE id=%s', (contract['id'],)), before)


if __name__ == '__main__':
    unittest.main()
