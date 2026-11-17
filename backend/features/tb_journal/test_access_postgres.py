"""Safety journal paths tested with real authentication and a disposable database."""
import importlib,os,unittest
from unittest.mock import patch
from ..staff.test_access_postgres import StaffAccessPostgresTests

@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class SafetyJournalAccessTests(unittest.TestCase):
    api = StaffAccessPostgresTests.api
    sql = StaffAccessPostgresTests.sql

    @classmethod
    def setUpClass(cls):
        StaffAccessPostgresTests.setUpClass.__func__(cls)
        with cls.main.get_db() as conn, conn.cursor() as cur:
            cur.execute(importlib.import_module('migrations.versions.0110_tb_journal_owner').SCHEMA_SQL)
            cur.execute('INSERT INTO projects(company_id,name) VALUES(3,%s) RETURNING id',(cls.fixture['project'],))
            cls.foreign_project = cur.fetchone()[0]
        conn.close()

    def create(self,company=2,**values):
        user=self.fixture['users']['director' if company==2 else 'stranger']
        return self.api(user,'POST','/tb-journal',{'projectId':self.fixture['projectId'] if company==2 else self.foreign_project,
            'projectName':self.fixture['project'],'instructionText':'Owned instruction','participants':['Person'],**values},company=company)

    def test_list_and_delete_do_not_cross_company_even_same_name(self):
        foreign=self.create(3)['id'];own=self.create()['id'];actor=self.fixture['users']['director']
        for suffix in ('','?project_name='+self.fixture['project']):
            rows=self.api(actor,'GET','/tb-journal'+suffix)
            self.assertNotIn(foreign,[r['id'] for r in rows]);self.assertIn(own,[r['id'] for r in rows])
        self.api(actor,'DELETE',f'/tb-journal/{foreign}',expected=404)
        self.assertEqual(len(self.sql('SELECT id FROM tb_journal WHERE id=%s',(foreign,))),1)

    def test_post_returns_persisted_owner_and_rejects_foreign_parent(self):
        actor=self.fixture['users']['director']
        self.api(actor,'POST','/tb-journal',{'projectId':self.foreign_project},expected=404)
        saved=self.create(companyId=3,createdByUserId=999)
        self.assertEqual((saved['companyId'],saved['projectId']),(2,self.fixture['projectId']))
        self.assertEqual(self.sql('SELECT company_id,project_id,created_by_user_id FROM tb_journal WHERE id=%s',(saved['id'],)),[(2,self.fixture['projectId'],actor['id'])])
        reloaded=next(r for r in self.api(actor,'GET','/tb-journal') if r['id']==saved['id'])
        self.assertEqual(reloaded['instructionText'],'Owned instruction');self.assertEqual(reloaded['participants'],['Person'])
        self.api(actor,'DELETE',f'/tb-journal/{saved["id"]}')
        self.assertNotIn(saved['id'],[r['id'] for r in self.api(actor,'GET','/tb-journal')])

    def test_legacy_rows_and_wrong_company_header_fail_closed(self):
        legacy=self.sql('INSERT INTO tb_journal(project_name) VALUES(%s) RETURNING id',(self.fixture['project'],))[0][0]
        actor=self.fixture['users']['director']
        self.assertNotIn(legacy,[r['id'] for r in self.api(actor,'GET','/tb-journal')])
        self.api(actor,'DELETE',f'/tb-journal/{legacy}',expected=404)
        self.api(actor,'GET','/tb-journal',company=3,expected=403)

    def test_ai_requires_current_owned_project_before_provider_call(self):
        actor=self.fixture['users']['director']
        with patch.object(self.main,'generate_yandex_text',return_value='Test suggestion') as generate:
            self.api(actor,'POST','/tb-journal/ai-generate',{'projectId':self.foreign_project},expected=404)
            generate.assert_not_called()
            answer=self.api(actor,'POST','/tb-journal/ai-generate',{'projectId':self.fixture['projectId']})
            self.assertEqual(answer['instructionText'],'Test suggestion')
            generate.assert_called_once()
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(actor['id'],))
        try:
            with patch.object(self.main,'generate_yandex_text') as generate:
                self.api(actor,'POST','/tb-journal/ai-generate',{'projectId':self.fixture['projectId']},expected=403)
                generate.assert_not_called()
        finally:self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(actor['id'],))

    def test_staff_profile_cannot_pull_another_company_safety_entry(self):
        sid=self.sql("INSERT INTO staff(name,project,company_id,company_scope_verified) VALUES('Same employee',%s,2,TRUE) RETURNING id",(self.fixture['project'],))[0][0]
        own=self.create(masterName='Same employee')['id'];foreign=self.create(3,masterName='Same employee')['id']
        profile=self.api(self.fixture['users']['director'],'GET',f'/staff/{sid}/profile')
        ids=[r['id'] for r in profile['tbJournal']]
        self.assertIn(own,ids);self.assertNotIn(foreign,ids)

    def test_worker_can_create_only_in_assigned_project_and_cannot_delete(self):
        actor=dict(self.customer,role='мастер')
        self.sql("UPDATE users SET role='мастер' WHERE id=%s",(actor['id'],))
        self.sql("UPDATE user_company_roles SET role='мастер' WHERE user_id=%s AND company_id=2",(actor['id'],))
        other=self.sql("INSERT INTO projects(company_id,name) VALUES(2,'Unassigned TB object') RETURNING id")[0][0]
        try:
            saved=self.api(actor,'POST','/tb-journal',{'projectId':self.fixture['projectId'],'participants':['Worker']})
            self.api(actor,'DELETE',f'/tb-journal/{saved["id"]}',expected=403)
            self.api(actor,'POST','/tb-journal',{'projectId':other},expected=403)
            rows=self.api(actor,'GET','/tb-journal')
            self.assertIn(saved['id'],[r['id'] for r in rows])
        finally:
            self.sql("UPDATE users SET role='заказчик' WHERE id=%s",(actor['id'],))
            self.sql("UPDATE user_company_roles SET role='заказчик' WHERE user_id=%s AND company_id=2",(actor['id'],))

    def test_ambiguous_name_and_inconsistent_schema_owner_are_rejected(self):
        import psycopg2
        duplicate=self.sql('INSERT INTO projects(company_id,name) VALUES(2,%s) RETURNING id',(self.fixture['project'],))[0][0]
        actor=self.fixture['users']['director']
        try:
            self.api(actor,'POST','/tb-journal',{'projectName':self.fixture['project']},expected=409)
            saved=self.api(actor,'POST','/tb-journal',{'projectId':duplicate})
            with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
                self.sql('UPDATE tb_journal SET company_id=3 WHERE id=%s',(saved['id'],))
            with self.assertRaises(psycopg2.errors.CheckViolation):
                self.sql('UPDATE tb_journal SET company_id=NULL WHERE id=%s',(saved['id'],))
            self.api(actor,'DELETE',f'/tb-journal/{saved["id"]}')
        finally:self.sql('DELETE FROM projects WHERE id=%s',(duplicate,))
