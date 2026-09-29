"""Real authenticated project and journal customer projections."""
import os
import unittest
from . import test_authenticated_records_postgres as support


class CustomerProgressApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') != '1':
            raise unittest.SkipTest('isolated PostgreSQL required')
        support.AuthenticatedCustomerRecordTest.setUpClass.__func__(cls)

    api = support.AuthenticatedCustomerRecordTest.api

    def test_only_confirmed_owned_volumes_and_public_project_fields(self):
        project_id = self.fixture['projectId']
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                for company, status, description in ((2, 'Подтверждено', 'Visible'), (2, 'На проверке', 'Pending'), (3, 'Подтверждено', 'Foreign')):
                    cur.execute('''INSERT INTO work_journal(company_id,project,description,status,quantity,unit,comment,materials_used)
                        SELECT %s,name,%s,%s,3,'m2','Internal note','[]' FROM projects WHERE id=%s RETURNING id''',
                        (company, description, status, project_id))
            conn.commit()
        finally:
            conn.close()
        rows = self.api(self.customer, 'GET', '/work-journal')
        self.assertEqual([row['description'] for row in rows], ['Visible'])
        self.assertEqual((rows[0]['companyId'], rows[0]['projectId'], rows[0]['quantity']), (2, project_id, 3))
        for key in ('comment', 'materialsUsed', 'settlementContractId', 'masterId', 'responsibleItr'):
            self.assertNotIn(key, rows[0])
        projects = self.api(self.customer, 'GET', '/projects')
        for project in projects:
            for key in ('tasks', 'pricelistId', 'publicShowOnSite', 'archivedAt'):
                self.assertNotIn(key, project)
        self.api(self.customer, 'GET', '/work-journal', company=3, expected=403)
