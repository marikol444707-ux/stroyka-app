import unittest
from concurrent.futures import ThreadPoolExecutor
from ..accountable_payments import test_advances_postgres as fixture
from ..salary_payments.routes import register_salary_payments_module

@unittest.skipUnless(fixture.guarded.RUN_POSTGRES, 'Use isolated A93 launcher')
class ToolDeductionTests(unittest.TestCase):
    setUpClass=classmethod(fixture.AdvancePostgresTests.setUpClass.__func__)
    tearDownClass=classmethod(fixture.AdvancePostgresTests.tearDownClass.__func__)
    sql=fixture.AdvancePostgresTests.sql
    allocate_advance=fixture.AdvancePostgresTests.allocate

    def setUp(self):
        fixture.AdvancePostgresTests.setUp(self)
        self.sql('TRUNCATE tools,tool_history,tool_deduction_sources,tool_deduction_allocations,tool_deduction_events,salary_payments RESTART IDENTITY CASCADE')
        self.sql("""INSERT INTO tools(id,company_id,name,inventory_number,cost,master_name,project_id,project,issue_type)
            VALUES(1,4,'Drill','T-1',1000,'Same name',19,'Object','В счёт зарплаты'),
            (2,5,'Foreign','T-2',1000,'Same name',20,'Object','В счёт зарплаты');
            INSERT INTO tool_history(id,company_id,tool_id,master_name,project_id,project,date,action,issue_type)
            VALUES(10,4,1,'Same name',19,'Object','2026-07-01','Выдача','В счёт зарплаты');""")
        def connect():
            conn=self.connect();conn.autocommit=True;return conn
        register_salary_payments_module(self.app,dict(get_db=connect,get_current_user=lambda:self.user,
            resolve_work_company_context=lambda *a,**k:{'companyId':4,'mode':'company'},
            effective_company_actors=lambda u,c:[u],finance_roles=('бухгалтер','директор')))

    def review(self, **changes):
        data=self.client.get('/tool-deductions').json()
        source=next((s for s in data['sources'] if s['sourceKey']=='history:10'),None)
        if source is None:source=next(r['snapshot'] for r in data['reviewed'] if r['source_key']=='history:10')
        return self.client.post('/tool-deductions/review',json={'sourceKey':source['sourceKey'],
            'expectedState':source['expectedState'],'staffId':100,'projectId':19,'amount':'1000',
            'previouslyDeducted':'0','confirmed':True,'basis':'Проверенный документ покупки',**changes})

    def assign(self, amount, revision=1, **target):
        return self.client.put('/tool-deductions/1/allocations',json={'amount':amount,'expectedRevision':revision,
            'confirmed':True,'basis':'Распределение по документам',**target})

    def salary(self, month='2026-07', amount=8500):
        rows=self.client.get('/salary-tool-deductions',params={'month':month}).json()['rows']
        row=next(r for r in rows if r['staffId']==100)
        return self.client.post('/salary-payments',json={'staffId':100,'month':month,'amount':amount,
            'expectedToolState':row['state'],'toolDeductionAmount':row['amount']})

    def test_one_source_shared_between_act_and_month_cannot_be_repeated(self):
        result=self.review();self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.assign(600,actId=1).status_code,200)
        self.assertEqual(self.assign(400,revision=2,month='2026-07').status_code,200)
        self.assertEqual(self.assign(1,revision=3,actId=2).status_code,409)
        act=next(r for r in self.client.get('/interim-acts').json() if r['id']==1)
        self.assertEqual((act['toolDeductionAmount'],act['remainingAmount']),(600,9400))
        self.assertEqual(self.client.post('/interim-acts/1/pay',json={'amount':9401}).status_code,400)
        self.assertEqual(self.client.post('/interim-acts/1/pay',json={'amount':9400}).status_code,200)
        paid=self.salary();self.assertEqual(paid.status_code,200,paid.text)
        self.assertEqual(self.salary().status_code,409)
        self.assertEqual(self.sql('SELECT sum(amount) FROM tool_deduction_allocations')[0][0],1000)

    def test_two_tabs_and_legacy_requests_cannot_duplicate_or_change_allocation(self):
        self.assertEqual(self.review().status_code,200)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda act:self.assign(700,actId=act),[1,2]))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertEqual(self.sql('SELECT sum(amount) FROM tool_deduction_allocations')[0][0],700)
        self.assertEqual(self.client.post('/salary-payments',json={'staffId':100,'month':'2026-07','amount':100}).status_code,409)
        self.assertEqual(self.review().status_code,409) # source is no longer an unreviewed choice

    def test_review_requires_explicit_previous_amount_and_exact_company_person(self):
        self.assertEqual(self.review(previouslyDeducted=None).status_code,400)
        self.assertEqual(self.review(staffId=101).status_code,404)
        self.assertEqual(self.review(projectId=20).status_code,404)
        self.assertEqual(self.review(previouslyDeducted=800).status_code,200)
        self.assertEqual(self.assign(201,actId=1).status_code,409)
        self.assertEqual(self.assign(200,actId=4).status_code,404)
        self.assertEqual(self.assign(200,actId=1).status_code,200)

    def test_cash_refund_preserves_history_and_cannot_be_replayed(self):
        self.assertEqual(self.review().status_code,200)
        self.assertEqual(self.assign(1000,actId=1).status_code,200)
        self.assertEqual(self.client.post('/interim-acts/1/pay',json={'amount':9000}).status_code,200)
        self.assertEqual(self.assign(0,revision=2,actId=1).status_code,409)
        payload={'expectedRevision':2,'allocationId':1,'amount':1000,'confirmed':True,'basis':'Подтверждённый возврат денег за инструмент'}
        response=self.client.post('/tool-deductions/1/refunds',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post('/tool-deductions/1/refunds',json=payload).status_code,409)
        row=next(r for r in self.client.get('/interim-acts').json() if r['id']==1)
        self.assertEqual((row['paidAmount'],row['toolDeductionAmount'],row['remainingAmount'],row['status']),(10000,0,0,'Оплачен'))
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments')[0],(2,-10000))
        self.assertEqual(self.sql('SELECT amount,refunded FROM tool_deduction_allocations')[0],(1000,1000))

    def test_unpaid_cancel_and_warehouse_return_do_not_create_money(self):
        self.assertEqual(self.review().status_code,200)
        self.sql("UPDATE interim_acts SET status='Подписан' WHERE id=1")
        self.assertEqual(self.assign(1000,actId=1).status_code,200)
        self.sql("UPDATE tools SET master_id=NULL,master_name='',project='',project_id=NULL,issue_type='' WHERE id=1")
        self.assertEqual(self.sql('SELECT amount FROM tool_deduction_allocations')[0][0],1000)
        self.assertEqual(self.assign(0,revision=2,actId=1).status_code,200)
        self.assertEqual(self.sql('SELECT status FROM interim_acts WHERE id=1')[0][0],'Подписан')
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],0)

    def test_salary_stale_snapshot_keeps_payment_unwritten_and_refund_preserves_salary(self):
        self.assertEqual(self.review().status_code,200)
        old=next(r for r in self.client.get('/salary-tool-deductions',params={'month':'2026-07'}).json()['rows'] if r['staffId']==100)
        self.assertEqual(self.assign(1000,month='2026-07').status_code,200)
        response=self.client.post('/salary-payments',json={'staffId':100,'month':'2026-07','amount':8700,
            'expectedToolState':old['state'],'toolDeductionAmount':0})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.sql('SELECT count(*) FROM salary_payments')[0][0],0)
        self.assertEqual(self.salary(amount=7700).status_code,200)
        self.assertEqual(self.client.delete('/salary-payments/1').status_code,409)
        self.assertEqual(self.assign(0,revision=2,month='2026-07').status_code,409)
        payload={'expectedRevision':2,'allocationId':1,'amount':500,'confirmed':True,'basis':'Фактический возврат части удержания'}
        result=self.client.post('/tool-deductions/1/refunds',json=payload)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.sql('SELECT amount,tool_deduction_snapshot->>\'amount\' FROM salary_payments')[0],(7700,'1000.0'))
        self.assertEqual(self.sql('SELECT sum(amount) FROM project_payments')[0][0],-500)

    def test_fully_withheld_salary_can_be_recorded_with_zero_cash_once(self):
        self.assertEqual(self.review().status_code,200)
        self.assertEqual(self.assign(1000,month='2026-07').status_code,200)
        response=self.salary(amount=0);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.salary(amount=0).status_code,409)

    def test_new_and_existing_financial_paths_share_the_same_act_capacity(self):
        self.assertEqual(self.review().status_code,200)
        self.assertEqual(self.assign(1000,actId=1).status_code,200)
        self.assertEqual(self.allocate_advance(amount=9500).status_code,409)
        self.assertEqual(self.client.put('/interim-acts/1/retention',json={'amount':9500,'basis':'Договор','confirmed':True,'expectedRevision':0}).status_code,409)
        self.assertEqual(self.client.put('/interim-acts/1',json={'paidAmount':10000}).status_code,409)
        self.assertEqual(self.client.delete('/interim-acts/1').status_code,409)
        self.assertEqual(self.allocate_advance(amount=9000).status_code,200)
        self.assertEqual(self.sql('SELECT status FROM interim_acts WHERE id=1')[0][0],'Оплачен')

    def test_worker_and_other_company_source_are_rejected(self):
        source=self.client.get('/tool-deductions').json()['sources'][0]
        self.assertNotIn('card:2',[r['sourceKey'] for r in self.client.get('/tool-deductions').json()['sources']])
        self.user['role']='мастер'
        self.assertEqual(self.client.get('/tool-deductions').status_code,403)
        self.assertEqual(self.client.post('/tool-deductions/review',json={'sourceKey':source['sourceKey']}).status_code,403)
        self.user['role']='бухгалтер'
        self.assertEqual(self.client.post('/tool-deductions/review',json={'sourceKey':'card:2','confirmed':True,'basis':'Подмена'}).status_code,404)

    def test_cancelling_both_kinds_of_credit_restores_signed_status(self):
        self.review();self.sql("UPDATE interim_acts SET status='Подписан' WHERE id=1")
        self.assertEqual(self.assign(1000,actId=1).status_code,200)
        self.assertEqual(self.allocate_advance(amount=1000).status_code,200)
        self.assertEqual(self.assign(0,revision=2,actId=1).status_code,200)
        self.assertEqual(self.allocate_advance(amount=0,revision=1).status_code,200)
        self.assertEqual(self.sql('SELECT status FROM interim_acts WHERE id=1')[0][0],'Подписан')

    def test_legacy_project_name_and_user_identity_must_match_exactly(self):
        self.sql("UPDATE tool_history SET project_id=NULL,project='Other object' WHERE id=10")
        self.assertEqual(self.review().status_code,409)
        self.sql("UPDATE tool_history SET project='Object',master_id=900 WHERE id=10")
        self.assertEqual(self.review().status_code,409)
        self.sql("INSERT INTO user_company_roles(id,user_id,company_id,role,active,staff_id) VALUES(9900,900,4,'мастер',TRUE,100)")
        self.assertEqual(self.review().status_code,200)

    def test_salary_payment_competes_with_allocation_without_overwriting_snapshot(self):
        self.review()
        state=next(r for r in self.client.get('/salary-tool-deductions',params={'month':'2026-07'}).json()['rows'] if r['staffId']==100)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.assign,1000,month='2026-07')
            b=pool.submit(self.client.post,'/salary-payments',json={'staffId':100,'month':'2026-07','amount':8700,'expectedToolState':state['state'],'toolDeductionAmount':0})
            results=[a.result(),b.result()]
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertEqual(self.sql('SELECT (SELECT count(*) FROM salary_payments)+(SELECT count(*) FROM tool_deduction_allocations)')[0][0],1)

    def test_two_cash_refunds_cannot_duplicate_and_sql_cannot_erase_history(self):
        import psycopg2
        self.review();self.assign(1000,actId=1)
        self.client.post('/interim-acts/1/pay',json={'amount':9000})
        payload={'expectedRevision':2,'allocationId':1,'amount':1000,'confirmed':True,'basis':'Возврат по документам'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.client.post('/tool-deductions/1/refunds',json=payload),range(2)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        for sql in ['DELETE FROM tools WHERE id=1','DELETE FROM interim_acts WHERE id=1','UPDATE interim_acts SET paid_amount=0 WHERE id=1',
                    'DELETE FROM tool_deduction_events',
                    'DELETE FROM project_payments WHERE id=2']:
            with self.subTest(sql=sql),self.assertRaises(psycopg2.Error):self.sql(sql)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments')[0],(2,-10000))

    def test_legacy_null_cash_is_unpaid_and_confirmed_snapshot_survives_catalog_change(self):
        self.review();self.sql('UPDATE interim_acts SET paid_amount=NULL WHERE id=1')
        response=self.assign(1000,actId=1);self.assertEqual(response.status_code,200,response.text)
        self.sql("UPDATE tools SET name='Different tool',cost=9000 WHERE id=1")
        case=self.client.get('/tool-deductions').json()['reviewed'][0]
        self.assertEqual((case['tool_name'],case['amount']),('Drill',1000))
