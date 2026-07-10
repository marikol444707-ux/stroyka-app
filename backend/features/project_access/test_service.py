import unittest

from fastapi import HTTPException

from backend.features.project_access.service import (
    project_visibility_filter,
    require_project_row_company,
    require_project_write_actor,
)


FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
WRITE_ROLES = ("директор", "зам_директора", "главный_инженер", "сметчик")


class ProjectAccessTests(unittest.TestCase):
    def test_list_scope_keeps_membership_role_and_projects_per_company(self):
        sql, params = project_visibility_filter(
            [
                {"companyId": 1, "role": "директор"},
                {"companyId": 2, "role": "прораб", "assignedProjects": ["Объект Б"]},
                {"companyId": 3, "role": "мастер", "assignedProjects": []},
            ],
            FULL_VIEW_ROLES,
        )

        self.assertIn("p.company_id=%s", sql)
        self.assertIn("p.name = ANY(%s)", sql)
        self.assertEqual(params, [1, 2, ["Объект Б"]])
        self.assertEqual(sql.count("%s"), len(params))

    def test_list_scope_fails_closed_without_valid_membership(self):
        self.assertEqual(project_visibility_filter([], FULL_VIEW_ROLES), ("FALSE", []))
        self.assertEqual(
            project_visibility_filter(
                [{"companyId": 3, "role": "мастер", "assignedProjects": []}],
                FULL_VIEW_ROLES,
            ),
            ("FALSE", []),
        )

    def test_project_write_requires_one_selected_company(self):
        with self.assertRaises(HTTPException) as error:
            require_project_write_actor(
                [
                    {"companyId": 1, "role": "директор"},
                    {"companyId": 2, "role": "директор"},
                ],
                WRITE_ROLES,
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_project_write_uses_effective_membership_role(self):
        with self.assertRaises(HTTPException) as error:
            require_project_write_actor(
                [{"companyId": 2, "role": "бухгалтер"}],
                WRITE_ROLES,
            )
        self.assertEqual(error.exception.status_code, 403)

        actor = require_project_write_actor(
            [{"companyId": 2, "role": "главный_инженер"}],
            WRITE_ROLES,
        )
        self.assertEqual(actor["companyId"], 2)

    def test_direct_id_write_checks_stored_project_company(self):
        self.assertEqual(require_project_row_company({"companyId": 4}, 4), 4)
        with self.assertRaises(HTTPException) as error:
            require_project_row_company({"companyId": 4}, 5)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
