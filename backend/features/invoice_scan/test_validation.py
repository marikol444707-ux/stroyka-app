import ast
import copy
import io
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock

from .validation import number, validate_invoice_scan


ROOT = Path(__file__).resolve().parents[2]


def invoice():
    return {"totalWithVat": 106880, "items": [
        {"name": "Synthetic plaster", "article": str(i), "quantity": qty,
         "price": 400, "lineTotal": qty * 400, "unit": "шт"}
        for i, qty in enumerate([6, 6, 42, 26, 40, 120], 1)
    ] + [{"name": "Synthetic primer", "quantity": 20, "price": 544, "lineTotal": 10880}]}


def main_functions(names, namespace=None):
    functions = [node for node in ast.parse((ROOT / 'main.py').read_text()).body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    for fn in functions:
        fn.decorator_list = []
        fn.args.defaults = [ast.Constant(None)] * len(fn.args.defaults)
    ns = dict(namespace or {})
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])), '<invoice-runtime>', 'exec'), ns)
    return ns


class InvoiceArithmeticTest(unittest.TestCase):
    def test_all_seven_source_rows_are_valid_without_merging_equal_names(self):
        data = invoice()
        original = copy.deepcopy(data)
        result = validate_invoice_scan(data)
        self.assertTrue(result['valid'])
        self.assertEqual(result['itemsTotal'], 106880)
        self.assertEqual(data, original)
        self.assertEqual(len(data['items']), 7)

    def test_okei_code_in_quantity_is_rejected_even_when_row_multiplication_agrees(self):
        data = invoice()
        for item in data['items']:
            item['quantity'] = 796
            item['lineTotal'] = 796 * item['price']
        result = validate_invoice_scan(data)
        self.assertFalse(result['valid'])
        self.assertIn('document_total_mismatch', [e['code'] for e in result['errors']])

    def test_legitimate_quantity_796_is_not_guessed_or_replaced(self):
        data = {'items': [{'name': 'Synthetic bolts', 'quantity': 796, 'price': 2, 'lineTotal': 1592}], 'totalWithVat': 1592}
        self.assertTrue(validate_invoice_scan(data)['valid'])

    def test_matching_document_total_cannot_hide_wrong_quantities_and_prices(self):
        data = invoice()
        data['items'][0]['quantity'] = 796
        self.assertIn('line_total_mismatch', [e['code'] for e in validate_invoice_scan(data)['errors']])

    def test_small_document_discrepancy_is_not_allowed_by_percentage(self):
        data = invoice()
        data['totalWithVat'] += 50
        self.assertFalse(validate_invoice_scan(data)['valid'])

    def test_printed_unit_price_rounding_is_accepted(self):
        data = {'items': [{'name': 'Synthetic goods', 'quantity': 270, 'price': 349.56, 'lineTotal': 94380}], 'totalWithVat': 94380}
        self.assertTrue(validate_invoice_scan(data)['valid'])

    def test_missing_total_is_computed_without_replacing_source(self):
        data = {'items': [{'name': 'Synthetic goods', 'quantity': '2', 'price': '1 200,50'}], 'totalWithVat': '2 401,00'}
        self.assertTrue(validate_invoice_scan(data)['valid'])
        self.assertNotIn('lineTotal', data['items'][0])

    def test_nonfinite_missing_negative_and_zero_quantities_are_rejected(self):
        for value in [None, 'NaN', 'Infinity', True, -1, 0]:
            with self.subTest(value=value):
                data = invoice()
                data['items'][0]['quantity'] = value
                self.assertFalse(validate_invoice_scan(data)['valid'])

    def test_gross_price_and_line_sum_aliases_take_precedence(self):
        data = {'items': [{'name': 'Synthetic goods', 'quantity': 6, 'price': 327.87, 'priceWithVat': 400,
                           'lineTotal': 1967.21, 'lineTotalWithVat': 2400}], 'totalWithVat': 2400}
        self.assertTrue(validate_invoice_scan(data)['valid'])

    def test_nonfinite_explicit_amounts_cannot_be_treated_as_missing(self):
        for field in ['price', 'lineTotal']:
            data = invoice()
            data['items'][0][field] = 'NaN'
            self.assertFalse(validate_invoice_scan(data)['valid'])
        data = invoice()
        data['totalWithVat'] = 'Infinity'
        self.assertFalse(validate_invoice_scan(data)['valid'])

    def test_currency_and_locale_parsing(self):
        for value in ['106 880,00 ₽', '106\u00a0880.00', '106.880,00', '106,880.00', '106880 руб.']:
            self.assertEqual(number(value), 106880)


class InvoiceRuntimeGuardTest(unittest.TestCase):
    def test_direct_receipt_request_is_rejected_before_database_access(self):
        class HTTPException(Exception):
            def __init__(self, status_code, detail):
                self.status_code, self.detail = status_code, detail
        get_db = Mock(side_effect=AssertionError('Unexpected database access'))
        ns = main_functions({'_create_warehouse_invoice_record'}, {'HTTPException': HTTPException, 'get_db': get_db})
        data = invoice()
        data.update(sourceType='scan_project_invoice', scanValidation={'valid': True})
        data['items'][0]['quantity'] = 796
        with self.assertRaises(HTTPException) as caught:
            ns['_create_warehouse_invoice_record'](data, {'id': 8})
        self.assertEqual(caught.exception.status_code, 422)
        get_db.assert_not_called()

    def test_scan_response_preserves_bad_values_for_review_and_marks_current_errors(self):
        data = invoice()
        data['items'][0]['quantity'] = 796
        ns = main_functions({'scan_invoice'}, {
            '_normalize_invoice_scan_image_entry': lambda entry: entry,
            '_invoice_scan_template_hint': lambda: '',
            '_invoice_scan_ai_content': lambda *args: [],
            '_invoice_scan_json_format': lambda: '{}',
            'ModelInputPart': lambda **kwargs: kwargs,
            'generate_yandex_parts': lambda **kwargs: json.dumps(data),
            '_parse_ai_json_object': lambda text: (json.loads(text), ''),
            '_normalize_invoice_totals_payload': lambda payload: payload,
            '_apply_supplier_invoice_template_metadata': lambda payload, user: payload,
            'YANDEX_API_KEY': '', 'YANDEX_FOLDER_ID': '',
        })
        result = ns['scan_invoice']({'images': [{'mimeType': 'image/jpeg', 'data': 'synthetic'}]}, {'id': 8})
        self.assertTrue(result['ok'])
        self.assertFalse(result['data']['scanValidation']['valid'])
        self.assertEqual(result['data']['items'][0]['quantity'], 796)

    def test_pdf_layout_keeps_columns_and_older_reader_falls_back(self):
        ns = main_functions({'_extract_invoice_scan_pdf_text'}, {'io': io, 're': re})
        from unittest.mock import patch
        for old_reader in [False, True]:
            page = Mock()
            page.extract_text.side_effect = ([TypeError('old reader'), '796  шт  6  327.87'] if old_reader else ['796        шт        6        327.87'])
            reader = Mock(return_value=type('Reader', (), {'pages': [page]})())
            with patch('pypdf.PdfReader', reader):
                text = ns['_extract_invoice_scan_pdf_text'](b'%PDF synthetic')
            self.assertIn('796  шт  6  327.87', text)
            self.assertLess(len(text), 100)


if __name__ == '__main__':
    unittest.main()
