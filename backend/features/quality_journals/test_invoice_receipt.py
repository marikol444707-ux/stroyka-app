import os
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from .invoice_receipt import invoice_quality_enabled, create_invoice_quality


class InvoiceQualityTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(invoice_quality_enabled())

    def test_owner_validation_precedes_sql(self):
        for company, project, invoice, index in ((True, 7, 1, 0), (2, '7', 1, 0), (2, 7, 0, 0), (2, 7, 1, -1)):
            cur = Mock()
            with self.assertRaises(HTTPException):
                create_invoice_quality(cur, company_id=company, project_id=project, invoice_id=invoice,
                    line_index=index, name='Material', quantity=2, unit='шт')
            cur.execute.assert_not_called()

    def test_autocommit_is_rejected(self):
        cur = Mock()
        cur.connection.autocommit = True
        with self.assertRaises(HTTPException):
            create_invoice_quality(cur, company_id=2, project_id=7, invoice_id=1,
                                   line_index=0, name='Material', quantity=2, unit='шт')
        cur.execute.assert_not_called()

    def test_unrepresentable_quantities_rejected_before_sql(self):
        for quantity, cable in [('1.23456', None), ('10000000000', None),
                                ('1.234', {'isCable': True}), ('100000000', {'isCable': True})]:
            cur = Mock()
            cur.connection.autocommit = False
            with self.assertRaises(HTTPException) as error:
                create_invoice_quality(cur, company_id=2, project_id=7, invoice_id=1,
                    line_index=0, name='Material', quantity=quantity, unit='м', cable_info=cable)
            self.assertEqual(error.exception.status_code, 400)
            cur.connection.cursor.assert_not_called()
