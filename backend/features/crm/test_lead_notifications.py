import json
import unittest
import urllib.error
from io import BytesIO

from backend.features.crm.lead_notifications import (
    dispatch_telegram_lead_outbox,
    enqueue_lead_owner_notification,
    send_telegram_lead_message,
)


class FakeCursor:
    def __init__(self, rows=None, fail_sql=""):
        self.rows = list(rows or [])
        self.fail_sql = fail_sql
        self.calls = []

    def execute(self, sql, params=None):
        compact = " ".join(str(sql).split())
        if self.fail_sql and self.fail_sql in compact:
            raise RuntimeError("database rejected notification")
        self.calls.append((compact, params))

    def fetchall(self):
        return list(self.rows)


class LeadNotificationTests(unittest.TestCase):
    def test_disabled_when_chat_env_is_unset(self):
        cursor = FakeCursor()
        queued = enqueue_lead_owner_notification(
            cursor,
            company_id=4,
            lead_id=15,
            name="Иван",
            phone="+79990000000",
            environ={},
        )
        self.assertFalse(queued)
        self.assertEqual(cursor.calls, [])

    def test_enqueues_telegram_and_max_for_the_lead_company(self):
        cursor = FakeCursor()
        queued = enqueue_lead_owner_notification(
            cursor,
            company_id=4,
            lead_id=15,
            name="Иван",
            phone="+79990000000",
            work_type="Дом",
            address="Ставрополь",
            source="Сайт / Нетипичный Ставрополь",
            environ={
                "LEAD_NOTIFY_TELEGRAM_CHAT_ID": "1001",
                "LEAD_NOTIFY_MAX_CHAT_ID": "2002",
                "APP_PUBLIC_URL": "https://stroyka26.pro",
            },
        )
        self.assertTrue(queued)
        inserts = [params for sql, params in cursor.calls if sql.startswith("INSERT INTO messenger_outbox")]
        self.assertEqual([params[1] for params in inserts], ["telegram", "max"])
        for params in inserts:
            self.assertEqual(params[0], 4)
            self.assertEqual(params[4], 15)
            self.assertEqual(params[5], "Новая заявка")
            body = params[6]
            self.assertIn("Имя: Иван", body)
            self.assertIn("Телефон: +79990000000", body)
            self.assertIn("Что нужно: Дом", body)
            self.assertIn("Адрес: Ставрополь", body)
            self.assertIn("Источник: Сайт / Нетипичный Ставрополь", body)
            self.assertIn("https://stroyka26.pro/app?page=crm&lead=15", body)
            self.assertEqual(json.loads(params[7])["companyId"], 4)

    def test_skips_another_company_when_owner_company_is_configured(self):
        cursor = FakeCursor()
        queued = enqueue_lead_owner_notification(
            cursor,
            company_id=8,
            lead_id=15,
            environ={"LEAD_NOTIFY_TELEGRAM_CHAT_ID": "1001", "LEAD_NOTIFY_COMPANY_ID": "4"},
        )
        self.assertFalse(queued)
        self.assertEqual(cursor.calls, [])

    def test_enqueue_failure_does_not_raise(self):
        cursor = FakeCursor(fail_sql="INSERT INTO messenger_outbox")
        queued = enqueue_lead_owner_notification(
            cursor,
            company_id=4,
            lead_id=15,
            environ={"LEAD_NOTIFY_MAX_CHAT_ID": "2002"},
        )
        self.assertFalse(queued)
        self.assertTrue(any(sql.startswith("ROLLBACK TO SAVEPOINT crm_lead_notify") for sql, _params in cursor.calls))

    def test_telegram_dispatch_marks_sent_and_keeps_company(self):
        cursor = FakeCursor(rows=[{
            "id": 9,
            "company_id": 4,
            "chat_id": "1001",
            "title": "Новая заявка",
            "body": "Имя: Иван",
            "attempts": 0,
        }])
        sent_to = []
        outcome = dispatch_telegram_lead_outbox(
            cursor,
            send_message=lambda chat_id, text: sent_to.append((chat_id, text)) or "41",
        )
        self.assertEqual(outcome["sent"], [{"id": 9, "provider": "telegram", "companyId": 4}])
        self.assertEqual(sent_to[0][0], "1001")
        self.assertIn("Новая заявка", sent_to[0][1])
        update = next(params for sql, params in cursor.calls if sql.startswith("UPDATE messenger_outbox"))
        self.assertEqual(update[0], "41")
        self.assertEqual(update[2], 4)

    def test_telegram_dispatch_failure_stays_queued_for_retry(self):
        cursor = FakeCursor(rows=[{
            "id": 9,
            "company_id": 4,
            "chat_id": "1001",
            "title": "Новая заявка",
            "body": "Имя: Иван",
            "attempts": 1,
        }])

        def fail(chat_id, text):
            raise RuntimeError("telegram_delivery_failed")

        outcome = dispatch_telegram_lead_outbox(cursor, send_message=fail)
        self.assertEqual(outcome["failed"], [{"id": 9, "error": "telegram_delivery_failed"}])
        update = next(sql for sql, _params in cursor.calls if sql.startswith("UPDATE messenger_outbox"))
        self.assertIn("telegram_delivery_failed", update)
        self.assertIn("ELSE 'queued'", update)

    def test_missing_telegram_token_does_not_include_secret_text(self):
        def opener(request, timeout):
            self.assertNotIn("secret-token", str(timeout))
            raise urllib.error.HTTPError(request.full_url, 401, "unauthorized", hdrs=None, fp=BytesIO(b"{}"))

        with self.assertRaises(RuntimeError) as raised:
            send_telegram_lead_message("1001", "Новая заявка", token="secret-token", opener=opener)
        self.assertEqual(str(raised.exception), "telegram_delivery_failed")
        self.assertNotIn("secret-token", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
