"""Effective membership scope controls profile visibility and sensitive fields."""

import unittest

from fastapi import HTTPException

from backend.features.company_context.service import effective_company_actors
from backend.features.master_profiles.access import authorized_profile_users, require_profile_user
from backend.features.master_profiles.routes import register_master_profiles_module, SENSITIVE_PROFILE_FIELDS
from backend.features.master_profiles import test_routes as fixtures


COMPANY_USERS = {
    2: [
        {"id": 1, "projects": ["Alpha"], "project": ""},
        {"id": 42, "projects": ["Alpha", "Shared"], "project": ""},
        {"id": 43, "projects": ["Beta"], "project": ""},
        {"id": 44, "projects": [], "project": "Alpha"},
        {"id": 45, "projects": [], "project": ""},
    ],
    3: [{"id": 99, "projects": ["Alpha"], "project": ""}],
}
PROFILES = {row["id"]: {**fixtures.PROFILE, "userId": row["id"]}
            for rows in COMPANY_USERS.values() for row in rows}
BASE_DIRECTOR = {"id": 1, "role": "директор", "company_id": 3,
                 "assigned_projects": ["Beta"], "project_name": "Beta"}


class ScopedCursor(fixtures.FakeCursor):
    """Return fixture rows for bound company/user IDs, without a database."""

    def fetchall(self):
        sql, params = self.calls[-1]
        if "FROM users u" in sql:
            company, legacy_company = params
            if company != legacy_company:
                raise AssertionError("Membership and legacy company scopes must agree")
            return [dict(row) for row in COMPANY_USERS.get(company, [])]
        if "FROM master_profiles" in sql:
            return [dict(PROFILES[user_id]) for user_id in params[0] if user_id in PROFILES]
        raise AssertionError(f"Unexpected query: {sql}")

    def fetchone(self):
        user_id = self.calls[-1][1][0]
        return dict(PROFILES[user_id]) if user_id in PROFILES else None


def build(role, projects=("Alpha",)):
    context = {"mode": "company", "companyId": 2, "effectiveRole": role,
               "assignedProjects": list(projects), "active": True}
    cursor = ScopedCursor()
    connection = fixtures.FakeConnection(cursor)
    deps = {
        "resolve_work_company_context": lambda *args, **kwargs: context,
        "effective_company_actors": effective_company_actors,
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "finance_roles": ("директор", "бухгалтер"),
    }
    app = fixtures.FakeApp()
    register_master_profiles_module(app, deps)
    return app, cursor, deps


class MasterProfileAccessTests(unittest.TestCase):
    def authorize(self, role, *, projects=("Alpha",), write=False):
        _app, cursor, deps = build(role, projects)
        return authorized_profile_users(
            cursor, BASE_DIRECTOR, deps, manager_roles=("директор", "бухгалтер"),
            project_roles=() if write else ("прораб", "главный_инженер"),
            company_id="2", company_mode="company", write=write,
        )

    def test_effective_foreman_cannot_inherit_base_director_sensitive_fields(self):
        app, _cursor, _deps = build("прораб")
        rows = app.routes[("GET", "/master-profiles")](
            current_user=BASE_DIRECTOR, x_company_id="2", x_company_mode="company",
        )
        self.assertEqual({row["userId"] for row in rows}, {1, 42, 44})
        self.assertEqual(next(row for row in rows if row["userId"] == 1)["passport"], "1234")
        for row in rows:
            if row["userId"] != 1:
                self.assertTrue(set(SENSITIVE_PROFILE_FIELDS).isdisjoint(row))
        detail = app.routes[("GET", "/master-profile/{user_id}")](
            user_id=42, current_user=BASE_DIRECTOR, x_company_id="2", x_company_mode="company",
        )
        self.assertEqual(detail["fullName"], fixtures.PROFILE["fullName"])
        self.assertTrue(set(SENSITIVE_PROFILE_FIELDS).isdisjoint(detail))

    def test_worker_can_access_only_own_profile_with_sensitive_fields(self):
        allowed = self.authorize("мастер")
        self.assertEqual(allowed, {1: True})
        require_profile_user(allowed, "1")
        with self.assertRaises(HTTPException) as error:
            require_profile_user(allowed, 42)
        self.assertEqual(error.exception.status_code, 403)

    def test_effective_finance_role_sees_company_profiles_and_sensitive_fields(self):
        for role in ("директор", "бухгалтер"):
            with self.subTest(role=role):
                self.assertEqual(self.authorize(role), {1: True, 42: True, 43: True, 44: True, 45: True})
                app, _cursor, _deps = build(role)
                rows = app.routes[("GET", "/master-profiles")](
                    current_user=BASE_DIRECTOR, x_company_id="2", x_company_mode="company",
                )
                self.assertEqual({row["userId"] for row in rows}, {1, 42, 43, 44, 45})
                for row in rows:
                    self.assertEqual(row["passport"], "1234")
                    self.assertEqual(row["bankAccount"], "408")

    def test_project_scope_intersects_membership_projects_and_legacy_project(self):
        self.assertEqual(self.authorize("прораб"), {1: True, 42: False, 44: False})
        self.assertEqual(self.authorize("главный_инженер", projects=("Shared",)), {1: True, 42: False})

    def test_no_membership_projects_does_not_fall_back_to_base_user_projects(self):
        self.assertEqual(self.authorize("прораб", projects=()), {1: True})

    def test_foreign_user_with_same_project_name_is_forbidden(self):
        for role in ("прораб", "директор", "бухгалтер", "мастер"):
            with self.subTest(role=role):
                allowed = self.authorize(role)
                self.assertNotIn(99, allowed)
                with self.assertRaises(HTTPException) as error:
                    require_profile_user(allowed, 99)
                self.assertEqual(error.exception.status_code, 403)

    def test_effective_foreman_cannot_write_peer_using_base_director_role(self):
        allowed = self.authorize("прораб", write=True)
        self.assertEqual(allowed, {1: True})
        with self.assertRaises(HTTPException) as error:
            require_profile_user(allowed, 42)
        self.assertEqual(error.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
