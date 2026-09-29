"""Real authorization, reviewed contract and SQL trigger; disposable database only."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from uuid import uuid4

from ..supplier_payments.test_contract_context_postgres import ContractContextTests
from .legacy_binding_routes import register_legacy_binding_routes


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class LegacyBindingPostgresTests(unittest.TestCase):
    api = ContractContextTests.api
    sql = ContractContextTests.sql
    create_offer = ContractContextTests.create_offer
    check_contract = ContractContextTests.check_contract

    @classmethod
    def setUpClass(cls):
        ContractContextTests.setUpClass.__func__(cls)
        seed = cls('runTest')
        # This fixture predates the payment/line ledger. The transition reads only
        # identity/existence; real binding/party/contract FK and triggers are used.
        seed.sql('CREATE TABLE supplier_payment_documents (document_kind TEXT, document_id INTEGER)')
        seed.sql('CREATE TABLE supplier_invoice_line_specs (invoice_id INTEGER)')
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/0062_supplier_legacy_contract_binding.py'
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                tree = ast.parse(path.read_text())
                namespace = {'op': SimpleNamespace(execute=cur.execute)}
                exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.Assign))],type_ignores=[]),str(path),'exec'),namespace)
                namespace['upgrade']()
        finally: conn.close()
        register_legacy_binding_routes(cls.main.app, cls.main.supplier_deal_dependencies)

    def setUp(self):
        self.invoice = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,offer_id,request_id,project_name,work_package,status,amount,paid_amount)
            SELECT company_id,supplier_id,offer_id,request_id,project_name,work_package,'На утверждении',amount,0
            FROM supplier_invoices WHERE id=%s RETURNING id''',(type(self).invoice_id,))[0][0]
        self.path = f'/supplier-invoices/{self.invoice}/legacy-contract-binding'
        self.body = dict(requestId=str(uuid4()),contractVersionId=self.contract_id,
                         expectedAmount='200.00',reason='Проверено по оригиналу',confirmed=True)

    def test_bind_replay_and_preserve_invoice_values(self):
        before = self.sql("SELECT to_jsonb(i)-'contract_version_id' FROM supplier_invoices i WHERE id=%s",(self.invoice,))
        preview = self.api('director','GET',self.path)
        self.assertEqual(preview['contract']['id'],self.contract_id)
        first = self.api('director','POST',self.path,self.body)
        self.assertFalse(first['replayed'])
        self.assertTrue(self.api('director','POST',self.path,self.body)['replayed'])
        self.assertEqual(before,self.sql("SELECT to_jsonb(i)-'contract_version_id' FROM supplier_invoices i WHERE id=%s",(self.invoice,)))
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_legacy_contract_bindings WHERE invoice_id=%s',(self.invoice,))[0][0],1)

    def test_approved_unpaid_invoice_can_bind(self):
        self.sql("UPDATE supplier_invoices SET status='Утверждён' WHERE id=%s", (self.invoice,))
        response = self.api('director', 'POST', self.path, self.body)
        self.assertEqual(response['bindingStatus'], 'bound')
        self.assertEqual(self.sql(
            'SELECT contract_version_id FROM supplier_invoices WHERE id=%s', (self.invoice,)
        ), [(self.contract_id,)])

    def test_paid_invoice_cannot_bind(self):
        self.sql('UPDATE supplier_invoices SET paid_amount=1 WHERE id=%s',(self.invoice,))
        rejection = self.api('director','POST',self.path,self.body,expected=409)
        self.assertEqual(rejection['detail']['code'], 'legacy_binding_not_saved')
        self.assertEqual(rejection['detail']['requestId'], self.body['requestId'])
        self.assertEqual(self.sql('SELECT contract_version_id FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(None,)])

    def test_registered_invoice_cannot_bind(self):
        self.sql("INSERT INTO supplier_payment_documents VALUES('invoice',%s)",(self.invoice,))
        self.api('director','POST',self.path,self.body,expected=409)

    def test_supplier_and_other_company_cannot_bind(self):
        self.api('supplier','POST',self.path,self.body,expected=403)
        self.api('stranger','POST',self.path,self.body,expected=403)

    def test_stale_amount_and_missing_confirmation_reject(self):
        self.api('director','POST',self.path,{**self.body,'expectedAmount':'201.00'},expected=409)
        self.api('director','POST',self.path,{**self.body,'confirmed':False},expected=422)

    def test_replay_payload_mismatch_rejects(self):
        self.api('director','POST',self.path,self.body)
        self.api('director','POST',self.path,{**self.body,'reason':'Другое основание'},expected=409)

    def test_direct_update_without_evidence_remains_forbidden(self):
        with self.assertRaises(Exception):
            self.sql('UPDATE supplier_invoices SET contract_version_id=%s WHERE id=%s',(self.contract_id,self.invoice))
        self.assertEqual(self.sql('SELECT contract_version_id FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(None,)])

    def test_audit_cannot_be_removed_after_binding(self):
        self.api('director','POST',self.path,self.body)
        with self.assertRaises(Exception):
            self.sql('DELETE FROM supplier_legacy_contract_bindings WHERE invoice_id=%s',(self.invoice,))
