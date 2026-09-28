import json
import unittest
from unittest.mock import MagicMock
from .procurement_inventory import attachments, inventory


class ProcurementInventoryTests(unittest.TestCase):
    def test_duplicate_pages_count_once(self):
        self.assertEqual(attachments({'photo_url':'/a', 'photo_urls':'["/a", "/b"]'},
                                    ('photo_url','photo_urls')), (['/a','/b'],0))

    def test_malformed_pages_are_reported_not_guessed(self):
        for value in ('broken', '{"url":"/a"}', '[1]'):
            self.assertEqual(attachments({'photo_urls':value}, ('photo_urls',)), ([],1))

    def test_unknown_owner_and_foreign_parent_flagged_without_exposing_urls(self):
        cur = MagicMock()
        cur.fetchall.return_value = [(8,2,'/private/original','active')]
        rows = [
            [{'id':1,'company_id':2,'pdf_url':'/tenant-files/8/content'}],
            [{'id':2,'company_id':1,'offer_id':1,'file_url':'/private/original'}], [], []]
        cur.__iter__.side_effect = lambda: iter([(json.dumps(row),) for row in rows.pop(0)])
        result = inventory(cur)
        self.assertEqual(result['supplier_invoices']['ownerMismatch'],1)
        self.assertEqual(result['supplier_invoices']['links']['offer_id']['missingOrForeignParent'],1)
        self.assertNotIn('/private/original', str(result))
        for call in cur.execute.call_args_list:
            self.assertTrue(call.args[0].startswith('SELECT'))
