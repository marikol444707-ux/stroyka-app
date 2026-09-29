"""Bound payment context from real reviewed contract/API fixtures, no runtime API."""
import hashlib
import json
import os
import unittest

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor, Json
from ..supplier_access import test_multicompany_chain as chain


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ContractContextTests(unittest.TestCase):
    api = chain.MultiCompanyChainTest.api
    sql = chain.MultiCompanyChainTest.sql
    create_offer = chain.MultiCompanyChainTest.create_offer
    check_contract = chain.MultiCompanyChainTest.check_contract

    @classmethod
    def setUpClass(cls):
        from ..supplier_access.test_postgres_chain_support import build_fixture
        from fastapi.testclient import TestClient
        cls.main, cls.fixture, cleanup = build_fixture(contract_review=True, document_bindings=True)
        cls.addClassCleanup(cleanup)
        cls.client = TestClient(cls.main.app)
        cls.addClassCleanup(cls.client.close)
        seed = cls('runTest')
        seed.sql("INSERT INTO company_requisites(company_id,full_name,inn) VALUES(2,'Synthetic buyer','7702222222')")
        cls.request_id, cls.offer_id = seed.create_offer('director', 2, cls.fixture['project'])
        path = '/supplier-offers/' + str(cls.offer_id)
        seed.api('director', 'PUT', path + '/parties', dict(buyerCompanyId=2, payerCompanyId=2,
                 expectedVersion=0, reason='Synthetic payment context'))
        seed.check_contract('director', 'stranger', 2, cls.offer_id,
                            seed.api('director', 'GET', path + '/contract-review-context'))
        cls.contract_id = seed.api('supplier', 'GET', path + '/contracts')['items'][0]['id']
        cls.invoice_id = seed.api('supplier', 'POST', path + '/create-invoice',
            dict(invoiceNumber='LEDGER-CONTEXT', amount=200, contractVersionId=cls.contract_id))['id']

    def setUp(self):
        self.invoice_id = type(self).invoice_id
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)

    def load(self, company=2):
        from .contract_context import load_invoice_contract
        return load_invoice_contract(self.cur, self.invoice_id, company)

    def reject(self, status=409, **kwargs):
        with self.assertRaises(HTTPException) as error:
            self.load(**kwargs)
        self.assertEqual(error.exception.status_code, status)

    def change_snapshot(self, change, rehash=True):
        self.cur.execute('SELECT snapshot_json FROM supplier_contract_versions WHERE id=%s', (self.contract_id,))
        snapshot = self.cur.fetchone()['snapshot_json']
        change(snapshot)
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                                          separators=(',', ':')).encode()).hexdigest()
        self.cur.execute('''INSERT INTO supplier_contract_versions
            (offer_id,company_id,party_version,version,source_file_id,snapshot_json,snapshot_hash,reason,reviewed_by_id,reviewed_by)
            SELECT offer_id,company_id,party_version,version+1,source_file_id,%s,
                   CASE WHEN %s THEN %s ELSE snapshot_hash END,'Synthetic malformed insert',reviewed_by_id,reviewed_by
            FROM supplier_contract_versions WHERE id=%s RETURNING id''',
            (Json(snapshot), rehash, digest, self.contract_id))
        contract_id = self.cur.fetchone()['id']
        self.cur.execute('''INSERT INTO supplier_invoices
            (company_id,offer_id,request_id,supplier_id,project_name,work_package,amount,contract_version_id)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,amount,%s
            FROM supplier_invoices WHERE id=%s RETURNING id''', (contract_id, type(self).invoice_id))
        self.invoice_id = self.cur.fetchone()['id']

    def test_bound_version_not_latest_and_profiles_not_used(self):
        self.cur.execute("UPDATE company_requisites SET full_name='Changed profile',inn='7700000000' WHERE company_id=2")
        self.cur.execute('''INSERT INTO supplier_contract_versions
            (offer_id,company_id,party_version,version,source_file_id,snapshot_json,snapshot_hash,reason,reviewed_by_id,reviewed_by)
            SELECT offer_id,company_id,party_version,version+1,source_file_id,snapshot_json,snapshot_hash,
                   'Newer version',reviewed_by_id,reviewed_by FROM supplier_contract_versions WHERE id=%s''', (self.contract_id,))
        context = self.load()
        self.assertEqual(context['contractVersionId'], self.contract_id)
        self.assertEqual(context['payerCompanyId'], 2)
        self.assertEqual(context['snapshot']['payer']['inn'], '7702222222')

    def test_other_company_and_unbound_invoice_fail_closed(self):
        self.reject(status=404, company=3)
        self.cur.execute('INSERT INTO supplier_invoices(company_id,amount) VALUES(2,200) RETURNING id')
        self.invoice_id = self.cur.fetchone()['id']
        self.reject()

    def test_invoice_project_and_package_must_match(self):
        for column, value in (('project_name', 'Other object'), ('work_package', 'Other package')):
            with self.subTest(column=column):
                self.cur.execute('SAVEPOINT corrupt_invoice')
                self.cur.execute(f'UPDATE supplier_invoices SET {column}=%s WHERE id=%s', (value, self.invoice_id))
                self.reject()
                self.cur.execute('ROLLBACK TO SAVEPOINT corrupt_invoice')

    def test_changed_snapshot_hash_is_rejected(self):
        self.change_snapshot(lambda snapshot: snapshot.update(paymentTerms='Changed'), rehash=False)
        self.reject()

    def test_payer_and_supplier_snapshot_ids_must_match_recorded_parties(self):
        for side, key, value in (('payer', 'companyId', 3), ('buyer', 'companyId', True),
                                  ('supplier', 'supplierId', 2147483647)):
            with self.subTest(side=side):
                self.cur.execute('SAVEPOINT corrupt_snapshot')
                self.change_snapshot(lambda snapshot: snapshot[side].update({key: value}))
                self.reject()
                self.cur.execute('ROLLBACK TO SAVEPOINT corrupt_snapshot')
                self.invoice_id = type(self).invoice_id

    def test_missing_project_owner_is_not_inferred_from_display_name(self):
        self.cur.execute('UPDATE projects SET company_id=3 WHERE id=%s', (self.fixture['projectId'],))
        self.reject()

    def test_invalid_structured_schedule_is_rejected(self):
        self.change_snapshot(lambda snapshot: snapshot.update(paymentSchedule={'stages': []}))
        self.reject()

    def test_distinct_payer_comes_from_matching_historical_parties(self):
        self.cur.execute('UPDATE supplier_deal_parties SET payer_company_id=3 WHERE offer_id=%s AND version=1',
                         (self.offer_id,))
        self.change_snapshot(lambda snapshot: snapshot['payer'].update(companyId=3))
        self.assertEqual(self.load()['payerCompanyId'], 3)

    def test_changed_party_payer_does_not_override_saved_snapshot(self):
        self.cur.execute('UPDATE supplier_deal_parties SET payer_company_id=3 WHERE offer_id=%s AND version=1',
                         (self.offer_id,))
        self.reject()

    def test_ambiguous_project_name_is_not_guessed(self):
        self.cur.execute('INSERT INTO projects(company_id,name) VALUES(2,%s)', (self.fixture['project'],))
        self.reject()

    def test_bound_context_rows_stay_locked_until_transaction_ends(self):
        from psycopg2.errors import LockNotAvailable
        self.load()
        other = self.main.get_db()
        other.autocommit = False
        try:
            with other.cursor() as cur:
                for table, row_id in (('supplier_invoices', self.invoice_id),
                                      ('supplier_contract_versions', self.contract_id),
                                      ('supplier_offers', self.offer_id), ('supply_requests', self.request_id)):
                    with self.subTest(table=table), self.assertRaises(LockNotAvailable):
                        cur.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE NOWAIT', (row_id,))
                    other.rollback()
        finally:
            other.close()

    def test_requires_transaction(self):
        self.conn.autocommit = True
        with self.assertRaises(RuntimeError):
            self.load()

    def receipt(self, status='Принято', received='2', received_at='2026-09-18'):
        self.cur.execute('''INSERT INTO supply_deliveries
            (company_id,offer_id,request_id,supplier_id,project,work_package,contract_version_id,
             source_supplier_invoice_id,status,received_quantity,shipped_quantity,price_per_unit,received_at)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,contract_version_id,
                   id,%s,%s,2,100,%s FROM supplier_invoices WHERE id=%s RETURNING id''',
            (status, received, received_at, self.invoice_id))
        return self.cur.fetchone()['id']

    def receipts(self):
        from .contract_context import load_invoice_receipts
        return load_invoice_receipts(self.cur, self.load())

    def test_exact_receipts_only_and_no_stock_mutation(self):
        from decimal import Decimal
        self.assertEqual(self.receipts()['acceptedAmount'], Decimal('0'))
        stock = self.sql('SELECT id,quantity FROM materials ORDER BY id')
        self.receipt('Проблема', '0.4')
        receipt = self.receipts()
        self.assertEqual(receipt['acceptedAmount'], Decimal('40.00'))
        self.assertEqual(receipt['receivedCount'], 1)
        self.assertTrue(receipt['hasProblem'])
        self.assertEqual(self.sql('SELECT id,quantity FROM materials ORDER BY id'), stock)

    def test_unconfirmed_receipt_cannot_release_postpayment(self):
        self.receipt('В пути', '2', None)
        self.assertEqual(self.receipts()['receivedCount'], 0)
        self.assertEqual(self.receipts()['acceptedAmount'], 0)

    def test_corrupt_receipt_project_and_missing_confirmation_fail_closed(self):
        delivery = self.receipt()
        self.cur.execute("UPDATE supply_deliveries SET project='Other project' WHERE id=%s", (delivery,))
        with self.assertRaises(HTTPException):
            self.receipts()
        self.cur.execute('UPDATE supply_deliveries SET project=%s,received_at=NULL WHERE id=%s',
                         (self.fixture['project'], delivery))
        with self.assertRaises(HTTPException):
            self.receipts()

    def test_over_received_or_nonfinite_quantity_is_rejected(self):
        delivery = self.receipt(received='3')
        with self.assertRaises(HTTPException):
            self.receipts()
        self.cur.execute("UPDATE supply_deliveries SET received_quantity='NaN' WHERE id=%s", (delivery,))
        with self.assertRaises(HTTPException):
            self.receipts()

    def test_receipt_of_another_invoice_of_same_offer_is_not_counted(self):
        original = self.invoice_id
        self.cur.execute('''INSERT INTO supplier_invoices
            (company_id,offer_id,request_id,supplier_id,project_name,work_package,amount,contract_version_id)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,amount,contract_version_id
            FROM supplier_invoices WHERE id=%s RETURNING id''', (original,))
        self.invoice_id = self.cur.fetchone()['id']
        self.receipt()
        self.invoice_id = original
        self.assertEqual(self.receipts()['acceptedAmount'], 0)

    def test_subkopeck_receipt_requires_reconciliation_not_new_rounding(self):
        delivery = self.receipt(received='0.3')
        self.cur.execute('UPDATE supply_deliveries SET price_per_unit=0.05 WHERE id=%s', (delivery,))
        # Existing warehouse writer rounds float(0.3)*float(0.05) to .01,
        # whereas Decimal half-up would invent a different .02 valuation.
        with self.assertRaises(HTTPException) as error:
            self.receipts()
        self.assertEqual(error.exception.status_code, 409)
