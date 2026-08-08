import unittest

from backend.features.estimate_revision_impact.contract import (
    validate_estimate_revision_source,
)
from backend.features.estimate_revision_impact.job_contract import (
    EstimateRevisionImpactJobContractError,
    build_estimate_revision_impact_job_plan,
    validate_estimate_revision_impact_job_plan,
)


def source():
    return validate_estimate_revision_source({
        "schemaVersion": 1,
        "eventType": "estimate.version_activated",
        "companyId": 4,
        "projectId": 17,
        "estimateId": 52,
        "sourceRevision": "sha256:" + "a" * 64,
    })


class EstimateRevisionImpactJobContractTests(unittest.TestCase):
    def test_builds_deterministic_project_scoped_exact_source_plan(self):
        first = build_estimate_revision_impact_job_plan(source())
        second = build_estimate_revision_impact_job_plan(source())

        self.assertEqual(first, second)
        self.assertEqual(first.company_id, 4)
        self.assertEqual(first.project_id, 17)
        self.assertEqual(first.job_type, "estimate.revision_impact")
        self.assertEqual(dict(first.payload), {
            "schemaVersion": 1,
            "eventType": "estimate.version_activated",
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "sourceRevision": "sha256:" + "a" * 64,
        })
        self.assertRegex(first.idempotency_key, r"^revision-impact:[0-9a-f]{32}$")
        self.assertRegex(first.correlation_id, r"^revision-impact:[0-9a-f]{32}$")
        self.assertEqual(validate_estimate_revision_impact_job_plan(first), first)

    def test_rejects_unvalidated_source_and_tampered_plan(self):
        with self.assertRaises(EstimateRevisionImpactJobContractError):
            build_estimate_revision_impact_job_plan({})

        plan = build_estimate_revision_impact_job_plan(source())
        for changes in (
            {"company_id": 5},
            {"project_id": 18},
            {"job_type": "director.daily_brief"},
            {"idempotency_key": "revision-impact:" + "0" * 32},
            {"payload": plan.payload + (("extra", True),)},
        ):
            with self.subTest(changes=changes):
                tampered = type(plan)(**{**plan.__dict__, **changes})
                with self.assertRaises(EstimateRevisionImpactJobContractError):
                    validate_estimate_revision_impact_job_plan(tampered)


if __name__ == "__main__":
    unittest.main()
