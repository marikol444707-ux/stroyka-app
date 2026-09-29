"""Internal engine tests; synthetic authorization adapter, not real route policy."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi import HTTPException

from ..supplier_access import test_postgres_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LedgerTests(unittest.TestCase):
    sql = chain.PostgresSupplyChainTests.sql

    @classmethod
    def setUpClass(cls):
        from ..supplier_access.test_postgres_chain_support import build_fixture
        cls.main, cls.fixture, cleanup = build_fixture()
        cls.addClassCleanup(cleanup)
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0045_supplier_payment_ledger.py'
        tree = ast.parse(path.read_text())
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                namespace = {'op': SimpleNamespace(execute=cur.execute)}
                exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign))],
                                        type_ignores=[]), str(path), 'exec'), namespace)
                namespace['upgrade']()
        finally:
            conn.close()

    def setUp(self):
        self.actor = self.fixture['users']['accountant']['id']
        self.invoice = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,supplier_name,project_name,amount,paid_amount,status)
            VALUES (2,%s,'Synthetic',%s,200,20,'Частично оплачен') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]

    def body(self, amount='10.00', **extra):
        return dict(requestId=str(uuid4()),kind='payment',documentKind='invoice',
                    documentId=self.invoice,amount=amount,paidAt='2026-09-18',reason='Synthetic payment', **extra)

    def policy(self, cur, actor_id, company_id, command):
        # Intentionally synthetic boundary: production authorization/schedule adapter
        # is a release gate, not replaced by this fixture in application code.
        if actor_id != self.actor or company_id != 2:
            raise HTTPException(403, 'Synthetic permission denied')
        cur.execute('SELECT * FROM supplier_invoices WHERE id=%s AND company_id=%s FOR UPDATE',
                    (command['documentId'], company_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, 'Missing document')
        return {'actorName': 'Synthetic accountant', 'documents': [dict(kind='invoice', id=row['id'],
                companyId=2,payerCompanyId=2,supplierId=row['supplier_id'],
                projectName=row['project_name'],workPackage='',amount=row['amount'],paidAmount=row['paid_amount'])]}

    def execute(self, body, policy=None, actor=None):
        from .engine import execute
        return execute(self.main.get_db, policy or self.policy, self.actor if actor is None else actor, 2, body,
                       validate_new=lambda *args: None)

    def test_payment_replay_equal_installments_and_full_reversal(self):
        body = self.body()
        first = self.execute(body)
        self.assertEqual(self.execute(body), first)
        second = self.execute(self.body())
        self.assertNotEqual(second['operationId'], first['operationId'])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(40,)])
        reverse = {key:value for key,value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal',reversesId=first['operationId'],reason='Correction')
        result = self.execute(reverse)
        self.assertEqual(self.execute(reverse), result)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(30,)])
        with self.assertRaises(HTTPException) as error:
            self.execute({**reverse,'requestId':str(uuid4())})
        self.assertEqual(error.exception.status_code, 409)

    def test_conflict_revocation_and_external_drift(self):
        body = self.body(); self.execute(body)
        with self.assertRaises(HTTPException) as conflict:
            self.execute({**body,'amount':'11'})
        self.assertEqual(conflict.exception.status_code,409)
        with self.assertRaises(HTTPException) as denied:
            self.execute(body, actor=self.fixture['users']['stranger']['id'])
        self.assertEqual(denied.exception.status_code,403)
        self.sql('UPDATE supplier_invoices SET paid_amount=31 WHERE id=%s', (self.invoice,))
        with self.assertRaises(HTTPException) as drift:
            self.execute(self.body())
        self.assertEqual(drift.exception.status_code,409)

    def test_parallel_duplicate_and_overpayment(self):
        body = self.body('100')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.execute,[body,body]))
        self.assertEqual(results[0],results[1])
        with self.assertRaises(HTTPException):
            self.execute(self.body('80.01'))
        self.execute(self.body('80'))
        self.assertEqual(self.sql('SELECT status,paid_amount FROM supplier_invoices WHERE id=%s',
                                  (self.invoice,)), [('Оплачен',200)])

    def test_late_sql_error_rolls_back_baseline_operation_and_project_payment(self):
        import psycopg2
        before = self.sql('SELECT count(*) FROM project_payments')
        self.sql('''CREATE FUNCTION synthetic_ledger_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic failure'; END $$''')
        self.sql('''CREATE TRIGGER synthetic_ledger_failure BEFORE UPDATE ON supplier_invoices
                    FOR EACH ROW EXECUTE FUNCTION synthetic_ledger_failure()''')
        try:
            with self.assertRaises(psycopg2.Error):
                self.execute(self.body())
        finally:
            self.sql('DROP TRIGGER synthetic_ledger_failure ON supplier_invoices')
            self.sql('DROP FUNCTION synthetic_ledger_failure()')
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_documents WHERE document_id=%s',
                                  (self.invoice,)),[(0,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)),[(20,)])

    def seed_warehouse(self):
        return self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,total_with_vat,paid_amount,status,supplier_invoice_id)
            VALUES (2,%s,%s,200,20,'Проведена',%s) RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],self.invoice))[0][0]

    def pair_policy(self, warehouse):
        def resolve(cur, actor_id, company_id, command):
            context = self.policy(cur, actor_id, company_id, command)
            cur.execute('SELECT * FROM warehouse_invoices WHERE id=%s FOR UPDATE',(warehouse,))
            row = cur.fetchone()
            context['documents'].append(dict(kind='warehouse',id=row['id'],companyId=row['company_id'],
                payerCompanyId=row['company_id'],supplierId=row['supplier_id'],projectName=row['project'],
                workPackage='',amount=row['total_with_vat'],paidAmount=row['paid_amount']))
            return context
        return resolve

    def test_linked_pair_is_one_expense_and_reversal_does_not_touch_stock(self):
        warehouse = self.seed_warehouse(); policy = self.pair_policy(warehouse)
        stock = self.sql('SELECT * FROM materials ORDER BY id')
        before = self.sql('SELECT count(*) FROM project_payments')[0][0]
        paid = self.execute(self.body('30'),policy=policy)
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],before+1)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(warehouse,)),[(50,)])
        reverse = {key:value for key,value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal',reversesId=paid['operationId'])
        self.execute(reverse,policy=policy)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(warehouse,)),[(20,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(20,)])
        self.assertEqual(self.sql('SELECT * FROM materials ORDER BY id'),stock)

    def test_standalone_warehouse_payment_and_reversal(self):
        warehouse = self.seed_warehouse()
        self.sql('UPDATE warehouse_invoices SET supplier_invoice_id=NULL WHERE id=%s', (warehouse,))
        def warehouse_policy(cur, actor_id, company_id, command):
            context = self.pair_policy(warehouse)(cur, actor_id, company_id,
                                                 {**command, 'documentId': self.invoice})
            context['documents'] = [d for d in context['documents'] if d['kind'] == 'warehouse']
            return context
        body = {**self.body('180'), 'documentKind': 'warehouse', 'documentId': warehouse}
        paid = self.execute(body, policy=warehouse_policy)
        self.assertEqual(self.execute(body, policy=warehouse_policy), paid)
        self.assertEqual(self.sql('SELECT paid_amount,accounting_status FROM warehouse_invoices WHERE id=%s',
                                  (warehouse,)), [(200, 'Оплачена')])
        reverse = {key: value for key, value in body.items() if key != 'amount'}
        reverse.update(requestId=str(uuid4()), kind='reversal', reversesId=paid['operationId'])
        self.execute(reverse, policy=warehouse_policy)
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (warehouse,)), [(20,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(20,)])

    def test_changed_pair_and_mismatched_baselines_are_not_guessed(self):
        operation = self.execute(self.body())
        warehouse = self.seed_warehouse()
        with self.assertRaises(HTTPException) as mismatch:
            self.execute(self.body(),policy=self.pair_policy(warehouse))
        self.assertEqual(mismatch.exception.status_code,409)
        self.sql('UPDATE warehouse_invoices SET paid_amount=30 WHERE id=%s',(warehouse,))
        with self.assertRaises(HTTPException) as addition:
            self.execute(self.body(),policy=self.pair_policy(warehouse))
        self.assertEqual(addition.exception.status_code,409)
        reverse = {key:value for key,value in self.body().items() if key != 'amount'}
        reverse.update(kind='reversal',reversesId=operation['operationId'])
        with self.assertRaises(HTTPException) as changed:
            self.execute(reverse,policy=self.pair_policy(warehouse))
        self.assertEqual(changed.exception.status_code,409)
        self.assertEqual(self.sql("SELECT count(*) FROM supplier_payment_documents WHERE document_kind='warehouse' AND document_id=%s",
                                  (warehouse,)),[(0,)])

    def test_existing_pair_cannot_be_removed_or_substituted_for_new_payment(self):
        warehouse = self.seed_warehouse()
        self.execute(self.body(),policy=self.pair_policy(warehouse))
        with self.assertRaises(HTTPException) as removed:
            self.execute(self.body())
        self.assertEqual(removed.exception.status_code,409)
        substitute = self.seed_warehouse()
        self.sql('UPDATE warehouse_invoices SET paid_amount=30 WHERE id=%s',(substitute,))
        with self.assertRaises(HTTPException) as changed:
            self.execute(self.body(),policy=self.pair_policy(substitute))
        self.assertEqual(changed.exception.status_code,409)

    def test_new_policy_runs_after_replay_but_before_any_writes(self):
        from .engine import execute
        body = self.body(); first = self.execute(body)
        def denied(*args):
            raise HTTPException(400,'Synthetic new-operation restriction')
        self.assertEqual(execute(self.main.get_db,self.policy,self.actor,2,body,validate_new=denied),first)
        with self.assertRaises(HTTPException) as error:
            execute(self.main.get_db,self.policy,self.actor,2,self.body(),validate_new=denied)
        self.assertEqual(error.exception.status_code,400)

    def test_competing_distinct_requests_cannot_exceed_remaining_amount(self):
        def attempt(body):
            try:
                self.execute(body)
                return 200
            except HTTPException as error:
                return error.status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(attempt,[self.body('100'),self.body('110')]))
        self.assertEqual(sorted(result),[200,400])
        self.assertIn(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,))[0][0],(120,130))
