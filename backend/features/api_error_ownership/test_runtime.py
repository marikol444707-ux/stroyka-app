import unittest

from fastapi import HTTPException

from backend.features.api_error_ownership.runtime import (
    insert_api_error,
    resolve_api_error_read_scope,
    resolve_api_error_write_owner,
    scoped_api_error_filter,
)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))


class ApiErrorRuntimeTests(unittest.TestCase):
    def test_company_request_error_uses_validated_selected_company(self):
        calls = []

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            calls.append((requested_company_id, action_mode, kwargs))
            return {"mode": "company", "companyId": 4, "companyIds": [4]}

        owner = resolve_api_error_write_owner(
            FakeCursor(),
            {"id": 9, "role": "director"},
            resolve_context,
            x_company_id="4",
            x_company_mode="company",
        )

        self.assertEqual(owner, {"ownerScope": "company", "companyId": 4, "projectId": None})
        self.assertEqual(calls, [(None, "read", {"x_company_id": "4", "x_company_mode": "company"})])

    def test_unscoped_or_platform_request_error_stays_platform_owned(self):
        resolver_called = False

        def resolve_context(*_args, **_kwargs):
            nonlocal resolver_called
            resolver_called = True
            return {"mode": "company", "companyId": 4}

        anonymous = resolve_api_error_write_owner(FakeCursor(), {}, resolve_context)
        platform = resolve_api_error_write_owner(
            FakeCursor(), {"id": 1, "role": "system_owner"}, resolve_context
        )

        self.assertEqual(anonymous["ownerScope"], "platform")
        self.assertEqual(platform["ownerScope"], "platform")
        self.assertFalse(resolver_called)

    def test_ambiguous_write_context_fails_closed_to_platform(self):
        def resolve_context(*_args, **_kwargs):
            raise HTTPException(status_code=400, detail="Выберите компанию")

        owner = resolve_api_error_write_owner(
            FakeCursor(), {"id": 9, "role": "директор"}, resolve_context
        )

        self.assertEqual(owner, {"ownerScope": "platform", "companyId": None, "projectId": None})

    def test_company_read_scope_keeps_only_leadership_memberships(self):
        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            return {"mode": "all_companies", "companyIds": [4, 5]}

        result = resolve_api_error_read_scope(
            FakeCursor(),
            {"id": 9, "role": "директор"},
            resolve_context,
            lambda _user, _context: [
                {"role": "директор", "companyId": 4},
                {"role": "мастер", "companyId": 5},
            ],
            allowed_roles=("директор", "зам_директора"),
            x_company_mode="all_companies",
        )

        self.assertEqual(result["where"], "owner_scope='company' AND company_id = ANY(%s)")
        self.assertEqual(result["params"], ([4],))

    def test_platform_read_scope_excludes_company_and_legacy_errors(self):
        result = resolve_api_error_read_scope(
            FakeCursor(),
            {"id": 1, "role": "system_owner"},
            lambda *_args, **_kwargs: self.fail("platform scope must not resolve a company"),
            lambda *_args: [],
            allowed_roles=("директор", "зам_директора"),
        )

        self.assertEqual(result, {"where": "owner_scope='platform'", "params": ()})

    def test_company_read_scope_rejects_non_leadership_membership(self):
        with self.assertRaises(HTTPException) as raised:
            resolve_api_error_read_scope(
                FakeCursor(),
                {"id": 9, "role": "директор"},
                lambda *_args, **_kwargs: {"mode": "company", "companyId": 4, "companyIds": [4]},
                lambda *_args: [{"role": "мастер", "companyId": 4}],
                allowed_roles=("директор", "зам_директора"),
            )

        self.assertEqual(raised.exception.status_code, 403)

    def test_insert_persists_exact_owner_columns(self):
        cursor = FakeCursor()

        insert_api_error(
            cursor,
            method="GET",
            path="/projects",
            status_code=500,
            error_type="RuntimeError",
            error_message="failure",
            user_id=9,
            user_name="Director",
            user_role="director",
            owner={"ownerScope": "company", "companyId": 4, "projectId": None},
        )

        sql, params = cursor.calls[0]
        self.assertIn("owner_scope, company_id, project_id", sql)
        self.assertEqual(params[-3:], ("company", 4, None))

    def test_scope_filter_is_applied_before_time_window(self):
        where, params = scoped_api_error_filter(
            {"where": "owner_scope='company' AND company_id = ANY(%s)", "params": ([4],)},
            "created_at >= NOW() - (%s || ' hours')::interval",
            (24,),
        )

        self.assertEqual(
            where,
            "(owner_scope='company' AND company_id = ANY(%s)) AND "
            "(created_at >= NOW() - (%s || ' hours')::interval)",
        )
        self.assertEqual(params, ([4], 24))


if __name__ == "__main__":
    unittest.main()
