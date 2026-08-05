import unittest
from types import MappingProxyType

from backend.features.agent_jobs.handler_registry import AgentJobContext
from backend.features.director_daily_brief.handler import (
    DirectorDailyBriefHandlerError,
    build_director_daily_brief_handler,
)
from backend.features.director_daily_brief.test_service import valid_facts


def job_context(**overrides):
    row = {
        "id": 41,
        "company_id": 7,
        "project_id": None,
        "requested_by_user_id": 5,
        "requested_by_role": "директор",
        "job_type": "director.daily_brief",
        "correlation_id": "corr-41",
        "payload_json": {"briefDate": "2026-08-05"},
        "attempts": 1,
        "max_attempts": 3,
    }
    row.update(overrides)
    return AgentJobContext.from_claimed_row(row)


class DirectorDailyBriefHandlerTests(unittest.TestCase):
    def test_reads_exactly_one_owner_company_and_builds_without_model(self):
        calls = []

        def read_results(company_id):
            calls.append(company_id)
            return valid_facts()

        handler = build_director_daily_brief_handler(read_results=read_results)
        result = handler(job_context())

        self.assertEqual(calls, [7])
        self.assertEqual(result["briefDate"], "2026-08-05")
        self.assertEqual(result["mode"], "deterministic_read_only")
        self.assertNotIn("companyId", str(result))

    def test_rejects_project_scope_unknown_payload_and_wrong_job_type_before_read(self):
        calls = []
        handler = build_director_daily_brief_handler(
            read_results=lambda company_id: calls.append(company_id) or valid_facts()
        )

        invalid_contexts = (
            job_context(project_id=12),
            job_context(payload_json={"briefDate": "2026-08-05", "companyId": 8}),
            job_context(job_type="system.worker_probe"),
        )
        for context in invalid_contexts:
            with self.subTest(context=context):
                with self.assertRaises(DirectorDailyBriefHandlerError):
                    handler(context)

        self.assertEqual(calls, [])

    def test_rejects_non_mapping_read_result(self):
        handler = build_director_daily_brief_handler(read_results=lambda company_id: [])

        with self.assertRaises(DirectorDailyBriefHandlerError):
            handler(job_context())

    def test_handler_dependency_is_immutable_after_construction(self):
        dependency = {"read": lambda company_id: valid_facts()}
        handler = build_director_daily_brief_handler(read_results=dependency["read"])
        dependency["read"] = lambda company_id: MappingProxyType({})

        self.assertEqual(handler(job_context())["briefDate"], "2026-08-05")


if __name__ == "__main__":
    unittest.main()
