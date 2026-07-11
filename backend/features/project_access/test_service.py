import unittest

from fastapi import HTTPException

from backend.features.project_access.service import (
    project_visibility_filter,
    require_child_project_identity,
    require_project_parent_access,
    require_project_row_company,
    require_project_write_actor,
    resolve_project_parent,
)


FULL_VIEW_ROLES = ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик")
WRITE_ROLES = ("директор", "зам_директора", "главный_инженер", "сметчик")


class FakeCursor:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


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

    def test_parent_resolver_prefers_id_and_scopes_it_by_company(self):
        cur = FakeCursor(one={"id": 17, "company_id": 4, "name": "Лицей"})
        parent = resolve_project_parent(
            cur,
            {"companyId": 4},
            project_id=17,
            project_name="Лицей",
            for_update=True,
        )

        self.assertEqual(parent, {"id": 17, "companyId": 4, "name": "Лицей"})
        self.assertIn("id=%s AND company_id=%s", cur.calls[0][0])
        self.assertTrue(cur.calls[0][0].endswith(" FOR UPDATE"))
        self.assertEqual(cur.calls[0][1], (17, 4))

    def test_parent_resolver_rejects_ambiguous_legacy_name(self):
        cur = FakeCursor(many=[
            {"id": 17, "company_id": 4, "name": "Лицей"},
            {"id": 18, "company_id": 4, "name": "Лицей"},
        ])

        with self.assertRaises(HTTPException) as error:
            resolve_project_parent(cur, {"companyId": 4}, project_name="Лицей")
        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("company_id=%s AND name=%s", cur.calls[0][0])
        self.assertEqual(cur.calls[0][1], (4, "Лицей"))

    def test_parent_resolver_does_not_fall_back_to_another_company(self):
        cur = FakeCursor(one=None)
        with self.assertRaises(HTTPException) as error:
            resolve_project_parent(cur, {"companyId": 4}, project_id=99)
        self.assertEqual(error.exception.status_code, 404)

    def test_child_identity_must_match_resolved_parent(self):
        parent = {"id": 17, "companyId": 4, "name": "Лицей"}
        self.assertEqual(
            require_child_project_identity(
                {"companyId": 4, "projectId": 17, "projectName": "Лицей"},
                parent,
                child_label="Смета",
            ),
            parent,
        )
        with self.assertRaises(HTTPException) as error:
            require_child_project_identity(
                {"companyId": 5, "projectId": 17, "projectName": "Лицей"},
                parent,
                child_label="Смета",
            )
        self.assertEqual(error.exception.status_code, 409)

    def test_duplicate_project_name_requires_exact_project_id_for_scoped_role(self):
        duplicate_rows = [
            {"id": 17},
            {"id": 18},
        ]
        project = {"id": 17, "companyId": 4, "name": "Лицей"}

        for actor in (
            {"companyId": 4, "role": "прораб", "assignedProjects": ["Лицей"]},
            {"companyId": 4, "role": "прораб", "assignedProjects": ["Лицей"], "projectId": 17},
            {"companyId": 4, "role": "прораб", "assignedProjects": ["Лицей"], "projectId": 18},
        ):
            with self.subTest(actor=actor), self.assertRaises(HTTPException) as error:
                require_project_parent_access(
                    FakeCursor(many=duplicate_rows),
                    actor,
                    project,
                    FULL_VIEW_ROLES,
                )
            self.assertEqual(error.exception.status_code, 409)

    def test_unique_project_name_keeps_legacy_scoped_access(self):
        project = {"id": 17, "companyId": 4, "name": "Лицей"}
        allowed = require_project_parent_access(
            FakeCursor(many=[{"id": 17}]),
            {"companyId": 4, "role": "прораб", "assignedProjects": ["Лицей"]},
            project,
            FULL_VIEW_ROLES,
        )
        self.assertEqual(allowed, project)

        with self.assertRaises(HTTPException) as error:
            require_project_parent_access(
                FakeCursor(many=[{"id": 18}]),
                {"companyId": 4, "role": "прораб", "assignedProjects": ["Лицей"]},
                project,
                FULL_VIEW_ROLES,
            )
        self.assertEqual(error.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
