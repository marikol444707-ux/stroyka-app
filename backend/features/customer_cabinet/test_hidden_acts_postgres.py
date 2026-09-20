import os
import unittest
from . import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class CustomerHiddenActTests(unittest.TestCase):
    api = support.CustomerExtraWorksTests.api
    sql = support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)

    def seed(self, company=2, status='Подтверждено'):
        name=self.fixture['project']
        journal=self.sql("INSERT INTO work_journal(company_id,project,status,description,quantity) VALUES(%s,%s,%s,'Hidden work',1) RETURNING id",(company,name,status))[0][0]
        return self.sql("""INSERT INTO hidden_works_acts(company_id,project_name,work_journal_id,
            work_name,quantity,status,comments,total,signed_contractor)
            VALUES(%s,%s,%s,'Hidden work',1,'Черновик','PRIVATE',99,'Contractor') RETURNING id""",(company,name,journal))[0][0]

    def rows(self):
        return self.api(self.customer,'GET','/hidden-works-acts/customer-visible')

    def test_published_act_confirmation_is_narrow_and_replay_safe(self):
        row_id=self.seed(); row=next(r for r in self.rows() if r['id']==row_id)
        self.assertEqual(row['projectId'],self.fixture['projectId'])
        self.assertNotIn('total',row); self.assertNotIn('comments',row)
        body={'revision':row['revision']}
        self.api(self.customer,'POST',f'/hidden-works-acts/{row_id}/customer-confirm',dict(body,signedContractor='Forgery'),expected=422)
        for _ in range(2):
            self.api(self.customer,'POST',f'/hidden-works-acts/{row_id}/customer-confirm',body)
        self.assertEqual(self.sql('SELECT signed_customer,signed_contractor,total,comments FROM hidden_works_acts WHERE id=%s',(row_id,)),[(self.customer['name'],'Contractor',99,'PRIVATE')])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM audit_log WHERE entity_type='hidden_works_act' AND action='customer_confirm' AND entity_id=%s",(row_id,)),[(1,)])

    def test_foreign_unconfirmed_and_stale_acts_are_not_confirmable(self):
        foreign=self.seed(3); pending=self.seed(status='На проверке'); own=self.seed()
        rows=self.rows(); self.assertNotIn(foreign,[r['id'] for r in rows]);self.assertNotIn(pending,[r['id'] for r in rows])
        body={'revision':next(r['revision'] for r in rows if r['id']==own)}
        for row_id in (foreign,pending):
            self.api(self.customer,'POST',f'/hidden-works-acts/{row_id}/customer-confirm',body,expected=404)
        self.sql("UPDATE hidden_works_acts SET quantity=2 WHERE id=%s",(own,))
        self.api(self.customer,'POST',f'/hidden-works-acts/{own}/customer-confirm',body,expected=409)
        self.api(self.fixture['users']['director'],'POST',f'/hidden-works-acts/{own}/customer-confirm',body,expected=403)
        self.api(self.customer,'GET','/hidden-works-acts',expected=403)
        self.api(self.customer,'PUT',f'/hidden-works-acts/{own}',{},expected=403)

    def test_internal_routes_also_reject_foreign_company_acts(self):
        foreign=self.seed(3); director=self.fixture['users']['director']
        rows=self.api(director,'GET','/hidden-works-acts')
        self.assertNotIn(foreign,[r['id'] for r in rows])
        for method,path,body in [('PUT',f'/hidden-works-acts/{foreign}',{}),
             ('POST',f'/hidden-works-acts/{foreign}/pay',{}),
             ('DELETE',f'/hidden-works-acts/{foreign}',None),
             ('POST',f'/hidden-works-acts/{foreign}/ai-prefill',{})]:
            self.api(director,method,path,body,expected=404)

    def test_last_signature_derives_status_when_no_manual_status_and_replay_is_safe(self):
        row_id=self.seed()
        self.sql("UPDATE hidden_works_acts SET status='',signed_supervisor='Supervisor',signed_subcontractor='Worker' WHERE id=%s",(row_id,))
        body={'revision':next(r['revision'] for r in self.rows() if r['id']==row_id)}
        for _ in range(2):
            self.api(self.customer,'POST',f'/hidden-works-acts/{row_id}/customer-confirm',body)
        self.assertEqual(self.sql('SELECT status FROM hidden_works_acts WHERE id=%s',(row_id,)),[('Подписан',)])
        self.api(self.fixture['users']['director'],'PUT',f'/hidden-works-acts/{row_id}',{'signedCustomer':'Forgery'},expected=409)

    def test_ai_does_not_apply_text_after_a_concurrent_act_edit(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        row_id=self.seed()
        self.sql("UPDATE hidden_works_acts SET conclusion='Keep' WHERE id=%s",(row_id,))
        def generate(**kwargs):
            self.sql('UPDATE hidden_works_acts SET quantity=2 WHERE id=%s',(row_id,))
            return SimpleNamespace(output_text='{"conclusion":"Stale","projectDocs":"Stale","normatives":""}')
        fake=SimpleNamespace(responses=SimpleNamespace(create=generate))
        with patch('openai.OpenAI',return_value=fake):
            self.api(self.fixture['users']['director'],'POST',f'/hidden-works-acts/{row_id}/ai-prefill',{},expected=409)
        self.assertEqual(self.sql('SELECT conclusion,quantity FROM hidden_works_acts WHERE id=%s',(row_id,)),[('Keep',2)])

    def test_audit_failure_rolls_back_customer_signature(self):
        import psycopg2
        row_id=self.seed();body={'revision':next(r['revision'] for r in self.rows() if r['id']==row_id)}
        self.sql("""CREATE FUNCTION test_reject_customer_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.action='customer_confirm' THEN RAISE EXCEPTION 'audit failure'; END IF;
            RETURN NEW; END; $$;
            CREATE TRIGGER test_reject_customer_audit BEFORE INSERT ON audit_log
            FOR EACH ROW EXECUTE FUNCTION test_reject_customer_audit();""")
        try:
            with self.assertRaises(psycopg2.Error):
                self.api(self.customer,'POST',f'/hidden-works-acts/{row_id}/customer-confirm',body)
            self.assertFalse(self.sql('SELECT signed_customer FROM hidden_works_acts WHERE id=%s',(row_id,))[0][0])
        finally:
            self.sql('DROP TRIGGER test_reject_customer_audit ON audit_log; DROP FUNCTION test_reject_customer_audit()')
