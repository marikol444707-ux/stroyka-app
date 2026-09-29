"""Opt-in synthetic schema tests; no runtime adapter or authorization claims."""
import os
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from . import test_engine_postgres as engine_tests
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AllocationStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine_tests.LedgerTests.setUpClass.__func__(cls)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                # Older synthetic chain fixture predates delivery provenance.
                cur.execute('ALTER TABLE supply_deliveries ADD COLUMN IF NOT EXISTS source_supplier_invoice_id INTEGER')
                for table in ('supplier_invoices','supply_deliveries'):
                    cur.execute('ALTER TABLE '+table+' ADD COLUMN IF NOT EXISTS contract_version_id INTEGER')
                for name in ('0046_supplier_payment_attachments.py', '0047_supplier_payment_packages.py',
                             '0048_supplier_payment_cancellations.py'):
                    migration(cur, name)
        finally:
            conn.close()

    def setUp(self):
        self.conn = self.main.get_db()
        self.conn.autocommit = False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        migration(self.cur, '0049_supplier_payment_allocations.py')
        self.actor = self.fixture['users']['accountant']['id']

    def test_additive_four_empty_tables(self):
        for table in ('groups', 'revisions', 'rows'):
            self.cur.execute('SELECT count(*) AS n FROM supplier_payment_allocation_' + table)
            self.assertEqual(self.cur.fetchone()['n'], 0)
        self.cur.execute('SELECT count(*) AS n FROM supplier_payment_receipt_relations')
        self.assertEqual(self.cur.fetchone()['n'], 0)

    def test_empty_downgrade_reupgrade(self):
        migration(self.cur, '0049_supplier_payment_allocations.py', 'downgrade')
        migration(self.cur, '0049_supplier_payment_allocations.py')
        self.test_additive_four_empty_tables()

    def one(self, sql, params=()):
        self.cur.execute(sql, params)
        return self.cur.fetchone()

    def seed(self, *, group=True):
        self.invoice = self.one('''INSERT INTO supplier_invoices(company_id,supplier_id,project_name,
            work_package,amount,paid_amount,status,offer_id,request_id,contract_version_id)
            VALUES(2,%s,%s,'',200,0,'Утверждён',123,123,123) RETURNING id''',
            (self.fixture['supplierId'], self.fixture['project']))['id']
        self.record = self.one('''INSERT INTO supplier_payment_documents(company_id,document_kind,document_id,
            payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'invoice',%s,2,%s,%s,'',200,0) RETURNING id''',
            (self.invoice,self.fixture['supplierId'],self.fixture['project']))['id']
        self.payment = self.payment_row()
        self.group = self.one('''INSERT INTO supplier_payment_allocation_groups(company_id,invoice_record_id)
            VALUES(2,%s) RETURNING id''', (self.record,))['id'] if group else None
        return dict(invoice=self.invoice,record=self.record,payment=self.payment,group=self.group)

    def payment_row(self, amount=100, *, request_id=None, reverses=None):
        signed = -amount if reverses else amount
        pp = self.one('''INSERT INTO project_payments(company_id,project_name,work_package,amount,note,date,added_by)
            VALUES(2,%s,'',%s,'Synthetic','2026-09-18','Synthetic') RETURNING id''',
            (self.fixture['project'],signed))['id']
        operation = self.one('''INSERT INTO supplier_payment_operations(company_id,request_id,fingerprint,
            document_kind,document_id,kind,amount,payer_company_id,supplier_id,project_payment_id,
            reverses_id,actor_id,actor_name,reason,payment_date)
            VALUES(2,%s,%s,'invoice',%s,%s,%s,2,%s,%s,%s,%s,'Synthetic','Synthetic','2026-09-18') RETURNING id''',
            (request_id or str(uuid4()),'a'*64,self.invoice,'reversal' if reverses else 'payment',amount,
             self.fixture['supplierId'],pp,reverses,self.actor))['id']
        self.cur.execute('INSERT INTO supplier_payment_impacts VALUES(%s,%s,2,%s)', (operation,self.record,signed))
        self.cur.execute('UPDATE supplier_invoices SET paid_amount=paid_amount+%s WHERE id=%s', (signed,self.invoice))
        return operation

    def receipt(self, amount=60, *, relation=True):
        self.delivery = self.one('''INSERT INTO supply_deliveries(company_id,supplier_id,project,work_package,
            source_supplier_invoice_id,status,quality_status,received_at,received_quantity,shipped_quantity,
            planned_quantity,price_per_unit,material_name,unit,request_id,offer_id,contract_version_id)
            VALUES(2,%s,%s,'',%s,'Принято','Принято',NOW(),1,1,1,%s,'Synthetic','шт',123,123,123) RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],self.invoice,amount))['id']
        self.warehouse = self.one('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,
            total_with_vat,total_base,total_vat,paid_amount,status,supply_delivery_id,source_type,source_id,supply_request_id)
            VALUES(2,%s,%s,%s,%s,%s,0,0,'Принята',%s,'supply_delivery',%s,123) RETURNING id''',
            (self.fixture['supplierId'],self.fixture['project'],Json([dict(workPackage='',quantity=1,price=amount,name='Synthetic',unit='шт')]),
             amount,amount,self.delivery,str(self.delivery)))['id']
        return self.one('''INSERT INTO supplier_payment_receipt_relations(group_id,company_id,warehouse_invoice_id,amount)
            VALUES(%s,2,%s,%s) RETURNING id''', (self.group,self.warehouse,amount))['id'] if relation else self.warehouse

    def revision(self, rows=(), *, version=1, previous=None, row_count=None, request_id=None):
        header = self.one('''INSERT INTO supplier_payment_allocation_revisions(group_id,company_id,version,
            previous_revision_id,request_id,fingerprint,actor_id,reason,row_count)
            VALUES(%s,2,%s,%s,%s,%s,%s,'Synthetic',%s) RETURNING *''',
            (self.group,version,previous,request_id or str(uuid4()),'b'*64,self.actor,
             len(rows) if row_count is None else row_count))
        for payment, receipt, amount in rows:
            self.cur.execute('INSERT INTO supplier_payment_allocation_rows VALUES(%s,%s,2,%s,%s,%s)',
                             (header['id'],self.group,payment,receipt,amount))
        return header

    def flush(self):
        self.cur.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.cur.execute('SET CONSTRAINTS ALL DEFERRED')

    def rejects(self, action, match=None):
        self.cur.execute('SAVEPOINT invalid_case')
        with self.assertRaises(psycopg2.Error) as error:
            action()
            self.flush()
        if match:
            self.assertIn(match, str(error.exception))
        self.cur.execute('ROLLBACK TO SAVEPOINT invalid_case')

    def test_full_revision_replacement_empty_map_and_no_financial_mutation(self):
        self.seed()
        a, b = self.receipt(60), self.receipt(80)
        first = self.revision([(self.payment,a,40),(self.payment,b,60)])
        self.flush()
        second = self.revision([],version=2,previous=first['id'])
        self.flush()
        self.assertEqual(second['row_count'],0)
        self.assertEqual(self.one('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,))['paid_amount'],100)
        self.assertEqual(self.one('SELECT count(*) n FROM supplier_payment_operations')['n'],1)
        snap = self.one('SELECT provenance FROM supplier_payment_receipt_relations WHERE id=%s',(a,))['provenance']
        self.assertEqual(snap['sourceSupplierInvoiceId'],self.invoice)

    def test_caps_completeness_cas_duplicate_pairs_and_wrong_root(self):
        self.seed()
        a,b = self.receipt(60),self.receipt(80)
        self.rejects(lambda:self.revision([(self.payment,a,61)]),'Incomplete')
        self.rejects(lambda:self.revision([(self.payment,a,60),(self.payment,b,41)]),'Incomplete')
        self.rejects(lambda:self.revision([(self.payment,a,10)],row_count=2),'Incomplete')
        self.rejects(lambda:self.revision([(self.payment,a,10),(self.payment,a,10)]))
        self.rejects(lambda:self.revision([],version=2),'Stale')
        first=self.revision([(self.payment,a,10)])
        self.flush()
        self.rejects(lambda:self.revision([],version=2),'Stale')
        self.rejects(lambda:self.revision([],version=1,previous=first['id']),'Stale')
        old_group,old_payment=self.group,self.payment
        self.seed()
        self.group=old_group
        self.rejects(lambda:self.revision([(self.payment,a,10)],version=2,previous=first['id']),'Incomplete')
        self.payment=old_payment

    def test_receipt_identity_provenance_and_total_caps(self):
        self.seed()
        self.receipt(150)
        self.rejects(lambda:self.receipt(51),'Receipt total')
        self.receipt(40,relation=False)
        insert=lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (group_id,company_id,warehouse_invoice_id,amount) VALUES(%s,2,%s,40)''',(self.group,self.warehouse))
        for table, field, value in [('warehouse_invoices','paid_amount',1),('warehouse_invoices','status','Аннулирована'),
            ('warehouse_invoices','company_id',3),('supply_deliveries','status','В пути'),
            ('supply_deliveries','source_supplier_invoice_id',None)]:
            self.cur.execute('SAVEPOINT changed_receipt')
            self.cur.execute('UPDATE '+table+' SET '+field+'=%s WHERE id=%s',(value,self.delivery if table=='supply_deliveries' else self.warehouse))
            self.rejects(insert)
            self.cur.execute('ROLLBACK TO SAVEPOINT changed_receipt')
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (group_id,company_id,warehouse_invoice_id,amount,provenance) VALUES(%s,2,%s,40,'{"deliveryId":0}')''',
            (self.group,self.warehouse)),'Forged')

    def test_immutable_all_tables_and_physical_provenance(self):
        self.seed()
        receipt=self.receipt()
        self.revision([(self.payment,receipt,10)])
        self.flush()
        for table in ('supplier_payment_allocation_groups','supplier_payment_receipt_relations',
                      'supplier_payment_allocation_revisions','supplier_payment_allocation_rows'):
            for sql in ('DELETE FROM '+table,'TRUNCATE '+table,'UPDATE '+table+' SET company_id=company_id'):
                self.rejects(lambda sql=sql:self.cur.execute(sql))
        for table, id_ in [('warehouse_invoices',self.warehouse),('supply_deliveries',self.delivery)]:
            self.rejects(lambda:self.cur.execute('UPDATE '+table+' SET company_id=company_id WHERE id=%s',(id_,)))
            self.rejects(lambda:self.cur.execute('DELETE FROM '+table+' WHERE id=%s',(id_,)))
        self.rejects(lambda:self.cur.execute('UPDATE supplier_invoices SET amount=199 WHERE id=%s',(self.invoice,)))
        self.rejects(lambda:migration(self.cur,'0049_supplier_payment_allocations.py','downgrade'))

    def test_related_receipt_cannot_be_baseline_or_legacy_link(self):
        self.seed()
        self.receipt()
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_documents(company_id,document_kind,document_id,
            payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'warehouse',%s,2,%s,%s,'',60,0)''',
            (self.warehouse,self.fixture['supplierId'],self.fixture['project'])),'financial baseline')
        self.rejects(lambda:self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(self.warehouse,self.invoice)))
        self.rejects(lambda:self.cur.execute('UPDATE warehouse_invoices SET supplier_invoice_id=%s WHERE id=%s',(self.invoice,self.warehouse)))

    def test_revision_uuid_namespace_both_directions(self):
        self.seed()
        header=self.revision()
        self.flush()
        self.rejects(lambda:self.payment_row(1,request_id=str(header['request_id'])),'UUID belongs')
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_request_cancellations
            (company_id,request_id,fingerprint,actor_id,document_kind,document_id) VALUES(2,%s,%s,%s,'invoice',%s)''',
            (str(header['request_id']),'c'*64,self.actor,self.invoice)),'UUID belongs')
        operation=self.one('SELECT request_id FROM supplier_payment_operations WHERE id=%s',(self.payment,))
        self.rejects(lambda:self.revision(version=2,previous=header['id'],request_id=str(operation['request_id'])),'UUID already')
        cancelled=str(uuid4())
        self.cur.execute('''INSERT INTO supplier_payment_request_cancellations
            (company_id,request_id,fingerprint,actor_id,document_kind,document_id) VALUES(2,%s,%s,%s,'invoice',%s)''',
            (cancelled,'c'*64,self.actor,self.invoice))
        self.rejects(lambda:self.revision(version=2,previous=header['id'],request_id=cancelled),'UUID already')

    def assert_committed_reversal(self):
        self.seed()
        receipt=self.receipt()
        header=self.revision([(self.payment,receipt,30)])
        self.flush()
        self.conn.commit()
        self.payment_row(reverses=self.payment)
        self.flush()
        self.assertEqual(self.one('SELECT count(*) n FROM supplier_payment_allocation_rows WHERE revision_id=%s',(header['id'],))['n'],1)
        self.rejects(lambda:self.revision([(self.payment,receipt,30)],version=2,previous=header['id']),'Incomplete')
        self.revision([],version=2,previous=header['id'])
        self.flush()

    def test_exact_zero_vat_receipt_no_duplicate_delivery(self):
        self.seed()
        self.receipt(relation=False)
        insert=lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (group_id,company_id,warehouse_invoice_id,amount) VALUES(%s,2,%s,60)''',(self.group,self.warehouse))
        for table, field, value in [('warehouse_invoices','total_vat',1),('warehouse_invoices','total_base',59),
            ('warehouse_invoices','source_type','manual'),('warehouse_invoices','source_id','0'),
            ('warehouse_invoices','supply_request_id',None),('supply_deliveries','received_quantity',2),
            ('supply_deliveries','received_quantity','NaN'),('supply_deliveries','price_per_unit',61),
            ('supply_deliveries','received_quantity','0.3333')]:
            with self.subTest(table=table,field=field,value=value):
                self.cur.execute('SAVEPOINT changed_receipt')
                self.cur.execute('UPDATE '+table+' SET '+field+'=%s WHERE id=%s',(value,self.delivery if table=='supply_deliveries' else self.warehouse))
                self.rejects(insert)
                self.cur.execute('ROLLBACK TO SAVEPOINT changed_receipt')
        insert()
        copy=self.one('''INSERT INTO warehouse_invoices(company_id,supplier_id,project,items,total_with_vat,
            total_base,total_vat,paid_amount,status,supply_delivery_id,source_type,source_id,supply_request_id)
            SELECT company_id,supplier_id,project,items,total_with_vat,total_base,total_vat,paid_amount,status,
            supply_delivery_id,source_type,source_id,supply_request_id FROM warehouse_invoices WHERE id=%s RETURNING id''',
            (self.warehouse,))['id']
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (group_id,company_id,warehouse_invoice_id,amount) VALUES(%s,2,%s,60)''',(self.group,copy)), 'source_delivery_id')

    def warehouse_baseline(self, amount=60):
        return self.one('''INSERT INTO supplier_payment_documents(company_id,document_kind,document_id,
            payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            VALUES(2,'warehouse',%s,2,%s,%s,'',%s,0) RETURNING id''',
            (self.warehouse,self.fixture['supplierId'],self.fixture['project'],amount))['id']

    def test_existing_baseline_blocks_relation_and_paired_impacts_block_group(self):
        self.seed(group=False)
        self.receipt(200,relation=False)
        target=self.warehouse_baseline(200)
        self.cur.execute('INSERT INTO supplier_payment_impacts VALUES(%s,%s,2,100)', (self.payment,target))
        self.rejects(lambda:self.cur.execute('INSERT INTO supplier_payment_allocation_groups(company_id,invoice_record_id) VALUES(2,%s)',
                                            (self.record,)), 'invoice-only')
        self.seed()
        self.receipt(relation=False)
        self.warehouse_baseline()
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (group_id,company_id,warehouse_invoice_id,amount) VALUES(%s,2,%s,60)''',(self.group,self.warehouse)), 'identity or mode')

    def test_group_blocks_later_paired_impact_and_attachment(self):
        self.seed()
        self.receipt(200,relation=False)
        target=self.warehouse_baseline(200)
        self.rejects(lambda:self.cur.execute('INSERT INTO supplier_payment_impacts VALUES(%s,%s,2,100)',
                                            (self.payment,target)), 'invoice-only impacts')
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_attachments(company_id,request_id,fingerprint,
            invoice_record_id,warehouse_record_id,mirrored_paid,actor_id,actor_name,reason)
            VALUES(2,%s,'test',%s,%s,100,%s,'Synthetic','Synthetic')''',
            (str(uuid4()),self.record,target,self.actor)), 'attachment mode')

    def make_attachment(self, request_id):
        self.receipt(200,relation=False)
        target=self.warehouse_baseline(200)
        self.cur.execute('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(self.warehouse,self.invoice))
        self.cur.execute('UPDATE warehouse_invoices SET supplier_invoice_id=%s WHERE id=%s',(self.invoice,self.warehouse))
        self.cur.execute('''INSERT INTO supplier_payment_attachments(company_id,request_id,fingerprint,
            invoice_record_id,warehouse_record_id,mirrored_paid,actor_id,actor_name,reason)
            VALUES(2,%s,'test',%s,%s,100,%s,'Synthetic','Synthetic')''', (request_id,self.record,target,self.actor))
        self.cur.execute('UPDATE warehouse_invoices SET paid_amount=100 WHERE id=%s',(self.warehouse,))

    def test_attachment_namespace_both_directions(self):
        self.seed(group=False)
        attached=str(uuid4())
        self.make_attachment(attached)
        self.flush()
        self.seed()
        self.rejects(lambda:self.revision(request_id=attached),'UUID already')
        header=self.revision()
        self.flush()
        self.seed(group=False)
        self.rejects(lambda:self.make_attachment(str(header['request_id'])),'UUID belongs')

    def test_composite_scope_and_header_bounds(self):
        self.seed()
        receipt=self.receipt()
        header=self.revision(row_count=0)
        self.flush()
        self.rejects(lambda:self.cur.execute('INSERT INTO supplier_payment_allocation_rows VALUES(%s,%s,3,%s,%s,1)',
                                            (header['id'],self.group,self.payment,receipt)))
        self.rejects(lambda:self.revision(version=2,previous=header['id'],row_count=2001))
        self.rejects(lambda:self.revision([(self.payment,receipt,-1)],version=2,previous=header['id']))

    def test_repeatable_read_and_serializable_rejected(self):
        # No physical/evidence rows committed by these tests. Roll back the
        # per-test schema and recreate it inside the prohibited isolation mode.
        for isolation in ('REPEATABLE READ','SERIALIZABLE'):
            self.conn.rollback()
            self.cur.execute('SET TRANSACTION ISOLATION LEVEL '+isolation)
            migration(self.cur,'0049_supplier_payment_allocations.py')
            self.rejects(lambda:self.cur.execute('SELECT supplier_allocation_lock(2)'), 'READ COMMITTED')

    def test_flushed_new_revision_cannot_then_be_reversed_in_same_transaction(self):
        self.seed()
        receipt=self.receipt()
        self.revision([(self.payment,receipt,10)])
        self.flush()
        self.rejects(lambda:self.payment_row(reverses=self.payment), 'New allocation revision')

    def test_cross_company_legacy_link_rejected_even_without_group(self):
        self.seed(group=False)
        self.rejects(lambda:self.cur.execute('''INSERT INTO warehouse_invoices(company_id,supplier_invoice_id)
            VALUES(3,%s)''',(self.invoice,)), 'Cross-company')

    def test_group_freezes_invoice_contract_offer_request(self):
        self.seed()
        for column in ('contract_version_id','offer_id','request_id'):
            self.rejects(lambda:self.cur.execute('UPDATE supplier_invoices SET '+column+'=124 WHERE id=%s',
                                                (self.invoice,)), 'provenance')

    def test_fractional_kopecks_never_round_into_allocation(self):
        self.seed()
        self.receipt(.01,relation=False)
        self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
            (group_id,company_id,warehouse_invoice_id,amount) VALUES(%s,2,%s,0.014)''',(self.group,self.warehouse)))
        relation=self.receipt()
        self.rejects(lambda:self.revision([(self.payment,relation,'0.014')]))

    def test_delivery_must_match_invoice_contract_offer_request(self):
        self.seed()
        self.receipt(relation=False)
        for column in ('contract_version_id','offer_id','request_id'):
            self.cur.execute('SAVEPOINT lineage')
            self.cur.execute('UPDATE supply_deliveries SET '+column+'=124 WHERE id=%s',(self.delivery,))
            self.rejects(lambda:self.cur.execute('''INSERT INTO supplier_payment_receipt_relations
                (group_id,company_id,warehouse_invoice_id,amount) VALUES(%s,2,%s,60)''',
                (self.group,self.warehouse)), 'provenance')
            self.cur.execute('ROLLBACK TO SAVEPOINT lineage')


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class AllocationCommittedTests(unittest.TestCase):
    """Run this class on its OWN fresh DB, separately from AllocationStorageTests."""
    one=AllocationStorageTests.one
    seed=AllocationStorageTests.seed
    payment_row=AllocationStorageTests.payment_row
    receipt=AllocationStorageTests.receipt
    revision=AllocationStorageTests.revision
    flush=AllocationStorageTests.flush
    rejects=AllocationStorageTests.rejects

    @classmethod
    def setUpClass(cls):
        AllocationStorageTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0049_supplier_payment_allocations.py')
        finally:
            conn.close()

    def setUp(self):
        self.conn=self.main.get_db()
        self.conn.autocommit=False
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.cur=self.conn.cursor(cursor_factory=RealDictCursor)
        self.addCleanup(self.cur.close)
        self.actor=self.fixture['users']['accountant']['id']

    def test_committed_revision_rows_sealed_and_xid_not_forgeable(self):
        self.seed()
        receipt=self.receipt()
        header=self.revision([(self.payment,receipt,10)])
        self.conn.commit()
        other=self.receipt()
        self.rejects(lambda:self.cur.execute('INSERT INTO supplier_payment_allocation_rows VALUES(%s,%s,2,%s,%s,1)',
            (header['id'],self.group,self.payment,other)), 'sealed')
        new=self.one('''INSERT INTO supplier_payment_allocation_revisions(group_id,company_id,version,
            previous_revision_id,request_id,fingerprint,actor_id,reason,row_count,creation_xid)
            VALUES(%s,2,2,%s,%s,%s,%s,'Synthetic',0,%s) RETURNING creation_xid''',
            (self.group,header['id'],str(uuid4()),'b'*64,self.actor,header['creation_xid']))
        self.assertNotEqual(new['creation_xid'],header['creation_xid'])
        self.flush()

    def test_reversal_invalidates_committed_map_without_rewriting_it(self):
        AllocationStorageTests.assert_committed_reversal(self)

    def test_parallel_cas_waits_then_rejects_stale_revision(self):
        self.seed()
        self.conn.commit()
        leader=self.revision()
        pid=self.one('SELECT pg_backend_pid() pid')['pid']
        def competing():
            conn=self.main.get_db()
            conn.autocommit=False
            try:
                with conn,conn.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='4s'")
                    cur.execute('''INSERT INTO supplier_payment_allocation_revisions(group_id,company_id,version,
                        request_id,fingerprint,actor_id,reason,row_count)
                        VALUES(%s,2,1,%s,%s,%s,'Synthetic',0)''',(self.group,str(uuid4()),'b'*64,self.actor))
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            follower=pool.submit(competing)
            try:
                deadline=time.monotonic()+3
                blocked=False
                while time.monotonic()<deadline:
                    self.cur.execute('SELECT pg_stat_clear_snapshot()')
                    blocked=self.one("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE wait_event='advisory' AND %s=ANY(pg_blocking_pids(pid))) blocked",(pid,))['blocked']
                    if blocked: break
                    time.sleep(.01)
                self.assertTrue(blocked)
            finally:
                self.conn.commit()
            with self.assertRaises(psycopg2.Error) as error:
                follower.result(timeout=5)
            self.assertIn('Stale allocation revision',str(error.exception))
        self.assertEqual(self.one('SELECT id FROM supplier_payment_allocation_revisions WHERE group_id=%s',(self.group,))['id'],leader['id'])

    def test_cross_company_link_cannot_race_uncommitted_group(self):
        self.seed(group=False)
        self.conn.commit()
        self.cur.execute('INSERT INTO supplier_payment_allocation_groups(company_id,invoice_record_id) VALUES(2,%s)',(self.record,))
        def illegal_link():
            conn=self.main.get_db()
            conn.autocommit=False
            try:
                with conn,conn.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='3s'")
                    cur.execute('INSERT INTO warehouse_invoices(company_id,supplier_invoice_id) VALUES(3,%s)',(self.invoice,))
            finally:
                conn.close()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with self.assertRaises(psycopg2.Error) as error:
                pool.submit(illegal_link).result(timeout=4)
            self.assertIn('Cross-company',str(error.exception))
        self.conn.commit()
        self.assertEqual(self.one('SELECT count(*) n FROM warehouse_invoices WHERE supplier_invoice_id=%s',(self.invoice,))['n'],0)
