import unittest
from unittest.mock import Mock

from scripts.expire_public_site_leads import (
    _fetch_candidate_page,
    _delete_upload_metadata,
    _file_is_retained,
    _restore_file_states,
)


class PublicLeadRetentionHelpersTests(unittest.TestCase):
    def test_retained_original_is_detected_even_without_crm_contract_document(self):
        self.assertTrue(_file_is_retained((1, "/tenant-files/1/content", "key", None, 1, "2026-11-02")))
        self.assertFalse(_file_is_retained((1, "/tenant-files/1/content", "key", None, 1, None)))

    def test_restore_reverts_only_files_marked_deleting_by_expiration(self):
        cur = Mock()
        rows = [
            (10, "/tenant-files/10/content", "key-10", "", 1, None, "old error", "2026-01-01"),
            (11, "/tenant-files/11/content", "key-11", "cleanup_failed", 1, None, None, None),
        ]
        _restore_file_states(cur, rows)

        self.assertEqual(cur.execute.call_count, 2)
        self.assertEqual(cur.execute.call_args_list[0].args[1], ("", "old error", "2026-01-01", 10, 1))
        self.assertIn("deletion_status='deleting'", cur.execute.call_args_list[0].args[0])
        self.assertEqual(cur.execute.call_args_list[1].args[1], ("cleanup_failed", None, None, 11, 1))

    def test_candidate_pages_advance_after_preserved_records(self):
        cur = Mock()
        cur.fetchall.return_value = [(9, "2025-01-01"), (12, "2025-02-01")]

        rows = _fetch_candidate_page(cur, 20, after=("2024-12-31", 8))

        self.assertEqual(rows, [(9, "2025-01-01"), (12, "2025-02-01")])
        query, params = cur.execute.call_args.args
        self.assertIn("(privacy_last_activity_at,id) > (%s,%s)", query)
        self.assertIn("ORDER BY privacy_last_activity_at,id LIMIT %s", query)
        self.assertEqual(params, ("2024-12-31", 8, 20))

    def test_attached_upload_metadata_delete_is_scoped_to_company_and_lead(self):
        cur = Mock()
        cur.fetchone.return_value = ("public_lead_uploads",)

        _delete_upload_metadata(cur, company_id=4, lead_id=29)

        self.assertEqual(cur.execute.call_args.args[1], (4, 29))
        self.assertIn("company_id=%s AND lead_id=%s", cur.execute.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
