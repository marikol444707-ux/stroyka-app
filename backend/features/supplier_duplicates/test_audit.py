import unittest

from .audit import build_report_from_rows


class SupplierDuplicateAuditTests(unittest.TestCase):
    def test_separates_strong_identity_from_name_only_candidates(self):
        report = build_report_from_rows({
            "suppliers": [
                {"id": 1, "name": "ИП Литашов", "inn": "261908121534"},
                {"id": 2, "name": "ИП Литашов", "inn": "261908121534"},
                {"id": 3, "name": "ТД Электомонтаж"},
                {"id": 4, "name": "ТД Электомонтаж"},
            ],
            "aliases": [{"supplier_id": 1, "related_supplier_id": 2, "source": "manual_supplier_duplicate_link"}],
        })
        self.assertEqual(report["summary"]["manualLinkedPairs"], 1)
        self.assertEqual(report["summary"]["strongIdentityGroups"], 1)
        self.assertEqual(report["summary"]["nameOnlyCandidateGroups"], 1)
        self.assertEqual(report["nameOnlyCandidateGroups"][0]["supplierIds"], [3, 4])
