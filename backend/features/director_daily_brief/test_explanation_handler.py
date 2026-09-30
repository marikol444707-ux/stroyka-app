import unittest
from types import MappingProxyType, SimpleNamespace

from backend.features.director_daily_brief.explanation_handler import (
    DirectorDailyBriefExplanationHandlerError,
    build_daily_brief_explanation_handler,
)
from backend.features.director_daily_brief.test_query_service import valid_result
from backend.features.agent_jobs.handler_registry import build_default_handler_registry


def context(**overrides):
    values = {
        "job_type": "director.daily_brief.explanation",
        "owner_company_id": 4,
        "project_id": None,
        "payload": MappingProxyType({"sourceJobId": 17}),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class DirectorDailyBriefExplanationHandlerTests(unittest.TestCase):
    def test_registry_keeps_explanation_off_by_default_and_allows_explicit_enable(self):
        self.assertNotIn(
            "director.daily_brief.explanation",
            build_default_handler_registry().job_types,
        )
        self.assertIn(
            "director.daily_brief.explanation",
            build_default_handler_registry(
                enable_daily_brief_explanation=True,
            ).job_types,
        )

    def test_reads_exact_company_source_and_generates_validated_explanation(self):
        calls = []

        def read_source(company_id, source_job_id):
            calls.append(("read", company_id, source_job_id))
            return {"sourceJobId": source_job_id, "brief": valid_result()}

        def generate(*, brief, source_job_id):
            calls.append(("generate", source_job_id, brief["briefDate"]))
            return {"schemaVersion": 1, "sourceJobId": source_job_id}

        handler = build_daily_brief_explanation_handler(
            read_source=read_source,
            generate_explanation=generate,
        )

        self.assertEqual(handler(context())["sourceJobId"], 17)
        self.assertEqual(calls, [("read", 4, 17), ("generate", 17, "2026-08-05")])

    def test_fails_before_dependencies_for_wrong_scope_or_payload(self):
        calls = []
        handler = build_daily_brief_explanation_handler(
            read_source=lambda *args: calls.append(args),
            generate_explanation=lambda **kwargs: calls.append(kwargs),
        )
        invalid = (
            context(job_type="director.daily_brief"),
            context(project_id=9),
            context(payload=MappingProxyType({})),
            context(payload=MappingProxyType({"sourceJobId": 0})),
            context(payload=MappingProxyType({"sourceJobId": 17, "extra": True})),
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(DirectorDailyBriefExplanationHandlerError):
                    handler(value)
        self.assertEqual(calls, [])

    def test_rejects_source_identity_drift_without_model_call(self):
        generated = []
        handler = build_daily_brief_explanation_handler(
            read_source=lambda company_id, source_job_id: {
                "sourceJobId": 18,
                "brief": valid_result(),
            },
            generate_explanation=lambda **kwargs: generated.append(kwargs),
        )

        with self.assertRaises(DirectorDailyBriefExplanationHandlerError):
            handler(context())

        self.assertEqual(generated, [])


if __name__ == "__main__":
    unittest.main()
