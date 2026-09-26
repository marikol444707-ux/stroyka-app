"""Internal document resolver: isolated PostgreSQL, no payment writes/routes."""
import json
import os
import unittest
from unittest.mock import Mock
from uuid import uuid4

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from . import test_contract_context_postgres as contract_tests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class DocumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        contract_tests.ContractContextTests.setUpClass.__func__(cls)
        from ..supplier_deal_parties.test_payment_ledger_migration import migration_statements
        conn = cls.main.get_db()
        conn.autocommit = False
        try:
            with conn, conn.cursor() as cur:
                for statement in migration_statements()[1]:
                    cur.execute(statement)
        finally:
            conn.close()
    sql = contract_tests.ContractContextTests.sql
    api = contract_tests.ContractContextTests.api
    create_offer = contract_tests.ContractContextTests.create_offer
    check_contract = contract_tests.ContractContextTests.check_contract
    change_snapshot = contract_tests.ContractContextTests.change_snapshot

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        self.cur.execute('SELECT pg_advisory_xact_lock(1735289201,2)')
        self.cur.execute('''INSERT INTO supplier_invoices
            (company_id,supplier_id,project_name,work_package,amount,paid_amount,status)
            VALUES(2,%s,%s,'',200,0,'Аннулирован') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))
        self.invoice = self.cur.fetchone()['id']
        self.cur.execute('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,paid_amount,status)
            VALUES(2,%s,%s,%s,200,200,0,'Аннулирована') RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'], json.dumps([{'workPackage': ''}])))
        self.warehouse = self.cur.fetchone()['id']

    def authorization(self):
        from .access import build_payment_access
        return build_payment_access(dict(
            resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access,
            has_package_access=self.main.has_package_access))

    def resolve(self, kind='invoice', document_id=None, actor='accountant'):
        from .documents import build_document_resolver
        return build_document_resolver(self.authorization())(self.cur, self.fixture['users'][actor]['id'], 2,
            dict(documentKind=kind, documentId=document_id or
                 (self.invoice if kind == 'invoice' else self.warehouse)))

    def reject(self, status=409, **kwargs):
        with self.assertRaises(HTTPException) as error:
            self.resolve(**kwargs)
        self.assertEqual(error.exception.status_code, status)

    def link(self):
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',
                         (self.warehouse, self.invoice))
        self.cur.execute('UPDATE warehouse_invoices SET supplier_invoice_id=%s WHERE id=%s',
                         (self.invoice, self.warehouse))

    def test_standalone_invoice_does_not_infer_link_or_check_eligibility_status(self):
        result = self.resolve()
        self.assertEqual([(d['kind'], d['id']) for d in result['documents']], [('invoice', self.invoice)])
        self.assertEqual(result['documents'][0]['payerCompanyId'], 2)

    def test_standalone_warehouse_owner_payer(self):
        doc = self.resolve('warehouse')['documents'][0]
        self.assertEqual((doc['payerCompanyId'], doc['workPackage']), (2, ''))

    def test_reciprocal_pair_resolves_identically_from_both_sides(self):
        self.link()
        self.assertEqual(self.resolve()['documents'], self.resolve('warehouse')['documents'])
        self.assertEqual(len(self.resolve()['documents']), 2)

    def test_one_sided_links_are_rejected_from_either_side(self):
        self.cur.execute('UPDATE warehouse_invoices SET supplier_invoice_id=%s WHERE id=%s',
                         (self.invoice, self.warehouse))
        self.reject()
        self.reject(kind='warehouse')

    def test_missing_forward_link_rejected(self):
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=2147483647 WHERE id=%s', (self.invoice,))
        self.reject()

    def test_duplicate_reverse_invoice_is_not_hidden(self):
        self.link()
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,warehouse_invoice_id)
                            VALUES(2,%s)''', (self.warehouse,))
        self.reject()
        self.reject(kind='warehouse')

    def test_foreign_reverse_document_is_not_filtered_out(self):
        self.cur.execute('UPDATE warehouse_invoices SET company_id=3,supplier_invoice_id=%s WHERE id=%s',
                         (self.invoice, self.warehouse))
        self.reject()

    def test_foreign_root_is_not_accessible(self):
        self.cur.execute('UPDATE supplier_invoices SET company_id=3 WHERE id=%s', (self.invoice,))
        self.reject(status=404)

    def test_unbound_offer_invoice_never_infers_payer(self):
        self.cur.execute('UPDATE supplier_invoices SET offer_id=%s WHERE id=%s', (self.offer_id, self.invoice))
        self.reject()

    def test_bound_invoice_uses_exact_contract(self):
        result = self.resolve(document_id=type(self).invoice_id)
        self.assertEqual(result['contract']['contractVersionId'], self.contract_id)
        self.assertEqual(result['documents'][0]['payerCompanyId'], 2)

    def test_distinct_bound_payer_requires_its_own_current_membership(self):
        self.cur.execute('UPDATE supplier_deal_parties SET payer_company_id=3 WHERE offer_id=%s AND version=1',
                         (self.offer_id,))
        self.change_snapshot(lambda snapshot: snapshot['payer'].update(companyId=3))
        self.reject(status=403, document_id=self.invoice_id)
        self.cur.execute('''INSERT INTO user_company_roles(user_id,company_id,role,active,
                            assigned_projects,assigned_packages) VALUES(%s,3,'бухгалтер',TRUE,'[]','[]')''',
                         (self.fixture['users']['accountant']['id'],))
        self.assertEqual(self.resolve(document_id=self.invoice_id)['documents'][0]['payerCompanyId'], 3)
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=3',
                         (self.fixture['users']['accountant']['id'],))
        self.reject(status=403, document_id=self.invoice_id)

    def test_authorizer_cannot_be_omitted(self):
        from .documents import build_document_resolver
        with self.assertRaises(TypeError):
            build_document_resolver(None)

    def test_both_physical_rows_remain_locked(self):
        from psycopg2.errors import LockNotAvailable
        # Rows must already be visible to the competing transaction; uncommitted
        # inserts would make its SELECT return nothing, not exercise row locks.
        self.invoice = self.sql('''INSERT INTO supplier_invoices
            (company_id,supplier_id,project_name,work_package,amount,paid_amount)
            VALUES(2,%s,%s,'',200,0) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))[0][0]
        self.warehouse = self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,paid_amount,supplier_invoice_id)
            VALUES(2,%s,%s,%s,200,0,%s) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project'],
             json.dumps([{'workPackage': ''}]), self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',
                 (self.warehouse, self.invoice))
        self.resolve('warehouse')
        other = self.main.get_db()
        try:
            with other.cursor() as cur:
                for table, row_id in (('supplier_invoices', self.invoice), ('warehouse_invoices', self.warehouse)):
                    with self.subTest(table=table), self.assertRaises(LockNotAvailable):
                        cur.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE NOWAIT', (row_id,))
                    other.rollback()
        finally:
            other.close()

    def test_current_authorization_required_even_cancelled_or_paid(self):
        self.reject(status=403, actor='stranger')
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s',
                         (self.fixture['users']['accountant']['id'],))
        self.reject(status=403)

    def denied_actors_before_document_errors(self, **kwargs):
        for actor_state in ('stranger', 'revoked', 'disabled'):
            with self.subTest(actor_state=actor_state):
                self.cur.execute('SAVEPOINT denied_actor')
                try:
                    if actor_state == 'revoked':
                        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',
                                         (self.fixture['users']['accountant']['id'],))
                    if actor_state == 'disabled':
                        self.cur.execute('UPDATE users SET active=FALSE WHERE id=%s',
                                         (self.fixture['users']['accountant']['id'],))
                    self.reject(status=403, actor='stranger' if actor_state == 'stranger' else 'accountant', **kwargs)
                finally:
                    self.cur.execute('ROLLBACK TO SAVEPOINT denied_actor')

    def test_owner_authorization_precedes_corrupt_link_errors(self):
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=2147483647 WHERE id=%s',
                         (self.invoice,))
        self.denied_actors_before_document_errors()
        self.reject()  # Authorized actor still receives the integrity conflict.

    def test_owner_authorization_precedes_corrupt_contract_errors(self):
        self.change_snapshot(lambda snapshot: snapshot.update(paymentTerms='Tampered'), rehash=False)
        self.denied_actors_before_document_errors(document_id=self.invoice_id)
        self.reject(document_id=self.invoice_id)

    def test_owner_authorization_precedes_corrupt_warehouse_package_errors(self):
        self.cur.execute("UPDATE warehouse_invoices SET items='not-json' WHERE id=%s", (self.warehouse,))
        self.denied_actors_before_document_errors(kind='warehouse')
        self.reject(kind='warehouse')

    def test_replay_callback_rechecks_revoked_owner_before_corrupt_link(self):
        from .documents import build_document_resolver
        from .engine import execute
        actor_id = self.fixture['users']['accountant']['id']
        self.conn.commit()  # Publish the synthetic invoice to the engine connection.
        callback = Mock(wraps=build_document_resolver(self.authorization()))
        policy = Mock()  # Eligibility is a separate, deliberately synthetic boundary.
        body = dict(requestId=str(uuid4()), kind='payment', documentKind='invoice',
                    documentId=self.invoice, amount='1.00', paidAt='2026-09-18', reason='Auth replay regression')
        first = execute(self.main.get_db, callback, actor_id, 2, body, validate_new=policy)
        self.assertEqual(execute(self.main.get_db, callback, actor_id, 2, body, validate_new=policy), first)
        self.assertEqual(callback.call_count, 2)
        self.assertEqual(policy.call_count, 1)
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=2147483647 WHERE id=%s', (self.invoice,))
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (actor_id,))
        before = self.sql('SELECT to_jsonb(t) FROM supplier_payment_operations t ORDER BY id')
        try:
            with self.assertRaises(HTTPException) as error:
                execute(self.main.get_db, callback, actor_id, 2, body, validate_new=policy)
            self.assertEqual(error.exception.status_code, 403)
            self.assertEqual(callback.call_count, 3)
            self.assertEqual(policy.call_count, 1)
            self.assertEqual(self.sql('SELECT to_jsonb(t) FROM supplier_payment_operations t ORDER BY id'), before)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (actor_id,))

    def test_packages_must_be_explicit_unmixed_and_supported_by_baseline(self):
        for items in ([], [{}], [None], [{'workPackage': None}],
                      [{'workPackage': ''}, {'workPackage': 'Other'}],
                      [{'workPackage': 'Основная'}],
                      [{'workPackage': '', 'work_package': 'Other'}]):
            with self.subTest(items=items):
                self.cur.execute('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                                 (json.dumps(items), self.warehouse))
                self.reject(kind='warehouse')

    def test_invoice_package_not_erased_to_fit_warehouse(self):
        self.link()
        self.cur.execute("UPDATE supplier_invoices SET work_package='Основная' WHERE id=%s", (self.invoice,))
        self.reject()

    def test_mismatched_pair_amount_or_paid_rejected(self):
        self.link()
        for column in ('total_with_vat', 'paid_amount'):
            with self.subTest(column=column):
                self.cur.execute('SAVEPOINT mismatch')
                self.cur.execute(f'UPDATE warehouse_invoices SET {column}=100 WHERE id=%s', (self.warehouse,))
                self.reject()
                self.cur.execute('ROLLBACK TO SAVEPOINT mismatch')

    def test_requires_transaction_and_read_committed(self):
        self.conn.rollback()
        self.cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        self.reject()

    def test_resolver_does_not_modify_documents(self):
        self.link()
        def rows():
            self.cur.execute('SELECT to_jsonb(i) AS row FROM supplier_invoices i ORDER BY id')
            invoices = self.cur.fetchall()
            self.cur.execute('SELECT to_jsonb(w) AS row FROM warehouse_invoices w ORDER BY id')
            return invoices, self.cur.fetchall()
        before = rows()
        self.resolve()
        self.assertEqual(rows(), before)
