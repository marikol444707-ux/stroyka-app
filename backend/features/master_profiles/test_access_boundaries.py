"""Explicit self-access settings must not grant a profile implicitly."""
import unittest

from fastapi import HTTPException

from .access import authorized_profile_users, require_profile_user
from .test_access import BASE_DIRECTOR, ScopedCursor, build


class MasterProfileAccessBoundaryTests(unittest.TestCase):
    def test_legacy_and_current_project_fields_preserve_the_same_access(self):
        cases = [({'assignedProjects': ['Shared']}, {1: True, 42: False}),
                 ({'assigned_projects': ['Shared']}, {1: True, 42: False}),
                 ({'projectName': 'Alpha'}, {1: True, 42: False, 44: False}),
                 ({'project_name': 'Alpha'}, {1: True, 42: False, 44: False}),
                 ({}, {1: True}),
                 ({'assignedProjects': [], 'projectName': ''}, {1: True}),
                 ({'assigned_projects': None, 'project_name': None}, {1: True})]
        for company_key in ('companyId', 'company_id'):
            for fields, expected in cases:
                with self.subTest(company_key=company_key, fields=fields):
                    actor = {'id': 1, company_key: 2, 'role': 'прораб', **fields}
                    deps = {'resolve_work_company_context': lambda *args, **kwargs: {},
                            'effective_company_actors': lambda user, context: [actor]}
                    allowed = authorized_profile_users(ScopedCursor(), actor, deps,
                        manager_roles=('директор', 'бухгалтер'), project_roles=('прораб',))
                    self.assertEqual(allowed, expected)
                    self.assertNotIn(99, allowed)

    def test_worker_cannot_access_own_profile_when_self_access_is_disabled(self):
        _app, cursor, deps = build('мастер')
        allowed = authorized_profile_users(
            cursor, BASE_DIRECTOR, deps,
            manager_roles=('директор', 'бухгалтер'),
            project_roles=('прораб', 'главный_инженер'),
            allow_self=False,
        )
        self.assertEqual(allowed, {})
        with self.assertRaises(HTTPException) as error:
            require_profile_user(allowed, BASE_DIRECTOR['id'])
        self.assertEqual(error.exception.status_code, 403)

    def test_missing_actor_id_does_not_create_a_profile_permission(self):
        for actor_id in (None, 0, ''):
            with self.subTest(actor_id=actor_id):
                _app, cursor, deps = build('мастер')
                allowed = authorized_profile_users(
                    cursor, {**BASE_DIRECTOR, 'id': actor_id}, deps,
                    manager_roles=('директор', 'бухгалтер'),
                )
                self.assertEqual(allowed, {})
