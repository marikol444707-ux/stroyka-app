"""Mixed opening database admission is atomic and retains original scope."""
import os
import unittest
from uuid import uuid4
from .test_mixed_scope_schema_postgres import MixedScopeSchemaTests
from .test_cancellations_postgres import migration


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class MixedBindingTests(MixedScopeSchemaTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conn=cls.main.get_db()
        try:
            with conn,conn.cursor() as cur:
                migration(cur,'0061_supplier_mixed_bindings.py')
                migration(cur,'0061_supplier_mixed_bindings.py',method='downgrade')
                migration(cur,'0061_supplier_mixed_bindings.py')
        finally:conn.close()

    def bind(self, evidence):
        self.cur.execute("""SELECT nextval('supplier_payment_documents_id_seq') AS invoice,
            nextval('supplier_payment_documents_id_seq') AS warehouse,
            nextval('supplier_opening_confirmations_id_seq') AS confirmation""")
        ids=self.cur.fetchone()
        self.cur.execute("""INSERT INTO supplier_mixed_opening_bindings
            (review_id,company_id,invoice_record_id,warehouse_record_id,confirmation_id)
            VALUES(%s,2,%s,%s,%s)""",
            (evidence['id'],ids['invoice'],ids['warehouse'],ids['confirmation']))
        return ids

    def finish(self, ids, evidence, *, confirmation=True):
        for kind, source in [('invoice',evidence['invoice_snapshot']),('warehouse',evidence['warehouse_snapshot'])]:
            self.cur.execute("""INSERT INTO supplier_payment_documents
                (id,company_id,document_kind,document_id,payer_company_id,supplier_id,
                 project_name,work_package,amount,opening_paid)
                VALUES(%s,2,%s,%s,2,%s,%s,'',200,50)""",
                (ids[kind],kind,source['id'],source['supplier_id'],self.fixture['project']))
        if not confirmation:
            return
        self.cur.execute("""INSERT INTO supplier_opening_confirmations
            (id,company_id,request_id,fingerprint,document_record_id,warehouse_record_id,
             actor_id,actor_name,reason,source_snapshot,warehouse_snapshot,reviewed_hash)
            SELECT %s,2,%s,%s,%s,%s,actor_id,'Accountant',reason,invoice_snapshot,
                   warehouse_snapshot,%s FROM supplier_mixed_scope_reviews WHERE id=%s""",
            (ids['confirmation'],str(uuid4()),'a'*64,ids['invoice'],ids['warehouse'],'b'*64,evidence['id']))

    def test_complete_binding_preserves_one_opening_without_cash(self):
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        evidence=self.insert()
        ids=self.bind(evidence)
        self.finish(ids,evidence)
        self.conn.commit()
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        self.assertEqual(self.sql('SELECT opening_paid FROM supplier_payment_documents WHERE id IN (%s,%s)',
                                 (ids['invoice'],ids['warehouse'])),[(50,),(50,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(50,)])

    def test_incomplete_binding_cannot_commit(self):
        evidence=self.insert()
        ids=self.bind(evidence)
        self.finish(ids,evidence,confirmation=False)
        import psycopg2
        with self.assertRaises(psycopg2.Error):
            self.conn.commit()
        self.conn.rollback()
        self.assertEqual(self.sql('SELECT id FROM supplier_payment_documents WHERE id IN (%s,%s)',
                                 (ids['invoice'],ids['warehouse'])),[])
        self.assertEqual(self.sql('SELECT review_id FROM supplier_mixed_opening_bindings WHERE review_id=%s',(evidence['id'],)),[])

    def test_stale_binding_and_removal_are_rejected(self):
        evidence=self.insert()
        self.cur.execute('UPDATE warehouse_invoices SET paid_amount=49 WHERE id=%s',(self.warehouse,))
        self.reject(lambda:self.bind(evidence))
        self.cur.execute('UPDATE warehouse_invoices SET paid_amount=50 WHERE id=%s',(self.warehouse,))
        ids=self.bind(evidence)
        self.finish(ids,evidence)
        self.reject(lambda:self.cur.execute('DELETE FROM supplier_mixed_opening_bindings WHERE review_id=%s',(evidence['id'],)))
        self.reject(lambda:self.cur.execute('TRUNCATE supplier_mixed_opening_bindings'))
        self.reject(lambda:migration(self.cur,'0061_supplier_mixed_bindings.py',method='downgrade'))

    def test_source_changed_after_binding_rolls_back_the_whole_opening(self):
        import psycopg2
        evidence=self.insert()
        ids=self.bind(evidence)
        self.finish(ids,evidence)
        self.cur.execute('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                         ('[{"workPackage":"Другое"},{"workPackage":"Электрика"}]',self.warehouse))
        with self.assertRaises(psycopg2.Error):
            self.conn.commit()
        self.conn.rollback()
        self.assertEqual(self.sql('SELECT id FROM supplier_opening_confirmations WHERE id=%s',
                                 (ids['confirmation'],)),[])
        self.assertEqual(self.sql('SELECT id FROM supplier_payment_documents WHERE id IN (%s,%s)',
                                 (ids['invoice'],ids['warehouse'])),[])

    def test_binding_cannot_borrow_other_company_evidence(self):
        evidence=self.insert()
        self.reject(lambda:self.cur.execute("""INSERT INTO supplier_mixed_opening_bindings
            (review_id,company_id,invoice_record_id,warehouse_record_id,confirmation_id)
            VALUES(%s,1,9000001,9000002,9000003)""",(evidence['id'],)))

    def test_application_confirmation_retries_without_cash_and_requires_all_packages(self):
        from .mixed_openings import confirm
        from .access import build_payment_access
        from fastapi import HTTPException
        self.cur.execute("UPDATE warehouse_invoices SET accounting_status='К оплате' WHERE id=%s",(self.warehouse,))
        evidence=self.insert()
        self.conn.commit()
        actor=self.fixture['users']['accountant']['id']
        authorize=build_payment_access(self.main._supplier_payment_access_deps,operation='update')
        body=dict(requestId=str(uuid4()),invoiceId=self.invoice,reviewId=evidence['id'],reason='Проверено бухгалтером')
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')
        first=confirm(self.main.get_db,authorize,actor,2,body)
        self.assertEqual(first['openingPaid'],'50.00')
        self.assertEqual(first['newCashAmount'],'0.00')
        self.assertEqual(confirm(self.main.get_db,authorize,actor,2,body),first)
        self.assertEqual(self.sql('SELECT count(*),sum(amount) FROM project_payments'),before)
        deps=dict(self.main._supplier_payment_access_deps)
        deps['has_package_access']=lambda actor,package:package!='Электрика'
        with self.assertRaises(HTTPException) as error:
            confirm(self.main.get_db,build_payment_access(deps,operation='update'),actor,2,body)
        self.assertEqual(error.exception.status_code,403)

    def test_application_commit_failure_leaves_no_opening_or_baselines(self):
        from .mixed_openings import confirm
        from .access import build_payment_access
        from fastapi import HTTPException
        self.cur.execute("UPDATE warehouse_invoices SET accounting_status='К оплате' WHERE id=%s",(self.warehouse,))
        evidence=self.insert()
        self.conn.commit()
        self.sql("""CREATE FUNCTION synthetic_mixed_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic failure' USING ERRCODE='23514'; END $$""")
        self.sql("""CREATE CONSTRAINT TRIGGER synthetic_mixed_commit_failure
            AFTER INSERT ON supplier_mixed_opening_bindings DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION synthetic_mixed_commit_failure()""")
        body=dict(requestId=str(uuid4()),invoiceId=self.invoice,reviewId=evidence['id'],reason='Проверено')
        try:
            with self.assertRaises(HTTPException) as error:
                confirm(self.main.get_db,build_payment_access(self.main._supplier_payment_access_deps),
                        self.fixture['users']['accountant']['id'],2,body)
            self.assertEqual(error.exception.status_code,503)
            self.assertEqual(self.sql('SELECT id FROM supplier_opening_confirmations WHERE request_id=%s',(body['requestId'],)),[])
            self.assertEqual(self.sql("SELECT id FROM supplier_payment_documents WHERE document_kind='invoice' AND document_id=%s",(self.invoice,)),[])
        finally:
            self.sql('DROP TRIGGER synthetic_mixed_commit_failure ON supplier_mixed_opening_bindings')
            self.sql('DROP FUNCTION synthetic_mixed_commit_failure()')

    def test_mixed_opening_payment_and_reversal_keep_one_cash_operation(self):
        from .mixed_openings import confirm
        from .mixed_payments import build_resolver, validate_new
        from .access import build_payment_access
        from .engine import execute
        from fastapi import HTTPException
        self.cur.execute("UPDATE warehouse_invoices SET accounting_status='К оплате' WHERE id=%s",(self.warehouse,))
        evidence=self.insert()
        self.conn.commit()
        actor=self.fixture['users']['accountant']['id']
        access=build_payment_access(self.main._supplier_payment_access_deps)
        confirm(self.main.get_db,access,actor,2,dict(requestId=str(uuid4()),
            invoiceId=self.invoice,reviewId=evidence['id'],reason='Сверено'))
        resolver=build_resolver(access)
        payment=dict(requestId=str(uuid4()),documentKind='invoice',documentId=self.invoice,
                     kind='payment',amount='20.00',paidAt='2026-09-28',reason='Доплата')
        before=self.sql('SELECT count(*),sum(amount) FROM project_payments')[0]
        result=execute(self.main.get_db,resolver,actor,2,payment,validate_new=validate_new)
        self.assertEqual(execute(self.main.get_db,resolver,actor,2,payment,validate_new=validate_new),result)
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(70,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(self.warehouse,)),[(70,)])
        self.assertEqual(self.sql('SELECT count(*) FROM project_payments')[0][0],before[0]+1)
        deps=dict(self.main._supplier_payment_access_deps)
        deps['has_package_access']=lambda actor,package:package!='Электрика'
        with self.assertRaises(HTTPException) as error:
            execute(self.main.get_db,build_resolver(build_payment_access(deps)),actor,2,payment,validate_new=validate_new)
        self.assertEqual(error.exception.status_code,403)
        original_items=self.sql('SELECT items FROM warehouse_invoices WHERE id=%s',(self.warehouse,))[0][0]
        try:
            self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s',
                     ('[{"workPackage":"Другое"},{"workPackage":"Электрика"}]',self.warehouse))
            with self.assertRaises(HTTPException) as error:
                execute(self.main.get_db,resolver,actor,2,payment,validate_new=validate_new)
            self.assertEqual(error.exception.status_code,409)
        finally:
            self.sql('UPDATE warehouse_invoices SET items=%s WHERE id=%s',(original_items,self.warehouse))
        reverse=dict(requestId=str(uuid4()),documentKind='invoice',documentId=self.invoice,
                     kind='reversal',reversesId=result['operationId'],paidAt='2026-09-28',reason='Отмена доплаты')
        with self.assertRaises(HTTPException) as error:
            execute(self.main.get_db,resolver,actor,2,dict(payment,requestId=str(uuid4()),amount='131.00'),validate_new=validate_new)
        self.assertEqual(error.exception.status_code,400)
        with self.assertRaises(HTTPException) as error:
            execute(self.main.get_db,build_resolver(build_payment_access(deps)),actor,2,reverse,validate_new=validate_new)
        self.assertEqual(error.exception.status_code,403)
        self.sql("UPDATE supplier_invoices SET status='Аннулирован' WHERE id=%s",(self.invoice,))
        self.sql("UPDATE warehouse_invoices SET status='Аннулирована' WHERE id=%s",(self.warehouse,))
        execute(self.main.get_db,resolver,actor,2,reverse,validate_new=validate_new)
        self.assertEqual(self.sql('SELECT status FROM supplier_invoices WHERE id=%s',(self.invoice,)),[('Аннулирован',)])
        self.assertEqual(self.sql('SELECT status FROM warehouse_invoices WHERE id=%s',(self.warehouse,)),[('Аннулирована',)])
        self.assertEqual(self.sql('SELECT paid_amount FROM supplier_invoices WHERE id=%s',(self.invoice,)),[(50,)])
        self.assertEqual(self.sql('SELECT paid_amount FROM warehouse_invoices WHERE id=%s',(self.warehouse,)),[(50,)])
        self.assertEqual(self.sql('SELECT COALESCE(sum(amount),0) FROM project_payments')[0][0],before[1] or 0)
