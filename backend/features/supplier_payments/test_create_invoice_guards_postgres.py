"""Real HTTP/PG coverage for the legacy supplier invoice create writer."""
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import HTTPException

from .test_accounting_sync_guards_postgres import AccountingSyncGuardTests


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CreateInvoiceGuardTests(unittest.TestCase):
    setUpClass = classmethod(AccountingSyncGuardTests.setUpClass.__func__)
    setUp = AccountingSyncGuardTests.setUp
    sql = AccountingSyncGuardTests.sql
    api = AccountingSyncGuardTests.api
    invoice = AccountingSyncGuardTests.invoice
    warehouse = AccountingSyncGuardTests.warehouse
    snapshot = AccountingSyncGuardTests.snapshot

    def payload(self, **extra):
        return dict(companyId=2, supplierId=self.supplier, supplierName=self.supplier_name,
                    invoiceNumber=self.number, invoiceDate='2026-09-18', amount=200, **extra)

    def denied(self, payload, expected=409, actor='director'):
        before = self.snapshot()
        self.api(actor, 'POST', '/supplier-invoices', payload, expected=expected)
        self.assertEqual(self.snapshot(), before)

    def offer(self):
        request = self.sql('''INSERT INTO supply_requests(company_id,project,material_name,quantity,unit,
            status,prorab_confirmed_at,director_approved_at,selected_suppliers)
            VALUES(2,%s,'Synthetic',2,'шт','В работе',NOW(),NOW(),%s) RETURNING id''',
            (self.fixture['project'], [self.supplier]))[0][0]
        offer = self.sql('''INSERT INTO supplier_offers(company_id,request_id,supplier_id,total_price,status)
            VALUES(2,%s,%s,200,'Утверждено') RETURNING id''', (request, self.supplier))[0][0]
        return self.payload(projectName=self.fixture['project'], offerId=offer, requestId=request)

    def test_registered_duplicate_denied_before_supplier_enrichment(self):
        self.invoice()
        self.denied(self.payload(phone='+70000009999'))

    def test_registered_selected_warehouse_denied(self):
        self.denied(self.payload(warehouseInvoiceId=self.warehouse(registered=True)))

    def test_payload_cannot_reassign_source_company(self):
        warehouse = self.warehouse()
        self.denied({**self.payload(warehouseInvoiceId=warehouse), 'companyId': 3})

    def test_foreign_actor_cannot_reuse_invoice(self):
        self.invoice(registered=False)
        self.denied(self.payload(), expected=403, actor='stranger')

    def test_registered_same_offer_reuse_denied(self):
        payload = self.offer()
        invoice = self.invoice()
        self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s,project_name=%s WHERE id=%s',
                 (payload['offerId'], payload['requestId'], payload['projectName'], invoice))
        self.denied(payload)

    def test_existing_warehouse_link_requires_live_reciprocal_same_owner(self):
        for change in ('company_id=3', "status='Аннулирован'", 'warehouse_invoice_id=NULL'):
            with self.subTest(change=change):
                self.number = 'LINK-' + uuid4().hex
                invoice = self.invoice(registered=False)
                warehouse = self.warehouse(linked=invoice)
                self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s', (warehouse, invoice))
                self.sql('UPDATE supplier_invoices SET ' + change + ' WHERE id=%s', (invoice,))
                self.denied(self.payload(warehouseInvoiceId=warehouse))

    def test_registered_reverse_link_denied(self):
        invoice = self.invoice(registered=False)
        self.warehouse(registered=True, linked=invoice)
        self.denied(self.payload())

    def test_supplier_requires_canonical_offer_visibility(self):
        payload = self.offer()
        self.sql('UPDATE supply_requests SET director_approved_at=NULL WHERE id=%s', (payload['requestId'],))
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.main.create_supplier_invoice(payload, self.fixture['users']['supplier'])
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_supplier_scoped_offer_succeeds_but_other_supplier_cannot_reuse(self):
        payload = self.offer()
        # Generic-route subscription middleware does not expose this external
        # supplier exception; test this handler without replacing its auth.
        result = self.main.create_supplier_invoice(payload, self.fixture['users']['supplier'])
        self.assertEqual(self.sql('SELECT company_id,offer_id FROM supplier_invoices WHERE id=%s',
                                 (result['id'],)), [(2, payload['offerId'])])
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            self.main.create_supplier_invoice(payload, self.fixture['users']['stranger_supplier'])
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(self.snapshot(), before)

    def test_unmanaged_duplicate_reused(self):
        invoice = self.invoice(registered=False)
        self.assertEqual(self.api('director', 'POST', '/supplier-invoices', self.payload())['id'], invoice)

    def test_late_link_failure_rolls_back_insert_and_enrichment(self):
        import psycopg2
        warehouse = self.warehouse()
        self.sql('''CREATE FUNCTION create_invoice_test_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Synthetic late failure'; END $$''')
        self.sql('''CREATE TRIGGER create_invoice_test_failure BEFORE UPDATE ON warehouse_invoices
            FOR EACH ROW EXECUTE FUNCTION create_invoice_test_failure()''')
        before = self.snapshot()
        try:
            with self.assertRaises(psycopg2.Error):
                self.main.create_supplier_invoice(self.payload(warehouseInvoiceId=warehouse, phone='+70000008888'),
                                                  _current_user=self.fixture['users']['director'])
            self.assertEqual(self.snapshot(), before)
        finally:
            self.sql('DROP TRIGGER create_invoice_test_failure ON warehouse_invoices')
            self.sql('DROP FUNCTION create_invoice_test_failure()')

    def test_no_runtime_ddl_with_0017(self):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('LOCK TABLE supplier_invoices,warehouse_invoices,supply_requests,supplier_offers IN ACCESS SHARE MODE')
                pending = pool.submit(self.main.create_supplier_invoice, self.payload(), self.fixture['users']['director'])
                try:
                    self.assertTrue(pending.result(timeout=4)['ok'])
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def wait_and_change(self, payload, mutate, expected=409):
        conn = self.main.get_db()
        conn.autocommit = False
        try:
            with conn.cursor() as cur, ThreadPoolExecutor(max_workers=1) as pool:
                cur.execute('SELECT pg_backend_pid(),pg_advisory_xact_lock(%s,%s)', (1735289201, 2))
                blocker = cur.fetchone()[0]
                pending = pool.submit(self.main.create_supplier_invoice,
                    payload, self.fixture['users']['director'])
                try:
                    deadline = time.monotonic() + 3
                    waiting = []
                    while time.monotonic() < deadline:
                        waiting = self.sql("SELECT pid FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))", (blocker,))
                        if waiting:
                            break
                        time.sleep(.01)
                    self.assertTrue(waiting, 'Must serialize company before document row locks')
                    mutate(cur)
                    conn.commit()
                    with self.assertRaises(HTTPException) as error:
                        pending.result(timeout=4)
                    self.assertEqual(error.exception.status_code, expected)
                finally:
                    conn.rollback()
        finally:
            conn.close()

    def test_company_wait_precedes_rowlocks_and_rechecks_owner(self):
        warehouse = self.warehouse()
        self.wait_and_change(self.payload(warehouseInvoiceId=warehouse), lambda cur:
            cur.execute('UPDATE warehouse_invoices SET company_id=3 WHERE id=%s', (warehouse,)))

    def test_registration_during_company_wait_is_seen(self):
        invoice = self.invoice(registered=False)
        self.wait_and_change(self.payload(), lambda cur: cur.execute('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'invoice',%s,2,%s,'','',200,0)''', (invoice, self.supplier)))
        self.assertEqual(self.sql('SELECT warehouse_invoice_id FROM supplier_invoices WHERE id=%s', (invoice,)), [(None,)])

    def test_membership_revoked_during_wait_cannot_reuse(self):
        self.invoice(registered=False)
        user_id = self.fixture['users']['director']['id']
        try:
            self.wait_and_change(self.payload(), lambda cur: cur.execute(
                'UPDATE user_company_roles SET active=FALSE WHERE user_id=%s', (user_id,)), expected=403)
        finally:
            self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s', (user_id,))

    def test_offer_owner_change_during_wait_rejected(self):
        payload = self.offer()
        self.wait_and_change(payload, lambda cur: cur.execute(
            'UPDATE supplier_offers SET company_id=3 WHERE id=%s', (payload['offerId'],)))

    def test_parallel_same_document_creates_one_invoice(self):
        payload = self.payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.main.create_supplier_invoice(
                payload, self.fixture['users']['director']), range(2)))
        self.assertEqual(results[0]['id'], results[1]['id'])
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_invoices WHERE invoice_number=%s', (self.number,)), [(1,)])

    def test_invalid_explicit_source_ids_do_not_become_standalone(self):
        for field in ('offerId', 'offer_id', 'requestId', 'request_id', 'warehouseInvoiceId', 'warehouse_invoice_id'):
            for value in ('oops', 0, -1, True, 1.5, 2147483648):
                with self.subTest(field=field, value=value):
                    self.denied({**self.payload(), field: value}, expected=422)

    def test_conflicting_source_aliases_are_rejected(self):
        warehouse = self.warehouse()
        self.denied(self.payload(warehouseInvoiceId=warehouse, warehouse_invoice_id=warehouse + 1), expected=422)

    def test_package_limited_foreman_cannot_create_invoice(self):
        payload = self.offer()
        self.denied(payload, actor='foreman', expected=403)

    def test_finance_actor_retains_existing_unrestricted_package_policy(self):
        payload = self.offer()
        self.sql("UPDATE supply_requests SET work_package='Other package' WHERE id=%s", (payload['requestId'],))
        result = self.api('accountant', 'POST', '/supplier-invoices', payload)
        self.assertEqual(self.sql('SELECT work_package FROM supplier_invoices WHERE id=%s', (result['id'],)), [('Other package',)])

    def other_supplier(self):
        return self.sql("INSERT INTO suppliers(name,status) VALUES(%s,'Активный') RETURNING id",
                        ('Other legal supplier ' + uuid4().hex,))[0][0]

    def test_warehouse_supplier_must_match_new_invoice(self):
        warehouse = self.warehouse()
        self.denied({**self.payload(warehouseInvoiceId=warehouse), 'supplierId': self.other_supplier()})

    def test_existing_offer_invoice_supplier_must_match_offer(self):
        payload = self.offer()
        invoice = self.invoice(registered=False)
        self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s,project_name=%s,supplier_id=%s WHERE id=%s',
                 (payload['offerId'], payload['requestId'], payload['projectName'], self.other_supplier(), invoice))
        self.denied(payload)

    def test_existing_reciprocal_invoice_supplier_must_match_warehouse(self):
        invoice = self.invoice(registered=False)
        warehouse = self.warehouse(linked=invoice)
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s,supplier_id=%s WHERE id=%s',
                 (warehouse, self.other_supplier(), invoice))
        self.denied(self.payload(warehouseInvoiceId=warehouse))

    def test_object_warehouse_requires_offer_not_omitted_project(self):
        warehouse = self.warehouse()
        self.sql('UPDATE warehouse_invoices SET project=%s WHERE id=%s', (self.fixture['project'], warehouse))
        self.denied(self.payload(warehouseInvoiceId=warehouse))

    def test_object_warehouse_exact_offer_project_succeeds(self):
        payload = self.offer()
        warehouse = self.warehouse()
        self.sql('UPDATE warehouse_invoices SET project=%s,supply_request_id=%s WHERE id=%s',
                 (payload['projectName'], payload['requestId'], warehouse))
        result = self.api('director', 'POST', '/supplier-invoices', {**payload, 'warehouseInvoiceId': warehouse})
        self.assertEqual(self.sql('SELECT project_name,warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                 (result['id'],)), [(payload['projectName'], warehouse)])

    def test_main_warehouse_location_not_treated_as_object(self):
        warehouse = self.warehouse()
        result = self.api('director', 'POST', '/supplier-invoices', self.payload(warehouseInvoiceId=warehouse))
        self.assertEqual(self.sql('SELECT project_name,warehouse_invoice_id FROM supplier_invoices WHERE id=%s',
                                 (result['id'],)), [('', warehouse)])

    def test_binding_flag_routes_offer_create_and_reuse_to_canonical_endpoint(self):
        from unittest.mock import patch
        for reuse in (False, True):
            with self.subTest(reuse=reuse):
                payload = self.offer()
                if reuse:
                    invoice = self.invoice(registered=False)
                    self.sql('UPDATE supplier_invoices SET offer_id=%s,request_id=%s,project_name=%s WHERE id=%s',
                             (payload['offerId'], payload['requestId'], payload['projectName'], invoice))
                with patch.dict(os.environ, {'SUPPLIER_DOCUMENT_CONTRACT_BINDINGS_ENABLED': '1'}):
                    before = self.snapshot()
                    result = self.api('director', 'POST', '/supplier-invoices',
                                      {**payload, 'contractVersionId': 123}, expected=409)
                    self.assertIn('/supplier-offers/' + str(payload['offerId']) + '/create-invoice', result['detail'])
                    self.assertEqual(self.snapshot(), before)


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class CreateInvoicePreledgerTests(unittest.TestCase):
    from ..supplier_access.test_postgres_chain import PostgresSupplyChainTests as _Chain
    setUpClass = classmethod(_Chain.setUpClass.__func__)
    setUp = CreateInvoiceGuardTests.setUp
    sql = CreateInvoiceGuardTests.sql
    api = CreateInvoiceGuardTests.api
    invoice = CreateInvoiceGuardTests.invoice
    warehouse = CreateInvoiceGuardTests.warehouse
    snapshot = CreateInvoiceGuardTests.snapshot
    payload = CreateInvoiceGuardTests.payload
    denied = CreateInvoiceGuardTests.denied
    offer = CreateInvoiceGuardTests.offer
    test_unmanaged_duplicate_reused = CreateInvoiceGuardTests.test_unmanaged_duplicate_reused
    test_late_link_failure_rolls_back_insert_and_enrichment = CreateInvoiceGuardTests.test_late_link_failure_rolls_back_insert_and_enrichment
    test_supplier_scoped_offer_succeeds_but_other_supplier_cannot_reuse = CreateInvoiceGuardTests.test_supplier_scoped_offer_succeeds_but_other_supplier_cannot_reuse
    test_payload_cannot_reassign_source_company = CreateInvoiceGuardTests.test_payload_cannot_reassign_source_company

    def test_true_legacy_user_without_memberships_can_create(self):
        user_id = self.sql('''INSERT INTO users(name,email,role,active,company_id)
            VALUES('Legacy finance','legacy-create@supply-chain.invalid','бухгалтер',TRUE,2) RETURNING id''')[0][0]
        result = self.main.create_supplier_invoice(self.payload(), {'id': user_id})
        self.assertEqual(self.sql('SELECT company_id FROM supplier_invoices WHERE id=%s', (result['id'],)), [(2,)])
