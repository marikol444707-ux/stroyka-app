import unittest

from .service import (
    _contains_estimate_lineage,
    delete_estimate_technical_records,
    find_estimate_delete_blockers,
)


class Cursor:
    def __init__(self, counts, supply_rows=()):
        self.counts = iter(counts)
        self.supply_rows = list(supply_rows)
        self.last_supply = False
        self.calls = []

    def execute(self, query, params):
        self.calls.append((" ".join(query.split()), params))
        self.last_supply = "FROM supply_requests" in query

    def fetchone(self):
        return (next(self.counts),)

    def fetchall(self):
        return self.supply_rows if self.last_supply else []


class EstimateDeletePolicyTests(unittest.TestCase):
    def test_unused_draft_has_no_blockers(self):
        blockers = find_estimate_delete_blockers(
            Cursor([0] * 8),
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )
        self.assertEqual(blockers, [])

    def test_technical_version_history_does_not_block_unused_draft_deletion(self):
        cursor = Cursor([0] * 8)
        blockers = find_estimate_delete_blockers(
            cursor,
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )
        self.assertEqual(blockers, [])
        self.assertTrue(any(
            "JOIN estimate_versions ev" in query and params == (17,)
            for query, params in cursor.calls
        ))

    def test_non_draft_reconciliation_blocks_deletion(self):
        blockers = find_estimate_delete_blockers(
            Cursor([1] + [0] * 7),
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )
        self.assertEqual(blockers, ["сверки смет на проверке или утверждении"])

    def test_work_document_blocks_deletion(self):
        blockers = find_estimate_delete_blockers(
            Cursor([0, 0, 1, 0, 0, 0, 0, 0]),
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )
        self.assertEqual(blockers, ["записи ЖПР"])

    def test_exact_source_estimate_version_blocks_deletion(self):
        cursor = Cursor([0] * 6 + [1, 0])

        blockers = find_estimate_delete_blockers(
            cursor,
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )

        self.assertEqual(blockers, ["договорные позиции"])
        self.assertTrue(any(
            "ev.id=bci.source_estimate_version_id" in query
            and "ev.estimate_id=%s" in query
            and params == (17,)
            for query, params in cursor.calls
        ))

    def test_only_explicit_legacy_key_fallback_blocks_deletion(self):
        cursor = Cursor([0] * 7 + [1])

        blockers = find_estimate_delete_blockers(
            cursor,
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )

        self.assertEqual(blockers, ["договорные позиции"])
        self.assertTrue(any(
            "source_type='legacy'" in query
            and "estimate_item_key LIKE %s" in query
            and params == ("17:%",)
            for query, params in cursor.calls
        ))

    def test_exact_and_legacy_contract_references_share_one_blocker(self):
        blockers = find_estimate_delete_blockers(
            Cursor([0] * 6 + [1, 1]),
            estimate_id=17,
            company_id=1,
            project_name="Школа",
        )

        self.assertEqual(blockers, ["договорные позиции"])

    def test_nested_supply_lineage_blocks_deletion(self):
        self.assertTrue(_contains_estimate_lineage({"estimateLineage": {"estimateId": 17}}, 17))
        self.assertFalse(_contains_estimate_lineage({"estimateLineage": {"estimateId": 18}}, 17))

    def test_deletes_only_technical_history_and_draft_reconciliations(self):
        cursor = Cursor([])

        delete_estimate_technical_records(cursor, estimate_id=17)

        statements = [query for query, _params in cursor.calls]
        self.assertTrue(any("DELETE FROM project_documents" in query for query in statements))
        self.assertTrue(any("DELETE FROM estimate_reconciliations" in query for query in statements))
        self.assertTrue(any("DELETE FROM estimate_versions" in query for query in statements))
        self.assertTrue(all("Черновик" in query or "estimate_versions" in query for query in statements))
