"""Real allocation authority on isolated PG; no routes or production grants."""
import importlib
import os
import unittest
from unittest.mock import Mock

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor

from . import test_allocation_store_postgres as store_tests


class AllocationAccessContractTests(unittest.TestCase):
    def test_factory_rejects_unknown_operation(self):
        module = importlib.import_module('backend.features.supplier_payments.allocation_access')
        with self.assertRaises(ValueError):
            module.build_allocation_access({}, operation='delete')

    def test_package_accepts_0019_nonpackage_duplicates_and_nonascii_whitespace(self):
        from .allocation_access import _package
        for raw, expected in (
            ('[{"workPackage":"A","name":"one","name":"two"}]', 'A'),
            ('[{"workPackage":"A","metadata":{"workPackage":"a","workPackage":"b"}}]', 'A'),
            ('[{"workPackage":"\u00a0A\u00a0"}]', '\u00a0A\u00a0'),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(_package(raw), expected)


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AllocationAccessPostgresTests(unittest.TestCase):
    sql = store_tests.AllocationStorePostgresTests.sql
    api = store_tests.AllocationStorePostgresTests.api
    create_offer = store_tests.AllocationStorePostgresTests.create_offer
    check_contract = store_tests.AllocationStorePostgresTests.check_contract
    pay = store_tests.AllocationStorePostgresTests.pay
    seed_receipt = store_tests.AllocationStorePostgresTests.seed_receipt
    body = store_tests.AllocationStorePostgresTests.body
    snapshot = store_tests.AllocationStorePostgresTests.snapshot

    @classmethod
    def setUpClass(cls):
        store_tests.AllocationStorePostgresTests.setUpClass.__func__(cls)
        seed = cls('runTest')
        seed.sql("INSERT INTO companies(id,name,plan,active,payment_status) VALUES(4,'Synthetic allocation payer','pro',TRUE,'active')")
        seed.sql("INSERT INTO company_requisites(company_id,full_name,inn) VALUES(4,'Synthetic allocation payer','7704444444')")
        for actor in ('director', 'accountant'):
            seed.sql('''INSERT INTO user_company_roles(user_id,company_id,platform_account_id,role,active,is_default)
                VALUES(%s,4,1,'бухгалтер',TRUE,FALSE)''', (cls.fixture['users'][actor]['id'],))
        seed.sql("""UPDATE estimates SET sections_json=jsonb_set(sections_json::jsonb,
            '{0,items,0,quantity}','4'::jsonb)::text WHERE id=%s""", (cls.fixture['estimateId'],))
        _, offer = seed.create_offer('director', 2, cls.fixture['project'])
        path = f'/supplier-offers/{offer}'
        seed.api('director', 'PUT', path + '/parties', dict(buyerCompanyId=2, payerCompanyId=4,
            expectedVersion=0, reason='Synthetic distinct payer allocation authority'))
        seed.check_contract('director', 'stranger', 2, offer,
                            seed.api('director', 'GET', path + '/contract-review-context'))
        contract = seed.api('supplier', 'GET', path + '/contracts')['items'][0]['id']
        cls.distinct_payer_invoice = seed.api('supplier', 'POST', path + '/create-invoice',
            dict(invoiceNumber='ALLOCATION-PAYER-4', amount=200, contractVersionId=contract))['id']

    def setUp(self):
        store_tests.AllocationStorePostgresTests.setUp(self)
        self.deps = dict(resolve_resource_company_actor=self.main.resolve_resource_company_actor,
            finance_roles=self.main.FINANCE_ROLES, platform_staff_roles=self.main.PLATFORM_STAFF_ROLES,
            client_account_roles=self.main.CLIENT_ACCOUNT_ROLES,
            require_project_access=self.main.require_project_access, has_package_access=self.main.has_package_access)
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)

    def adapter(self, operation='update', deps=None):
        from .allocation_access import build_allocation_access
        return build_allocation_access(self.deps if deps is None else deps, operation=operation)

    def authorize(self, *, operation='update', company=2, actor=None, command=None, deps=None):
        return self.adapter(operation, deps)(self.cur, self.actor if actor is None else actor,
                                            company, dict(groupId=self.group) if command is None else command)

    def rejected(self, status, **kwargs):
        with self.assertRaises(HTTPException) as error:
            self.authorize(**kwargs)
        self.assertEqual(error.exception.status_code, status)

    def corrupt_warehouse(self, warehouse, expression, params=()):
        # Deliberately simulate preexisting physical corruption in this test's
        # rollback-only transaction; never weaken production or admission code.
        self.cur.execute('ALTER TABLE warehouse_invoices DISABLE TRIGGER a_allocation_physical')
        self.cur.execute('UPDATE warehouse_invoices SET ' + expression + ' WHERE id=%s', (*params, warehouse))
        self.cur.execute('ALTER TABLE warehouse_invoices ENABLE TRIGGER a_allocation_physical')

    def test_read_and_write_authorize_real_membership_without_mutations_or_transaction_end(self):
        before = self.snapshot()
        self.cur.execute('SELECT pg_current_xact_id() AS xid')
        xid = self.cur.fetchone()['xid']
        self.authorize()
        self.authorize(operation='read')
        self.cur.execute('SELECT pg_current_xact_id() AS xid')
        self.assertEqual(self.cur.fetchone()['xid'], xid)
        self.assertEqual(self.snapshot(), before)

    def test_selected_membership_not_global_role_and_foreign_group(self):
        self.cur.execute("UPDATE user_company_roles SET role='снабженец' WHERE user_id=%s AND company_id=2", (self.actor,))
        self.rejected(403)
        self.conn.rollback()
        self.cur.execute("UPDATE users SET role='прораб' WHERE id=%s", (self.actor,))
        self.authorize()
        self.conn.rollback()
        # No selected-company membership: deny before discovering groups.
        self.rejected(403, company=3)
        self.rejected(404, command=dict(groupId=self.group + 100000))

    def test_revoked_membership_and_inactive_user_cannot_use_global_fallback(self):
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        self.rejected(403)
        self.conn.rollback()
        self.cur.execute('UPDATE users SET active=FALSE WHERE id=%s', (self.actor,))
        self.rejected(403, operation='read')

    def test_all_omitted_receipts_check_current_project_before_malformed_items(self):
        self.corrupt_warehouse(self.receipts[0]['warehouse'], "items='not json'")
        self.corrupt_warehouse(self.receipts[1]['warehouse'], 'project=%s', (self.main.SYSTEM_PROJECT_NAME,))
        # Accountant has real company-wide project access EXCEPT system tasks.
        self.rejected(403, command=dict(groupId=self.group, rows=[]))

    def test_current_membership_denial_precedes_malformed_receipt_and_empty_map(self):
        self.corrupt_warehouse(self.receipts[1]['warehouse'], "items='not json'")
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        self.rejected(403, command=dict(groupId=self.group, rows=[]))

    def test_authorized_malformed_receipt_is_domain_conflict_without_aborted_transaction(self):
        self.corrupt_warehouse(self.receipts[1]['warehouse'], "items='not json'")
        self.rejected(409)
        self.cur.execute('SELECT 1 AS usable')
        self.assertEqual(self.cur.fetchone()['usable'], 1)

    def test_every_receipt_package_uses_existing_policy_and_drift_is_not_repaired(self):
        package_check = Mock(wraps=self.main.has_package_access)
        deps = {**self.deps, 'has_package_access': package_check}
        self.corrupt_warehouse(self.receipts[1]['warehouse'],
            "items=jsonb_set(items::jsonb,'{0,workPackage}','\"Other package\"'::jsonb)::text")
        self.rejected(409, deps=deps, command=dict(groupId=self.group, rows=[]))
        self.assertIn('Other package', [call.args[1] for call in package_check.call_args_list])

    def test_amount_identity_legacy_link_and_frozen_metadata_drift_fail_closed(self):
        for expression, params in [('total_base=total_base+1', ()), ('company_id=3', ()),
                                   ('supplier_invoice_id=%s', (self.invoice,)),
                                   ("source_type='manual'", ())]:
            with self.subTest(expression=expression):
                self.corrupt_warehouse(self.receipts[1]['warehouse'], expression, params)
                self.rejected(409)
                self.conn.rollback()

    def test_readonly_context_contract_denies_write_but_explicit_read_allowed(self):
        # Existing membership resolver does not derive readOnly from billing;
        # billing is HTTP middleware. Preserve the documented callback contract
        # by adding only the readOnly bit to an otherwise REAL resolved context.
        modes = []
        def readonly_context(cur, user, company, operation, **kwargs):
            modes.append(operation)
            context, actor = self.main.resolve_resource_company_actor(cur, user, company, operation, **kwargs)
            return {**context, 'readOnly': True}, actor
        deps = {**self.deps, 'resolve_resource_company_actor': readonly_context}
        self.rejected(403, deps=deps)
        self.authorize(operation='read', deps=deps)
        self.assertEqual(modes[0], 'update')
        self.assertTrue(all(mode == 'read' for mode in modes[1:]))

    def test_expired_billing_does_not_block_explicit_financial_read(self):
        self.cur.execute("UPDATE companies SET plan='standard',trial_until=NULL,plan_expires_at='2000-01-01',payment_status='expired' WHERE id=2")
        self.authorize(operation='read')

    def test_distinct_contract_payer_revocation_precedes_malformed_receipt_and_replay(self):
        from .allocation_store import replace_allocations, replace_allocations_in_transaction
        self.invoice = self.sql('''INSERT INTO supplier_invoices
            (company_id,offer_id,request_id,supplier_id,project_name,work_package,amount,paid_amount,status,contract_version_id)
            SELECT company_id,offer_id,request_id,supplier_id,project_name,work_package,200,0,'Утверждён',contract_version_id
            FROM supplier_invoices WHERE id=%s RETURNING id''', (self.distinct_payer_invoice,))[0][0]
        self.payment = self.pay('60.00')['operationId']
        self.group = self.sql('''INSERT INTO supplier_payment_allocation_groups(company_id,invoice_record_id)
            SELECT company_id,id FROM supplier_payment_documents
            WHERE document_kind='invoice' AND document_id=%s AND company_id=2 RETURNING id''', (self.invoice,))[0][0]
        self.receipts = [self.seed_receipt('60.00'), self.seed_receipt('80.00')]
        body = self.body()
        result = replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body)
        context = self.authorize()
        self.assertEqual(context['documents'][0]['payerCompanyId'], 4)
        self.assertEqual(context['contract']['payerCompanyId'], 4)
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=4', (self.actor,))
        self.corrupt_warehouse(self.receipts[1]['warehouse'], "items='not json'")
        self.rejected(403, operation='read')
        with self.assertRaises(HTTPException) as error:
            replace_allocations_in_transaction(self.cur, self.adapter(), self.actor, 2, body)
        self.assertEqual(error.exception.status_code, 403)
        self.conn.rollback()
        self.assertEqual(replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body), result)

    def test_live_delivery_metadata_and_invoice_balance_drift_fail_closed(self):
        self.cur.execute('ALTER TABLE supply_deliveries DISABLE TRIGGER a_allocation_physical')
        self.cur.execute("UPDATE supply_deliveries SET received_by='Changed historical receipt' WHERE id=%s",
                         (self.receipts[1]['delivery'],))
        self.cur.execute('ALTER TABLE supply_deliveries ENABLE TRIGGER a_allocation_physical')
        self.rejected(409)
        self.conn.rollback()
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=paid_amount+1 WHERE id=%s', (self.invoice,))
        self.rejected(409)

    def test_separate_source_delivery_identity_must_match_actual_frozen_receipt(self):
        self.cur.execute('INSERT INTO supply_deliveries(company_id) VALUES(2) RETURNING id')
        unrelated = self.cur.fetchone()['id']
        self.cur.execute('ALTER TABLE supplier_payment_receipt_relations DISABLE TRIGGER allocation_immutable')
        self.cur.execute('UPDATE supplier_payment_receipt_relations SET source_delivery_id=%s WHERE id=%s',
                         (unrelated, self.receipts[1]['id']))
        self.cur.execute('ALTER TABLE supplier_payment_receipt_relations ENABLE TRIGGER allocation_immutable')
        self.rejected(409)

    def test_invoice_lock_precedes_receipt_locks_without_transaction_control_or_writes(self):
        statements = []
        class AuditedCursor:
            def __init__(self, cursor):
                self.cursor = cursor
            def __getattr__(self, name):
                return getattr(self.cursor, name)
            def execute(self, sql, params=()):
                statements.append(' '.join(sql.split()))
                return self.cursor.execute(sql, params)
        self.adapter()(AuditedCursor(self.cur), self.actor, 2, dict(groupId=self.group))
        invoice_lock = next(i for i, sql in enumerate(statements)
                            if 'FROM supplier_invoices' in sql and 'FOR UPDATE' in sql)
        warehouse_lock = next(i for i, sql in enumerate(statements)
                              if 'FROM warehouse_invoices' in sql and 'FOR UPDATE' in sql)
        self.assertLess(invoice_lock, warehouse_lock)
        self.assertTrue(all(sql.startswith(('SELECT ', 'SHOW ')) for sql in statements), statements)

    def test_receipt_scope_checks_reuse_pinned_authority_without_per_receipt_membership_queries(self):
        resolve = Mock(wraps=self.main.resolve_resource_company_actor)
        self.authorize(deps={**self.deps, 'resolve_resource_company_actor': resolve})
        # Initial owner/payer, then the canonical document resolver's checks.
        # More receipts must not repeat locked membership resolution per scope.
        self.assertLessEqual(resolve.call_count, 3)

    def test_annulled_invoice_keeps_saved_uuid_replay_and_historical_read(self):
        from .allocation_store import replace_allocations, read_allocations_in_transaction
        body = self.body()
        saved = replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body)
        self.sql("UPDATE supplier_invoices SET status='Аннулирован' WHERE id=%s", (self.invoice,))
        self.assertEqual(replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body), saved)
        projection = read_allocations_in_transaction(self.cur, self.adapter('read'), self.actor, 2, self.group)
        self.assertEqual((projection['version'], projection['allocations']), (1, body['rows']))

    def test_revoked_selected_company_denied_before_missing_allocation_schema(self):
        self.cur.execute('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        self.cur.execute('ALTER TABLE supplier_payment_allocation_groups RENAME TO synthetic_unavailable_allocation_groups')
        self.rejected(403)

    def test_package_parser_matches_installed_0019_contract(self):
        from .allocation_access import _package
        accepted = ('[{"workPackage":"A","name":"one","name":"two"}]',
                    '[{"workPackage":"\u00a0A\u00a0"}]', '[{"work_package":""}]',
                    '[{"workPackage":"A","work_package":"A"}]')
        for raw in accepted:
            self.cur.execute('SELECT supplier_payment_warehouse_package(%s) AS package', (raw,))
            self.assertEqual(_package(raw), self.cur.fetchone()['package'])
        rejected = ('[{"workPackage":" A"}]', '[{"workPackage":"A","workPackage":"A"}]',
                    '[{"workPackage":"A","work_package":"B"}]', '[{"workPackage":true}]',
                    '[{}]', '[]', '[{"workPackage":"A"},{"workPackage":"B"}]')
        import psycopg2
        for raw in rejected:
            with self.subTest(raw=raw):
                self.cur.execute('SAVEPOINT sql_contract')
                with self.assertRaises(psycopg2.errors.CheckViolation):
                    self.cur.execute('SELECT supplier_payment_warehouse_package(%s)', (raw,))
                self.cur.execute('ROLLBACK TO SAVEPOINT sql_contract')
                with self.assertRaises(HTTPException) as error:
                    _package(raw)
                self.assertEqual(error.exception.status_code, 409)

    def test_store_replay_requires_current_real_authority(self):
        from .allocation_store import replace_allocations
        body = self.body()
        saved = replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body)
        self.assertEqual(replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body), saved)
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2', (self.actor,))
        try:
            with self.assertRaises(HTTPException) as error:
                replace_allocations(self.main.get_db, self.adapter(), self.actor, 2, body)
            self.assertEqual(error.exception.status_code, 403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2', (self.actor,))

    def test_invalid_group_ids_and_autocommit_fail_before_access(self):
        for group in (None, True, 1.5, '1', 0):
            self.rejected(422, command=dict(groupId=group))
        self.rejected(422, command={})
        self.conn.rollback()
        self.conn.autocommit = True
        with self.assertRaises(RuntimeError):
            self.authorize()
