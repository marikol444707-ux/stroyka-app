"""Retention HTTP and database regression tests on a disposable PostgreSQL cluster."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from ..accountable_payments import test_advances_postgres as fixture

@unittest.skipUnless(fixture.guarded.RUN_POSTGRES, 'Use isolated A93 launcher')
class RetentionPostgresTests(unittest.TestCase):
    setUpClass = classmethod(fixture.AdvancePostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.AdvancePostgresTests.tearDownClass.__func__)
    setUp = fixture.AdvancePostgresTests.setUp
    sql = fixture.AdvancePostgresTests.sql
    allocate = fixture.AdvancePostgresTests.allocate

    def hold(self, amount=500, revision=0, act=1, **kwargs):
        return self.client.put(f'/interim-acts/{act}/retention',json={
            'amount':amount,'expectedRevision':revision,'basis':'Договор, пункт 5','confirmed':True,**kwargs})

    def release(self, amount=500, revision=1, act=1, **kwargs):
        return self.client.post(f'/interim-acts/{act}/retention-release',json={
            'amount':amount,'expectedRevision':revision,'basis':'Условия договора проверены','confirmed':True,**kwargs})

    def act_row(self):
        response=self.client.get('/interim-acts')
        self.assertEqual(response.status_code,200,response.text)
        return next(a for a in response.json() if a['id']==1)

    def test_default_zero_then_confirm_hold_pay_release_and_final_payment(self):
        self.assertEqual((self.act_row()['retentionOutstanding'],self.act_row()['remainingAmount']),(0,10000))
        response=self.hold();self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(response.json()['paymentCreated'])
        self.assertEqual(self.act_row()['remainingAmount'],9500)
        self.assertEqual(self.client.post('/interim-acts/1/pay',json={'amount':9501}).status_code,400)
        paid=self.client.post('/interim-acts/1/pay',json={'amount':9500})
        self.assertEqual(paid.status_code,200,paid.text)
        self.assertEqual((self.act_row()['remainingAmount'],self.act_row()['status']),(0,'Частично оплачен'))
        self.assertEqual(self.hold(0,1).status_code,409)
        result=self.release();self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],1)
        self.assertEqual((self.act_row()['remainingAmount'],self.act_row()['paidAmount']),(500,9500))
        self.assertEqual(self.release(revision=2).status_code,409)
        paid=self.client.post('/interim-acts/1/pay',json={'amount':500})
        self.assertEqual(paid.status_code,200,paid.text)
        self.assertEqual(self.act_row()['status'],'Оплачен')
        self.assertEqual(self.sql('SELECT sum(amount) FROM project_payments')[0][0],-10000)

    def test_two_release_tabs_do_not_unlock_twice(self):
        self.assertEqual(self.hold().status_code,200)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.release(300),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.act_row()['retentionOutstanding'],200)
        self.assertEqual(self.sql('SELECT count(*) FROM performer_retention_events')[0][0],2)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_hold_competes_with_advance_without_overallocation(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.hold,7000);b=pool.submit(self.allocate,amount=7000)
            responses=[a.result(),b.result()]
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        row=self.act_row()
        self.assertEqual(row['retentionOutstanding']+row['advanceAmount'],7000)
        self.assertEqual(row['remainingAmount'],3000)

    def test_hold_competes_with_cash_without_overpayment(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.hold,7000)
            b=pool.submit(self.client.post,'/interim-acts/1/pay',json={'amount':7000})
            responses=[a.result(),b.result()]
        self.assertEqual(sum(r.status_code==200 for r in responses),1)
        row=self.act_row();self.assertEqual(row['paidAmount']+row['retentionOutstanding'],7000)

    def test_confirmation_basis_revision_and_exact_cents(self):
        for kwargs,code in [({'confirmed':False},409),({'expectedRevision':None},409),({'basis':''},400)]:
            r=self.hold(**kwargs);self.assertEqual(r.status_code,code,r.text)
        for amount in [None,True,-1,0.001,'NaN']:
            self.assertEqual(self.hold(amount).status_code,400)
        self.assertEqual(self.hold('0.30').status_code,200)
        self.assertEqual(self.release('0.10').status_code,200)
        self.assertEqual(self.act_row()['retentionOutstanding'],0.2)
        self.assertEqual(self.release('0.20',revision=2).status_code,200)
        self.assertEqual(self.act_row()['remainingAmount'],10000)

    def test_company_role_and_daily_v2_boundaries(self):
        self.assertEqual(self.hold(act=3).status_code,404)
        self.user['role']='мастер';self.assertEqual(self.hold().status_code,403)
        self.user['role']='бухгалтер'
        self.sql("UPDATE interim_acts SET source_type='daily_work' WHERE id=1")
        self.assertEqual(self.hold().status_code,409)
        self.sql("INSERT INTO brigade_contracts(id,company_id,settlement_version) VALUES(40,4,2)")
        self.sql("INSERT INTO brigade_contract_items(id,contract_id) VALUES(41,40)")
        self.sql("INSERT INTO work_journal(id,company_id,contract_item_id) VALUES(42,4,41)")
        self.sql("UPDATE interim_acts SET work_journal_ids='[42]' WHERE id=2")
        self.assertEqual(self.hold(act=2).status_code,409)
        self.assertEqual(self.sql('SELECT count(*) FROM performer_retention_events')[0][0],0)

    def test_old_writers_cannot_bypass_hold_and_unrelated_scan_edit_stays_available(self):
        import psycopg2
        self.assertEqual(self.hold().status_code,200)
        for data in [{'paidAmount':10000},{'totalAmount':1},{'status':'Аннулирован'}]:
            self.assertEqual(self.client.put('/interim-acts/1',json=data).status_code,409)
        self.assertEqual(self.client.delete('/interim-acts/1').status_code,409)
        for query in ["UPDATE interim_acts SET paid_amount=10000 WHERE id=1",
                      "UPDATE interim_acts SET total_amount=1 WHERE id=1",
                      "UPDATE interim_acts SET company_id=5 WHERE id=1",
                      "UPDATE interim_acts SET status='Аннулирован' WHERE id=1",
                      "DELETE FROM interim_acts WHERE id=1"]:
            with self.subTest(query=query),self.assertRaises(psycopg2.Error):self.sql(query)
        self.assertEqual(self.act_row()['paidAmount'],0)
        self.assertEqual(self.client.put('/interim-acts/1',json={'scanUrl':'/test-signed.pdf','status':'Подписан'}).status_code,200)

    def test_set_zero_allows_cancellation_and_preserves_audit(self):
        self.assertEqual(self.hold().status_code,200)
        self.assertEqual(self.hold(0,1).status_code,200)
        self.assertEqual(self.act_row()['remainingAmount'],10000)
        self.assertEqual(self.client.delete('/interim-acts/1').status_code,200)
        self.assertEqual(self.sql('SELECT count(*) FROM performer_retention_events')[0][0],2)

    def test_first_confirmation_on_old_partially_paid_act_is_limited_to_unpaid_amount(self):
        self.sql("UPDATE interim_acts SET paid_amount=9500,status='Частично оплачен' WHERE id=1")
        self.assertEqual(self.hold(501).status_code,409)
        response=self.hold(500);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.act_row()['remainingAmount'],0)
        self.assertEqual(self.hold(400,1).status_code,409)
        self.assertEqual(self.release().status_code,200)
        self.assertEqual(self.act_row()['remainingAmount'],500)

    def test_null_legacy_cash_is_zero_for_explicit_confirmation(self):
        self.sql('UPDATE interim_acts SET paid_amount=NULL WHERE id=1')
        result=self.hold();self.assertEqual(result.status_code,200,result.text)
        self.assertEqual((self.act_row()['paidAmount'],self.act_row()['remainingAmount']),(0,9500))
