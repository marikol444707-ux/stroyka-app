import os
import unittest
from . import test_extra_works_postgres as support


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL required')
class CustomerPaymentTests(unittest.TestCase):
    api = support.CustomerExtraWorksTests.api
    sql = support.CustomerExtraWorksTests.sql

    @classmethod
    def setUpClass(cls):
        support.CustomerExtraWorksTests.setUpClass.__func__(cls)

    def test_customer_sees_only_owned_incoming_amount_without_internal_notes(self):
        name=self.fixture['project']
        for company,amount in [(2,150.12),(2,-40),(3,900)]:
            self.sql("INSERT INTO project_payments(company_id,project_name,amount,note,date) VALUES(%s,%s,%s,'PRIVATE','2026-09-20')",(company,name,amount))
        rows=self.api(self.customer,'GET','/project-payments/customer-visible')
        self.assertEqual([row['amount'] for row in rows],[150.12])
        self.assertEqual(set(rows[0]),{'id','companyId','projectId','amount','date'})
        self.assertEqual(rows[0]['projectId'],self.fixture['projectId'])
        self.api(self.customer,'GET','/project-payments',expected=403)
        self.api(self.customer,'GET','/project-payments/customer-visible',company=3,expected=403)

    def test_unverified_and_reversed_receipts_are_not_published(self):
        name = self.fixture['project']
        def receipt(amount, verified=True, note='Receipt', company=2, package='Основная'):
            return self.sql("""INSERT INTO project_payments
                (company_id,project_name,work_package,amount,note,company_scope_verified)
                VALUES(%s,%s,%s,%s,%s,%s) RETURNING id""",
                (company,name,package,amount,note,verified))[0][0]
        unverified = receipt(777, False)
        cancelled = receipt(123.45)
        self.api(self.fixture['users']['director'], 'DELETE', f'/project-payments/{cancelled}')
        active = receipt(123.45)
        # Similar reversals from another company/package must not cancel this receipt.
        receipt(-123.45, note=f'Сторно платежа #{active}: Receipt', company=3)
        receipt(-123.45, note=f'Сторно платежа #{active}: Receipt', package='Другое')
        ids = {row['id'] for row in self.api(self.customer,'GET','/project-payments/customer-visible')}
        self.assertNotIn(unverified, ids)
        self.assertNotIn(cancelled, ids)
        self.assertIn(active, ids)

    def test_explicit_project_does_not_guess_payments_when_names_repeat(self):
        project_id=self.fixture['projectId'];name=self.fixture['project']
        # The real legacy fixture identifies the project by name. Persist exact
        # user assignment, then duplicate the name to prove payment binding fails.
        self.sql('ALTER TABLE users ADD COLUMN IF NOT EXISTS project_id INTEGER')
        self.sql('UPDATE users SET project_id=%s WHERE id=%s',(project_id,self.customer['id']))
        self.customer=dict(self.customer,project_id=project_id)
        other=self.sql('INSERT INTO projects(company_id,name) VALUES(2,%s) RETURNING id',(name,))[0][0]
        try:
            self.api(self.customer,'GET','/project-payments/customer-visible',expected=409)
        finally:
            self.sql('DELETE FROM projects WHERE id=%s',(other,))
