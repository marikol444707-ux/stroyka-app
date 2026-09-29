"""Synthetic future-only invoice specifications; no runtime registration claims."""
import os
import unittest
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from . import test_allocation_store_postgres as base
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class InvoiceLineSpecTests(unittest.TestCase):
    sql = base.AllocationStorePostgresTests.sql
    api = base.AllocationStorePostgresTests.api
    create_offer = base.AllocationStorePostgresTests.create_offer
    check_contract = base.AllocationStorePostgresTests.check_contract

    @classmethod
    def setUpClass(cls):
        base.AllocationStorePostgresTests.setUpClass.__func__(cls)

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        migration(self.cur, '0050_supplier_invoice_line_specs.py')

    def one(self, query, params=()):
        self.cur.execute(query, params)
        return self.cur.fetchone()

    def invoice(self, **changes):
        from psycopg2 import sql
        values = dict(self.one('''SELECT company_id,offer_id,request_id,supplier_id,project_name,
            work_package,contract_version_id FROM supplier_invoices WHERE id=%s''', (type(self).invoice_id,)))
        values.update(amount='200', vat_amount='0', paid_amount='0', status='На утверждении')
        values.update(changes)
        return self.one(sql.SQL('INSERT INTO supplier_invoices ({}) VALUES ({}) RETURNING *').format(
            sql.SQL(',').join(map(sql.Identifier, values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values)), list(values.values()))

    def header(self, invoice_id, **changes):
        values = dict(company_id=2, invoice_id=invoice_id, row_count=1, amount='200',
                      source_payload=Json({'kind': 'synthetic invoice creation'}))
        values.update(changes)
        from psycopg2 import sql
        return self.one(sql.SQL('INSERT INTO supplier_invoice_line_specs ({}) VALUES ({}) RETURNING *').format(
            sql.SQL(',').join(map(sql.Identifier, values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values)), list(values.values()))

    def line(self, spec_id, **changes):
        values = dict(spec_id=spec_id, company_id=2, line_no=1, source_request_position=0,
                      source_offer_position=0, material_name='Synthetic', unit='шт',
                      work_package=self.fixture['workPackage'], quantity='2', unit_price='100', amount='200')
        values.update(changes)
        from psycopg2 import sql
        return self.one(sql.SQL('INSERT INTO supplier_invoice_lines ({}) VALUES ({}) RETURNING *').format(
            sql.SQL(',').join(map(sql.Identifier, values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values)), list(values.values()))

    def complete(self):
        invoice = self.invoice()
        header = self.header(invoice['id'])
        self.line(header['id'], work_package=invoice['work_package'] or '')
        self.flush()
        return invoice, header

    def flush(self):
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.cur.execute('SET CONSTRAINTS ALL DEFERRED')

    def rejects(self, action, text=None):
        self.cur.execute('SAVEPOINT invalid_spec')
        with self.assertRaises(psycopg2.Error) as caught:
            action()
            self.flush()
        if text:
            self.assertIn(text, str(caught.exception))
        self.cur.execute('ROLLBACK TO SAVEPOINT invalid_spec')
        self.cur.execute('RELEASE SAVEPOINT invalid_spec')

    def test_birth_metadata_is_future_only_and_old_update_cannot_attest_insert(self):
        old = self.one('SELECT * FROM supplier_invoices WHERE id=%s', (type(self).invoice_id,))
        self.assertIsNone(old['line_spec_insert_xid'])
        self.assertIsNone(old['line_spec_insert_identity'])
        self.cur.execute('UPDATE supplier_invoices SET description=%s WHERE id=%s',
                         ('Synthetic update', old['id']))
        self.rejects(lambda: self.header(old['id']), 'creation transaction')
        self.rejects(lambda: self.cur.execute('''UPDATE supplier_invoices
            SET line_spec_insert_xid=pg_current_xact_id(),line_spec_insert_identity='{}' WHERE id=%s''',
            (old['id'],)), 'metadata')

    def test_complete_spec_has_server_identity_and_no_financial_mutation(self):
        invoice, header = self.complete()
        self.assertEqual(header['source_identity'], invoice['line_spec_insert_identity'])
        self.assertEqual(str(header['creation_xid']), str(invoice['line_spec_insert_xid']))
        self.assertEqual(header['amount'], Decimal('200'))
        self.assertEqual(self.one('SELECT paid_amount FROM supplier_invoices WHERE id=%s', (invoice['id'],))['paid_amount'], 0)
        self.assertEqual(self.one('SELECT count(*) n FROM supplier_payment_operations')['n'], 0)

    def test_empty_downgrade_reupgrade_and_nonempty_refusal(self):
        migration(self.cur, '0050_supplier_invoice_line_specs.py', 'downgrade')
        migration(self.cur, '0050_supplier_invoice_line_specs.py')
        self.complete()
        self.rejects(lambda: migration(self.cur, '0050_supplier_invoice_line_specs.py', 'downgrade'), 'evidence')

    def test_birth_identity_changed_before_header_is_not_reconstructed(self):
        invoice = self.invoice()
        self.cur.execute('UPDATE supplier_invoices SET amount=201 WHERE id=%s', (invoice['id'],))
        self.rejects(lambda: self.header(invoice['id'], amount='201'), 'identity')

    def test_missing_rows_wrong_sum_and_early_flush_extra_row(self):
        invoice = self.invoice()
        self.rejects(lambda: self.header(invoice['id']), 'Incomplete')
        header = self.header(invoice['id'])
        self.rejects(lambda: self.line(header['id'], quantity='1', amount='100'), 'Incomplete')
        self.line(header['id'])
        self.flush()
        self.rejects(lambda: self.line(header['id'], line_no=2, source_request_position=1,
                                       source_offer_position=1), 'Incomplete')

    def test_exact_money_quantity_and_price_reject_rounding_and_nonfinite(self):
        invoice = self.invoice()
        header = self.header(invoice['id'])
        for field, value in (('quantity','2.0000001'), ('unit_price','100.0000001'),
                             ('amount','200.001'), ('quantity','NaN'), ('unit_price','Infinity'),
                             ('quantity','0'), ('unit_price','-1'), ('amount','199.99')):
            with self.subTest(field=field, value=value):
                self.rejects(lambda: self.line(header['id'], **{field:value}))
        self.line(header['id'])
        self.flush()

    def test_unique_source_positions_and_uniform_package(self):
        invoice = self.invoice()
        header = self.header(invoice['id'], row_count=2)
        self.line(header['id'], quantity='1', amount='100')
        for changes in (dict(line_no=1, source_request_position=1, source_offer_position=1),
                        dict(line_no=2, source_request_position=0, source_offer_position=1),
                        dict(line_no=2, source_request_position=1, source_offer_position=0),
                        dict(line_no=2, source_request_position=1, source_offer_position=1, work_package='wrong')):
            with self.subTest(changes=changes):
                self.rejects(lambda: self.line(header['id'], quantity='1', amount='100', **changes))
        self.line(header['id'], line_no=2, source_request_position=1, source_offer_position=1,
                  quantity='1', amount='100')
        self.flush()

    def test_header_scope_vat_and_binding_fail_closed(self):
        invoice = self.invoice()
        for changes in (dict(company_id=3), dict(amount='200.001'), dict(row_count=0), dict(row_count=2001)):
            with self.subTest(changes=changes):
                self.rejects(lambda: self.header(invoice['id'], **changes))
        for column, value in (('contract_version_id',None), ('offer_id',None), ('request_id',None), ('vat_amount',1)):
            with self.subTest(column=column):
                # New invoice identity itself is unsupported, not merely changed after INSERT.
                self.rejects(lambda: self.header(self.invoice(**{column:value})['id']))

    def test_birth_and_header_ignore_caller_supplied_attestation(self):
        invoice = self.invoice(line_spec_insert_xid='1', line_spec_insert_identity=Json({'forged':True}))
        self.assertNotEqual(str(invoice['line_spec_insert_xid']), '1')
        self.assertEqual(invoice['line_spec_insert_identity']['id'], invoice['id'])
        header = self.header(invoice['id'], creation_xid='1', source_identity=Json({'forged':True}),
                             created_at='2000-01-01')
        self.assertEqual(header['source_identity'], invoice['line_spec_insert_identity'])
        self.assertEqual(str(header['creation_xid']), str(invoice['line_spec_insert_xid']))
        self.assertGreater(header['created_at'].year, 2000)
        self.line(header['id'])
        self.flush()

    def test_legacy_unmanaged_update_adds_no_0022_company_lock(self):
        # Isolate the new trigger from 0021's pre-existing broad physical lock.
        self.cur.execute('ALTER TABLE supplier_invoices DISABLE TRIGGER a_allocation_physical')
        self.cur.execute('UPDATE supplier_invoices SET description=%s WHERE id=%s',
                         ('Synthetic metadata', type(self).invoice_id))
        locks = self.one("SELECT count(*) n FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory'")
        self.assertEqual(locks['n'], 0)

    def test_immutable_evidence_and_physical_identity_but_status_paid_mutable(self):
        invoice, header = self.complete()
        for table in ('supplier_invoice_line_specs', 'supplier_invoice_lines'):
            for query in (f'UPDATE {table} SET company_id=company_id', f'DELETE FROM {table}', f'TRUNCATE {table} CASCADE'):
                with self.subTest(query=query):
                    self.rejects(lambda: self.cur.execute(query), 'immutable')
        for column, value in (('amount',201), ('project_name','wrong'), ('contract_version_id',None),
                               ('offer_id',None), ('request_id',None), ('work_package','wrong')):
            from psycopg2 import sql
            self.rejects(lambda: self.cur.execute(sql.SQL('UPDATE supplier_invoices SET {}=%s WHERE id=%s').format(
                sql.Identifier(column)), (value, invoice['id'])), 'identity')
        self.cur.execute("UPDATE supplier_invoices SET status='Утверждён',paid_amount=20 WHERE id=%s", (invoice['id'],))
        self.flush()
        self.rejects(lambda: self.cur.execute('DELETE FROM supplier_invoices WHERE id=%s', (invoice['id'],)))
        self.rejects(lambda: self.cur.execute('TRUNCATE supplier_invoices CASCADE'))


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class InvoiceLineSpecCommittedTests(unittest.TestCase):
    """Run in a separate fresh DB from InvoiceLineSpecTests; real commit seals."""
    sql = InvoiceLineSpecTests.sql
    api = InvoiceLineSpecTests.api
    create_offer = InvoiceLineSpecTests.create_offer
    check_contract = InvoiceLineSpecTests.check_contract
    one = InvoiceLineSpecTests.one
    invoice = InvoiceLineSpecTests.invoice
    header = InvoiceLineSpecTests.header
    line = InvoiceLineSpecTests.line
    complete = InvoiceLineSpecTests.complete
    flush = InvoiceLineSpecTests.flush
    rejects = InvoiceLineSpecTests.rejects

    @classmethod
    def setUpClass(cls):
        base.AllocationStorePostgresTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                migration(cur, '0050_supplier_invoice_line_specs.py')
        finally:
            conn.close()

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)

    def test_committed_invoice_cannot_be_retrofitted_even_after_update(self):
        invoice = self.invoice()
        self.conn.commit()
        self.cur.execute('UPDATE supplier_invoices SET description=%s WHERE id=%s', ('Later',invoice['id']))
        self.rejects(lambda: self.header(invoice['id']), 'creation transaction')

    def test_committed_spec_rejects_append_and_forged_creation_xid(self):
        invoice, header = self.complete()
        self.conn.commit()
        self.rejects(lambda: self.line(header['id'], line_no=2, source_request_position=1,
                                       source_offer_position=1), 'sealed')
        self.rejects(lambda: self.cur.execute('''UPDATE supplier_invoice_line_specs
            SET creation_xid=pg_current_xact_id() WHERE id=%s''', (header['id'],)), 'immutable')
        self.rejects(lambda: self.header(invoice['id']))

    def test_incomplete_commit_rolls_back_invoice_header_and_lines(self):
        invoice = self.invoice()
        self.header(invoice['id'])
        with self.assertRaises(psycopg2.Error):
            self.conn.commit()
        self.conn.rollback()
        self.assertIsNone(self.one('SELECT id FROM supplier_invoices WHERE id=%s', (invoice['id'],)))
        self.assertIsNone(self.one('SELECT id FROM supplier_invoice_line_specs WHERE invoice_id=%s', (invoice['id'],)))

    def test_non_read_committed_header_admission_rejected(self):
        for isolation in ('REPEATABLE READ', 'SERIALIZABLE'):
            with self.subTest(isolation=isolation):
                self.conn.rollback()
                self.cur.execute('SET TRANSACTION ISOLATION LEVEL '+isolation)
                self.rejects(lambda: self.header(type(self).invoice_id), 'READ COMMITTED')
