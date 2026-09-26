import unittest
from decimal import Decimal
from pydantic import ValidationError

from .payment_schedule import PaymentSchedule, schedule_amounts, advance_amount, schedule_paid_amount, schedule_projection
from .contracts import ContractReview, build_snapshot
from .test_contracts import payload


def schedule():
    return {'schemaVersion': 1, 'stages': [
        {'title': 'Первый аванс', 'percentBasisPoints': 2000, 'event': 'invoice_issued', 'daysAfter': 0},
        {'title': 'До отгрузки', 'percentBasisPoints': 3000, 'event': 'before_shipment', 'daysAfter': 0},
        {'title': 'Остаток', 'percentBasisPoints': 5000, 'event': 'after_acceptance', 'daysAfter': 10},
    ]}


class PaymentScheduleTests(unittest.TestCase):
    def test_multiple_stages_and_exact_advance(self):
        plan = PaymentSchedule(**schedule())
        self.assertEqual(schedule_amounts(plan, '200'), [Decimal('40'), Decimal('60'), Decimal('100')])
        self.assertEqual(advance_amount({'paymentSchedule': schedule()}, '200'), Decimal('100'))

    def test_no_guess_for_legacy_text(self):
        self.assertIsNone(advance_amount({'paymentTerms': '30% аванс'}, '200'))

    def test_cumulative_rounding_preserves_every_kopeck(self):
        data = schedule()
        for stage, share in zip(data['stages'], (3333, 3333, 3334)):
            stage['percentBasisPoints'] = share
        amounts = schedule_amounts(PaymentSchedule(**data), '0.05')
        self.assertEqual(amounts, [Decimal('0.02'), Decimal('0.01'), Decimal('0.02')])
        self.assertEqual(sum(amounts), Decimal('0.05'))

    def test_rejects_invalid_stages_and_totals(self):
        for change in ({'percentBasisPoints': True}, {'percentBasisPoints': '2000'},
                       {'percentBasisPoints': 2000.0}, {'percentBasisPoints': 0},
                       {'percentBasisPoints': 1999}, {'daysAfter': -1}, {'daysAfter': True},
                       {'daysAfter': 3651}, {'event': 'bank_transfer'}, {'title': ' '}, {'signed': True}):
            data = schedule(); data['stages'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                PaymentSchedule(**data)

    def test_rejects_wrong_order_and_date_for_before_shipment(self):
        data = schedule(); data['stages'].reverse()
        with self.assertRaises(ValidationError): PaymentSchedule(**data)
        data = schedule(); data['stages'][1]['daysAfter'] = 1
        with self.assertRaises(ValidationError): PaymentSchedule(**data)
        for stages in ([], schedule()['stages'] * 7):
            with self.assertRaises(ValidationError): PaymentSchedule(schemaVersion=1, stages=stages)

    def test_invalid_amount_is_not_silently_rounded_or_coerced(self):
        for amount in ('NaN', 'Infinity', '-1', '1.001', True, 'invalid'):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                schedule_amounts(PaymentSchedule(**schedule()), amount)

    def test_review_snapshot_keeps_detached_schedule_and_legacy_shape(self):
        parties = {'buyer_company_id': 12, 'payer_company_id': 99, 'supplier_id': 5}
        legacy = build_snapshot(ContractReview(**payload()), parties)
        self.assertNotIn('paymentSchedule', legacy)
        review = ContractReview(**{**payload(), 'paymentSchedule': schedule()})
        saved = build_snapshot(review, parties)
        review.paymentSchedule.stages[0].title = 'Changed'
        self.assertEqual(saved['paymentSchedule'], schedule())

    def test_payment_amount_is_exact_and_rejects_non_money(self):
        self.assertEqual(schedule_paid_amount(0.1), Decimal('0.10'))
        self.assertEqual(schedule_paid_amount(0), Decimal('0'))
        for amount in (True, -1, 'NaN', 'Infinity', 'invalid', '0.001'):
            with self.subTest(amount=amount), self.assertRaises(ValueError): schedule_paid_amount(amount)

    def test_deadline_uses_calendar_days_and_waits_for_real_acceptance(self):
        projected = schedule_projection({'paymentSchedule': schedule()}, '200', '2026-09-15')
        self.assertEqual([s['dueDate'] for s in projected['stages']], ['2026-09-15', None, None])
        projected = schedule_projection({'paymentSchedule': schedule()}, '200', '2026-09-15', '2026-09-25')
        self.assertEqual(projected['stages'][2]['dueDate'], '2026-10-05')

    def test_deadline_overflow_is_a_validation_error(self):
        with self.assertRaises(ValueError):
            schedule_projection({'paymentSchedule': schedule()}, '200', '2026-09-15', '9999-12-31')
