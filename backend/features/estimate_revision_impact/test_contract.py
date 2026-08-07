import hashlib
import json
import unittest

from backend.features.agent_change_dispatch.shadow import (
    build_estimate_activation_dispatch_plan,
)
from backend.features.estimate_revision_impact.contract import (
    EstimateRevisionImpactContractError,
    build_estimate_revision_source,
    build_source_revision,
    validate_estimate_revision_source,
)


def sections():
    return [{
        "name": "Работы",
        "items": [{"name": "Стена", "quantity": 2}],
    }]


class EstimateRevisionImpactContractTests(unittest.TestCase):
    def test_builds_canonical_source_equal_to_activation_dispatch_identity(self):
        source = build_estimate_revision_source(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=sections(),
        )
        dispatch = build_estimate_activation_dispatch_plan(
            company_id=4,
            project_id=17,
            estimate_id=52,
            version="v2.0",
            sections=sections(),
            brief_date="2026-08-08",
        )

        self.assertEqual(source.schema_version, 1)
        self.assertEqual(source.event_type, "estimate.version_activated")
        self.assertEqual(source.company_id, 4)
        self.assertEqual(source.project_id, 17)
        self.assertEqual(source.estimate_id, 52)
        self.assertEqual(source.source_revision, dispatch.source_revision)

    def test_revision_is_stable_canonical_sha256(self):
        canonical = json.dumps(
            {"sections": sections(), "version": "v2.0"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        self.assertEqual(
            build_source_revision("v2.0", sections()),
            "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def test_validator_requires_exact_allowlist_and_strict_ids(self):
        valid = {
            "schemaVersion": 1,
            "eventType": "estimate.version_activated",
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "sourceRevision": "sha256:" + "a" * 64,
        }

        source = validate_estimate_revision_source(valid)
        self.assertEqual(source.company_id, 4)

        invalid_values = (
            {**valid, "extra": True},
            {key: value for key, value in valid.items() if key != "projectId"},
            {**valid, "schemaVersion": 2},
            {**valid, "eventType": "estimate.updated"},
            {**valid, "companyId": True},
            {**valid, "projectId": 0},
            {**valid, "estimateId": "52"},
            {**valid, "sourceRevision": "A" * 64},
            {**valid, "sourceRevision": "sha256:" + "A" * 64},
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(EstimateRevisionImpactContractError):
                    validate_estimate_revision_source(value)

    def test_revision_rejects_invalid_or_unbounded_content(self):
        invalid_values = (
            ("", sections()),
            (" " * 2, sections()),
            ("x" * 101, sections()),
            ("v2", None),
            ("v2", {}),
            ("v2", [{"quantity": float("nan")}]),
        )
        for version, value in invalid_values:
            with self.subTest(version=version, value=value):
                with self.assertRaises(EstimateRevisionImpactContractError):
                    build_source_revision(version, value)


if __name__ == "__main__":
    unittest.main()
