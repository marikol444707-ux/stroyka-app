import hashlib
import unittest
from unittest.mock import MagicMock
from .inventory import inventory, SOURCES


class InventoryTests(unittest.TestCase):
    def test_read_only_report_has_counts_and_hashes_without_document_contents(self):
        cur = MagicMock()
        cur.__iter__.side_effect = lambda: iter([('{"private":"document body"}',)])
        cur.fetchall.return_value = [(1, 1)]
        cur.fetchone.return_value = (1, 2, 3, 4)
        result = inventory(cur)
        self.assertEqual(set(result), {name for name, _ in SOURCES})
        for item in result.values():
            self.assertEqual(item['count'], 1)
            self.assertEqual(item['owners'], [{'companyId':1,'count':1}])
            self.assertEqual(item['ownerNeedsReview'], 3)
            self.assertEqual(item['sha256'], hashlib.sha256(b'{"private":"document body"}\n').hexdigest())
        self.assertNotIn('document body', str(result))
        for call in cur.execute.call_args_list:
            self.assertTrue(call.args[0].lstrip().startswith('SELECT'))

    def test_empty_archives_have_stable_digest(self):
        cur = MagicMock()
        cur.__iter__.side_effect = lambda: iter([])
        cur.fetchall.return_value = []
        cur.fetchone.return_value = (0, 0, 0, 0)
        for item in inventory(cur).values():
            self.assertEqual(item['count'], 0)
            self.assertEqual(item['sha256'], hashlib.sha256(b'').hexdigest())
