"""Payment status boundaries used by the production invoice update route."""
import unittest

from fastapi import HTTPException

from .fulfilment import invoice_payment_status


class InvoicePaymentStatusTests(unittest.TestCase):
    def test_unpaid_kopeck_keeps_invoice_partially_paid(self):
        self.assertEqual(invoice_payment_status('Оплачен', 100, 99.99), 'Частично оплачен')

    def test_full_payment_normalizes_partial_status(self):
        self.assertEqual(invoice_payment_status('Частично оплачен', 100, 100), 'Оплачен')

    def test_approval_without_payment_is_allowed(self):
        self.assertEqual(invoice_payment_status('Утверждён', 100, 0), 'Утверждён')

    def test_invalid_amounts_cannot_mark_invoice_paid(self):
        for amount, paid in [(100, 0), (100, -1), (-1, 1), (100, 101),
                             (float('nan'), 1), (100, float('nan')),
                             (float('inf'), 1), (100, float('inf'))]:
            with self.subTest(amount=amount, paid=paid):
                with self.assertRaises(HTTPException) as error:
                    invoice_payment_status('Оплачен', amount, paid)
                self.assertEqual(error.exception.status_code, 400)
