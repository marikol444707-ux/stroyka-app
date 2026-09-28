import unittest
from unittest.mock import MagicMock
from .ownership import recover_ownership


class OwnershipTests(unittest.TestCase):
    def test_preview_never_writes(self):
        cur = MagicMock()
        cur.fetchall.return_value = [(1, 7)]
        self.assertEqual(recover_ownership(cur)['updated'], [])
        self.assertEqual(cur.execute.call_count, 1)
        query = cur.execute.call_args.args[0]
        for restriction in ('d.company_id IS NULL', 'f.project_id IS NULL', "f.context='company-documents'", "'active'"):
            self.assertIn(restriction, query)

    def test_apply_rechecks_ownership_and_retains_assigned_records(self):
        cur = MagicMock()
        cur.fetchall.return_value = [(1, 7), (2, 7)]
        cur.fetchone.side_effect = [(1,), None]
        self.assertEqual(recover_ownership(cur, apply=True)['updated'], [1])
        query, args = cur.execute.call_args.args
        self.assertIn('d.company_id IS NULL AND EXISTS', query)
        self.assertEqual(args, (7, 2, 7))

    def test_no_candidates_is_idempotent(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        self.assertEqual(recover_ownership(cur, apply=True)['updated'], [])
        self.assertEqual(cur.execute.call_count, 1)
