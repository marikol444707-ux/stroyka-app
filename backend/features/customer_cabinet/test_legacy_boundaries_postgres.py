import os
import unittest
from . import test_extra_works_postgres as support
from ..estimate_deletion.service import delete_estimate_technical_records


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class LegacyBoundaryTests(unittest.TestCase):
    api = support.CustomerExtraWorksTests.api
    sql = support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)

    def test_customer_cannot_read_internal_launch_data(self):
        for path in ['/project-launch/drafts?project_name='+self.fixture['project'],
                     '/project-launch/drafts/9999',
                     '/project-launch/readiness?project_name='+self.fixture['project']]:
            self.api(self.customer,'GET',path,expected=403)

    def test_launch_drafts_are_exactly_company_and_project_scoped(self):
        director=self.fixture['users']['director']; name=self.fixture['project']
        other=self.sql('INSERT INTO projects(company_id,name) VALUES(3,%s) RETURNING id',(name,))[0][0]
        foreign=self.sql("INSERT INTO project_launch_drafts(company_id,project_id,project_name,source_file_name) VALUES(3,%s,%s,'PRIVATE') RETURNING id",(other,name))[0][0]
        self.api(director,'GET',f'/project-launch/drafts/{foreign}',expected=404)
        self.api(director,'PATCH',f'/project-launch/drafts/{foreign}',{'sourceFileName':'changed'},expected=404)
        doc=self.sql("INSERT INTO project_documents(company_id,project_id,project_name,doc_type) VALUES(3,%s,%s,'Договор') RETURNING id",(other,name))[0][0]
        self.api(director,'POST','/project-launch/drafts',{'projectName':name,'sourceDocumentId':doc},expected=404)
        own=self.api(director,'POST','/project-launch/drafts',{'projectName':name,'sourceFileName':'OWN'})['draft']
        rows=self.api(director,'GET','/project-launch/drafts?project_name='+name)['items']
        self.assertIn(own['id'],[r['id'] for r in rows])
        self.assertNotIn(foreign,[r['id'] for r in rows])
        report=self.api(director,'GET','/project-launch/readiness?project_name='+name)['readiness']
        self.assertEqual(report['documentsCount'],0)
        self.assertEqual(report['launchDraftsCount'],1)
        self.api(director,'PATCH',f"/project-launch/drafts/{own['id']}",{'status':'reviewed'})
        self.api(director,'POST',f"/project-launch/drafts/{own['id']}/reject",{'reason':'Test'})

    def test_technical_deletion_preserves_other_owners_and_unassigned_documents(self):
        conn=self.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute('CREATE TEMP TABLE project_documents(id INT, company_id INT, project_id INT, project_name TEXT, doc_type TEXT, number TEXT)')
                cur.execute('CREATE TEMP TABLE estimate_reconciliations(id INT, base_estimate_id INT, next_estimate_id INT, status TEXT, project_name TEXT)')
                cur.execute('CREATE TEMP TABLE estimate_versions(estimate_id INT)')
                cur.execute("INSERT INTO estimate_reconciliations VALUES(7,17,18,'Черновик','Same')")
                cur.execute("INSERT INTO project_documents VALUES (1,2,11,'Same','Сверка смет','СС-7'),(2,3,12,'Same','Сверка смет','СС-7'),(3,NULL,NULL,'Same','Сверка смет','СС-7'),(4,2,13,'Same','Сверка смет','СС-7')")
                delete_estimate_technical_records(cur,estimate_id=17,company_id=2,project_id=11)
                cur.execute('SELECT id FROM project_documents ORDER BY id')
                self.assertEqual(cur.fetchall(),[(2,),(3,),(4,)])
        finally:
            conn.close()
