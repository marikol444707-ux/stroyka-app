import unittest

from backend.features.audit_ownership.runtime import (
    legacy_owner,
    resolve_audit_owner,
)


class FakeCursor:
    def __init__(self, *, projects=(), memberships=(), entity_rows=(), columns=()):
        self.projects = list(projects)
        self.memberships = list(memberships)
        self.entity_rows = list(entity_rows)
        self.columns = list(columns)
        self.rows = []
        self.calls = []

    def execute(self, sql, params=()):
        compact = " ".join(sql.split())
        self.calls.append((compact, tuple(params)))
        if "FROM information_schema.columns" in compact:
            self.rows = [{"column_name": value} for value in self.columns]
        elif "FROM user_company_roles" in compact:
            self.rows = list(self.memberships)
        elif "FROM projects" in compact:
            self.rows = list(self.projects)
        else:
            self.rows = list(self.entity_rows)

    def fetchall(self):
        return list(self.rows)


class AuditRuntimeTests(unittest.TestCase):
    def test_platform_identity_event_never_gets_company_owner(self):
        owner = resolve_audit_owner(
            FakeCursor(),
            action="login",
            entity_type="user",
            entity_id=12,
            user_id=12,
        )

        self.assertEqual(owner, {
            "scope": "platform",
            "companyId": None,
            "projectId": None,
            "reason": "platform_identity_event",
        })

    def test_exact_project_resolves_company_and_project(self):
        cursor = FakeCursor(projects=({"id": 7, "name": "Объект", "company_id": 4},))

        owner = resolve_audit_owner(
            cursor,
            action="update",
            entity_type="ui",
            project_name="Объект",
        )

        self.assertEqual(owner["scope"], "company")
        self.assertEqual(owner["companyId"], 4)
        self.assertEqual(owner["projectId"], 7)

    def test_actor_membership_resolves_company_level_event(self):
        cursor = FakeCursor(memberships=({"user_id": 9, "company_id": 4, "active": True},))

        owner = resolve_audit_owner(
            cursor,
            action="director_agent_ask",
            entity_type="director_agent",
            user_id=9,
        )

        self.assertEqual(owner["scope"], "company")
        self.assertEqual(owner["companyId"], 4)
        self.assertIsNone(owner["projectId"])

    def test_ambiguous_project_is_preserved_as_terminal_legacy(self):
        cursor = FakeCursor(projects=(
            {"id": 7, "name": "Объект", "company_id": 4},
            {"id": 8, "name": "Объект", "company_id": 5},
        ))

        owner = resolve_audit_owner(
            cursor,
            action="update",
            entity_type="ui",
            project_name="Объект",
        )

        self.assertEqual(owner, legacy_owner("project_name_ambiguous"))

    def test_explicit_company_project_must_match_database_parent(self):
        cursor = FakeCursor(projects=({"id": 7, "name": "Объект", "company_id": 5},))

        owner = resolve_audit_owner(
            cursor,
            action="update",
            entity_type="ui",
            owner_scope="company",
            company_id=4,
            project_id=7,
        )

        self.assertEqual(owner, legacy_owner("explicit_project_company_mismatch"))


if __name__ == "__main__":
    unittest.main()
