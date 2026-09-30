import unittest

from backend.features.director_daily_brief.explanation_max_delivery import (
    prepare_daily_brief_explanation_max_delivery,
)
from backend.features.director_daily_brief.test_query_service import valid_result


def explanation():
    return {
        "schemaVersion": 1,
        "sourceJobId": 17,
        "headline": "Есть вопросы, требующие внимания",
        "overview": "Проверьте сроки объекта.",
        "points": [{
            "sourceCode": "project.deadline_overdue",
            "text": "Срок объекта требует проверки.",
        }],
    }


class Cursor:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.current = None
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self.current = self.responses.pop(0) if self.responses else None

    def fetchone(self):
        return self.current

    def fetchall(self):
        return list(self.current or [])


class DirectorDailyBriefExplanationMaxDeliveryTests(unittest.TestCase):
    def test_disabled_mode_attempts_no_reads_or_writes(self):
        cur = Cursor()
        result = prepare_daily_brief_explanation_max_delivery(
            cur, company_id=4, explanation_job_id=19, recipient_user_id=7
        )
        self.assertEqual(result["state"], "disabled")
        self.assertEqual(result["writesAttempted"], 0)
        self.assertEqual(cur.calls, [])

    def test_enabled_dry_run_validates_exact_explanation_and_recipient(self):
        cur = Cursor([
            {"id": 19, "payload_json": {"sourceJobId": 17}, "result_json": explanation()},
            {"id": 17, "result_json": valid_result()},
            [{"id": 3, "user_id": 7, "external_user_id": "max-7", "chat_id": "chat-7"}],
            None,
        ])
        result = prepare_daily_brief_explanation_max_delivery(
            cur,
            company_id=4,
            explanation_job_id=19,
            recipient_user_id=7,
            enabled=True,
        )
        self.assertEqual(result["state"], "would_enqueue")
        self.assertTrue(result["dryRun"])
        self.assertEqual(result["recipientUserId"], 7)
        self.assertEqual(result["writesAttempted"], 0)
        account_sql, account_params = cur.calls[2]
        self.assertIn("EXISTS", account_sql)
        self.assertEqual(account_params, (7, 4))

    def test_apply_inserts_actionless_idempotent_company_message(self):
        cur = Cursor([
            {"id": 19, "payload_json": {"sourceJobId": 17}, "result_json": explanation()},
            {"id": 17, "result_json": valid_result()},
            [{"id": 3, "user_id": 7, "external_user_id": "max-7", "chat_id": "chat-7"}],
            None,
            None,
            {"id": 41},
        ])
        result = prepare_daily_brief_explanation_max_delivery(
            cur,
            company_id=4,
            explanation_job_id=19,
            recipient_user_id=7,
            enabled=True,
            apply=True,
        )
        self.assertEqual(result["state"], "enqueued")
        self.assertEqual(result["outboxId"], 41)
        self.assertEqual(result["writesAttempted"], 1)
        insert_sql, insert_params = cur.calls[-1]
        self.assertIn("INSERT INTO messenger_outbox", insert_sql)
        self.assertEqual(insert_params[-2], "[]")
        self.assertNotIn("оплат", insert_params[-4].lower())

    def test_malformed_payload_fails_before_source_query_or_write(self):
        cur = Cursor([{"id": 19, "payload_json": {"sourceJobId": "17"}, "result_json": explanation()}])
        with self.assertRaisesRegex(ValueError, "source_job_id"):
            prepare_daily_brief_explanation_max_delivery(
                cur,
                company_id=4,
                explanation_job_id=19,
                recipient_user_id=7,
                enabled=True,
                apply=True,
            )
        self.assertEqual(len(cur.calls), 1)
        self.assertNotIn("::int", cur.calls[0][0])

    def test_recipient_with_multiple_max_accounts_fails_closed(self):
        cur = Cursor([
            {"id": 19, "payload_json": {"sourceJobId": 17}, "result_json": explanation()},
            {"id": 17, "result_json": valid_result()},
            [
                {"id": 3, "user_id": 7, "external_user_id": "max-7", "chat_id": "chat-7"},
                {"id": 4, "user_id": 7, "external_user_id": "max-8", "chat_id": "chat-8"},
            ],
        ])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            prepare_daily_brief_explanation_max_delivery(
                cur,
                company_id=4,
                explanation_job_id=19,
                recipient_user_id=7,
                enabled=True,
                apply=True,
            )
        self.assertFalse(any("INSERT INTO" in sql for sql, _ in cur.calls))


if __name__ == "__main__":
    unittest.main()
