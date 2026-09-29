"""Stage boundaries through real authentication and company membership."""
import os
import unittest

from . import test_authenticated_records_postgres as support


class AuthenticatedCustomerStagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') != '1':
            raise unittest.SkipTest('isolated PostgreSQL required')
        support.AuthenticatedCustomerRecordTest.setUpClass.__func__(cls)

    api = support.AuthenticatedCustomerRecordTest.api

    def test_stages_use_exact_parent_and_hide_internal_fields(self):
        project_id = self.fixture['projectId']
        director = self.fixture['users']['director']
        own = self.api(director, 'POST', '/project-stages', {
            'projectId': project_id, 'name': 'Foundation', 'notes': 'Internal',
            'responsible': 'Internal assignee', 'progress': 25,
        })
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO projects(company_id,name) SELECT 3,name FROM projects WHERE id=%s RETURNING id', (project_id,))
                foreign_project = cur.fetchone()[0]
                cur.execute('INSERT INTO project_stages(project_id,project_name,name) SELECT id,name,%s FROM projects WHERE id=%s RETURNING id', ('Foreign', foreign_project))
                foreign_stage = cur.fetchone()[0]
                cur.execute('INSERT INTO project_stages(project_name,name) SELECT name,%s FROM projects WHERE id=%s RETURNING id', ('Unowned', project_id))
                unowned_stage = cur.fetchone()[0]
            conn.commit()
        finally:
            conn.close()
        rows = self.api(self.customer, 'GET', '/project-stages')
        self.assertEqual([row['id'] for row in rows], [own['id']])
        self.assertEqual((rows[0]['companyId'], rows[0]['projectId']), (2, project_id))
        self.assertNotIn('notes', rows[0])
        self.assertNotIn('responsible', rows[0])
        self.assertEqual((rows[0]['startDate'], rows[0]['endDate'], rows[0]['status']), ('', '', 'Не начат'))
        internal = self.api(director, 'GET', '/project-stages')
        self.assertEqual(internal[0]['notes'], 'Internal')
        self.api(self.customer, 'POST', '/project-stages', {'projectId': project_id}, expected=403)
        for identity in (foreign_stage, unowned_stage):
            self.api(director, 'PUT', f'/project-stages/{identity}', {'name': 'Changed'}, expected=404)
            self.api(director, 'DELETE', f'/project-stages/{identity}', expected=404)
        self.api(director, 'PUT', f'/project-stages/{own["id"]}', {'progress': 50})
        updated = self.api(self.customer, 'GET', '/project-stages')[0]
        self.assertEqual((updated['name'], updated['progress']), ('Foundation', 50))
        self.api(director, 'DELETE', f'/project-stages/{own["id"]}')
        self.assertEqual(self.api(self.customer, 'GET', '/project-stages'), [])
        minimal = self.api(director, 'POST', '/project-stages', {'projectId': project_id})
        saved = next(row for row in self.api(director, 'GET', '/project-stages') if row['id'] == minimal['id'])
        self.assertEqual([saved[key] for key in ('name', 'startDate', 'endDate', 'responsible', 'notes')], [''] * 5)
        self.assertEqual((saved['progress'], saved['orderNum'], saved['status']), (0, 0, 'Не начат'))
        self.api(self.customer, 'GET', '/project-stages', company=3, expected=403)
        for value in (-1, 101, True, 'invalid', 1.5):
            self.api(director, 'PUT', f'/project-stages/{minimal["id"]}', {'progress': value}, expected=422)
