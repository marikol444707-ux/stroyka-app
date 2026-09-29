"""Review evidence is exact/immutable and cannot bypass cash admission."""
import os
import unittest
from uuid import uuid4
import psycopg2
from psycopg2.extras import RealDictCursor
from .test_mixed_opening_review_postgres import MixedOpeningReviewTests
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES')=='1','isolated PostgreSQL opt-in')
class MixedScopeSchemaTests(unittest.TestCase):
    sql=MixedOpeningReviewTests.sql
    api=MixedOpeningReviewTests.api
    create_offer=MixedOpeningReviewTests.create_offer
    check_contract=MixedOpeningReviewTests.check_contract

    @classmethod
    def setUpClass(cls):
        MixedOpeningReviewTests.setUpClass.__func__(cls)
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0058_supplier_paired_openings.py')
                migration(cur,'0059_supplier_refund_allocations.py')
                migration(cur,'0060_supplier_mixed_scopes.py')
                migration(cur,'0060_supplier_mixed_scopes.py',method='downgrade')
                migration(cur,'0060_supplier_mixed_scopes.py')
        finally:conn.close()

    def setUp(self):
        MixedOpeningReviewTests.setUp(self)
        self.conn=self.main.get_db();self.conn.autocommit=False
        self.addCleanup(self.conn.close);self.addCleanup(self.conn.rollback)
        self.cur=self.conn.cursor(cursor_factory=RealDictCursor);self.addCleanup(self.cur.close)

    def insert(self, scope='supplier_mixed_package_scope(w.items::text,i.work_package)', company='i.company_id'):
        self.cur.execute(f'''INSERT INTO supplier_mixed_scope_reviews
            (company_id,invoice_id,warehouse_id,request_id,actor_id,reason,package_scope,invoice_snapshot,warehouse_snapshot)
            SELECT {company},i.id,w.id,%s,%s,'Сверка исходных пакетов',{scope},to_jsonb(i),to_jsonb(w)
            FROM supplier_invoices i JOIN warehouse_invoices w ON w.id=i.warehouse_invoice_id WHERE i.id=%s RETURNING *''',
            (str(uuid4()),self.fixture['users']['accountant']['id'],self.invoice))
        return self.cur.fetchone()

    def reject(self, action):
        self.cur.execute('SAVEPOINT rejected')
        with self.assertRaises(psycopg2.Error):action()
        self.cur.execute('ROLLBACK TO SAVEPOINT rejected');self.cur.execute('RELEASE SAVEPOINT rejected')

    def test_review_keeps_full_scope_and_creates_no_cash_or_baseline(self):
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        result=self.insert()
        self.assertEqual(result['package_scope'],dict(requiredPackages=['','Отделка','Электрика'],linePackages=['Отделка','Электрика']))
        self.conn.commit()
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s",(self.invoice,)),[])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(50,)])

    def test_tampered_scope_foreign_company_and_changed_balance_fail(self):
        self.reject(lambda:self.insert(scope="'{}'::jsonb"))
        self.reject(lambda:self.insert(company='1'))
        self.cur.execute('UPDATE warehouse_invoices SET paid_amount=49 WHERE id=%s',(self.warehouse,))
        self.reject(self.insert)

    def test_evidence_cannot_be_changed_removed_or_downgraded(self):
        row=self.insert()
        self.reject(lambda:self.cur.execute("UPDATE supplier_mixed_scope_reviews SET reason='new' WHERE id=%s",(row['id'],)))
        self.reject(lambda:self.cur.execute('DELETE FROM supplier_mixed_scope_reviews WHERE id=%s',(row['id'],)))
        self.reject(lambda:self.cur.execute('TRUNCATE supplier_mixed_scope_reviews'))
        self.reject(lambda:migration(self.cur,'0060_supplier_mixed_scopes.py',method='downgrade'))
        self.reject(lambda:self.cur.execute('''INSERT INTO supplier_payment_documents
            (company_id,document_kind,document_id,payer_company_id,supplier_id,project_name,work_package,amount,opening_paid)
            SELECT company_id,'warehouse',id,company_id,supplier_id,project,'',200,50
            FROM warehouse_invoices WHERE id=%s''',(self.warehouse,)))

    def test_parser_rejects_missing_conflicting_and_duplicate_packages(self):
        for raw in ('[]','[{}]','[{"workPackage":"A","workPackage":"B"}]',
                    '[{"workPackage":"A","work_package":"B"}]','[{"workPackage":" A"}]'):
            with self.subTest(raw=raw):
                self.reject(lambda:self.cur.execute('SELECT supplier_mixed_package_scope(%s,\'\')',(raw,)))
