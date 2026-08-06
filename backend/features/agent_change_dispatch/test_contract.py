import unittest
from dataclasses import replace

from backend.features.agent_change_dispatch.contract import (
    AgentChangeContractError,
    AgentChangeEvent,
    build_agent_dispatch_plan,
    validate_agent_change_event,
    validate_agent_dispatch_plan,
)


def valid_event(**overrides):
    event = {
        "schemaVersion": 1,
        "eventType": "estimate.version_activated",
        "companyId": 4,
        "projectId": 17,
        "sourceType": "estimate",
        "sourceId": 52,
        "sourceRevision": "sha256:8a8d74a2",
    }
    event.update(overrides)
    return event


class AgentChangeContractTests(unittest.TestCase):
    def test_validates_one_exact_company_project_event(self):
        event = validate_agent_change_event(valid_event())

        self.assertEqual(event.schema_version, 1)
        self.assertEqual(event.event_type, "estimate.version_activated")
        self.assertEqual(event.company_id, 4)
        self.assertEqual(event.project_id, 17)
        self.assertEqual(event.source_type, "estimate")
        self.assertEqual(event.source_id, 52)
        self.assertEqual(event.source_revision, "sha256:8a8d74a2")

    def test_rejects_unknown_or_extra_event_fields(self):
        with self.assertRaisesRegex(AgentChangeContractError, "fields"):
            validate_agent_change_event(valid_event(nextAction="delete_everything"))

    def test_rejects_aggregate_or_missing_owner(self):
        for company_id in (None, "", 0, -1, True, 4.5, "4", "all_companies"):
            with self.subTest(company_id=company_id):
                with self.assertRaises(AgentChangeContractError):
                    validate_agent_change_event(valid_event(companyId=company_id))

        for project_id in (None, "", 0, -1, True, 17.5, "17"):
            with self.subTest(project_id=project_id):
                with self.assertRaises(AgentChangeContractError):
                    validate_agent_change_event(valid_event(projectId=project_id))

    def test_rejects_unknown_event_or_mismatched_source(self):
        with self.assertRaisesRegex(AgentChangeContractError, "event type"):
            validate_agent_change_event(valid_event(eventType="warehouse.deleted"))
        with self.assertRaisesRegex(AgentChangeContractError, "source type"):
            validate_agent_change_event(valid_event(sourceType="warehouse"))

    def test_rejects_unsafe_source_revision(self):
        for revision in ("", "contains space", "../../secret", "x" * 121):
            with self.subTest(revision=revision):
                with self.assertRaises(AgentChangeContractError):
                    validate_agent_change_event(valid_event(sourceRevision=revision))

    def test_builds_deterministic_read_only_company_dispatch_plan(self):
        event = validate_agent_change_event(valid_event())

        first = build_agent_dispatch_plan(event, brief_date="2026-08-06")
        second = build_agent_dispatch_plan(event, brief_date="2026-08-06")

        self.assertEqual(first, second)
        self.assertEqual(first.company_id, 4)
        self.assertIsNone(first.project_id)
        self.assertEqual(first.source_project_id, 17)
        self.assertEqual(first.job_type, "director.daily_brief")
        self.assertEqual(first.requested_by_role, "system")
        self.assertEqual(first.payload, (("briefDate", "2026-08-06"),))
        self.assertTrue(first.idempotency_key.startswith("change:estimate.version_activated:"))
        self.assertLessEqual(len(first.idempotency_key), 180)

    def test_dispatch_idempotency_changes_with_source_or_business_date(self):
        base = validate_agent_change_event(valid_event())
        changed_source = validate_agent_change_event(
            valid_event(sourceRevision="sha256:29e7e03f")
        )

        base_plan = build_agent_dispatch_plan(base, brief_date="2026-08-06")
        changed_plan = build_agent_dispatch_plan(
            changed_source,
            brief_date="2026-08-06",
        )
        next_day_plan = build_agent_dispatch_plan(
            base,
            brief_date="2026-08-07",
        )

        self.assertNotEqual(base_plan.idempotency_key, changed_plan.idempotency_key)
        self.assertNotEqual(base_plan.idempotency_key, next_day_plan.idempotency_key)

    def test_rejects_invalid_brief_date_before_any_dispatch(self):
        event = validate_agent_change_event(valid_event())
        for brief_date in ("", "06.08.2026", "2026-02-30", None):
            with self.subTest(brief_date=brief_date):
                with self.assertRaisesRegex(AgentChangeContractError, "brief date"):
                    build_agent_dispatch_plan(event, brief_date=brief_date)

    def test_revalidates_manually_constructed_event_before_dispatch(self):
        unsafe = AgentChangeEvent(
            schema_version=1,
            event_type="estimate.version_activated",
            company_id=4,
            project_id=0,
            source_type="estimate",
            source_id=52,
            source_revision="sha256:8a8d74a2",
        )

        with self.assertRaisesRegex(AgentChangeContractError, "project_id"):
            build_agent_dispatch_plan(unsafe, brief_date="2026-08-06")

    def test_revalidates_deterministic_plan_before_queue_dispatch(self):
        plan = build_agent_dispatch_plan(
            validate_agent_change_event(valid_event()),
            brief_date="2026-08-06",
        )

        self.assertIs(validate_agent_dispatch_plan(plan), plan)

        for changed in (
            replace(plan, company_id=5),
            replace(plan, source_project_id=18),
            replace(plan, job_type="system.worker_probe"),
            replace(plan, idempotency_key="change:forged"),
            replace(plan, payload=(("briefDate", "2026-08-07"),)),
            replace(plan, priority=10),
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(AgentChangeContractError):
                    validate_agent_dispatch_plan(changed)


if __name__ == "__main__":
    unittest.main()
