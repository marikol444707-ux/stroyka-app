"""Historical refunds use explicit opening review, real HTTP and disposable PG."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException
from fastapi.testclient import TestClient
from .test_postgres import ToolDeductionTests
from ..accountable_payments.test_advances_postgres import guarded
from ..project_payment_access.routes import register_project_payments_module

@unittest.skipUnless(guarded.RUN_POSTGRES, 'Use isolated A93 launcher')
class HistoricalToolRefundTests(unittest.TestCase):
    setUpClass=classmethod(ToolDeductionTests.setUpClass.__func__)
    tearDownClass=classmethod(ToolDeductionTests.tearDownClass.__func__)
    sql=ToolDeductionTests.sql
    review=ToolDeductionTests.review
    assign=ToolDeductionTests.assign

    def setUp(self):
        ToolDeductionTests.setUp(self)
        def context(cur,user,project,mode,**kw):
            if kw.get('x_company_id') not in (None,'4'):raise HTTPException(403,'Foreign company')
            return {'companyId':4,'mode':'company'}
        def connect():
            conn=self.connect();conn.autocommit=True;return conn
        register_project_payments_module(self.app,dict(get_db=connect,get_current_user=lambda:self.user,
            finance_roles=('бухгалтер','директор'),platform_staff_roles=(),client_account_roles=(),
            resolve_work_company_context=context,effective_company_actors=lambda u,c:[u],
            resolve_project_payment_actor=lambda *a,**k:(4,self.user),positive_int_or_none=lambda n:int(n) if n else None,
            require_project_access=lambda *a:None,has_package_access=lambda *a:True))

    def opening(self, **data):
        return self.client.put('/tool-deductions/1/historical-refund-review',json={
            'expectedRevision':1,'previouslyRefunded':'100','basis':'Сверены прежние возвраты по документам',
            'confirmed':True,**data})

    def refund(self, **data):
        return self.client.post('/tool-deductions/1/historical-refunds',json={
            'expectedRevision':2,'amount':'200','basis':'Возврат подтверждён распиской','confirmed':True,**data})

    def test_opening_is_explicit_no_cash_then_refund_preserves_originals_and_capacity(self):
        self.review(previouslyDeducted=600)
        row=self.client.get('/tool-deductions').json()['reviewed'][0]
        self.assertFalse(row['historicalRefund']['reviewed'])
        self.assertIsNone(row['historicalRefund']['remaining'])
        self.assertEqual(self.refund(expectedRevision=1).status_code,409)
        before=self.sql('SELECT to_jsonb(t) FROM tools t ORDER BY id')
        acts=self.sql('SELECT to_jsonb(t) FROM interim_acts t ORDER BY id')
        self.assertEqual(self.opening().status_code,200)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)
        result=self.refund();self.assertEqual(result.status_code,200,result.text)
        state=self.client.get('/tool-deductions').json()['reviewed'][0]['historicalRefund']
        self.assertEqual(state,{'reviewed':True,'previouslyRefunded':100,'refunded':200,'remaining':300})
        self.assertEqual(self.sql('SELECT amount,previously_deducted,staff_id,project_id,revision FROM tool_deduction_sources')[0],(1000,600,100,19,3))
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM tools t ORDER BY id'),before)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM interim_acts t ORDER BY id'),acts)
        self.assertEqual(self.sql('SELECT count(*) FROM salary_payments')[0][0],0)
        self.assertEqual(self.assign(401,revision=3,actId=1).status_code,409)
        self.assertEqual(self.assign(400,revision=3,actId=1).status_code,200)
        self.assertEqual(self.sql('SELECT company_id,project_name,amount FROM project_payments'),[(4,'Object',-200)])

    def test_two_equal_refunds_reach_payment_list_without_dedup_or_cross_company_leak(self):
        self.review(previouslyDeducted=600);self.opening(previouslyRefunded=0)
        self.assertEqual(self.refund().status_code,200)
        self.assertEqual(self.refund(expectedRevision=3).status_code,200)
        self.sql("INSERT INTO project_payments(company_id,project_name,amount,note,date,added_by) VALUES(5,'Object',-200,'Foreign','2026-07-01','Accountant')")
        rows=self.client.get('/project-payments',params={'project_name':'Object'}).json()
        self.assertEqual(len(rows),2,rows)
        self.assertEqual(sum(r['amount'] for r in rows),-400)
        self.assertEqual({r['companyId'] for r in rows},{4})
        self.assertEqual({r.get('projectId') for r in rows},{19})
        self.assertEqual(len({r['id'] for r in rows}),2)
        state=self.client.get('/tool-deductions').json()['reviewed'][0]['historicalRefund']
        self.assertEqual(state['remaining'],200)

    def test_explicit_zero_one_opening_and_refund_limit(self):
        self.review(previouslyDeducted=600)
        for value in (None,'',-1,601,'0.001',True):
            with self.subTest(value=value):self.assertIn(self.opening(previouslyRefunded=value).status_code,(400,409))
        self.assertEqual(self.opening(previouslyRefunded=0).status_code,200)
        self.assertEqual(self.opening(expectedRevision=2,previouslyRefunded=0).status_code,409)
        self.assertEqual(self.refund(amount=601).status_code,409)
        self.assertEqual(self.refund(amount=600).status_code,200)
        self.assertEqual(self.refund(expectedRevision=3,amount=1).status_code,409)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments')[0],(1,-600))

    def test_concurrent_refunds_and_replay_do_not_pay_twice(self):
        self.review(previouslyDeducted=600);self.opening(previouslyRefunded=0)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.refund(amount=400),range(2)))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.refund(amount=400).status_code,409)
        self.assertEqual(self.refund(expectedRevision=3,amount=201).status_code,409)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments')[0],(1,-400))

    def test_concurrent_opening_is_a_single_immutable_fact(self):
        self.review(previouslyDeducted=600)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda value:self.opening(previouslyRefunded=value),[0,100]))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.sql('SELECT count(*) FROM tool_deduction_events')[0][0],2)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_missing_confirmation_revision_and_foreign_identity_do_not_write(self):
        self.review(previouslyDeducted=600)
        for kwargs,status in [({'expectedRevision':None},409),({'confirmed':False},409),({'basis':''},400),({'companyId':5},400)]:
            with self.subTest(kwargs=kwargs):self.assertEqual(self.opening(**kwargs).status_code,status)
        self.assertEqual(self.opening().status_code,200)
        for kwargs,status in [({'expectedRevision':None},409),({'confirmed':False},409),({'basis':''},400),({'staffId':101},400),({'amount':0},400),({'amount':'0.001'},400)]:
            with self.subTest(kwargs=kwargs):self.assertEqual(self.refund(**kwargs).status_code,status)
        self.assertEqual(self.client.post('/tool-deductions/1/historical-refunds',json={},headers={'X-Company-Id':'5'}).status_code,403)
        self.user['role']='мастер';self.assertEqual(self.refund().status_code,403)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_zero_previous_deduction_and_fully_returned_source_cannot_pay(self):
        self.review()
        self.assertEqual(self.opening(previouslyRefunded=0).status_code,409)
        self.assertEqual(self.refund(expectedRevision=1).status_code,409)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_ambiguous_project_name_blocks_cash_and_audit_failure_rolls_back(self):
        self.review(previouslyDeducted=600);self.opening()
        self.sql("INSERT INTO projects(id,company_id,name) VALUES(22,4,'Object')")
        self.assertEqual(self.refund().status_code,409)
        self.sql('DELETE FROM projects WHERE id=22')
        self.sql("""CREATE FUNCTION reject_historical_refund() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.change->>'operation'='historical_refund' THEN RAISE EXCEPTION 'Synthetic audit failure'; END IF; RETURN NEW; END $$;
            CREATE TRIGGER reject_historical_refund BEFORE INSERT ON tool_deduction_events FOR EACH ROW EXECUTE FUNCTION reject_historical_refund();""")
        try:
            with TestClient(self.app,raise_server_exceptions=False) as client:
                result=client.post('/tool-deductions/1/historical-refunds',json={'expectedRevision':2,'amount':200,'basis':'Расписка','confirmed':True})
            self.assertEqual(result.status_code,500)
            self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)
            self.assertEqual(self.sql('SELECT revision FROM tool_deduction_sources')[0][0],2)
        finally:self.sql('DROP TRIGGER reject_historical_refund ON tool_deduction_events; DROP FUNCTION reject_historical_refund()')
        self.assertEqual(self.refund().status_code,200)

    def test_new_allocation_refunds_and_historical_refunds_have_separate_limits(self):
        self.review(previouslyDeducted=600);self.opening(previouslyRefunded=100)
        self.assertEqual(self.assign(400,revision=2,actId=1).status_code,200)
        self.assertEqual(self.client.post('/interim-acts/1/pay',json={'amount':9600}).status_code,200)
        self.assertEqual(self.client.post('/tool-deductions/1/refunds',json={'expectedRevision':3,'allocationId':1,'amount':400,'basis':'Возврат нового удержания','confirmed':True}).status_code,200)
        self.assertEqual(self.refund(expectedRevision=4,amount=500).status_code,200)
        self.assertEqual(self.sql('SELECT paid_amount FROM interim_acts WHERE id=1')[0][0],10000)
        self.assertEqual(self.sql('SELECT amount,refunded FROM tool_deduction_allocations')[0],(400,400))
        self.assertEqual(self.refund(expectedRevision=5,amount=1).status_code,409)
        import psycopg2
        with self.assertRaises(psycopg2.Error):self.sql('DELETE FROM project_payments WHERE id=3')
        with self.assertRaises(psycopg2.Error):self.sql('DELETE FROM tool_deduction_events')

    def test_fully_returned_opening_preserves_old_deduction_without_new_cash(self):
        self.review(previouslyDeducted=600)
        self.assertEqual(self.opening(previouslyRefunded=600).status_code,200)
        self.assertEqual(self.refund(amount=1).status_code,409)
        self.assertEqual(self.client.get('/tool-deductions').json()['reviewed'][0]['historicalRefund']['remaining'],0)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_foreign_source_and_worker_payment_list_are_inaccessible(self):
        self.review(previouslyDeducted=600)
        self.sql("""INSERT INTO tool_deduction_sources(company_id,tool_id,source_key,staff_id,project_id,amount,previously_deducted,basis,snapshot,revision)
            VALUES(5,2,'card:2',101,20,1000,600,'Other company','{}',1)""")
        for method,path,payload in [('PUT','historical-refund-review',{'previouslyRefunded':0}),('POST','historical-refunds',{'amount':10})]:
            result=self.client.request(method,'/tool-deductions/2/'+path,json={'expectedRevision':1,'confirmed':True,'basis':'Подмена',**payload})
            self.assertEqual(result.status_code,404)
        self.opening();self.refund()
        self.user['role']='мастер'
        self.assertEqual(self.client.get('/tool-deductions').status_code,403)
        self.assertEqual(self.client.get('/project-payments').json(),[])

    def test_equal_new_allocation_refunds_also_keep_distinct_cash_rows(self):
        self.review();self.assign(1000,actId=1)
        self.assertEqual(self.client.post('/interim-acts/1/pay',json={'amount':9000}).status_code,200)
        for revision in (2,3):
            result=self.client.post('/tool-deductions/1/refunds',json={'expectedRevision':revision,'allocationId':1,'amount':200,'confirmed':True,'basis':'Две частичные выплаты'})
            self.assertEqual(result.status_code,200)
        rows=self.client.get('/project-payments').json()
        self.assertEqual(len(rows),3)
        self.assertEqual(sum(r['amount'] for r in rows),-9400)

    def test_api_storno_cannot_separate_cash_from_historical_refund_audit(self):
        from unittest.mock import patch
        self.review(previouslyDeducted=600);self.opening();self.refund()
        # The fixture injects company auth; real deletion SQL/guards run unchanged.
        with patch('backend.features.project_payment_access.routes.resolve_resource_company_actor',return_value=({'companyId':4},self.user)):
            result=self.client.delete('/project-payments/1')
        self.assertEqual(result.status_code,409)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments')[0],(1,-200))
        self.assertEqual(self.client.get('/tool-deductions').json()['reviewed'][0]['historicalRefund']['remaining'],300)
