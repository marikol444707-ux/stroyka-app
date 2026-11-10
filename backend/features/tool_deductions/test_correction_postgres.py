"""Correction of the initial review through real HTTP and disposable PostgreSQL."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from .test_postgres import ToolDeductionTests
from ..accountable_payments.test_advances_postgres import guarded

@unittest.skipUnless(guarded.RUN_POSTGRES, 'Use the isolated A93 launcher')
class ToolReviewCorrectionTests(unittest.TestCase):
    setUpClass=classmethod(ToolDeductionTests.setUpClass.__func__)
    tearDownClass=classmethod(ToolDeductionTests.tearDownClass.__func__)
    setUp=ToolDeductionTests.setUp
    sql=ToolDeductionTests.sql
    review=ToolDeductionTests.review
    assign=ToolDeductionTests.assign
    salary=ToolDeductionTests.salary

    def correct(self, **changes):
        return self.client.put('/tool-deductions/1/correction',json={
            'expectedRevision':1,'staffId':102,'amount':'800.25','basis':'Исправление по подписанной накладной',
            'confirmed':True,**changes})

    def test_correction_preserves_review_and_warehouse_snapshot_and_drives_new_owner_limit(self):
        self.assertEqual(self.review().status_code,200)
        before=self.sql('SELECT snapshot,basis FROM tool_deduction_sources WHERE id=1')[0]
        warehouse=self.sql('SELECT to_jsonb(t) FROM tools t ORDER BY id')
        response=self.correct();self.assertEqual(response.status_code,200,response.text)
        row=self.client.get('/tool-deductions').json()['reviewed'][0]
        self.assertEqual((row['staff_id'],row['amount'],row['revision']),(102,800.25,2))
        self.assertEqual(self.sql('SELECT snapshot,basis FROM tool_deduction_sources WHERE id=1')[0],before)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM tools t ORDER BY id'),warehouse)
        events=self.sql('SELECT change FROM tool_deduction_events ORDER BY revision')
        self.assertEqual(events[0][0]['operation'],'review')
        self.assertEqual(events[1][0]['before']['staffId'],100)
        self.assertEqual(events[1][0]['after']['staffId'],102)
        self.assertEqual(events[1][0]['after']['amount'],800.25)
        self.assertEqual(self.assign(800.26,revision=2,actId=4).status_code,409)
        self.assertEqual(self.assign(100,revision=2,actId=1).status_code,404)
        self.assertEqual(self.assign('800.25',revision=2,actId=4).status_code,200)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_active_allocations_require_explicit_cancel_before_correction(self):
        self.review();self.assign(600,actId=1)
        self.assertEqual(self.correct(expectedRevision=2).status_code,409)
        self.assertEqual(self.assign(0,revision=2,actId=1).status_code,200)
        self.assertEqual(self.correct(expectedRevision=3).status_code,200)
        self.assertEqual(self.sql('SELECT staff_id,amount FROM tool_deduction_allocations')[0],(100,0))
        self.assertEqual(self.sql('SELECT status FROM interim_acts WHERE id=1')[0][0],'Новый')
        self.assertEqual(self.assign(100,revision=4,month='2026-07').status_code,200)
        rows=self.client.get('/salary-tool-deductions',params={'month':'2026-07'}).json()['rows']
        self.assertEqual({r['staffId']:r['amount'] for r in rows},{100:0,102:100})

    def test_historical_deduction_blocks_correction_without_rewriting_history(self):
        self.review(previouslyDeducted=100)
        before=self.sql('SELECT to_jsonb(t) FROM tool_deduction_sources t')
        self.assertEqual(self.correct().status_code,409)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM tool_deduction_sources t'),before)
        self.assertEqual(self.sql('SELECT count(*) FROM tool_deduction_events')[0][0],1)

    def test_paid_or_refunded_act_is_not_reassigned(self):
        self.review();self.assign(1000,actId=1)
        self.client.post('/interim-acts/1/pay',json={'amount':9000})
        self.assertEqual(self.correct(expectedRevision=2).status_code,409)
        self.client.post('/tool-deductions/1/refunds',json={'expectedRevision':2,'allocationId':1,'amount':1000,'confirmed':True,'basis':'Возврат денег'})
        self.assertEqual(self.correct(expectedRevision=3).status_code,409)
        self.assertEqual(self.sql('SELECT staff_id,amount,refunded FROM tool_deduction_allocations')[0],(100,1000,1000))

    def test_concurrent_corrections_or_old_allocation_cannot_overwrite_new_owner(self):
        self.review()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda amount:self.correct(amount=amount),[700,800]))
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.assign(100,actId=1).status_code,409)
        self.assertEqual(self.sql('SELECT count(*) FROM tool_deduction_events')[0][0],2)

    def test_correction_and_allocation_share_one_transaction_lock(self):
        self.review()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.correct);b=pool.submit(self.assign,500,actId=1)
            responses=[a.result(),b.result()]
        self.assertEqual(sorted(r.status_code for r in responses),[200,409])
        self.assertEqual(self.sql('SELECT count(*) FROM tool_deduction_events')[0][0],2)

    def test_company_roles_revision_and_confirmation_are_required(self):
        self.review()
        for kwargs,status in [({'staffId':101},404),({'staffId':True},400),({'expectedRevision':None},409),
                              ({'confirmed':False},409),({'basis':''},400),({'amount':'0'},400),
                              ({'amount':'1.001'},400),({'projectId':20},400)]:
            with self.subTest(kwargs=kwargs):self.assertEqual(self.correct(**kwargs).status_code,status)
        self.assertEqual(self.client.put('/tool-deductions/1/correction',json={},headers={'X-Company-Id':'5'}).status_code,403)
        self.user['role']='мастер';self.assertEqual(self.correct().status_code,403)
        self.assertEqual(self.sql('SELECT revision FROM tool_deduction_sources WHERE id=1')[0][0],1)

    def test_known_user_identity_cannot_be_bypassed_by_manual_selection(self):
        self.sql("INSERT INTO user_company_roles(id,user_id,company_id,role,active,staff_id) VALUES(9990,900,4,'мастер',TRUE,100)")
        self.sql('UPDATE tool_history SET master_id=900 WHERE id=10')
        self.review()
        self.assertEqual(self.correct(staffId=102).status_code,409)
        self.assertEqual(self.correct(staffId=100,amount=800).status_code,200)

    def test_foreign_source_and_unverified_staff_are_not_corrected(self):
        self.review()
        self.sql("""INSERT INTO tool_deduction_sources(company_id,tool_id,source_key,staff_id,project_id,amount,previously_deducted,basis,snapshot,revision)
            VALUES(5,2,'card:2',101,20,1000,0,'Other company','{}',1)""")
        result=self.client.put('/tool-deductions/2/correction',json={'expectedRevision':1,'staffId':100,'amount':10,'confirmed':True,'basis':'Подмена'})
        self.assertEqual(result.status_code,404)
        self.sql('UPDATE staff SET company_scope_verified=FALSE WHERE id=102')
        self.assertEqual(self.correct().status_code,404)
        self.assertEqual(self.sql('SELECT staff_id,amount,revision FROM tool_deduction_sources ORDER BY id'),[(100,1000,1),(101,1000,1)])

    def test_paid_salary_snapshot_survives_rejected_correction(self):
        self.review();self.assign(1000,month='2026-07');self.salary(amount=7700)
        before=self.sql('SELECT to_jsonb(t) FROM salary_payments t')
        self.assertEqual(self.correct(expectedRevision=2).status_code,409)
        self.assertEqual(self.sql('SELECT to_jsonb(t) FROM salary_payments t'),before)
        self.assertEqual(self.sql('SELECT staff_id,amount,revision FROM tool_deduction_sources')[0],(100,1000,2))

    def test_audit_failure_rolls_back_source_and_revision(self):
        from fastapi.testclient import TestClient
        self.review()
        self.sql("""CREATE FUNCTION reject_review_correction() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.change->>'operation'='correct_review' THEN RAISE EXCEPTION 'Synthetic audit failure'; END IF; RETURN NEW; END $$;
            CREATE TRIGGER reject_review_correction BEFORE INSERT ON tool_deduction_events FOR EACH ROW EXECUTE FUNCTION reject_review_correction();""")
        try:
            with TestClient(self.app,raise_server_exceptions=False) as client:
                result=client.put('/tool-deductions/1/correction',json={'expectedRevision':1,'staffId':102,'amount':800,'confirmed':True,'basis':'Сверка'})
            self.assertEqual(result.status_code,500)
            self.assertEqual(self.sql('SELECT staff_id,amount,revision FROM tool_deduction_sources')[0],(100,1000,1))
            self.assertEqual(self.sql('SELECT count(*) FROM tool_deduction_events')[0][0],1)
        finally:
            self.sql('DROP TRIGGER reject_review_correction ON tool_deduction_events; DROP FUNCTION reject_review_correction()')
        self.assertEqual(self.correct().status_code,200)
