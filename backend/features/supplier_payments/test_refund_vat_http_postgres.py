"""Current real invoice/receipt chain and financial authority, disposable DB."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException
from . import test_receipt_vat_postgres as base
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class RefundVatHTTPTests(unittest.TestCase):
    sql=base.ReceiptVatTests.sql
    api=base.ReceiptVatTests.api
    create_offer=base.ReceiptVatTests.create_offer
    check_contract=base.ReceiptVatTests.check_contract
    raw_sources=base.ReceiptVatTests.raw_sources
    create=base.ReceiptVatTests.create
    ship=base.ReceiptVatTests.ship
    receive=base.ReceiptVatTests.receive
    pay=base.ReceiptVatTests.pay

    @classmethod
    def setUpClass(cls):
        base.ReceiptVatTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                for name in ('0057_supplier_opening_confirmations.py','0058_supplier_paired_openings.py',
                             '0059_supplier_refund_allocations.py'):
                    migration(cur,name)
        finally: conn.close()

    def setUp(self):
        base.ReceiptVatTests.setUp(self)
        flags=patch.dict(os.environ,SUPPLIER_SETTLEMENTS_ENABLED='1',SUPPLIER_ALLOCATED_REFUNDS_ENABLED='1',
                         SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED='1')
        flags.start(); self.addCleanup(flags.stop)
        for _ in range(2): self.receive(self.ship())
        self.payment=self.pay('120')['operationId']
        self.group=self.sql('''SELECT g.id FROM supplier_payment_allocation_groups g
            JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
            WHERE d.company_id=2 AND d.document_kind='invoice' AND d.document_id=%s''',(self.invoice,))[0][0]
        self.receipts=[row[0] for row in self.sql('SELECT id FROM supplier_payment_receipt_relations WHERE group_id=%s ORDER BY id',(self.group,))]
        self.actor=self.fixture['users']['accountant']['id']
        from .allocation_access import build_allocation_access
        from .access import build_payment_access
        from .documents import build_document_resolver
        self.deps=dict(resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES,platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access,has_package_access=self.main.has_package_access)
        self.authorize=build_allocation_access(self.deps)
        self.payment_authorize=build_document_resolver(build_payment_access(self.deps))

    def read(self):
        from .allocation_store import read_allocations_in_transaction
        conn=self.main.get_db()
        try:
            conn.autocommit=False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                return read_allocations_in_transaction(cur,self.authorize,self.actor,2,self.group)
        finally: conn.rollback(); conn.close()

    def test_current_vat_receipts_authorize_and_refund_without_changing_tax_or_stock(self):
        from .allocation_store import replace_allocations
        from .refund_store import refund
        from .policy import validate_new_payment
        before=self.sql('SELECT to_jsonb(p) FROM supplier_receipt_line_proofs p ORDER BY receipt_relation_id')
        stock=self.sql('SELECT count(*),sum(quantity) FROM materials WHERE company_id=2')
        self.assertEqual(self.read()['paid'],'120.00')
        replace_allocations(self.main.get_db,self.authorize,self.actor,2,dict(requestId=str(uuid4()),
            groupId=self.group,expectedVersion=0,reason='Allocate gross amount',rows=[
                dict(paymentId=self.payment,receiptId=self.receipts[0],amount='80'),
                dict(paymentId=self.payment,receiptId=self.receipts[1],amount='20')]))
        body=dict(requestId=str(uuid4()),groupId=self.group,expectedVersion=1,paymentId=self.payment,
            amount='25',unallocatedAmount='5',paidAt='2026-09-28',reason='Actual cash refund',
            releases=[dict(receiptId=self.receipts[0],amount='20')])
        result=refund(self.main.get_db,self.authorize,self.payment_authorize,self.actor,2,body,validate_new=validate_new_payment)
        self.assertEqual(refund(self.main.get_db,self.authorize,self.payment_authorize,self.actor,2,body,validate_new=validate_new_payment),result)
        view=self.read()
        self.assertEqual((view['paid'],view['allocated'],view['unallocatedPayments']),('95.00','80.00','15.00'))
        self.assertEqual(self.sql('SELECT to_jsonb(p) FROM supplier_receipt_line_proofs p ORDER BY receipt_relation_id'),before)
        self.assertEqual(self.sql('SELECT count(*),sum(quantity) FROM materials WHERE company_id=2'),stock)

    def test_full_http_chain_projects_net_supplier_expense_without_second_receipt_debt(self):
        """Real shipment/receipt fixture -> explicit allocation -> refund -> accounting."""
        from decimal import Decimal
        stock = self.sql('SELECT to_jsonb(m) FROM materials m WHERE company_id=2 ORDER BY id')
        proofs = self.sql('SELECT to_jsonb(p) FROM supplier_receipt_line_proofs p ORDER BY receipt_relation_id')
        body = dict(requestId=str(uuid4()), groupId=self.group, expectedVersion=0,
            reason='Assign the actual payment to two partial receipts', rows=[
                dict(paymentId=self.payment, receiptId=self.receipts[0], amount='80.00'),
                dict(paymentId=self.payment, receiptId=self.receipts[1], amount='20.00')])
        path = '/companies/2/supplier-payments/allocations'
        saved = self.api('accountant', 'POST', path, body)
        self.assertEqual(self.api('accountant', 'POST', path, body), saved)
        context = self.api('accountant', 'GET',
            f'/companies/2/supplier-payments/refund-context/{self.invoice}')
        self.assertEqual(context['version'], 1)
        self.assertEqual(context['allocations'], body['rows'])
        refund = self.refund_http(self.refund_body(expectedVersion=1, amount='25.00',
            unallocatedAmount='5.00', releases=[dict(receiptId=self.receipts[0], amount='20.00')]))
        document = self.api('accountant', 'GET',
            f'/companies/2/supplier-payment-documents/invoice/{self.invoice}')
        self.assertEqual((document['amount'], document['paidAmount'], document['remainingAmount']),
            ('200.00', '95.00', '105.00'))
        view = self.api('accountant', 'GET', f'/companies/2/supplier-payments/allocation-groups/{self.group}')
        self.assertEqual((view['paid'], view['allocated'], view['unallocatedPayments']),
            ('95.00', '80.00', '15.00'))
        operation_ids = [self.payment, refund['operationId']]
        cash_ids = {row[0] for row in self.sql(
            'SELECT project_payment_id FROM supplier_payment_operations WHERE id=ANY(%s)', (operation_ids,))}
        report = [row for row in self.api('accountant', 'GET', '/project-payments') if row['id'] in cash_ids]
        self.assertEqual(len(report), 2)
        self.assertEqual({row['operationKind'] for row in report}, {'payment', 'refund'})
        self.assertTrue(all(row['sourceKind'] == 'supplier_payment_ledger' for row in report))
        self.assertEqual(sum(Decimal(str(row['amount'])) for row in report), Decimal('95.00'))
        self.assertEqual(self.sql('SELECT to_jsonb(m) FROM materials m WHERE company_id=2 ORDER BY id'), stock)
        self.assertEqual(self.sql('SELECT to_jsonb(p) FROM supplier_receipt_line_proofs p ORDER BY receipt_relation_id'), proofs)

    def refund_body(self, **changes):
        return dict(dict(requestId=str(uuid4()),groupId=self.group,expectedVersion=0,paymentId=self.payment,
            amount='10',unallocatedAmount='10',paidAt='2026-09-28',reason='HTTP cash refund',releases=[]),**changes)

    def refund_http(self, body, actor='accountant', expected=200):
        token=self.main.create_auth_token(self.fixture['users'][actor],two_factor_passed=True)
        response=self.client.post('/companies/2/supplier-payments/allocated-refunds',json=body,
            headers={'Authorization':'Bearer '+token,'X-Company-Id':'2','X-Company-Mode':'company'})
        self.assertEqual(response.status_code,expected,response.text)
        self.assertEqual(response.headers.get('cache-control'),'no-store')
        return response.json()

    def test_actual_http_refund_replay_stale_version_and_reversal(self):
        body=self.refund_body()
        result=self.refund_http(body)
        self.assertEqual(self.refund_http(body),result)
        self.assertEqual((result['companyId'],result['requestId'],result['kind']), (2,body['requestId'],'refund'))
        self.refund_http(self.refund_body(),expected=409)
        self.refund_http(dict(body,reason='Changed reason'),expected=409)
        view=self.api('accountant','GET',f'/companies/2/supplier-payments/allocation-groups/{self.group}')
        self.assertEqual((view['paid'],view['unallocatedPayments']),('110.00','110.00'))
        self.api('accountant','POST','/companies/2/supplier-payments',dict(requestId=str(uuid4()),
            kind='reversal',documentKind='invoice',documentId=self.invoice,reversesId=result['operationId'],
            paidAt='2026-09-28',reason='Undo refund'))
        self.assertEqual(self.read()['paid'],'120.00')
        self.assertEqual(self.refund_http(body),result)

    def test_http_authority_and_strict_input(self):
        body=self.refund_body()
        self.refund_http(body,actor='supplier',expected=403)
        self.refund_http(body,actor='stranger',expected=403)
        self.refund_http(dict(body,actorId=self.actor),expected=422)
        self.refund_http(dict(body,paymentId=9223372036854775807),expected=409)
        result=self.refund_http(body)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(self.actor,))
        try: self.refund_http(body,expected=403)
        finally: self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(self.actor,))
        with patch.dict(os.environ,SUPPLIER_ALLOCATED_REFUNDS_ENABLED='0'):
            self.assertEqual(self.refund_http(body),result)
            self.refund_http(self.refund_body(expectedVersion=1),expected=409)

    def test_missing_proof_and_disabled_guard_fail_closed(self):
        conn=self.main.get_db()
        try:
            conn.autocommit=False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('ALTER TABLE supplier_receipt_line_proofs DISABLE TRIGGER receipt_line_immutable')
                cur.execute('DELETE FROM supplier_receipt_line_proofs WHERE receipt_relation_id=%s',(self.receipts[0],))
                cur.execute('ALTER TABLE supplier_receipt_line_proofs ENABLE TRIGGER receipt_line_immutable')
                with self.assertRaises(HTTPException) as error: self.authorize(cur,self.actor,2,dict(groupId=self.group))
                self.assertEqual(error.exception.status_code,409)
            conn.rollback()
        finally: conn.close()
        self.sql('ALTER TABLE supplier_receipt_line_proofs DISABLE TRIGGER receipt_line_validate')
        try: self.refund_http(self.refund_body(),expected=503)
        finally: self.sql('ALTER TABLE supplier_receipt_line_proofs ENABLE TRIGGER receipt_line_validate')
        self.assertEqual(self.read()['paid'],'120.00')

    def test_mixed_tax_lines_use_their_saved_tax(self):
        base.ReceiptVatTests.test_mixed_tax_lines_keep_their_own_amounts(self)
        self.group=self.sql('''SELECT g.id FROM supplier_payment_allocation_groups g
            JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
            WHERE d.company_id=2 AND d.document_kind='invoice' AND d.document_id=%s''',(self.invoice,))[0][0]
        self.payment=self.pay('200')['operationId']
        self.assertEqual(self.read()['paid'],'200.00')
        self.refund_http(self.refund_body())
        self.assertEqual(self.read()['paid'],'190.00')

    def test_proof_corruption_does_not_become_refundable(self):
        conn=self.main.get_db()
        try:
            conn.autocommit=False
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('ALTER TABLE supplier_receipt_line_proofs DISABLE TRIGGER receipt_line_immutable')
                cur.execute('UPDATE supplier_receipt_line_proofs SET vat_amount=vat_amount-1 WHERE receipt_relation_id=%s',(self.receipts[0],))
                cur.execute('ALTER TABLE supplier_receipt_line_proofs ENABLE TRIGGER receipt_line_immutable')
                with self.assertRaises(HTTPException) as error: self.authorize(cur,self.actor,2,dict(groupId=self.group))
                self.assertEqual(error.exception.status_code,409)
            conn.rollback()
        finally: conn.close()

    def test_http_header_company_and_feature_flags(self):
        body=self.refund_body()
        token=self.main.create_auth_token(self.fixture['users']['accountant'],two_factor_passed=True)
        path='/companies/2/supplier-payments/allocated-refunds'
        response=self.client.post(path,json=body,headers={'Authorization':'Bearer '+token,
            'X-Company-Id':'3','X-Company-Mode':'company'})
        self.assertIn(response.status_code,(403,409))
        with patch.dict(os.environ,SUPPLIER_PAYMENT_ALLOCATIONS_ENABLED='0'):
            self.refund_http(body,expected=404)
        self.assertEqual(self.read()['paid'],'120.00')

    def test_http_allocated_refund_lost_response_replays_one_operation(self):
        from . import refund_store
        self.api('accountant','POST','/companies/2/supplier-payments/allocations',dict(requestId=str(uuid4()),
            groupId=self.group,expectedVersion=0,reason='HTTP allocation',rows=[
                dict(paymentId=self.payment,receiptId=self.receipts[0],amount='80'),
                dict(paymentId=self.payment,receiptId=self.receipts[1],amount='20')]))
        body=self.refund_body(expectedVersion=1,amount='25',unallocatedAmount='5',
                              releases=[dict(receiptId=self.receipts[0],amount='20')])
        original=refund_store.refund
        def lost(*args,**kw):
            original(*args,**kw)
            raise ConnectionError('Synthetic response lost after commit')
        with patch.object(refund_store,'refund',side_effect=lost):
            result=self.refund_http(body,expected=503)
            self.assertEqual(result['detail']['code'],'refund_unconfirmed')
        result=self.refund_http(body)
        self.assertEqual(result['version'],2)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_operations WHERE company_id=2 AND request_id=%s',
                                 (body['requestId'],)),[(1,)])
        self.assertEqual((self.read()['paid'],self.read()['allocated']),('95.00','80.00'))

    def test_database_rejection_is_409_and_rolls_back_http_refund(self):
        body=self.refund_body()
        self.sql("CREATE FUNCTION reject_refund_http() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic rejection' USING ERRCODE='23514'; END $$")
        self.sql('''CREATE CONSTRAINT TRIGGER reject_refund_http AFTER INSERT ON supplier_payment_refund_links
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_refund_http()''')
        try:
            result=self.refund_http(body,expected=409)
            self.assertEqual(result['detail']['code'],'refund_conflict')
            self.assertEqual(self.read()['paid'],'120.00')
            self.assertEqual(self.read()['version'],0)
        finally:
            self.sql('DROP TRIGGER reject_refund_http ON supplier_payment_refund_links')
            self.sql('DROP FUNCTION reject_refund_http()')
        self.refund_http(body)

    def test_refund_form_context_has_source_capacities_and_physical_receipt_numbers(self):
        path=f'/companies/2/supplier-payments/refund-context/{self.invoice}'
        context=self.api('accountant','GET',path)
        self.assertEqual((context['companyId'],context['invoiceId'],context['groupId']),(2,self.invoice,self.group))
        payment=context['payments'][0]
        self.assertEqual((payment['paymentId'],payment['amount'],payment['unallocatedAmount']),
                         (self.payment,'120.00','120.00'))
        self.assertTrue(all(row['warehouseId']>0 for row in context['receipts']))
        self.refund_http(self.refund_body())
        payment=self.api('accountant','GET',path)['payments'][0]
        self.assertEqual((payment['refundedAmount'],payment['remainingAmount']),('10.00','110.00'))
        self.api('supplier','GET',path,expected=403)

    def test_pending_allocated_refund_can_be_cancelled_or_confirmed_without_duplicate(self):
        body=self.refund_body()
        cash=dict(requestId=body['requestId'],kind='refund',documentKind='invoice',documentId=self.invoice,
                  amount=body['amount'],paidAt=body['paidAt'],reason=body['reason'])
        result=self.api('accountant','POST','/companies/2/supplier-payments/cancel-request',cash)
        self.assertEqual(result['status'],'cancelled')
        self.refund_http(body,expected=409)
        self.assertEqual(self.read()['version'],0)
        body=self.refund_body(); saved=self.refund_http(body)
        cash['requestId']=body['requestId']
        result=self.api('accountant','POST','/companies/2/supplier-payments/cancel-request',cash)
        self.assertEqual(result['status'],'confirmed')
        self.assertEqual(result['result']['operationId'],saved['operationId'])
