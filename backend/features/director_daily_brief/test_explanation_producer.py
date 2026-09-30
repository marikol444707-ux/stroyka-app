import unittest

from backend.features.director_daily_brief.explanation_producer import (
    prepare_daily_brief_explanation_job,
)
from backend.features.director_daily_brief.test_query_service import valid_result


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchone(self):
        return self.rows.pop(0)


class DirectorDailyBriefExplanationProducerTests(unittest.TestCase):
    def test_default_off_never_enqueues(self):
        cur = Cursor([{"id": 17, "result_json": valid_result()}, None])
        writes = []

        result = prepare_daily_brief_explanation_job(
            cur,
            company_id=4,
            source_job_id=17,
            apply=True,
            enqueue_job=lambda *args, **kwargs: writes.append(kwargs),
        )

        self.assertEqual(result["state"], "disabled")
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(writes, [])

    def test_enabled_dry_run_reports_exact_source_without_writing(self):
        cur = Cursor([{"id": 17, "result_json": valid_result()}, None])

        result = prepare_daily_brief_explanation_job(
            cur, company_id=4, source_job_id=17, enabled=True
        )

        self.assertEqual(result["state"], "would_enqueue")
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["sourceJobId"], 17)

    def test_enabled_apply_enqueues_one_idempotent_company_job(self):
        cur = Cursor([{"id": 17, "result_json": valid_result()}, None])
        captured = {}

        def enqueue(cur_arg, **kwargs):
            captured.update(kwargs)
            return {"created": True, "job": {"id": 19, "status": "queued"}}

        result = prepare_daily_brief_explanation_job(
            cur,
            company_id=4,
            source_job_id=17,
            enabled=True,
            apply=True,
            enqueue_job=enqueue,
        )

        self.assertEqual(result["state"], "enqueued")
        self.assertEqual(result["writesAttempted"], 1)
        self.assertEqual(captured["company_id"], 4)
        self.assertEqual(captured["job_type"], "director.daily_brief.explanation")
        self.assertEqual(captured["idempotency_key"], "daily-explanation:17")
        self.assertEqual(captured["payload"], {"sourceJobId": 17})


if __name__ == "__main__":
    unittest.main()
