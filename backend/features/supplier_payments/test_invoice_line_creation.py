"""Small boundary tests; atomic creation is verified separately on PostgreSQL."""
import json
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from .invoice_line_creation import prepare_invoice_line_spec, require_invoice_line_schema, save_invoice_line_spec


class InvoiceLineCreationTests(unittest.TestCase):
    def offer(self):
        item = dict(materialName='Кирпич', unit='шт', workPackage='Основная', quantity='2')
        return dict(items_json=json.dumps([item]), items_kp_json=json.dumps([
            dict(item, pricePerUnit='100', totalPrice='200')]), exact_offer_total='200.00', vat_included=False)

    def test_prepare_retains_exact_sources_without_mutating_them(self):
        offer = self.offer(); before = dict(offer)
        spec, source = prepare_invoice_line_spec(offer, {}, 'Основная')
        self.assertEqual(spec['amount'], '200.00')
        self.assertEqual(spec['lines'][0]['quantity'], '2.000000')
        self.assertEqual(source['requestItemsJson'], offer['items_json'])
        self.assertEqual(source['offerItemsJson'], offer['items_kp_json'])
        self.assertEqual(offer, before)

    def test_invalid_amount_overrides_are_not_replaced_by_offer_total(self):
        for value in (0, '', None, True, 200.0, '200.001', '100'):
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                prepare_invoice_line_spec(self.offer(), {'amount': value}, 'Основная')
            self.assertEqual(caught.exception.status_code, 409)

    def test_invalid_source_returns_safe_domain_error(self):
        offer = self.offer(); offer['items_json'] = 'sensitive malformed source'
        with self.assertRaises(HTTPException) as caught:
            prepare_invoice_line_spec(offer, {}, 'Основная')
        self.assertEqual(caught.exception.status_code, 409)
        self.assertNotIn('sensitive', str(caught.exception.detail))

    def test_writer_does_not_end_caller_transaction(self):
        cur = Mock(); cur.connection.autocommit = False
        cur.fetchone.return_value = {'id': 7}
        spec, source = prepare_invoice_line_spec(self.offer(), {}, 'Основная')
        result = save_invoice_line_spec(cur, 12, 2, spec, source)
        self.assertEqual(result, 7)
        cur.connection.commit.assert_not_called()
        cur.connection.rollback.assert_not_called()
        cur.connection.close.assert_not_called()
        cur.close.assert_not_called()
        self.assertEqual(cur.execute.call_count, 2)
        self.assertIn('INSERT INTO supplier_invoice_line_specs', cur.execute.call_args_list[0].args[0])
        self.assertIn('INSERT INTO supplier_invoice_lines', cur.execute.call_args_list[1].args[0])

    def test_autocommit_is_rejected_before_any_write(self):
        cur = Mock(); cur.connection.autocommit = True
        with self.assertRaises(RuntimeError):
            save_invoice_line_spec(cur, 12, 2, {}, {})
        cur.execute.assert_not_called()

    def test_schema_admission_is_read_only_and_fails_closed(self):
        cur = Mock(); cur.fetchone.return_value = {'ready': False}
        with self.assertRaises(HTTPException) as caught:
            require_invoice_line_schema(cur)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertTrue(cur.execute.call_args.args[0].lstrip().startswith('SELECT'))
        self.assertEqual(len(cur.execute.call_args.args[1][0]), 11)
