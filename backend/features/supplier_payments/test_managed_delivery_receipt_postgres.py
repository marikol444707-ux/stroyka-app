"""Internal single-line receipt adapter, real warehouse membership and PostgreSQL."""
import ast
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from psycopg2.extras import Json, RealDictCursor

from . import test_contract_context_postgres as contract_tests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ManagedDeliveryReceiptTests(unittest.TestCase):
    sql = contract_tests.ContractContextTests.sql
    api = contract_tests.ContractContextTests.api
    create_offer = contract_tests.ContractContextTests.create_offer
    check_contract = contract_tests.ContractContextTests.check_contract

    @classmethod
    def setUpClass(cls):
        contract_tests.ContractContextTests.setUpClass.__func__(cls)
        seed = cls('runTest')
        seed.sql("INSERT INTO companies(id,name,plan,active,payment_status) VALUES(4,'Synthetic payer','pro',TRUE,'active')")
        seed.sql("INSERT INTO company_requisites(company_id,full_name,inn) VALUES(4,'Synthetic payer','7704444444')")
        for actor in ('director', 'accountant'):
            seed.sql('''INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default)
                VALUES(%s,4,1,'бухгалтер',TRUE,FALSE)''', (cls.fixture['users'][actor]['id'],))
        seed.sql("""UPDATE estimates SET sections_json=jsonb_set(sections_json::jsonb,
            '{0,items,0,quantity}', '4'::jsonb)::text WHERE id=%s""", (cls.fixture['estimateId'],))
        request, offer = seed.create_offer('director', 2, cls.fixture['project'])
        path = '/supplier-offers/' + str(offer)
        seed.api('director', 'PUT', path + '/parties', dict(buyerCompanyId=2, payerCompanyId=4,
                 expectedVersion=0, reason='Distinct payer receipt regression'))
        seed.check_contract('director', 'stranger', 2, offer,
                            seed.api('director', 'GET', path + '/contract-review-context'))
        contract = seed.api('supplier', 'GET', path + '/contracts')['items'][0]['id']
        invoice = seed.api('supplier', 'POST', path + '/create-invoice',
            dict(invoiceNumber='DISTINCT-PAYER', amount=200, contractVersionId=contract))['id']
        cls.distinct_payer_source = (request, offer, contract, invoice)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                for name in ('0045_supplier_payment_ledger', '0046_supplier_payment_attachments',
                             '0047_supplier_payment_packages'):
                    path = Path(__file__).resolve().parents[3] / 'migrations/versions' / (name + '.py')
                    tree = ast.parse(path.read_text())
                    namespace = {'op': SimpleNamespace(execute=cur.execute), '__file__': str(path)}
                    exec(compile(ast.Module(body=[node for node in tree.body
                        if isinstance(node, (ast.FunctionDef, ast.Assign))], type_ignores=[]), str(path), 'exec'), namespace)
                    namespace['upgrade']()
        finally:
            conn.close()
        from .access import build_payment_access
        from .documents import build_document_resolver
        from .engine import execute
        from .policy import validate_new_payment
        seed.sql("UPDATE supplier_invoices SET status='Утверждён' WHERE id=%s", (cls.invoice_id,))
        seed.sql("UPDATE supplier_invoices SET status='Утверждён' WHERE id=%s", (invoice,))
        access = build_payment_access(dict(resolve_resource_company_actor=cls.main.resolve_resource_company_actor,
            finance_roles=cls.main.FINANCE_ROLES, platform_staff_roles=cls.main.PLATFORM_STAFF_ROLES,
            client_account_roles=cls.main.CLIENT_ACCOUNT_ROLES, require_project_access=cls.main.require_project_access,
            has_package_access=cls.main.has_package_access))
        execute(cls.main.get_db, build_document_resolver(access), cls.fixture['users']['accountant']['id'], 2,
                dict(requestId=str(uuid4()), kind='payment', documentKind='invoice', documentId=cls.invoice_id,
                     amount='40', paidAt='2026-09-18', reason='Synthetic actual payment'),
                validate_new=validate_new_payment)
        execute(cls.main.get_db, build_document_resolver(access), cls.fixture['users']['accountant']['id'], 2,
                dict(requestId=str(uuid4()), kind='payment', documentKind='invoice', documentId=invoice,
                     amount='40', paidAt='2026-09-17', reason='Distinct payer actual payment'),
                validate_new=validate_new_payment)

    def setUp(self):
        from .managed_delivery_receipt import ManagedDeliveryReceipt
        self.adapter = ManagedDeliveryReceipt(dict(
            resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            warehouse_roles=self.main.WAREHOUSE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_or_warehouse_access=self.main.require_project_or_warehouse_access,
            has_package_access=self.main.has_package_access))
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        self.actor = self.fixture['users']['foreman']['id']
        self.seed_delivery()

    def seed_delivery(self):
        self.cur.execute("UPDATE users SET role='кладовщик' WHERE id=%s", (self.actor,))
        self.cur.execute("UPDATE user_company_roles SET role='кладовщик' WHERE user_id=%s AND company_id=2", (self.actor,))
        self.cur.execute('''INSERT INTO supply_deliveries(company_id,offer_id,request_id,supplier_id,
            project,work_package,material_name,unit,planned_quantity,shipped_quantity,price_per_unit,total_price,
            contract_version_id,source_supplier_invoice_id,status)
            VALUES(2,%s,%s,%s,%s,'Основная',%s,'шт',2,2,100,200,%s,%s,'В пути') RETURNING id''',
            (self.offer_id,self.request_id,self.fixture['supplierId'],self.fixture['project'],
             self.fixture['materialName'],self.contract_id,self.invoice_id))
        self.delivery = self.cur.fetchone()['id']
        self.params = dict(delivery_id=self.delivery, invoice_id=self.invoice_id,
                           contract_version_id=self.contract_id, received_quantity='2')

    def prepare(self, actor=None, **changes):
        return self.adapter.prepare(self.cur, self.actor if actor is None else actor, 2, **{**self.params, **changes})

    def history(self):
        result = {}
        for table in ('supplier_invoices','warehouse_invoices','supply_deliveries','materials',
                      'supplier_payment_documents','supplier_payment_attachments','supplier_payment_operations',
                      'supplier_payment_impacts','project_payments'):
            self.cur.execute(f'SELECT to_jsonb(t) AS row FROM {table} t ORDER BY to_jsonb(t)::text')
            result[table] = self.cur.fetchall()
        return result

    def create_warehouse(self, quantity=2, price=100):
        # Emulate only the caller's physical receipt; adapter does not create it.
        item = dict(name=self.fixture['materialName'], unit='шт', workPackage='Основная',
                    quantity=quantity, price=price, total=200, source='supply_delivery',
                    deliveryId=self.delivery, requestId=self.request_id)
        self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,location,
            items,total_base,total_with_vat,total_vat,paid_amount,status,source_type,source_id,
            supply_delivery_id,supply_request_id,supplier_invoice_id)
            VALUES(2,%s,%s,%s,%s,200,200,0,0,'Принята','supply_delivery',%s,%s,%s,%s) RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],self.fixture['project'],json.dumps([item]),
             str(self.delivery),self.delivery,self.request_id,self.invoice_id))
        warehouse = self.cur.fetchone()['id']
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse,self.invoice_id))
        self.cur.execute("""UPDATE supply_deliveries SET status='Принято',quality_status='Принято',
            received_quantity=2,received_at=NOW() WHERE id=%s""", (self.delivery,))
        return warehouse

    def attach(self, warehouse):
        return self.adapter.attach(self.cur, self.actor, 2, warehouse_id=warehouse, **self.params)

    def test_warehouse_actor_without_financial_role_can_prepare_without_writes(self):
        self.assertNotIn('кладовщик', self.main.FINANCE_ROLES)
        before = self.history()
        result = self.prepare()
        self.assertEqual(result['deliveryId'], self.delivery)
        self.assertFalse(result['alreadyReceived'])
        self.assertEqual(self.history(), before)
        self.assertFalse({'mirroredPaid','paidAmount','amount','payerCompanyId','contract'} & result.keys())

    def test_distinct_payer_requires_no_payer_membership_for_warehouse_receipt(self):
        self.conn.rollback()
        self.request_id, self.offer_id, self.contract_id, self.invoice_id = self.distinct_payer_source
        self.seed_delivery()
        self.cur.execute('SELECT company_id,role FROM user_company_roles WHERE user_id=%s', (self.actor,))
        self.assertEqual(self.cur.fetchall(), [dict(company_id=2, role='кладовщик')])
        before = self.history()
        prepared = self.prepare()
        warehouse = self.create_warehouse()
        result = self.attach(warehouse)
        self.assertEqual(result['requestId'], prepared['requestId'])
        self.assertEqual(set(result), {'deliveryId', 'invoiceId', 'requestId', 'alreadyReceived'})
        self.cur.execute('''SELECT company_id,payer_company_id FROM supplier_payment_documents
            WHERE (document_kind='invoice' AND document_id=%s)
               OR (document_kind='warehouse' AND document_id=%s) ORDER BY id''', (self.invoice_id, warehouse))
        self.assertEqual(self.cur.fetchall(), [dict(company_id=2, payer_company_id=4)] * 2)
        self.cur.execute('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (warehouse,))
        self.assertEqual(self.cur.fetchone()['paid_amount'], 40)
        saved = self.history()
        for table in ('supplier_payment_operations', 'supplier_payment_impacts', 'project_payments'):
            self.assertEqual(saved[table], before[table])
        self.assertTrue(self.prepare()['alreadyReceived'])
        self.assertEqual(self.history(), saved)

    def test_attach_and_other_actor_replay_never_create_expense_or_rewrite(self):
        before = self.history()
        self.prepare()
        warehouse = self.create_warehouse()
        first = self.attach(warehouse)
        self.assertEqual(first['invoiceId'], warehouse)
        self.cur.execute('SELECT paid_amount FROM warehouse_invoices WHERE id=%s', (warehouse,))
        self.assertEqual(self.cur.fetchone()['paid_amount'], 40)
        saved = self.history()
        for table in ('supplier_payment_operations','supplier_payment_impacts','project_payments','materials'):
            self.assertEqual(saved[table], before[table])
        class SelectOnlyCursor(RealDictCursor):
            def execute(cursor, query, vars=None):
                if str(query).lstrip().split()[0].upper() not in ('SELECT','SHOW','SAVEPOINT','RELEASE'):
                    raise AssertionError('Replay must not write: ' + str(query))
                return super().execute(query, vars)
        with self.conn.cursor(cursor_factory=SelectOnlyCursor) as cur:
            replay = self.adapter.prepare(cur, self.fixture['users']['director']['id'], 2, **self.params)
        self.assertTrue(replay['alreadyReceived'])
        self.assertEqual(replay['requestId'], first['requestId'])
        self.assertEqual(replay['invoiceId'], warehouse)
        self.assertEqual(self.history(), saved)
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (self.actor,))
        with self.assertRaises(HTTPException) as error:
            self.prepare()
        self.assertEqual(error.exception.status_code, 403)

    def test_current_warehouse_scope_not_legacy_user_role_controls_access(self):
        for sql, value in (("UPDATE user_company_roles SET role=%s WHERE user_id=%s", 'бухгалтер'),
                           ("UPDATE user_company_roles SET assigned_projects=%s WHERE user_id=%s", Json(['Other']))):
            with self.subTest(sql=sql):
                self.cur.execute('SAVEPOINT permission')
                if 'assigned_projects' in sql:
                    self.cur.execute("UPDATE user_company_roles SET role='прораб' WHERE user_id=%s", (self.actor,))
                self.cur.execute(sql, (value,self.actor))
                with self.assertRaises(HTTPException) as error:
                    self.prepare()
                self.assertEqual(error.exception.status_code, 403)
                self.cur.execute('ROLLBACK TO SAVEPOINT permission')

    def test_exact_source_ids_and_full_quantity_required_before_writes(self):
        before = self.history()
        for change in ({'invoice_id': self.invoice_id+100000}, {'contract_version_id': self.contract_id+100000},
                       {'received_quantity': '1'}, {'received_quantity': 'NaN'}, {'quality_status': 'Частично'}):
            with self.subTest(change=change), self.assertRaises(HTTPException):
                self.prepare(**change)
        self.assertEqual(self.history(), before)

    def test_same_value_different_line_and_multiline_are_not_full_coverage(self):
        for update in ("price_per_unit=200,planned_quantity=1,shipped_quantity=1", "unit='м'",
                       "material_name='Other material'", "work_package='Other package'"):
            self.cur.execute('SAVEPOINT bad_line')
            self.cur.execute('UPDATE supply_deliveries SET '+update+' WHERE id=%s', (self.delivery,))
            with self.assertRaises(HTTPException):
                self.prepare()
            self.cur.execute('ROLLBACK TO SAVEPOINT bad_line')
        self.cur.execute('UPDATE supply_requests SET items_json=%s WHERE id=%s',
            (json.dumps([dict(materialName=self.fixture['materialName'],unit='шт',quantity=1,workPackage='Основная')]*2),self.request_id))
        with self.assertRaises(HTTPException):
            self.prepare()

    def test_second_delivery_or_invoice_is_unsupported_not_latest_selected(self):
        self.cur.execute('SAVEPOINT duplicate')
        self.cur.execute('''INSERT INTO supply_deliveries(company_id,offer_id,request_id,supplier_id,
            contract_version_id,source_supplier_invoice_id) VALUES(2,%s,%s,%s,%s,%s)''',
            (self.offer_id,self.request_id,self.fixture['supplierId'],self.contract_id,self.invoice_id))
        with self.assertRaises(HTTPException):
            self.prepare()
        self.cur.execute('ROLLBACK TO SAVEPOINT duplicate')
        self.cur.execute('''INSERT INTO supplier_invoices(company_id,offer_id,request_id,supplier_id,
            contract_version_id,amount) VALUES(2,%s,%s,%s,%s,200)''',
            (self.offer_id,self.request_id,self.fixture['supplierId'],self.contract_id))
        with self.assertRaises(HTTPException):
            self.prepare()

    def test_wrong_warehouse_line_rejected_without_attachment(self):
        self.prepare()
        warehouse = self.create_warehouse(quantity=1, price=200)
        before = self.history()
        with self.assertRaises(HTTPException):
            self.attach(warehouse)
        self.assertEqual(self.history(), before)

    def test_new_contract_version_does_not_replace_persisted_source(self):
        self.cur.execute('''INSERT INTO supplier_contract_versions(offer_id,company_id,party_version,
            version,source_file_id,snapshot_json,snapshot_hash,reason,reviewed_by_id,reviewed_by)
            SELECT offer_id,company_id,party_version,version+1,source_file_id,snapshot_json,snapshot_hash,
                'Synthetic newer version',reviewed_by_id,reviewed_by
            FROM supplier_contract_versions WHERE id=%s RETURNING id''', (self.contract_id,))
        newer = self.cur.fetchone()['id']
        self.assertFalse(self.prepare()['alreadyReceived'])
        with self.assertRaises(HTTPException):
            self.prepare(contract_version_id=newer)

    def test_current_auth_and_source_rows_remain_locked(self):
        from psycopg2.errors import LockNotAvailable
        director = self.fixture['users']['director']['id']
        self.prepare(actor=director)
        self.cur.execute('SELECT id FROM user_company_roles WHERE user_id=%s AND company_id=2', (director,))
        membership = self.cur.fetchone()['id']
        other = self.main.get_db()
        other.autocommit = False
        try:
            with other.cursor() as cur:
                for table, row_id in (('users',director), ('companies',2), ('user_company_roles',membership),
                                      ('supplier_invoices',self.invoice_id), ('supplier_offers',self.offer_id),
                                      ('supply_requests',self.request_id), ('supplier_contract_versions',self.contract_id)):
                    with self.subTest(table=table), self.assertRaises(LockNotAvailable):
                        cur.execute(f'SELECT id FROM {table} WHERE id=%s FOR UPDATE NOWAIT', (row_id,))
                    other.rollback()
        finally:
            other.close()

    def test_existing_company_wide_warehouse_scope_is_not_silently_narrowed(self):
        self.cur.execute('''UPDATE user_company_roles SET assigned_projects=%s,assigned_packages=%s
            WHERE user_id=%s AND company_id=2''', (Json(['Other']),Json(['Other']),self.actor))
        self.assertFalse(self.prepare()['alreadyReceived'])

    def test_caller_rollback_reverts_warehouse_and_attachment(self):
        self.prepare()
        warehouse = self.create_warehouse()
        self.attach(warehouse)
        self.conn.rollback()
        self.assertEqual(self.sql('SELECT id FROM warehouse_invoices WHERE id=%s', (warehouse,)), [])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_payment_attachments'), [(0,)])
