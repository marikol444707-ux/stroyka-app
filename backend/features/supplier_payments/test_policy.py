"""New-payment status policy is separate from dates, receipt caps and reversal."""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from fastapi import HTTPException


class Cursor:
    connection = SimpleNamespace(autocommit=False)

    def __init__(self, row):
        self.row = row
        self.result = row

    def execute(self, sql, params=None):
        assert sql.lstrip().startswith('SELECT')
        if 'to_regprocedure' in sql:
            self.result = {'available': False}  # Existing pre-0019 policy fixture.
            return
        assert params == (self.row['id'],)
        self.result = self.row

    def fetchone(self):
        return self.result


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(id=7, company_id=2, supplier_id=3, project_name='Object',
                        work_package='', amount=Decimal('200'), paid_amount=Decimal('20'),
                        status='Утверждён')
        self.doc = dict(kind='invoice', id=7, companyId=2, payerCompanyId=2, supplierId=3,
                        projectName='Object', workPackage='', amount=Decimal('200'), paidAmount=Decimal('20'))

    def validate(self, kind='payment'):
        from .policy import validate_new_payment
        return validate_new_payment(Cursor(self.row), dict(documents=[self.doc]), dict(kind=kind),
                                    Decimal('10') if kind == 'payment' else Decimal('-10'))

    def test_approved_partial_paid_statuses_supported(self):
        for status in ('Утверждён', 'Частично оплачен', 'Оплачен'):
            with self.subTest(status=status):
                self.row['status'] = status
                self.validate()

    def test_pending_rejected_cancelled_unknown_fail_closed(self):
        for status in ('На утверждении', 'Отклонён', 'Аннулирован', '', None, 'unknown'):
            with self.subTest(status=status):
                self.row['status'] = status
                with self.assertRaises(HTTPException) as error:
                    self.validate()
                self.assertEqual(error.exception.status_code, 409)

    def test_reversal_does_not_require_positive_payment_status(self):
        for status in ('На утверждении', 'Отклонён', 'Аннулирован', None):
            with self.subTest(status=status):
                self.row['status'] = status
                self.validate('reversal')

    def test_live_identity_must_match_resolver_context_even_for_reversal(self):
        for key, value in (('company_id', 4), ('supplier_id', 4), ('project_name', 'Other'),
                           ('work_package', 'Other'), ('amount', Decimal('201')),
                           ('paid_amount', Decimal('21'))):
            for kind in ('payment', 'reversal'):
                with self.subTest(key=key, kind=kind):
                    old = self.row[key]
                    self.row[key] = value
                    try:
                        with self.assertRaises(HTTPException) as error:
                            self.validate(kind)
                        self.assertEqual(error.exception.status_code, 409)
                    finally:
                        self.row[key] = old

    def test_warehouse_financial_status_and_cancellation(self):
        self.doc['kind'] = 'warehouse'
        self.row.update(project='Object', location='', items='[{"workPackage":""}]',
                        total_with_vat=Decimal('200'), total_base=Decimal('200'), status='Принято')
        for status in ('К оплате', 'Частично оплачена', 'Оплачена'):
            self.row['accounting_status'] = status
            self.validate()
        for status in ('Нет фото', 'На проверке', 'Нужно уточнение', 'Отклонена', None):
            with self.subTest(status=status):
                self.row['accounting_status'] = status
                with self.assertRaises(HTTPException):
                    self.validate()
                self.validate('reversal')
        self.row.update(accounting_status='К оплате', status='Аннулирована')
        with self.assertRaises(HTTPException):
            self.validate()
        self.validate('reversal')
