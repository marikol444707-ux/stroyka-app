"""Structural access regressions for multi-page zero receipts (no database)."""
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from .supplier_files import authorize_read


class ReceiptOriginalAccessTests(unittest.TestCase):
    def test_only_exact_canonical_string_array_membership_joins_authorized_chain(self):
        cur = Mock()
        cur.fetchone.return_value = {'id': 41}
        user = {'id': 7, 'role': 'поставщик'}
        row = {'id': 78, 'company_id': 2, 'project_id': 9, 'file_url': '/uploads/legacy.png'}
        with patch('backend.features.document_access.supplier_files.supplier_ids', return_value=[44]), \
             patch('backend.features.document_access.supplier_files.supplier_offer_visibility_filter',
                   return_value=(' AND supplier_offers.supplier_id=ANY(%s)', [[44]])):
            self.assertEqual(authorize_read(cur, user, row), user)
        sql, params = cur.execute.call_args.args
        self.assertEqual(sql.count('%s'), len(params))
        self.assertIn("jsonb_typeof(to_jsonb(d)->'receipt_original_urls')='array'", sql)
        self.assertIn("(to_jsonb(d)->'receipt_original_urls') @> jsonb_build_array(%s::text)", sql)
        self.assertEqual(params[-3:-1], ['/tenant-files/78/content',
                         ['/tenant-files/78/content', '/uploads/legacy.png']])
        for boundary in ('supplier_offers.company_id=%s', 'p.company_id=supplier_offers.company_id',
                         'd.company_id=supplier_offers.company_id',
                         'd.supplier_id=supplier_offers.supplier_id',
                         'd.request_id=supplier_offers.request_id', 'd.project=r.project',
                         'supplier_offers.supplier_id=ANY(%s)'):
            self.assertIn(boundary, sql)
        self.assertEqual(params[:3], [2, 9, 9])

    def test_unrelated_file_without_authorized_company_supplier_chain_is_denied(self):
        cur = Mock()
        cur.fetchone.return_value = None
        cur.fetchall.return_value = []
        with patch('backend.features.document_access.supplier_files.supplier_ids', return_value=[99]), \
             patch('backend.features.document_access.supplier_files.supplier_offer_visibility_filter',
                   return_value=(' AND supplier_offers.supplier_id=ANY(%s)', [[99]])), \
             patch('backend.features.document_access.supplier_files.supplier_invoice_visibility_filter',
                   return_value=(' AND si.supplier_id=ANY(%s)', [[99]])):
            with self.assertRaises(HTTPException) as error:
                authorize_read(cur, {'id': 8, 'role': 'поставщик'},
                               {'id': 78, 'company_id': 3, 'file_url': '/uploads/file.png'})
        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(cur.execute.call_args_list[0].args[1][0], 3)


if __name__ == '__main__':
    unittest.main()
