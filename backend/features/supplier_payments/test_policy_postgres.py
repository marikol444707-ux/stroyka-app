"""Real engine + current authorization + document resolver + internal policy."""
import os
import unittest
from uuid import uuid4

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from . import test_documents_postgres as documents_tests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class PolicyPostgresTests(unittest.TestCase):
    setUpClass = classmethod(documents_tests.DocumentTests.setUpClass.__func__)
    sql = documents_tests.DocumentTests.sql
    api = documents_tests.DocumentTests.api
    create_offer = documents_tests.DocumentTests.create_offer
    check_contract = documents_tests.DocumentTests.check_contract
    change_snapshot = documents_tests.DocumentTests.change_snapshot
    authorization = documents_tests.DocumentTests.authorization

    def setUp(self):
        self.actor = self.fixture['users']['accountant']['id']
        self.invoice = self.sql('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount,status,payment_terms) VALUES(2,%s,%s,'',200,0,'Утверждён',
            'Отсрочка 30 дней после приёмки') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]

    def body(self, **extra):
        return dict(requestId=str(uuid4()), kind='payment', documentKind='invoice',
                    documentId=self.invoice, amount='10.00', paidAt='2026-09-01',
                    reason='Synthetic actual payment', **extra)

    def execute(self, body):
        from .engine import execute
        from .documents import build_document_resolver
        from .policy import validate_new_payment
        return execute(self.main.get_db, build_document_resolver(self.authorization()), self.actor, 2,
                       body, validate_new=validate_new_payment)

    def snapshot(self):
        return {table: self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text')
                for table in ('supplier_invoices', 'warehouse_invoices', 'project_payments',
                              'supplier_payment_documents', 'supplier_payment_operations', 'supplier_payment_impacts')}

    def test_actual_equal_partials_any_day_during_deferral(self):
        first = self.execute(self.body())
        second_body = self.body()
        second_body['paidAt'] = '2026-09-02'
        second = self.execute(second_body)
        self.assertNotEqual(first['operationId'], second['operationId'])
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(20, 'Частично оплачен')])

    def test_reviewed_after_acceptance_schedule_does_not_cap_actual_payment(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        try:
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            self.change_snapshot(lambda snapshot: snapshot.update(paymentSchedule=dict(schemaVersion=1,
                stages=[dict(title='After acceptance', percentBasisPoints=10000,
                             event='after_acceptance', daysAfter=30)])))
            self.cur.execute("UPDATE supplier_invoices SET status='Утверждён',paid_amount=0 WHERE id=%s", (self.invoice_id,))
            self.conn.commit()
        finally:
            self.conn.close()
        self.invoice = self.invoice_id
        body = self.body()
        body['amount'] = '150.00'
        self.execute(body)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (self.invoice,)), [(150,)])

    def test_pending_invoice_rolls_back_without_ledger_or_expense(self):
        self.sql("UPDATE supplier_invoices SET status='На утверждении' WHERE id=%s", (self.invoice,))
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.execute(self.body())
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_replay_survives_status_change_but_not_revoked_rights(self):
        body = self.body()
        result = self.execute(body)
        self.sql("UPDATE supplier_invoices SET status='На утверждении' WHERE id=%s", (self.invoice,))
        before = self.snapshot()
        self.assertEqual(self.execute(body), result)
        self.assertEqual(self.snapshot(), before)
        try:
            self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (self.actor,))
            with self.assertRaises(HTTPException) as error:
                self.execute(body)
            self.assertEqual(error.exception.status_code, 403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (self.actor,))

    def test_reversal_can_undo_record_even_after_cancellation(self):
        original = self.execute(self.body())
        self.sql("UPDATE supplier_invoices SET status='Аннулирован' WHERE id=%s", (self.invoice,))
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=original['operationId'])
        self.execute(reversal)
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(0, 'Аннулирован')])
        with self.assertRaises(HTTPException) as denied:
            self.execute(self.body())
        self.assertEqual(denied.exception.status_code, 409)
        before = self.snapshot()
        reversal['requestId'] = str(uuid4())
        with self.assertRaises(HTTPException):
            self.execute(reversal)
        self.assertEqual(self.snapshot(), before)

    def test_overpay_remains_rejected_atomically(self):
        body = self.body()
        body['amount'] = '200.01'
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.execute(body)
        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_standalone_warehouse_partial_uses_owner_and_one_expense(self):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,0,'Принято','К оплате') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]
        body = self.body()
        body.update(documentKind='warehouse', documentId=warehouse, amount='0.01')
        result = self.execute(body)
        self.assertEqual(self.execute(body), result)
        self.assertEqual(self.sql('SELECT paid_amount,accounting_status FROM warehouse_invoices WHERE id=%s',
                                 (warehouse,)), [(self.sql('SELECT 0.01::numeric')[0][0], 'Частично оплачена')])
        self.assertEqual(self.sql('''SELECT payer_company_id,project_payment_id FROM supplier_payment_operations
                                    WHERE id=%s''', (result['operationId'],)), [(2, result['projectPaymentId'])])

    def test_linked_warehouse_hold_blocks_new_payment_not_reversal(self):
        warehouse = self.sql('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,paid_amount,status,accounting_status,supplier_invoice_id)
            VALUES(2,%s,%s,'[{"workPackage":""}]',200,0,'Принято','К оплате',%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, self.invoice))
        original = self.execute(self.body())
        self.sql("UPDATE warehouse_invoices SET accounting_status='Нужно уточнение' WHERE id=%s", (warehouse,))
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.execute(self.body())
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=original['operationId'])
        self.execute(reversal)
        self.assertEqual(self.sql('SELECT paid_amount,accounting_status FROM warehouse_invoices WHERE id=%s',
                                 (warehouse,)), [(0, 'Нужно уточнение')])
        self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [('Частично оплачен',)])
        with self.assertRaises(HTTPException) as denied:
            self.execute(self.body())
        self.assertEqual(denied.exception.status_code, 409)

    def test_pending_invoice_status_survives_reversal(self):
        original = self.execute(self.body())
        self.sql("UPDATE supplier_invoices SET status='На утверждении' WHERE id=%s", (self.invoice,))
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=original['operationId'])
        self.execute(reversal)
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(0, 'На утверждении')])
        with self.assertRaises(HTTPException) as denied:
            self.execute(self.body())
        self.assertEqual(denied.exception.status_code, 409)

    def test_eligible_group_reversal_recalculates_financial_status(self):
        body = self.body()
        body['amount'] = '200.00'
        original = self.execute(body)
        self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s', (self.invoice,)), [('Оплачен',)])
        reversal = self.body()
        reversal.pop('amount')
        reversal.update(kind='reversal', reversesId=original['operationId'])
        self.execute(reversal)
        self.assertEqual(self.sql('SELECT paid_amount,status FROM supplier_invoices WHERE id=%s',
                                 (self.invoice,)), [(0, 'Утверждён')])
        self.execute(self.body())
