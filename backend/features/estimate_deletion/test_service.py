import unittest

from .service import _contains_estimate_lineage, find_estimate_delete_blockers


class Cursor:
    def __init__(self, counts, supply_rows=()):
        self.counts = iter(counts)
        self.supply_rows = list(supply_rows)
        self.last_supply = False

    def execute(self, query, _params):
        self.last_supply = "FROM supply_requests" in query

    def fetchone(self):
        return (next(self.counts),)

    def fetchall(self):
        return self.supply_rows if self.last_supply else []


class EstimateDeletePolicyTests(unittest.TestCase):
    def test_unused_draft_has_no_blockers(self):
        blockers = find_estimate_delete_blockers(Cursor([0] * 8), estimate_id=17, company_id=1, project_name="Школа")
        self.assertEqual(blockers, [])

    def test_work_document_blocks_deletion(self):
        blockers = find_estimate_delete_blockers(Cursor([0, 0, 0, 1, 0, 0, 0, 0]), estimate_id=17, company_id=1, project_name="Школа")
        self.assertEqual(blockers, ["записи ЖПР"])

    def test_nested_supply_lineage_blocks_deletion(self):
        self.assertTrue(_contains_estimate_lineage({"estimateLineage": {"estimateId": 17}}, 17))
        self.assertFalse(_contains_estimate_lineage({"estimateLineage": {"estimateId": 18}}, 17))
