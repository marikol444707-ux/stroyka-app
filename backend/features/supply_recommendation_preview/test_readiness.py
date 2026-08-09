import copy
import json
import unittest

from backend.features.estimate_revision_impact.combined_contract import (
    calculate_evidence_sha256,
)
from backend.features.supply_recommendation_preview.readiness import (
    PREVIEW_LIMIT,
    SupplyRecommendationReadinessError,
    build_supply_recommendation_readiness,
)
from backend.features.estimate_revision_impact.test_combined_report import (
    combined,
)


def stored_report():
    report = combined()
    report["readOnlyTransaction"] = True
    report["rolledBack"] = True
    return report


def rehash(report):
    report["evidenceSha256"] = calculate_evidence_sha256(report)
    return report


class SupplyRecommendationReadinessTests(unittest.TestCase):
    def test_builds_deterministic_exact_id_only_candidate(self):
        report = stored_report()

        first = build_supply_recommendation_readiness(report)
        second = build_supply_recommendation_readiness(copy.deepcopy(report))

        self.assertEqual(first, second)
        self.assertEqual(first, {
            "readinessVersion": 1,
            "ok": True,
            "dryRun": True,
            "writesAttempted": 0,
            "state": "ready",
            "source": {
                "companyId": 4,
                "projectId": 17,
                "estimateId": 52,
                "sourceRevision": report["source"]["sourceRevision"],
                "reconciliationId": 91,
                "baseEstimateId": 51,
                "impactEvidenceSha256": report["evidenceSha256"],
            },
            "readyForRecommendationPreview": True,
            "candidateCount": 1,
            "candidates": [{
                "requestId": 21,
                "requestItemIndex": 0,
                "base": {
                    "estimateId": 51,
                    "sectionIndex": 0,
                    "itemIndex": 0,
                },
                "target": {
                    "estimateId": 52,
                    "sectionIndex": 0,
                    "itemIndex": 0,
                },
                "matchKind": "stable_item_key",
                "aliasIds": [],
            }],
            "blockers": [],
        })
        serialized = json.dumps(first, ensure_ascii=False)
        for forbidden in (
            "must-not-leak", "materialName", "projectName", "quantity",
            "unit", "category", "supplier",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_unrelated_assignment_and_economics_state_do_not_block_supply(self):
        report = stored_report()
        for domain in ("assignments", "economics"):
            report["domains"][domain]["complete"] = False
            report["domains"][domain]["state"] = "incomplete"
        report["complete"] = False
        report["actionable"] = False
        rehash(report)

        readiness = build_supply_recommendation_readiness(report)

        self.assertTrue(readiness["readyForRecommendationPreview"])
        self.assertEqual(readiness["state"], "ready")
        self.assertEqual(readiness["candidateCount"], 1)

    def test_blocks_every_incomplete_relevant_domain(self):
        expected = {
            "materials": "supply_recommendation_materials_not_ready",
            "supply": "supply_recommendation_supply_not_ready",
            "warehouse": "supply_recommendation_warehouse_not_ready",
        }

        for domain, blocker in expected.items():
            with self.subTest(domain=domain):
                report = stored_report()
                report["domains"][domain]["complete"] = False
                report["domains"][domain]["state"] = "incomplete"
                report["domains"][domain]["factsTruncated"] = True
                report["complete"] = False
                report["actionable"] = False
                rehash(report)

                readiness = build_supply_recommendation_readiness(report)

                self.assertFalse(readiness["readyForRecommendationPreview"])
                self.assertEqual(readiness["state"], "blocked")
                self.assertEqual(readiness["candidateCount"], 0)
                self.assertEqual(readiness["candidates"], [])
                self.assertEqual(readiness["blockers"], [blocker])

    def test_blocks_missing_or_ambiguous_base_to_target_lineage(self):
        missing = stored_report()
        missing["domains"]["materials"]["changedPairs"] = []
        missing["domains"]["materials"]["summary"]["changedPairs"] = 0
        rehash(missing)

        missing_result = build_supply_recommendation_readiness(missing)

        self.assertEqual(missing_result["candidates"], [])
        self.assertEqual(missing_result["blockers"], [
            "supply_recommendation_lineage_missing",
        ])

        ambiguous = stored_report()
        second_pair = copy.deepcopy(
            ambiguous["domains"]["materials"]["changedPairs"][0]
        )
        second_pair["target"]["itemIndex"] = 1
        ambiguous["domains"]["materials"]["changedPairs"].append(second_pair)
        ambiguous["domains"]["materials"]["summary"]["changedPairs"] = 2
        rehash(ambiguous)

        ambiguous_result = build_supply_recommendation_readiness(ambiguous)

        self.assertEqual(ambiguous_result["candidates"], [])
        self.assertEqual(ambiguous_result["blockers"], [
            "supply_recommendation_lineage_ambiguous",
        ])

    def test_blocks_duplicate_open_requests_for_one_source_coordinate(self):
        report = stored_report()
        duplicate = copy.deepcopy(
            report["domains"]["supply"]["openSupply"][0]
        )
        duplicate["requestId"] = 22
        report["domains"]["supply"]["openSupply"].append(duplicate)
        report["domains"]["supply"]["summary"]["openSupplyItems"] = 2
        rehash(report)

        readiness = build_supply_recommendation_readiness(report)

        self.assertFalse(readiness["readyForRecommendationPreview"])
        self.assertEqual(readiness["candidates"], [])
        self.assertEqual(readiness["blockers"], [
            "supply_recommendation_open_request_ambiguous",
        ])

    def test_rejects_tamper_unknown_fields_invalid_lineage_and_bounds(self):
        invalid_cases = []

        bad_hash = stored_report()
        bad_hash["evidenceSha256"] = "0" * 64
        invalid_cases.append((
            "hash",
            bad_hash,
            "supply_recommendation_evidence_invalid",
        ))

        extra = stored_report()
        extra["privateMaterial"] = "must-not-leak"
        invalid_cases.append((
            "extra",
            extra,
            "supply_recommendation_report_invalid",
        ))

        drift = stored_report()
        drift["source"]["estimateId"] = 53
        rehash(drift)
        invalid_cases.append((
            "source drift",
            drift,
            "supply_recommendation_source_invalid",
        ))

        invalid_coordinate = stored_report()
        invalid_coordinate["domains"]["supply"]["openSupply"][0][
            "sourceSectionIndex"
        ] = True
        rehash(invalid_coordinate)
        invalid_cases.append((
            "coordinate",
            invalid_coordinate,
            "supply_recommendation_lineage_invalid",
        ))

        leaked_field = stored_report()
        leaked_field["domains"]["supply"]["openSupply"][0][
            "materialName"
        ] = "must-not-leak"
        rehash(leaked_field)
        invalid_cases.append((
            "business field",
            leaked_field,
            "supply_recommendation_lineage_invalid",
        ))

        extra_domain_field = stored_report()
        extra_domain_field["domains"]["supply"][
            "privateMaterial"
        ] = "must-not-leak"
        rehash(extra_domain_field)
        invalid_cases.append((
            "extra relevant domain field",
            extra_domain_field,
            "supply_recommendation_relevant_domain_invalid",
        ))

        supply_count_drift = stored_report()
        supply_count_drift["domains"]["supply"]["summary"][
            "openSupplyItems"
        ] = 0
        rehash(supply_count_drift)
        invalid_cases.append((
            "supply summary drift",
            supply_count_drift,
            "supply_recommendation_relevant_domain_invalid",
        ))

        material_count_drift = stored_report()
        material_count_drift["domains"]["materials"]["summary"][
            "changedPairs"
        ] = 0
        rehash(material_count_drift)
        invalid_cases.append((
            "material summary drift",
            material_count_drift,
            "supply_recommendation_relevant_domain_invalid",
        ))

        empty_change = stored_report()
        empty_change["domains"]["materials"]["changedPairs"][0][
            "changeKinds"
        ] = []
        rehash(empty_change)
        invalid_cases.append((
            "empty material change",
            empty_change,
            "supply_recommendation_lineage_invalid",
        ))

        review_count_drift = stored_report()
        review_count_drift["domains"]["supply"]["summary"][
            "needsReview"
        ] = 1
        rehash(review_count_drift)
        invalid_cases.append((
            "review count drift",
            review_count_drift,
            "supply_recommendation_relevant_domain_invalid",
        ))

        alias_without_evidence = stored_report()
        alias_pair = alias_without_evidence["domains"]["materials"][
            "changedPairs"
        ][0]
        alias_pair["matchKind"] = "confirmed_alias"
        alias_pair["aliasIds"] = []
        rehash(alias_without_evidence)
        invalid_cases.append((
            "alias without evidence",
            alias_without_evidence,
            "supply_recommendation_lineage_invalid",
        ))

        impossible_change_kind = stored_report()
        impossible_change_kind["domains"]["materials"]["changedPairs"][0][
            "changeKinds"
        ] = ["alias_identity_changed"]
        rehash(impossible_change_kind)
        invalid_cases.append((
            "stable key with alias change",
            impossible_change_kind,
            "supply_recommendation_lineage_invalid",
        ))

        oversized = stored_report()
        template = oversized["domains"]["supply"]["openSupply"][0]
        oversized["domains"]["supply"]["openSupply"] = [
            {**template, "requestId": index + 1}
            for index in range(PREVIEW_LIMIT + 1)
        ]
        oversized["domains"]["supply"]["summary"]["openSupplyItems"] = (
            PREVIEW_LIMIT + 1
        )
        rehash(oversized)
        invalid_cases.append((
            "bounds",
            oversized,
            "supply_recommendation_candidate_limit_exceeded",
        ))

        for name, report, expected_code in invalid_cases:
            with self.subTest(name=name):
                with self.assertRaises(SupplyRecommendationReadinessError) as error:
                    build_supply_recommendation_readiness(report)
                self.assertEqual(error.exception.code, expected_code)
                self.assertEqual(str(error.exception), expected_code)
                self.assertNotIn("must-not-leak", str(error.exception))


if __name__ == "__main__":
    unittest.main()
