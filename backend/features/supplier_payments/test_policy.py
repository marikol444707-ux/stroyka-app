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

    def test_payment_and_reversal_require_at_least_one_document(self):
        from .policy import validate_new_payment
        for kind, amount in (('payment', '0.01'), ('reversal', '-0.01')):
            with self.subTest(kind=kind), self.assertRaises(HTTPException) as error:
                validate_new_payment(Cursor(self.row), dict(documents=[]),
                                     dict(kind=kind), Decimal(amount))
            self.assertEqual(error.exception.status_code, 409)

    def test_one_kopeck_payment_and_reversal_are_valid(self):
        from .policy import validate_new_payment
        for kind, amount in (('payment', '0.01'), ('reversal', '-0.01')):
            with self.subTest(kind=kind):
                validate_new_payment(Cursor(self.row), dict(documents=[self.doc]),
                                     dict(kind=kind), Decimal(amount))

    def test_zero_and_wrong_direction_are_rejected_at_kopeck_boundary(self):
        from .policy import validate_new_payment
        for kind, amount in (('payment', '0'), ('payment', '-0.01'),
                             ('reversal', '0'), ('reversal', '0.01')):
            with self.subTest(kind=kind, amount=amount), self.assertRaises(HTTPException) as error:
                validate_new_payment(Cursor(self.row), dict(documents=[self.doc]),
                                     dict(kind=kind), Decimal(amount))
            self.assertEqual(error.exception.status_code, 409)

    def test_approved_partial_paid_statuses_supported(self):
        for status in ('Утверждён', 'Частично оплачен', 'Оплачен'):
            with self.subTest(status=status):
                self.row['status'] = status
                self.validate()

    def test_credit_and_its_reversal_accept_zero_cash(self):
        from .policy import validate_new_payment
        for kind in ('credit', 'reversal'):
            for amount in ('0.00', '-0.00'):
                with self.subTest(kind=kind, amount=amount):
                    validate_new_payment(Cursor(self.row),
                                         dict(documents=[self.doc], reversedKind='credit'),
                                         dict(kind=kind), Decimal(amount))

    def test_credit_and_its_reversal_reject_cash_movement(self):
        from .policy import validate_new_payment
        for kind in ('credit', 'reversal'):
            for amount in ('0.01', '-0.01'):
                with self.subTest(kind=kind, amount=amount):
                    with self.assertRaises(HTTPException) as error:
                        validate_new_payment(Cursor(self.row),
                                             dict(documents=[self.doc], reversedKind='credit'),
                                             dict(kind=kind), Decimal(amount))
                    self.assertEqual(error.exception.status_code, 409)

    def test_one_kopeck_refund_and_its_reversal_have_opposite_cash_directions(self):
        from .policy import validate_new_payment
        for kind, amount in (('refund', '-0.01'), ('reversal', '0.01')):
            with self.subTest(kind=kind):
                validate_new_payment(Cursor(self.row),
                                     dict(documents=[self.doc], reversedKind='refund'),
                                     dict(kind=kind), Decimal(amount))

    def test_refund_and_its_reversal_reject_zero_and_wrong_direction(self):
        from .policy import validate_new_payment
        for kind, amount in (('refund', '0'), ('refund', '0.01'),
                             ('reversal', '0'), ('reversal', '-0.01')):
            with self.subTest(kind=kind, amount=amount):
                with self.assertRaises(HTTPException) as error:
                    validate_new_payment(Cursor(self.row),
                                         dict(documents=[self.doc], reversedKind='refund'),
                                         dict(kind=kind), Decimal(amount))
                self.assertEqual(error.exception.status_code, 409)

    def test_internal_cash_amount_requires_a_finite_decimal(self):
        from .policy import validate_new_payment
        for kind, original in (('payment', None), ('refund', None), ('credit', None),
                               ('reversal', 'payment'), ('reversal', 'refund'),
                               ('reversal', 'credit')):
            for amount in (None, True, False, 1, 0.01, '0.01', Decimal('NaN'),
                           Decimal('sNaN'), Decimal('Infinity'), Decimal('-Infinity')):
                with self.subTest(kind=kind, original=original, amount=repr(amount)):
                    with self.assertRaises(HTTPException) as error:
                        validate_new_payment(Cursor(self.row),
                                             dict(documents=[self.doc], reversedKind=original),
                                             dict(kind=kind), amount)
                    self.assertEqual(error.exception.status_code, 409)

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
