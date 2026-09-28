"""Real HTTP/read authority for mixed historical packages, disposable DB only."""
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from .test_openings_postgres import OpeningTests
from .reads import transaction
from .access import build_payment_access
from .mixed_opening_review import review


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class MixedOpeningReviewTests(unittest.TestCase):
    sql=OpeningTests.sql
    api=OpeningTests.api
    create_offer=OpeningTests.create_offer
    check_contract=OpeningTests.check_contract

    @classmethod
    def setUpClass(cls):
        OpeningTests.setUpClass.__func__(cls)

    def setUp(self):
        OpeningTests.setUp(self)
        flag=patch.dict(os.environ,SUPPLIER_MIXED_OPENING_REVIEW_ENABLED='1')
        flag.start();self.addCleanup(flag.stop)
        self.warehouse=self.sql('''INSERT INTO warehouse_invoices
            (company_id,supplier_id,project,items,total_with_vat,total_base,paid_amount,supplier_invoice_id)
            VALUES(2,%s,%s,'[{"workPackage":"Отделка"},{"workPackage":"Электрика"}]',200,200,50,%s)
            RETURNING id''',(self.fixture['supplierId'],self.fixture['project'],self.invoice))[0][0]
        self.sql('UPDATE supplier_invoices SET warehouse_invoice_id=%s WHERE id=%s',(self.warehouse,self.invoice))
        self.url=self.path+'/package-review/'+str(self.invoice)

    def test_http_returns_one_balance_without_any_write_or_confirmation(self):
        def snapshot():
            return {table:self.sql(f'SELECT to_jsonb(t) FROM {table} t ORDER BY to_jsonb(t)::text') for table in
                ('supplier_invoices','warehouse_invoices','supplier_payment_documents','project_payments','supplier_opening_confirmations')}
        before=snapshot()
        result=self.api('accountant','GET',self.url)
        self.assertEqual(result['openingPaid'],'50.00')
        self.assertEqual(result['newCashAmount'],'0.00')
        self.assertEqual(result['requiredPackages'],['','Отделка','Электрика'])
        self.assertFalse(result['confirmationAvailable']);self.assertFalse(result['admissionGranted'])
        self.assertNotIn('reviewedHash',result)
        self.assertEqual(snapshot(),before)

    def test_each_package_is_authorized_before_balance_is_returned(self):
        seen=[]
        deps=dict(self.main._supplier_payment_access_deps)
        def packages(actor,package):
            seen.append(package)
            return package!='Электрика'
        deps['has_package_access']=packages
        authorize=build_payment_access(deps,operation='read')
        with self.assertRaises(HTTPException) as error:
            with transaction({'get_db':self.main.get_db,'authorize_read':authorize},2) as cur:
                review(cur,authorize,self.fixture['users']['accountant']['id'],2,self.invoice)
        self.assertEqual(error.exception.status_code,403)
        self.assertIn('Основная',seen);self.assertIn('Отделка',seen);self.assertIn('Электрика',seen)

    def test_roles_company_revocation_and_default_off(self):
        self.api('supplier','GET',self.url,expected=403)
        self.api('foreman','GET',self.url,expected=403)
        with patch.dict(os.environ,SUPPLIER_MIXED_OPENING_REVIEW_ENABLED='0'):
            self.api('accountant','GET',self.url,expected=404)
        uid=self.fixture['users']['accountant']['id']
        self.sql('UPDATE user_company_roles SET active=FALSE WHERE user_id=%s AND company_id=2',(uid,))
        try:self.api('accountant','GET',self.url,expected=403)
        finally:self.sql('UPDATE user_company_roles SET active=TRUE WHERE user_id=%s AND company_id=2',(uid,))

    def test_changed_balance_or_ambiguous_link_blocks_review(self):
        self.sql('UPDATE warehouse_invoices SET paid_amount=49 WHERE id=%s',(self.warehouse,))
        self.api('accountant','GET',self.url,expected=409)
        self.sql('UPDATE warehouse_invoices SET paid_amount=50,supplier_invoice_id=NULL WHERE id=%s',(self.warehouse,))
        self.api('accountant','GET',self.url,expected=409)
