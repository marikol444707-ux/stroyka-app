import unittest

from backend.features.estimate_volume_audit.volume_report import build_report


class EstimateVolumeAuditTest(unittest.TestCase):
    def test_reports_work_rows_scaled_units_and_duplicate_active_estimates(self):
        rows = [
            {"id": 1, "name": "Смета 1", "project_name": "Лицей", "work_package": "Основная", "sections_json": [{"name": "Раздел", "items": [
                {"name": "Установка сплит-системы", "itemType": "material", "quantity": 1, "unit": "компл"},
                {"name": "Затирка", "itemType": "material", "rawQuantity": 1312.05113, "unit": "100 т"},
            ]}]},
            {"id": 2, "name": "Смета 2", "project_name": "Лицей", "work_package": "Основная", "sections_json": [{"name": "Раздел", "items": [
                {"name": "Затирка", "itemType": "material", "quantity": 2, "unit": "т"},
            ]}]},
        ]

        report = build_report(rows, search_terms=("затир",))
        by_name = {row["name"]: row for row in report["needsReview"] if row["estimateId"] == 1}

        self.assertIn("work_name_marked_as_material", by_name["Установка сплит-системы"]["reasons"])
        self.assertEqual(by_name["Затирка"]["normalizedQuantity"], 131205.113)
        self.assertEqual(by_name["Затирка"]["normalizedUnit"], "т")
        self.assertIn("scaled_unit", by_name["Затирка"]["reasons"])
        self.assertIn("suspicious_volume", by_name["Затирка"]["reasons"])
        self.assertIn("multiple_active_estimates", by_name["Затирка"]["reasons"])
        self.assertEqual(report["matches"][0]["totalQuantity"], 131207.113)
        self.assertEqual(report["matches"][0]["sourceRowCount"], 2)
        self.assertEqual(len(report["matches"][0]["sourceRows"]), 2)
        self.assertEqual(report["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
