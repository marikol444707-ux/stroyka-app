import unittest

from fastapi import HTTPException

from backend.features.work_journal.service import (
    require_work_journal_parent_owner,
    resolve_work_journal_create_scope,
)


class WorkJournalCreateScopeTests(unittest.TestCase):
    def test_selected_company_returns_server_actor_and_project_owner(self):
        calls = []
        deps = {
            "resolve_work_company_context": lambda _cur, _user, _requested, mode, **kwargs: calls.append((mode, kwargs)) or {"companyId": 4},
            "effective_company_actors": lambda _user, _context: [{"companyId": 4, "role": "прораб", "name": "Петров"}],
            "require_project_write_actor": lambda actors, _roles: actors[0],
            "resolve_project_parent": lambda _cur, _actor, **_kwargs: {"id": 14, "companyId": 4, "name": "Лицей"},
            "require_project_parent_access": lambda _cur, _actor, project, _roles: project,
            "journal_write_roles": ("прораб",),
            "full_view_roles": ("директор",),
        }

        actor, project = resolve_work_journal_create_scope(
            object(),
            {"id": 9, "role": "account_owner"},
            "Лицей",
            x_company_id="4",
            x_company_mode="company",
            deps=deps,
        )

        self.assertEqual(actor["role"], "прораб")
        self.assertEqual(project, {"id": 14, "companyId": 4, "name": "Лицей"})
        self.assertEqual(calls, [("create", {"x_company_id": "4", "x_company_mode": "company"})])

    def test_aggregate_company_mode_stops_before_project_lookup(self):
        project_calls = []

        def reject_actor(_actors, _roles):
            raise HTTPException(status_code=409, detail="Выберите одну компанию")

        deps = {
            "resolve_work_company_context": lambda *_args, **_kwargs: {"mode": "all_companies"},
            "effective_company_actors": lambda *_args: [{"companyId": 4}, {"companyId": 8}],
            "require_project_write_actor": reject_actor,
            "resolve_project_parent": lambda *_args, **_kwargs: project_calls.append(True),
            "require_project_parent_access": lambda *_args: None,
            "journal_write_roles": ("прораб",),
            "full_view_roles": ("директор",),
        }

        with self.assertRaises(HTTPException) as raised:
            resolve_work_journal_create_scope(
                object(), {}, "Лицей",
                x_company_id=None,
                x_company_mode="all_companies",
                deps=deps,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(project_calls, [])

    def test_ownerless_project_fails_closed(self):
        deps = {
            "resolve_work_company_context": lambda *_args, **_kwargs: {},
            "effective_company_actors": lambda *_args: [{"companyId": 4, "role": "прораб"}],
            "require_project_write_actor": lambda actors, _roles: actors[0],
            "resolve_project_parent": lambda *_args, **_kwargs: {"id": 14, "companyId": None, "name": "Лицей"},
            "require_project_parent_access": lambda *_args: None,
            "journal_write_roles": ("прораб",),
            "full_view_roles": ("директор",),
        }

        with self.assertRaises(HTTPException) as raised:
            resolve_work_journal_create_scope(
                object(), {}, "Лицей",
                x_company_id="4",
                x_company_mode="company",
                deps=deps,
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_explicit_parent_must_match_selected_project_owner(self):
        with self.assertRaises(HTTPException) as raised:
            require_work_journal_parent_owner(
                {"companyId": 8, "projectId": 80},
                {"companyId": 4, "id": 14},
                "Смета",
            )
        self.assertEqual(raised.exception.status_code, 409)

        require_work_journal_parent_owner(
            {"companyId": 4, "projectId": 14},
            {"companyId": 4, "id": 14},
            "Смета",
        )


if __name__ == "__main__":
    unittest.main()
