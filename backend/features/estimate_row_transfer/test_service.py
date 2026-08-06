import json
import unittest

from backend.features.brigade_lineage.canonical import sections_sha256
from backend.features.estimate_row_transfer.plan import normalize_draft_payload
from backend.features.estimate_row_transfer.service import (
    build_current_plan,
    load_reconciliation_scope,
)
from backend.features.estimate_row_transfer.test_audit import _sections
from backend.features.estimate_row_transfer.test_plan import (
    assignment_mapping,
    assignment_report,
    supply_mapping,
    supply_report,
)


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.current = None
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        self.current = self.results.pop(0)

    def fetchall(self):
        return list(self.current or [])

    def fetchone(self):
        if isinstance(self.current, dict):
            return self.current
        rows = list(self.current or [])
        return rows[0] if rows else None


def snapshot_row(snapshot_id, estimate_id, sections):
    return {
        "id": snapshot_id,
        "estimate_id": estimate_id,
        "sections_json": json.dumps(sections, ensure_ascii=False),
        "sections_sha256": sections_sha256(sections),
    }


class EstimateRowTransferCurrentPlanTests(unittest.TestCase):
    def test_loads_minimal_reconciliation_scope_for_early_authorization(self):
        cursor = FakeCursor([{
            "company_id": 1,
            "project_id": 3,
            "work_package": "Каркас",
        }])

        scope = load_reconciliation_scope(cursor, 9)

        self.assertEqual(scope, {
            "companyId": 1,
            "projectId": 3,
            "workPackage": "Каркас",
        })
        sql, params = cursor.calls[0]
        self.assertIn("FROM public.estimate_reconciliations", sql)
        self.assertNotIn("sections_json", sql)
        self.assertEqual(params, (9,))

    def test_assignment_plan_resolves_unique_current_target_snapshot(self):
        target_sections = _sections("new-row")
        cursor = FakeCursor([[snapshot_row(72, 15, target_sections)]])
        payload = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })

        plan = build_current_plan(
            cursor,
            payload,
            impact_collector=lambda _cur, _id, _mappings: assignment_report(),
        )

        self.assertEqual(plan["targetSnapshot"]["estimateVersionId"], 72)
        self.assertEqual(plan["entries"][0]["source"]["estimateVersionId"], 71)
        sql, params = cursor.calls[0]
        self.assertIn("FROM public.estimate_versions", sql)
        self.assertEqual(params, (15, sections_sha256(target_sections)))

    def test_supply_plan_validates_client_version_against_current_base_snapshot(self):
        target_sections = _sections("new-material", name="Смесь", unit="кг")
        base_sections = _sections("old-material", name="Смесь", unit="кг")
        cursor = FakeCursor([
            [snapshot_row(72, 15, target_sections)],
            [snapshot_row(71, 14, base_sections)],
        ])
        payload = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [supply_mapping()],
        })

        plan = build_current_plan(
            cursor,
            payload,
            impact_collector=lambda _cur, _id, _mappings: supply_report(),
        )

        self.assertEqual(plan["entries"][0]["source"]["estimateVersionId"], 71)
        self.assertEqual(cursor.calls[1][1], ([71],))

    def test_ambiguous_target_snapshot_fails_closed(self):
        target_sections = _sections("new-row")
        cursor = FakeCursor([[
            snapshot_row(72, 15, target_sections),
            snapshot_row(73, 15, target_sections),
        ]])
        payload = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })

        with self.assertRaisesRegex(ValueError, "target_snapshot_ambiguous"):
            build_current_plan(
                cursor,
                payload,
                impact_collector=lambda _cur, _id, _mappings: assignment_report(),
            )

    def test_snapshot_content_hash_mismatch_fails_closed(self):
        stored = snapshot_row(72, 15, _sections("new-row"))
        stored["sections_json"] = json.dumps(_sections("changed-row"), ensure_ascii=False)
        cursor = FakeCursor([[stored]])
        payload = normalize_draft_payload({
            "reconciliationId": 9,
            "entries": [assignment_mapping()],
        })

        with self.assertRaisesRegex(ValueError, "target_snapshot_hash_mismatch"):
            build_current_plan(
                cursor,
                payload,
                impact_collector=lambda _cur, _id, _mappings: assignment_report(),
            )


if __name__ == "__main__":
    unittest.main()
