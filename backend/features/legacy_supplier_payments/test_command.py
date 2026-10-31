import ast
import unittest
from pathlib import Path
from unittest.mock import Mock
from fastapi import HTTPException
from .command import normalize, fingerprint, execute, replay, complete

BODY=dict(requestId='11111111-1111-4111-8111-111111111111',companyId=2,amount='10.00',expectedPaidAmount='0.00',paidAt='2026-10-31')

class CommandTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize(BODY,4)['amount'],'10.00')
    def test_invalid_money(self):
        for value in ('NaN','Infinity','-1','0','1.001'):
            with self.subTest(value=value), self.assertRaises(HTTPException): normalize({**BODY,'amount':value},4)
    def test_extra_fields_rejected(self):
        with self.assertRaises(HTTPException): normalize({**BODY,'paidBy':'forged'},4)
    def test_fingerprint_binds_document_company_actor_and_payload(self):
        c=normalize(BODY,4); original=fingerprint(c,7)
        for field,value in [('invoiceId',5),('companyId',3),('amount','11.00'),('paidAt','2026-10-30')]:
            self.assertNotEqual(original,fingerprint({**c,field:value},7))
        self.assertNotEqual(original,fingerprint(c,8))
    def test_exact_replay(self):
        c=normalize(BODY,4);cur=Mock();cur.fetchone.return_value=(fingerprint(c,7),{'ok':True})
        self.assertEqual(replay(cur,c,7),{'ok':True})
    def test_conflicting_replay(self):
        cur=Mock();cur.fetchone.return_value=('different',{})
        with self.assertRaises(HTTPException): replay(cur,normalize(BODY,4),7)
    def test_single_commit(self):
        conn=Mock();worker=Mock(return_value={'ok':True});result=execute(lambda:conn,worker,4,BODY,{'id':7},'2','company')
        self.assertTrue(result['ok']);conn.commit.assert_called_once();conn.rollback.assert_not_called()
        self.assertEqual(worker.call_args.kwargs['payment_command'],normalize(BODY,4))
    def test_worker_failure_rolls_back(self):
        conn=Mock();worker=Mock(side_effect=RuntimeError('expense failed'))
        with self.assertRaises(RuntimeError): execute(lambda:conn,worker,4,BODY,{'id':7},'2','company')
        conn.rollback.assert_called_once();conn.commit.assert_not_called();conn.close.assert_called_once()
    def test_commit_failure_does_not_report_success(self):
        conn=Mock();conn.commit.side_effect=RuntimeError('connection lost')
        with self.assertRaises(RuntimeError): execute(lambda:conn,Mock(),4,BODY,{'id':7},'2','company')
        conn.rollback.assert_called_once()
    def test_wrong_company_never_opens_connection(self):
        db=Mock()
        with self.assertRaises(HTTPException): execute(db,Mock(),4,BODY,{'id':7},'3','company')
        db.assert_not_called()
    def test_journal_failure_propagates(self):
        cur=Mock();cur.execute.side_effect=RuntimeError('journal failed')
        with self.assertRaises(RuntimeError): complete(cur,normalize(BODY,4),7,{'projectPaymentId':8})
    def test_shared_worker_has_no_transaction_ownership(self):
        tree=ast.parse(Path('backend/main.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_update_supplier_invoice_in_transaction')
        calls=[n.func.attr for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertFalse(set(calls)&{'commit','rollback','close'})
        text=ast.unparse(fn)
        for contract in ('invoice_advance_amount','accepted_amount','problem_rows','require_row_project_access','_require_unmanaged_payment_document','FOR UPDATE OF si'):
            self.assertIn(contract,text)

class SharedWorkerTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        tree=ast.parse(Path('backend/main.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_update_supplier_invoice_in_transaction')
        self.actor={'id':7,'name':'Test'}
        self.ns={'HTTPException':HTTPException,'_payment_ledger_available':Mock(return_value=False),
          '_positive_int_or_none':lambda x:int(x) if x else None,
          'resolve_resource_company_actor':Mock(return_value=({},self.actor)),
          'require_row_project_access':Mock(),'_resolve_project_payment_actor':Mock(),
          'FINANCE_ROLES':('бухгалтер',),'PLATFORM_STAFF_ROLES':(),'CLIENT_ACCOUNT_ROLES':(),
          '_float_or_zero':lambda x:float(x or 0)}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'shared-worker','exec'),self.ns)
        self.worker=self.ns[fn.name]
        self.guard=(100,0,'',None,0,'','',None,'Project','Supplier',2,3,'Утверждён')
        self.cur=Mock();self.cur.fetchone.side_effect=[self.guard,None,(8,)]
        self.schedule=patch('backend.features.supplier_deal_parties.payment_schedule.invoice_advance_amount',return_value=None)
        self.schedule.start();self.addCleanup(self.schedule.stop)
    def run_worker(self):
        return self.worker(self.cur,4,{},'2','company',self.actor,payment_command=normalize(BODY,4))
    def test_real_shared_worker_writes_all_records_on_same_cursor(self):
        result=self.run_worker();self.assertEqual(result['projectPaymentId'],8)
        sql=[c.args[0] for c in self.cur.execute.call_args_list]
        self.assertEqual(sum('INSERT INTO project_payments' in s for s in sql),1)
        self.assertEqual(sum('INSERT INTO legacy_supplier_payment_requests' in s for s in sql),1)
        self.assertEqual(sum('UPDATE supplier_invoices SET' in s for s in sql),1)
    def test_replay_does_not_write(self):
        c=normalize(BODY,4);self.cur.fetchone.side_effect=[self.guard,(fingerprint(c,7),{'ok':True,'projectPaymentId':8})]
        self.run_worker()
        self.assertFalse(any(c.args[0].lstrip().startswith(('UPDATE ', 'INSERT ')) for c in self.cur.execute.call_args_list))
    def test_changed_baseline_rejects_before_writes(self):
        guard=list(self.guard);guard[1]=20;self.cur.fetchone.side_effect=[guard,None]
        with self.assertRaises(HTTPException):self.run_worker()
        self.assertFalse(any(c.args[0].lstrip().startswith('UPDATE ') for c in self.cur.execute.call_args_list))
    def test_current_access_rechecked_before_replay(self):
        self.ns['require_row_project_access'].side_effect=HTTPException(403,'denied')
        with self.assertRaises(HTTPException):self.run_worker()
        self.assertFalse(any('legacy_supplier_payment_requests' in c.args[0] for c in self.cur.execute.call_args_list))
    def test_postpayment_before_receipt_still_rejected(self):
        guard=list(self.guard);guard[3]=5;self.cur.fetchone.side_effect=[guard,None,(0,0,0)]
        with self.assertRaises(HTTPException) as exc:self.run_worker()
        self.assertEqual(exc.exception.status_code,400)
        self.assertIn('до приёмки',exc.exception.detail)
    def test_schedule_advance_limit_preserved(self):
        from unittest.mock import patch
        guard=list(self.guard);guard[3]=5;self.cur.fetchone.side_effect=[guard,None,(0,0,0)]
        with patch('backend.features.supplier_deal_parties.payment_schedule.invoice_advance_amount',return_value=5):
            with self.assertRaises(HTTPException) as exc:self.run_worker()
        self.assertIn('по графику',exc.exception.detail)
    def test_accepted_value_cap_preserved(self):
        guard=list(self.guard);guard[3]=5;self.cur.fetchone.side_effect=[guard,None,(2,1,0)]
        with self.assertRaises(HTTPException) as exc:self.run_worker()
        self.assertIn('фактически принятой',exc.exception.detail)
    def test_expense_failure_rolls_back_shared_worker(self):
        conn=Mock();conn.cursor.return_value=self.cur
        def sql(command,*args):
            if command.lstrip().startswith('INSERT INTO project_payments'):raise RuntimeError('expense failed')
        self.cur.execute.side_effect=sql
        with self.assertRaises(RuntimeError):execute(lambda:conn,self.worker,4,BODY,self.actor,'2','company')
        conn.commit.assert_not_called();conn.rollback.assert_called_once()
    def test_journal_failure_rolls_back_shared_worker(self):
        conn=Mock();conn.cursor.return_value=self.cur
        def sql(command,*args):
            if command.lstrip().startswith('INSERT INTO legacy_supplier_payment_requests'):raise RuntimeError('journal failed')
        self.cur.execute.side_effect=sql
        with self.assertRaises(RuntimeError):execute(lambda:conn,self.worker,4,BODY,self.actor,'2','company')
        conn.commit.assert_not_called();conn.rollback.assert_called_once()
    def test_linked_warehouse_updated_with_invoice_and_expense(self):
        guard=list(self.guard);guard[7]=9
        warehouse=(9,'Project','',4,'Принято',2,3,'Supplier',100,100)
        self.ns['_row_get']=lambda row,key,index,default=None:row[index] if row[index] is not None else default
        self.cur.fetchone.side_effect=[guard,None,warehouse,(8,)]
        self.run_worker()
        sql=[c.args[0] for c in self.cur.execute.call_args_list]
        self.assertEqual(sum(s.startswith('UPDATE warehouse_invoices SET') for s in sql),1)
    def test_new_payment_cannot_exceed_exact_remaining_balance(self):
        guard=list(self.guard);guard[0]=9.99;self.cur.fetchone.side_effect=[guard,None]
        with self.assertRaises(HTTPException) as exc:self.run_worker()
        self.assertIn('превышает остаток',exc.exception.detail)

    def test_unapproved_invoice_rejected(self):
        guard=list(self.guard);guard[12]='На утверждении';self.cur.fetchone.side_effect=[guard,None]
        with self.assertRaises(HTTPException) as exc:self.run_worker()
        self.assertIn('не утверждён',exc.exception.detail)
