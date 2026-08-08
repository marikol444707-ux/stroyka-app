import unittest

from backend.features.agent_jobs.handler_registry import AgentJobContext
from backend.features.estimate_revision_impact.handler import (
    EstimateRevisionImpactHandlerError,
    build_estimate_revision_impact_handler,
)
from backend.features.estimate_revision_impact.test_combined_report import (
    combined,
    source_context,
)


def job_context(**overrides):
    row = {
        "id": 91,
        "company_id": 4,
        "project_id": 17,
        "requested_by_user_id": None,
        "requested_by_role": "system",
        "job_type": "estimate.revision_impact",
        "correlation_id": "revision-impact:" + "b" * 32,
        "payload_json": {
            "schemaVersion": 1,
            "eventType": "estimate.version_activated",
            "companyId": 4,
            "projectId": 17,
            "estimateId": 52,
            "sourceRevision": source_context()["sourceRevision"],
        },
        "attempts": 1,
        "max_attempts": 3,
    }
    row.update(overrides)
    return AgentJobContext.from_claimed_row(row)


def report(**changes):
    value = {
        **combined(),
        "readOnlyTransaction": True,
        "rolledBack": True,
    }
    value.update(changes)
    return value


class EstimateRevisionImpactHandlerTests(unittest.TestCase):
    def test_runs_only_exact_read_only_combined_report(self):
        calls = []
        connection_factory = lambda: None

        def run_report(factory, source):
            calls.append((factory, source))
            return report()

        handler = build_estimate_revision_impact_handler(
            run_report=run_report,
            connection_factory=connection_factory,
        )
        result = handler(job_context())

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], connection_factory)
        self.assertEqual(calls[0][1].company_id, 4)
        self.assertEqual(calls[0][1].project_id, 17)
        self.assertEqual(calls[0][1].estimate_id, 52)
        self.assertTrue(result["readOnlyTransaction"])
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)

    def test_rejects_queue_scope_or_payload_drift_before_report_runner(self):
        calls = []
        handler = build_estimate_revision_impact_handler(
            run_report=lambda *_args: calls.append(True) or report(),
            connection_factory=lambda: None,
        )
        invalid_contexts = (
            job_context(company_id=5),
            job_context(project_id=18),
            job_context(requested_by_user_id=7, requested_by_role="директор"),
            job_context(job_type="director.daily_brief"),
            job_context(payload_json={
                **dict(job_context().payload),
                "estimateId": 53,
                "extra": True,
            }),
        )

        for context in invalid_contexts:
            with self.subTest(context=context):
                with self.assertRaises(EstimateRevisionImpactHandlerError):
                    handler(context)
        self.assertEqual(calls, [])

    def test_rejects_untrusted_or_non_read_only_result(self):
        invalid_reports = (
            None,
            report(readOnlyTransaction=False),
            report(rolledBack=False),
            report(writesAttempted=1),
            report(evidenceSha256="0" * 64),
            {**report(), "secret": "must-not-leak"},
            {**report(), "source": {**report()["source"], "projectId": 18}},
        )

        for invalid in invalid_reports:
            with self.subTest(invalid=invalid):
                handler = build_estimate_revision_impact_handler(
                    run_report=lambda *_args, value=invalid: value,
                    connection_factory=lambda: None,
                )
                with self.assertRaises(EstimateRevisionImpactHandlerError):
                    handler(job_context())


if __name__ == "__main__":
    unittest.main()
