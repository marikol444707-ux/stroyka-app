"""Actual HTTP authorization on a disposable PostgreSQL database."""
import importlib
import os
import unittest

from ..customer_cabinet.test_authenticated_records_postgres import AuthenticatedCustomerRecordTest


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class RegulatoryRecordAccessTests(unittest.TestCase):
    api = AuthenticatedCustomerRecordTest.api

    @classmethod
    def setUpClass(cls):
        from ..supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        with cls.main.get_db() as conn, conn.cursor() as cur:
            cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS quality_projects_id_company_idx ON projects(id,company_id)')
            cur.execute(importlib.import_module('migrations.versions.0109_regulatory_record_owners').SCHEMA_SQL)
            cur.execute('INSERT INTO projects(company_id,name) VALUES(3,%s) RETURNING id', (cls.fixture['project'],))
            cls.foreign_project = cur.fetchone()[0]
        conn.close()
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)

    def sql(self, query, params=()):
        conn = self.main.get_db()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall() if cur.description else []
            conn.commit()
            return rows
        finally:
            conn.close()

    def create(self, route, company=2):
        actor = self.fixture['users']['director' if company == 2 else 'stranger']
        return self.api(actor, 'POST', route, {'projectName':self.fixture['project'],
            'projectId':self.fixture['projectId'] if company == 2 else self.foreign_project,
            'description':'Private inspection'}, company=company)['id']

    def test_lists_do_not_mix_companies_with_same_project_name(self):
        for route in ('/supervisor-acts', '/inspection-orders'):
            with self.subTest(route=route):
                foreign = self.create(route, 3)
                own = self.create(route)
                for suffix in ('', '?project_name='+self.fixture['project']):
                    rows = self.api(self.fixture['users']['director'],'GET',route+suffix)
                    self.assertNotIn(foreign, [r['id'] for r in rows])
                    saved = next(r for r in rows if r['id'] == own)
                    self.assertEqual((saved['companyId'],saved['projectId']), (2,self.fixture['projectId']))

    def test_foreign_known_ids_cannot_be_modified_or_deleted(self):
        for route in ('/supervisor-acts', '/inspection-orders'):
            with self.subTest(route=route):
                foreign = self.create(route,3)
                actor = self.fixture['users']['director']
                self.api(actor,'PUT',f'{route}/{foreign}',{'status':'Attack'},expected=404)
                self.api(actor,'DELETE',f'{route}/{foreign}',expected=404)
                table = route[1:].replace('-', '_')
                self.assertNotEqual(self.sql(f'SELECT status FROM {table} WHERE id=%s',(foreign,))[0][0],'Attack')

    def test_creation_cannot_target_foreign_parent_or_forge_owner(self):
        actor = self.fixture['users']['director']
        for route in ('/supervisor-acts','/inspection-orders'):
            with self.subTest(route=route):
                self.api(actor,'POST',route,{'projectId':self.foreign_project},expected=404)
                result = self.api(actor,'POST',route,{'projectId':self.fixture['projectId'],
                    'companyId':3,'createdByUserId':999})
                table = route[1:].replace('-', '_')
                self.assertEqual(self.sql(f'SELECT company_id,project_id,created_by_user_id FROM {table} WHERE id=%s',
                    (result['id'],)),[(2,self.fixture['projectId'],actor['id'])])

    def test_unassigned_legacy_rows_are_not_inferred_from_name(self):
        actor = self.fixture['users']['director']
        for table in ('supervisor_acts','inspection_orders'):
            legacy = self.sql(f'INSERT INTO {table}(project_name,description) VALUES(%s,%s) RETURNING id',
                (self.fixture['project'],'Legacy'))[0][0]
            route = '/'+table.replace('_','-')
            with self.subTest(route=route):
                rows = self.api(actor,'GET',route)
                self.assertNotIn(legacy,[r['id'] for r in rows])
                self.api(actor,'PUT',f'{route}/{legacy}',{'status':'Changed'},expected=404)

    def test_selected_company_and_revoked_membership(self):
        actor = self.fixture['users']['director']
        for route in ('/supervisor-acts','/inspection-orders'):
            self.api(actor,'GET',route,company=3,expected=403)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(actor['id'],))
        try:
            for route in ('/supervisor-acts','/inspection-orders'):
                self.api(actor,'GET',route,expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(actor['id'],))

    def test_own_mutations_survive_reload_and_keep_delete_semantics(self):
        actor = self.fixture['users']['director']
        for route in ('/supervisor-acts','/inspection-orders'):
            record = self.create(route)
            self.api(actor,'PUT',f'{route}/{record}',{'status':'Закрыто','response':'Done','responseDate':''})
            rows = self.api(actor,'GET',route)
            self.assertEqual(next(r for r in rows if r['id']==record)['status'],'Закрыто')
            self.api(actor,'DELETE',f'{route}/{record}')
            self.assertNotIn(record,[r['id'] for r in self.api(actor,'GET',route)])
            table = route[1:].replace('-','_')
            self.assertEqual(self.sql(f'SELECT status FROM {table} WHERE id=%s',(record,)),
                [('Аннулировано',)] if table=='inspection_orders' else [])

    def test_role_and_exact_project_boundaries(self):
        actor = dict(self.fixture['users']['foreman'], role='технадзор')
        self.sql("UPDATE users SET role='технадзор' WHERE id=%s", (actor['id'],))
        self.sql("UPDATE user_company_roles SET role='технадзор' WHERE user_id=%s AND company_id=2", (actor['id'],))
        other_project = self.sql("INSERT INTO projects(company_id,name) VALUES(2,'Other exact object') RETURNING id")[0][0]
        try:
            for route in ('/supervisor-acts', '/inspection-orders'):
                own = self.api(actor,'POST',route,{'projectId':self.fixture['projectId'], 'description':'Supervisor'})['id']
                other = self.api(self.fixture['users']['director'],'POST',route,{'projectId':other_project})['id']
                rows = self.api(actor,'GET',route)
                self.assertIn(own, [r['id'] for r in rows])
                self.assertNotIn(other, [r['id'] for r in rows])
                self.api(actor,'POST',route,{'projectId':other_project},expected=403)
                self.api(actor,'PUT',f'{route}/{other}',{'status':'Changed'},expected=404)
            self.sql("UPDATE user_company_roles SET role='мастер' WHERE user_id=%s AND company_id=2", (actor['id'],))
            for route in ('/supervisor-acts','/inspection-orders'):
                self.api(actor,'POST',route,{'projectId':self.fixture['projectId']},expected=403)
        finally:
            role = self.fixture['users']['foreman']['role']
            self.sql('UPDATE users SET role=%s WHERE id=%s',(role,actor['id']))
            self.sql('UPDATE user_company_roles SET role=%s WHERE user_id=%s AND company_id=2',(role,actor['id']))

    def test_ambiguous_name_requires_exact_parent_and_schema_rejects_wrong_pair(self):
        import psycopg2
        actor = self.fixture['users']['director']
        duplicate = self.sql('INSERT INTO projects(company_id,name) VALUES(2,%s) RETURNING id',(self.fixture['project'],))[0][0]
        try:
            for route in ('/supervisor-acts','/inspection-orders'):
                self.api(actor,'POST',route,{'projectName':self.fixture['project']},expected=409)
                record = self.api(actor,'POST',route,{'projectId':duplicate})['id']
                table = route[1:].replace('-','_')
                with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                    self.sql(f'UPDATE {table} SET company_id=3 WHERE id=%s',(record,))
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    self.sql(f'UPDATE {table} SET project_id=NULL WHERE id=%s',(record,))
                self.api(actor,'DELETE',f'{route}/{record}')
        finally:
            # Inspection orders intentionally retain soft-deleted records.
            self.sql('DELETE FROM inspection_orders WHERE project_id=%s',(duplicate,))
            self.sql('DELETE FROM projects WHERE id=%s',(duplicate,))
