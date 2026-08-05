import json
import unittest

from backend.features.director_daily_brief.service import (
    DirectorDailyBriefError,
    build_director_daily_brief,
)


def valid_facts():
    return {
        "projects": [
            {
                "name": "School",
                "status": "В работе",
                "budget": 1000,
                "progress": 50,
                "deadline": "2026-08-03",
            },
            {
                "name": "Finished",
                "status": "Завершен",
                "budget": 500,
                "progress": 100,
                "deadline": "2026-08-01",
            },
        ],
        "warehouse": {
            "mainWarehouse": [
                {
                    "name": "Paint",
                    "qty": 2,
                    "unit": "kg",
                    "minQty": 5,
                    "category": "Finishing",
                }
            ],
            "objectMaterials": [],
        },
        "supply": {
            "requestStatusCounts": {"Новая": 2, "Поставлено": 1},
            "recentRequests": [],
            "recentDeliveries": [],
            "openClaims": [
                {
                    "project": "School",
                    "material": "Cable",
                    "type": "shortage",
                    "status": "Открыта",
                    "shortage": 4,
                }
            ],
        },
        "estimates": [
            {
                "name": "Estimate v2",
                "project": "School",
                "version": "v2",
                "status": "Черновик",
                "type": "Заказчик",
                "package": "Main",
                "items": 11,
                "workItems": 6,
                "materialItems": 5,
                "total": 1200,
            },
            {
                "name": "Estimate v1",
                "project": "School",
                "version": "v1",
                "status": "Активная",
                "type": "Заказчик",
                "package": "Main",
                "items": 10,
                "workItems": 6,
                "materialItems": 4,
                "total": 1000,
            },
        ],
        "finances": [
            {
                "project": "School",
                "status": "В работе",
                "budget": 1000,
                "paymentsNet": 1200,
                "manualExpenses": None,
                "manualExpensesScoped": False,
            }
        ],
        "staff": {
            "roleCounts": [{"role": "мастер", "count": 1}],
            "staff": [
                {
                    "name": "Worker",
                    "role": "мастер",
                    "project": "School",
                    "specialization": "Electrical",
                }
            ],
        },
        "ai_tasks": {
            "openStatusCounts": {"Новая": 2},
            "tasks": [
                {
                    "project": "School",
                    "title": "Inspect cable",
                    "assignedRole": "мастер",
                    "assignedTo": "",
                    "status": "Новая",
                    "dueDate": "2026-08-04",
                },
                {
                    "project": "School",
                    "title": "Prepare report",
                    "assignedRole": "прораб",
                    "assignedTo": "Foreman",
                    "status": "В работе",
                    "dueDate": "2026-08-10",
                },
            ],
        },
    }


class DirectorDailyBriefServiceTests(unittest.TestCase):
    def test_builds_six_ordered_sections_from_sanitized_read_facts(self):
        brief = build_director_daily_brief(
            brief_date="2026-08-05",
            tool_results=valid_facts(),
        )

        self.assertEqual(brief["schemaVersion"], 1)
        self.assertEqual(brief["briefDate"], "2026-08-05")
        self.assertEqual(brief["mode"], "deterministic_read_only")
        self.assertEqual(
            [section["key"] for section in brief["sections"]],
            ["overdue", "shortages", "documents", "estimateDeviations", "payments", "tasks"],
        )
        items_by_section = {
            section["key"]: section["items"]
            for section in brief["sections"]
        }
        self.assertEqual(
            {item["code"] for item in items_by_section["overdue"]},
            {"project.deadline_overdue", "task.deadline_overdue"},
        )
        self.assertEqual(
            {item["code"] for item in items_by_section["shortages"]},
            {"warehouse.below_minimum", "supply.open_shortage_claim"},
        )
        self.assertEqual(
            {item["code"] for item in items_by_section["documents"]},
            {"estimate.unconfirmed", "supply.requests_pending"},
        )
        self.assertEqual(
            items_by_section["estimateDeviations"][0]["metricValue"],
            200.0,
        )
        self.assertEqual(
            items_by_section["estimateDeviations"][0]["code"],
            "estimate.total_difference_candidate",
        )
        self.assertEqual(
            items_by_section["estimateDeviations"][0]["severity"],
            "info",
        )
        self.assertEqual(
            {item["code"] for item in items_by_section["payments"]},
            {"finance.overview", "finance.project_fact"},
        )
        self.assertTrue(all(
            item["severity"] == "info"
            for item in items_by_section["payments"]
        ))
        self.assertEqual(
            {item["code"] for item in items_by_section["tasks"]},
            {"task.open_status", "task.unassigned"},
        )
        self.assertEqual(brief["sourceCounts"]["projects"], 2)
        self.assertEqual(brief["sourceCounts"]["staff"], 1)

    def test_is_deterministic_and_does_not_expose_internal_company_fields(self):
        facts = valid_facts()
        facts["finances"][0]["companyId"] = 99
        facts["projects"][0]["rawDatabaseRows"] = [{"password": "secret"}]

        first = build_director_daily_brief(
            brief_date="2026-08-05",
            tool_results=facts,
        )
        second = build_director_daily_brief(
            brief_date="2026-08-05",
            tool_results=facts,
        )

        first_json = json.dumps(first, ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)
        self.assertNotIn("companyId", first_json)
        self.assertNotIn("rawDatabaseRows", first_json)
        self.assertNotIn("secret", first_json)

    def test_fails_closed_for_invalid_date_or_incomplete_tool_set(self):
        for brief_date in (None, "05.08.2026", "2026-02-30"):
            with self.subTest(brief_date=brief_date):
                with self.assertRaises(DirectorDailyBriefError):
                    build_director_daily_brief(
                        brief_date=brief_date,
                        tool_results=valid_facts(),
                    )

        incomplete = valid_facts()
        incomplete.pop("finances")
        with self.assertRaises(DirectorDailyBriefError):
            build_director_daily_brief(
                brief_date="2026-08-05",
                tool_results=incomplete,
            )

        extra = valid_facts()
        extra["sql"] = [{"statement": "SELECT * FROM users"}]
        with self.assertRaises(DirectorDailyBriefError):
            build_director_daily_brief(
                brief_date="2026-08-05",
                tool_results=extra,
            )

    def test_caps_each_section_and_keeps_the_result_small(self):
        facts = valid_facts()
        facts["warehouse"]["mainWarehouse"] = [
            {
                "name": f"Material {index:02d}",
                "qty": 0,
                "unit": "pcs",
                "minQty": 100,
                "category": "",
            }
            for index in range(40)
        ]

        brief = build_director_daily_brief(
            brief_date="2026-08-05",
            tool_results=facts,
        )
        shortages = next(
            section for section in brief["sections"] if section["key"] == "shortages"
        )

        self.assertLessEqual(len(shortages["items"]), 20)
        self.assertTrue(shortages["truncated"])
        self.assertLess(len(json.dumps(brief, ensure_ascii=False).encode("utf-8")), 64 * 1024)

    def test_maximum_sanitized_inputs_still_fit_the_job_result_limit(self):
        facts = valid_facts()
        facts["projects"] = [
            {
                "name": f"{index:02d}" + "P" * 298,
                "status": "В работе",
                "budget": 1,
                "progress": 1,
                "deadline": "2026-08-01",
            }
            for index in range(40)
        ]
        facts["warehouse"]["mainWarehouse"] = [
            {
                "name": f"{index:02d}" + "M" * 298,
                "qty": 0,
                "unit": "unit" * 10,
                "minQty": 100,
                "category": "C" * 120,
            }
            for index in range(40)
        ]
        facts["supply"]["requestStatusCounts"] = {
            f"{index:02d}" + "S" * 98: 1
            for index in range(40)
        }
        facts["supply"]["openClaims"] = [
            {
                "project": "P" * 300,
                "material": f"{index:02d}" + "C" * 298,
                "type": "shortage",
                "status": "Открыта",
                "shortage": 1,
            }
            for index in range(20)
        ]
        facts["estimates"] = [
            {
                "name": f"{index:02d}" + "E" * 298,
                "project": f"Project {index // 2}",
                "version": f"v{index}",
                "status": "Черновик",
                "type": "Заказчик",
                "package": "Package",
                "items": 1,
                "workItems": 1,
                "materialItems": 0,
                "total": 1000 + index,
            }
            for index in range(30)
        ]
        facts["finances"] = [
            {
                "project": f"{index:02d}" + "F" * 298,
                "status": "В работе",
                "budget": 1000,
                "paymentsNet": 500,
                "manualExpenses": None,
                "manualExpensesScoped": False,
            }
            for index in range(40)
        ]
        facts["ai_tasks"] = {
            "openStatusCounts": {
                f"{index:02d}" + "T" * 98: 1
                for index in range(40)
            },
            "tasks": [
                {
                    "project": "P" * 300,
                    "title": f"{index:02d}" + "T" * 498,
                    "assignedRole": "R" * 100,
                    "assignedTo": "",
                    "status": "Новая",
                    "dueDate": "2026-08-01",
                }
                for index in range(30)
            ],
        }

        brief = build_director_daily_brief(
            brief_date="2026-08-05",
            tool_results=facts,
        )

        self.assertLess(len(json.dumps(brief, ensure_ascii=False).encode("utf-8")), 64 * 1024)


if __name__ == "__main__":
    unittest.main()
