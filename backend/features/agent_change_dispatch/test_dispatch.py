import unittest

from backend.features.agent_change_dispatch.contract import (
    build_agent_dispatch_plan,
    validate_agent_change_event,
)
from backend.features.agent_change_dispatch.dispatch import (
    AgentChangeDispatchError,
    dispatch_agent_change_plan,
)


def valid_plan():
    event = validate_agent_change_event({
        "schemaVersion": 1,
        "eventType": "estimate.version_activated",
        "companyId": 4,
        "projectId": 17,
        "sourceType": "estimate",
        "sourceId": 52,
        "sourceRevision": "sha256:8a8d74a2",
    })
    return build_agent_dispatch_plan(event, brief_date="2026-08-06")


class AgentChangeDispatchTests(unittest.TestCase):
    def test_dry_run_is_default_and_never_calls_enqueue(self):
        calls = []

        result = dispatch_agent_change_plan(
            object(),
            plan=valid_plan(),
            enqueue_job=lambda *_args, **kwargs: calls.append(kwargs),
        )

        self.assertEqual(calls, [])
        self.assertEqual(result, {
            "ok": True,
            "dryRun": True,
            "state": "would_enqueue",
            "enqueueAttempted": False,
            "writesAttempted": 0,
            "companyId": 4,
            "projectId": 17,
            "jobType": "director.daily_brief",
            "briefDate": "2026-08-06",
        })

    def test_apply_enqueues_exactly_one_validated_plan(self):
        calls = []

        def enqueue_job(cursor, **kwargs):
            calls.append((cursor, kwargs))
            return {
                "created": True,
                "job": {
                    "id": 81,
                    "status": "queued",
                    "company_id": 4,
                    "project_id": None,
                    "job_type": "director.daily_brief",
                    "idempotency_key": kwargs["idempotency_key"],
                },
            }

        cursor = object()
        plan = valid_plan()
        result = dispatch_agent_change_plan(
            cursor,
            plan=plan,
            apply=True,
            enqueue_job=enqueue_job,
        )

        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][0], cursor)
        self.assertEqual(calls[0][1], {
            "company_id": 4,
            "project_id": None,
            "job_type": "director.daily_brief",
            "idempotency_key": plan.idempotency_key,
            "requested_by_role": "system",
            "payload": {"briefDate": "2026-08-06"},
            "correlation_id": plan.correlation_id,
            "priority": 4,
            "max_attempts": 3,
        })
        self.assertEqual(result, {
            "ok": True,
            "dryRun": False,
            "state": "enqueued",
            "enqueueAttempted": True,
            "writesAttempted": 1,
            "companyId": 4,
            "projectId": 17,
            "jobType": "director.daily_brief",
            "briefDate": "2026-08-06",
            "jobId": 81,
            "status": "queued",
        })

    def test_idempotent_existing_job_is_reported_without_a_second_call(self):
        calls = []
        plan = valid_plan()

        def enqueue_job(_cursor, **kwargs):
            calls.append(kwargs)
            return {
                "created": False,
                "job": {
                    "id": 81,
                    "status": "succeeded",
                    "company_id": 4,
                    "project_id": None,
                    "job_type": "director.daily_brief",
                    "idempotency_key": plan.idempotency_key,
                },
            }

        result = dispatch_agent_change_plan(
            object(),
            plan=plan,
            apply=True,
            enqueue_job=enqueue_job,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["state"], "existing")
        self.assertEqual(result["jobId"], 81)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["writesAttempted"], 1)

    def test_rejects_invalid_apply_or_enqueue_dependency_before_dispatch(self):
        for apply in (None, 1, "true"):
            with self.subTest(apply=apply):
                with self.assertRaises(AgentChangeDispatchError):
                    dispatch_agent_change_plan(object(), plan=valid_plan(), apply=apply)

        with self.assertRaises(AgentChangeDispatchError):
            dispatch_agent_change_plan(
                object(),
                plan=valid_plan(),
                apply=True,
                enqueue_job=object(),
            )

    def test_rejects_untrusted_or_mismatched_enqueue_result(self):
        plan = valid_plan()
        invalid_results = (
            None,
            {"created": "yes", "job": {}},
            {"created": True, "job": {"id": 0, "status": "queued"}},
            {
                "created": True,
                "job": {
                    "id": 81,
                    "status": "queued",
                    "company_id": 5,
                    "project_id": None,
                    "job_type": "director.daily_brief",
                    "idempotency_key": plan.idempotency_key,
                },
            },
        )

        for outcome in invalid_results:
            with self.subTest(outcome=outcome):
                with self.assertRaises(AgentChangeDispatchError):
                    dispatch_agent_change_plan(
                        object(),
                        plan=plan,
                        apply=True,
                        enqueue_job=lambda *_args, _outcome=outcome, **_kwargs: _outcome,
                    )


if __name__ == "__main__":
    unittest.main()
