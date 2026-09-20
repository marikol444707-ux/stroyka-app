"""Customer decisions against real authenticated HTTP and an isolated database."""
import os
import unittest
from . import test_authenticated_records_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class CustomerExtraWorksTests(unittest.TestCase):
    api = support.AuthenticatedCustomerRecordTest.api

    @classmethod
    def setUpClass(cls):
        support.AuthenticatedCustomerRecordTest.setUpClass.__func__(cls)

    def sql(self, query, params=()):
        conn = self.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall() if cur.description else []
        finally:
            conn.close()

    def seed(self):
        return self.sql("""INSERT INTO unexpected_works(company_id,project_id,project_name,
            description,quantity,unit,price,total,status,notes)
            VALUES(2,%s,%s,'Дополнительная работа',2,'м2',150,300,'Ожидает согласования',
            'private note') RETURNING id""", (self.fixture['projectId'],self.fixture['project']))[0][0]

    def offer(self, row_id):
        return next(row for row in self.api(self.customer,'GET','/unexpected-works/customer-visible') if row['id']==row_id)

    def test_accept_keeps_amount_and_does_not_manufacture_completed_work(self):
        row_id=self.seed(); row=self.offer(row_id)
        self.assertNotIn('notes',row)
        self.assertEqual((row['companyId'],row['projectId']),(2,self.fixture['projectId']))
        body={'decision':'approve','revision':row['revision']}
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',body)
        self.assertEqual(self.sql('SELECT status,price,total FROM unexpected_works WHERE id=%s',(row_id,))[0],
                         ('Утверждено отдельной допработой',150,300))
        self.assertEqual(self.sql('SELECT COUNT(*) FROM work_journal WHERE unexpected_work_id=%s',(row_id,)),[(0,)])
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',body)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM audit_log WHERE entity_type='unexpected_work' AND entity_id=%s AND action='customer_decision'",(row_id,)),[(1,)])
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',dict(body,decision='reject'),expected=409)

    def test_changed_terms_and_extra_fields_cannot_be_approved(self):
        row_id=self.seed(); row=self.offer(row_id)
        body={'decision':'approve','revision':row['revision']}
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',dict(body,total=1),expected=422)
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',dict(body,decision=[]),expected=422)
        self.api(self.customer,'GET','/unexpected-works',expected=403)
        self.sql('UPDATE unexpected_works SET price=200,total=400 WHERE id=%s',(row_id,))
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',body,expected=409)
        self.assertEqual(self.sql('SELECT status FROM unexpected_works WHERE id=%s',(row_id,)),[('Ожидает согласования',)])

    def test_foreign_company_and_unassigned_project_and_staff_cannot_decide(self):
        row_id=self.seed(); row=self.offer(row_id); body={'decision':'reject','revision':row['revision']}
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',body,company=3,expected=403)
        self.api(self.fixture['users']['director'],'POST',f'/unexpected-works/{row_id}/customer-decision',body,expected=403)
        other=self.sql("INSERT INTO projects(company_id,name) VALUES(2,'Other customer project') RETURNING id")[0][0]
        self.sql('UPDATE unexpected_works SET project_id=%s WHERE id=%s',(other,row_id))
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',body,expected=404)

    def test_reject_is_recorded_and_not_listed_as_approved(self):
        row_id=self.seed(); row=self.offer(row_id)
        self.api(self.customer,'POST',f'/unexpected-works/{row_id}/customer-decision',
                 {'decision':'reject','revision':row['revision']})
        self.assertEqual(self.offer(row_id)['status'],'Отклонено')
        self.sql("UPDATE unexpected_works SET status='На рассмотрении' WHERE id=%s",(row_id,))
        self.assertNotIn(row_id,[r['id'] for r in self.api(self.customer,'GET','/unexpected-works/customer-visible')])
