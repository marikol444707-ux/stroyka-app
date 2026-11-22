import unittest
from pathlib import Path

from backend.features.ai_control.assignment import find_responsible, normalize_assignment


ROOT = Path(__file__).resolve().parents[3]


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        company_id = self.calls[-1][1][0]
        return [row for row in self.rows if row["company_id"] == company_id]


class AiAssignmentCompanyTests(unittest.TestCase):
    def test_person_name_does_not_select_another_company(self):
        cursor = Cursor([
            {
                "id": 2, "company_id": 3, "name": "Иванов", "role": "мастер",
                "assigned_projects": [],
            },
            {
                "id": 7, "company_id": 7, "name": "Петров", "role": "прораб",
                "assigned_projects": ["Лицей"],
            },
        ])

        role, name = find_responsible(
            cursor, 7, "Лицей", ["прораб"], preferred_name="Иванов", preferred_role="мастер",
        )

        self.assertEqual((role, name), ("прораб", "Петров"))
        self.assertTrue(all(params[0] == 7 for _sql, params in cursor.calls))
        self.assertTrue(all("m.company_id=%s" in sql for sql, _params in cursor.calls))
        self.assertFalse(any("FROM users\n" in sql or "FROM users WHERE" in sql for sql, _params in cursor.calls))

    def test_missing_company_does_not_search_people_by_name(self):
        cursor = Cursor([])

        result = normalize_assignment(
            cursor, "Лицей", assigned_role="мастер", assigned_to="Иванов", company_id=None,
        )

        self.assertEqual(result, {"assignedRole": "мастер", "assignedTo": ""})
        self.assertEqual(cursor.calls, [])

    def test_work_journal_ai_check_is_limited_to_the_owner_company(self):
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        start = source.index("def _run_project_ai_control(")
        end = source.index("\ndef _run_project_ai_control_safely", start)
        body = source[start:end]
        self.assertIn("FROM work_journal", body)
        self.assertIn("SELECT COUNT(*) AS project_count FROM projects", body)
        self.assertIn("WHERE company_id=%s AND project=%s", body)
        self.assertIn("FROM materials WHERE company_id=%s AND project=%s", body)
        self.assertIn("FROM warehouse_history", body)
        self.assertIn("WHERE company_id=%s", body)
        self.assertNotIn("WHERE project=%s AND COALESCE(status,'')", body)
        self.assertNotIn("FROM users", body)

    def test_daily_interim_act_stores_the_verified_company(self):
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        start = source.index("def _sync_daily_interim_act_group(")
        end = source.index("\ndef _sync_daily_interim_act_from_work_journal", start)
        body = source[start:end]
        self.assertIn("company_id = _positive_int_or_none(company_id)", body)
        self.assertIn("(company_id, master_id, master_name, project", body)
        self.assertIn("if not company_id", body)


if __name__ == "__main__":
    unittest.main()
