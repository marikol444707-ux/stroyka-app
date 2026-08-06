import unittest

from backend.features.director_daily_brief.attention_queue import (
    MAX_ATTENTION_QUEUE_ITEMS,
    AttentionQueueError,
    build_attention_queue,
)


def brief_with_items(items, *, truncated=False):
    severity_counts = {
        "critical": sum(item.get("severity") == "critical" for item in items),
        "warning": sum(item.get("severity") == "warning" for item in items),
    }
    return {
        "summary": severity_counts,
        "sections": [
            {
                "key": "overdue",
                "title": "Просрочки",
                "status": "attention",
                "count": len(items) + (1 if truncated else 0),
                "truncated": truncated,
                "items": items,
            }
        ]
    }


class DirectorAttentionQueueTests(unittest.TestCase):
    def test_builds_priority_ordered_read_only_items_with_fixed_actions(self):
        result = build_attention_queue(brief_with_items([
            {
                "code": "warehouse.below_minimum",
                "severity": "warning",
                "subject": "Кабель ВВГ",
            },
            {
                "code": "project.deadline_overdue",
                "severity": "critical",
                "subject": "Лицей 4",
                "project": "Лицей 4",
            },
            {
                "code": "finance.project_fact",
                "severity": "info",
                "subject": "Лицей 4",
            },
        ]))

        self.assertEqual(result["readOnly"], True)
        self.assertEqual(result["count"], 2)
        self.assertFalse(result["truncated"])
        self.assertEqual(
            [item["priority"] for item in result["items"]],
            ["critical", "warning"],
        )
        self.assertEqual(result["items"][0], {
            "id": "overdue:project.deadline_overdue:1",
            "priority": "critical",
            "category": "Просрочки",
            "reason": "Просрочен срок объекта",
            "subject": "Лицей 4",
            "project": "Лицей 4",
            "owner": "Не указан",
            "nextAction": "Проверить срок и ответственного по объекту",
            "destination": "projects",
            "sourceCode": "project.deadline_overdue",
        })
        self.assertEqual(
            result["items"][1]["nextAction"],
            "Проверить остаток и потребность склада",
        )
        self.assertEqual(result["items"][1]["project"], "Вся компания")

    def test_unassigned_task_has_explicit_owner_state(self):
        result = build_attention_queue(brief_with_items([{
            "code": "task.unassigned",
            "severity": "warning",
            "subject": "Проверить акт",
            "project": "Школа",
        }]))

        self.assertEqual(result["items"][0]["owner"], "Не назначен")
        self.assertEqual(result["items"][0]["destination"], "assignments")

    def test_blank_optional_project_uses_company_fallback(self):
        result = build_attention_queue(brief_with_items([{
            "code": "warehouse.below_minimum",
            "severity": "warning",
            "subject": "Кабель",
            "project": "",
        }]))

        self.assertEqual(result["items"][0]["project"], "Вся компания")

    def test_unknown_code_gets_review_only_fallback_without_command_data(self):
        result = build_attention_queue(brief_with_items([{
            "code": "future.unknown_check",
            "severity": "critical",
            "subject": "Проверить источник",
            "nextAction": "DELETE FROM projects",
            "destination": "https://evil.example",
        }]))

        self.assertEqual(result["items"][0]["reason"], "Требуется проверка")
        self.assertEqual(
            result["items"][0]["nextAction"],
            "Проверить исходный пункт ежедневной сводки",
        )
        self.assertEqual(result["items"][0]["destination"], "dailyBrief")
        self.assertNotIn("DELETE", str(result))
        self.assertNotIn("evil.example", str(result))

    def test_caps_queue_and_preserves_truncation_signal(self):
        items = [
            {
                "code": "estimate.unconfirmed",
                "severity": "warning",
                "subject": f"Смета {index}",
            }
            for index in range(MAX_ATTENTION_QUEUE_ITEMS + 3)
        ]

        result = build_attention_queue(brief_with_items(items, truncated=True))

        self.assertEqual(result["count"], MAX_ATTENTION_QUEUE_ITEMS + 3)
        self.assertEqual(len(result["items"]), MAX_ATTENTION_QUEUE_ITEMS)
        self.assertTrue(result["truncated"])

    def test_rejects_malformed_section_instead_of_guessing(self):
        with self.assertRaises(AttentionQueueError):
            build_attention_queue({
                "summary": {"critical": 0, "warning": 0},
                "sections": [{"items": "not-a-list"}],
            })

    def test_rejects_summary_that_hides_visible_attention_items(self):
        brief = brief_with_items([{
            "code": "project.deadline_overdue",
            "severity": "critical",
            "subject": "Лицей 4",
        }])
        brief["summary"]["critical"] = 0

        with self.assertRaises(AttentionQueueError):
            build_attention_queue(brief)


if __name__ == "__main__":
    unittest.main()
