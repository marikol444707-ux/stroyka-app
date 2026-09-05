import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.features.staff.routes import StaffModel, register_staff_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def delete(self, path):
        return self._register("DELETE", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, effects=()):
        self.effects = list(effects)
        self.current = {}
        self.calls = []
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params or ())))
        self.current = self.effects.pop(0) if self.effects else {}
        error = self.current.get("error")
        if error is not None:
            raise error
        self.rowcount = self.current.get("rowcount", -1)

    def fetchall(self):
        return list(self.current.get("rows", ()))

    def fetchone(self):
        return self.current.get("row")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def build(effects=(), audit_calls=None, context=None, actors=None):
    app = FakeApp()
    cursor = FakeCursor(effects)
    connection = FakeConnection(cursor)
    audit_log = audit_calls if audit_calls is not None else []
    selected_context = context or {"mode": "company", "companyId": 4}
    selected_actors = actors if actors is not None else [
        {"companyId": 4, "role": "директор", "name": "Директор компании"}
    ]

    register_staff_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "staff_view_roles": ("директор", "прораб"),
        "staff_manage_roles": ("директор",),
        "staff_full_view_roles": ("директор", "бухгалтер"),
        "user_project_names": lambda user: ["Объект"],
        "safe_project_list": lambda v: v if isinstance(v, list) else [],
        "prepare_user_access_scope": lambda cur, role, project, projects, packages: (projects, packages),
        "date_or_none": lambda v: v or None,
        "log_audit": lambda *args: audit_log.append(args),
        "resolve_work_company_context": (
            lambda _cur, _user, _claimed, _mode, **_headers: selected_context
        ),
        "effective_company_actors": lambda _user, _context: selected_actors,
    })
    return app, connection, cursor


def call(handler, *args, user=None, **kwargs):
    actor = user or {"id": 9, "role": "директор", "name": "Заголовок не источник"}
    parameter = "current_user" if "current_user" in handler.__annotations__ else "_current_user"
    return handler(
        *args,
        x_company_id="4",
        x_company_mode="company",
        **{parameter: actor},
        **kwargs,
    )


class StaffRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn, _cursor = build()
        self.assertEqual(set(app.routes), {
            ("GET", "/staff"),
            ("POST", "/staff/current-user-link"),
            ("POST", "/staff"),
            ("PUT", "/staff/{id}"),
            ("DELETE", "/staff/{id}"),
            ("GET", "/staff/{staff_id}/profile"),
            ("POST", "/staff/{staff_id}/documents"),
            ("DELETE", "/staff-documents/{doc_id}"),
        })

    def test_non_staff_role_gets_empty_list_without_query(self):
        app, _conn, cursor = build(actors=[
            {"companyId": 4, "role": "мастер", "name": "Мастер"}
        ])
        result = call(app.routes[("GET", "/staff")], user={"role": "мастер"})
        self.assertEqual(result, [])
        self.assertEqual(cursor.calls, [])

    def test_list_is_verified_and_company_scoped(self):
        app, conn, cursor = build([{"rows": []}, {"rows": []}])
        self.assertEqual(call(app.routes[("GET", "/staff")]), [])
        sql, params = cursor.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (4,))
        self.assertTrue(conn.closed)

    def test_full_staff_list_includes_exact_account_membership_link(self):
        app, _conn, cursor = build([
            {"rows": [{"id": 5, "name": "Директор"}]},
            {"rows": [{
                "staff_id": 5,
                "accessUserId": 42,
                "accessEmail": "director@example.test",
                "accessRole": "директор",
                "accessAssignedProjects": ["Объект"],
                "accessAssignedPackages": [],
            }]},
        ])

        result = call(app.routes[("GET", "/staff")])

        self.assertEqual(result[0]["accessUserId"], 42)
        self.assertEqual(result[0]["accessEmail"], "director@example.test")
        access_sql, access_params = cursor.calls[1]
        self.assertIn("FROM public.user_company_roles", access_sql)
        self.assertIn("membership.staff_id IS NOT NULL", access_sql)
        self.assertEqual(access_params, (4,))

    def test_current_user_link_creates_director_staff_and_links_exact_membership(self):
        actor = {
            "id": 9,
            "membershipId": 71,
            "companyId": 4,
            "role": "директор",
            "name": "Основной директор",
            "email": "director@example.test",
        }
        app, conn, cursor = build([
            {"row": {
                "id": 71, "user_id": 9, "company_id": 4,
                "staff_id": None, "role": "директор",
            }},
            {"rows": []},
            {"row": {"id": 12}},
            {"row": None},
            {"rowcount": 1},
        ], actors=[actor])

        result = call(
            app.routes[("POST", "/staff/current-user-link")],
            user=actor,
        )

        self.assertEqual(result, {
            "ok": True,
            "created": True,
            "staffId": 12,
            "email": "director@example.test",
        })
        insert_sql, insert_params = cursor.calls[2]
        self.assertIn("INSERT INTO public.staff", insert_sql)
        self.assertIn("company_scope_verified", insert_sql)
        self.assertIn("Основной директор", insert_params)
        self.assertIn("director@example.test", insert_params)
        update_sql, update_params = cursor.calls[4]
        self.assertIn("UPDATE public.user_company_roles", update_sql)
        self.assertEqual(update_params, (12, 71, 9, 4))
        self.assertEqual(conn.commits, 1)

    def test_current_user_link_is_idempotent_for_existing_exact_link(self):
        actor = {
            "id": 9,
            "membershipId": 71,
            "companyId": 4,
            "role": "директор",
            "name": "Основной директор",
            "email": "director@example.test",
        }
        app, conn, _cursor = build([
            {"row": {
                "id": 71, "user_id": 9, "company_id": 4,
                "staff_id": 12, "role": "директор",
            }},
            {"row": {
                "id": 12, "name": "Основной директор",
                "email_work": "director@example.test",
            }},
        ], actors=[actor])

        result = call(
            app.routes[("POST", "/staff/current-user-link")],
            user=actor,
        )

        self.assertEqual(result["staffId"], 12)
        self.assertFalse(result["created"])
        self.assertEqual(conn.commits, 0)

    def test_current_user_link_reuses_unique_same_email_staff(self):
        actor = {
            "id": 9,
            "membershipId": 71,
            "companyId": 4,
            "role": "директор",
            "name": "Основной директор",
            "email": "director@example.test",
        }
        app, conn, cursor = build([
            {"row": {
                "id": 71, "user_id": 9, "company_id": 4,
                "staff_id": None, "role": "директор",
            }},
            {"rows": [{"id": 12}]},
            {"row": None},
            {"rowcount": 1},
        ], actors=[actor])

        result = call(
            app.routes[("POST", "/staff/current-user-link")],
            user=actor,
        )

        self.assertEqual(result["staffId"], 12)
        self.assertFalse(result["created"])
        self.assertFalse(any(
            "INSERT INTO public.staff" in sql
            for sql, _params in cursor.calls
        ))
        self.assertEqual(conn.commits, 1)

    def test_current_user_link_rejects_staff_owned_by_another_account(self):
        actor = {
            "id": 9,
            "membershipId": 71,
            "companyId": 4,
            "role": "директор",
            "name": "Основной директор",
            "email": "director@example.test",
        }
        app, conn, cursor = build([
            {"row": {
                "id": 71, "user_id": 9, "company_id": 4,
                "staff_id": None, "role": "директор",
            }},
            {"rows": [{"id": 12}]},
            {"row": {"user_id": 99}},
        ], actors=[actor])

        with self.assertRaises(HTTPException) as caught:
            call(
                app.routes[("POST", "/staff/current-user-link")],
                user=actor,
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("другим аккаунтом", caught.exception.detail)
        self.assertFalse(any(
            "UPDATE public.user_company_roles" in sql
            for sql, _params in cursor.calls
        ))
        self.assertEqual(conn.rollbacks, 1)

    def test_foreman_list_adds_project_scope_after_company_scope(self):
        app, _conn, cursor = build(
            [{"rows": []}],
            actors=[{"companyId": 4, "role": "прораб", "name": "Прораб"}],
        )
        call(app.routes[("GET", "/staff")], user={"role": "прораб"})
        sql, params = cursor.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertIn("project = ANY(%s)", sql)
        self.assertEqual(params, (4, ["Объект"]))

    def test_create_derives_verified_company_and_project(self):
        app, conn, cursor = build([
            {"rows": [{"id": 12, "name": "Точный объект"}]},
            {"row": {"id": 7}},
        ])
        created = call(
            app.routes[("POST", "/staff")],
            StaffModel(name="Новый", role="мастер", project="Точный объект"),
        )
        self.assertEqual(created["id"], 7)
        project_sql, project_params = cursor.calls[0]
        insert_sql, insert_params = cursor.calls[1]
        self.assertIn("FROM public.projects", project_sql)
        self.assertIn("company_id=%s", project_sql)
        self.assertEqual(project_params, ("Точный объект", 4))
        self.assertIn("company_scope_verified", insert_sql)
        self.assertIn("company_id", insert_sql)
        self.assertEqual(insert_params[-2:], (4, True))
        self.assertEqual(conn.commits, 1)

    def test_update_locks_and_updates_only_exact_verified_staff(self):
        app, conn, cursor = build([
            {"rows": [{"id": 12, "name": "Объект"}]},
            {"row": {"id": 5}},
            {"rowcount": 1},
        ])
        result = call(
            app.routes[("PUT", "/staff/{id}")],
            id=5,
            s=StaffModel(name="Обновлён", role="мастер", project="Объект"),
        )
        self.assertTrue(result["ok"])
        lookup_sql, lookup_params = cursor.calls[1]
        update_sql, update_params = cursor.calls[2]
        self.assertIn("company_id=%s", lookup_sql)
        self.assertIn("company_scope_verified IS TRUE", lookup_sql)
        self.assertIn("FOR UPDATE", lookup_sql)
        self.assertEqual(lookup_params, (5, 4))
        self.assertIn("company_id=%s", update_sql)
        self.assertIn("company_scope_verified IS TRUE", update_sql)
        self.assertEqual(update_params[-2:], (5, 4))
        self.assertEqual(conn.commits, 1)

    def test_existing_cross_company_user_identity_is_not_rewritten(self):
        app, conn, cursor = build([
            {"row": {"id": 7}},
            {"rows": [{"id": 41, "company_id": 5}]},
            {"row": None},
            {"row": None},
            {"rowcount": 1},
            {"rowcount": 1},
        ])
        created = call(
            app.routes[("POST", "/staff")],
            StaffModel(
                name="Новый", role="мастер", email="shared@example.test",
                password="NEW SECRET", systemRole="мастер",
            ),
        )
        self.assertEqual(created["access"]["action"], "updated")
        self.assertFalse(any(
            sql.startswith("UPDATE public.users") for sql, _params in cursor.calls
        ))
        self.assertTrue(any(
            "INSERT INTO public.user_company_roles" in sql
            for sql, _params in cursor.calls
        ))
        self.assertEqual(conn.commits, 1)

    def test_staff_access_membership_is_explicitly_linked_to_staff_record(self):
        app, conn, cursor = build([
            {"row": {"id": 7}},
            {"rows": [{"id": 42, "company_id": 4}]},
            {"row": None},
            {"row": None},
            {"rowcount": 1},
            {"rowcount": 1},
        ])

        created = call(
            app.routes[("POST", "/staff")],
            StaffModel(
                name="Новый", role="мастер", email="worker@example.test",
                systemRole="мастер",
            ),
        )

        self.assertEqual(created["id"], 7)
        membership_sql, membership_params = next(
            item for item in cursor.calls
            if "INSERT INTO public.user_company_roles" in item[0]
        )
        self.assertIn("staff_id", membership_sql)
        self.assertIn("staff_id=EXCLUDED.staff_id", membership_sql)
        self.assertIn(7, membership_params)
        self.assertEqual(conn.commits, 1)

    def test_staff_access_rejects_link_owned_by_another_active_account(self):
        app, conn, cursor = build([
            {"row": {"id": 7}},
            {"rows": [{"id": 42, "company_id": 4}]},
            {"row": {"user_id": 99}},
        ])

        with self.assertRaises(HTTPException) as caught:
            call(
                app.routes[("POST", "/staff")],
                StaffModel(
                    name="Новый", role="мастер", email="worker@example.test",
                    systemRole="мастер",
                ),
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("другим аккаунтом", caught.exception.detail)
        self.assertFalse(any(
            "INSERT INTO public.user_company_roles" in sql
            for sql, _params in cursor.calls
        ))
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)

    def test_staff_access_rejects_ambiguous_case_insensitive_email(self):
        app, conn, cursor = build([
            {"row": {"id": 7}},
            {"rows": [
                {"id": 42, "company_id": 4},
                {"id": 43, "company_id": 4},
            ]},
        ])

        with self.assertRaises(HTTPException) as caught:
            call(
                app.routes[("POST", "/staff")],
                StaffModel(
                    name="Новый", role="мастер", email="WORKER@example.test",
                    systemRole="мастер",
                ),
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("несколькими аккаунтами", caught.exception.detail)
        identity_sql, identity_params = cursor.calls[1]
        self.assertIn("ORDER BY id", identity_sql)
        self.assertIn("LIMIT 2", identity_sql)
        self.assertIn("FOR UPDATE", identity_sql)
        self.assertEqual(identity_params, ("worker@example.test",))
        self.assertEqual(conn.rollbacks, 1)

    def test_staff_access_does_not_move_account_from_another_staff_record(self):
        app, conn, cursor = build([
            {"row": {"id": 7}},
            {"rows": [{"id": 42, "company_id": 4}]},
            {"row": None},
            {"row": {"staff_id": 6}},
        ])

        with self.assertRaises(HTTPException) as caught:
            call(
                app.routes[("POST", "/staff")],
                StaffModel(
                    name="Новый", role="мастер", email="worker@example.test",
                    systemRole="мастер",
                ),
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("другой карточкой сотрудника", caught.exception.detail)
        self.assertFalse(any(
            "INSERT INTO public.user_company_roles" in sql
            for sql, _params in cursor.calls
        ))
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)

    def test_mutation_rolls_back_and_closes_on_named_control(self):
        control = KeyboardInterrupt("stop")
        app, conn, _cursor = build([{"error": control}])
        with self.assertRaises(KeyboardInterrupt) as caught:
            call(
                app.routes[("POST", "/staff")],
                StaffModel(name="Новый", role="мастер"),
            )
        self.assertIs(caught.exception, control)
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)

    def test_fire_revokes_only_selected_company_membership(self):
        staff_row = {
            "id": 5,
            "name": "Мастер Тест",
            "role": "мастер",
            "project": "Объект",
            "email_work": "",
            "email_personal": "",
        }
        app, conn, cursor = build([
            {"row": staff_row},
            {"rowcount": 1},
            {"rows": [{"id": 42}]},
            {"rows": [{"id": 42}]},
        ])
        with patch("backend.features.staff.routes._revoke_user_sessions") as revoke:
            result = call(app.routes[("DELETE", "/staff/{id}")], id=5)
        self.assertEqual(result["status"], "Уволен")
        lookup_sql, lookup_params = cursor.calls[0]
        self.assertIn("company_id=%s", lookup_sql)
        self.assertIn("company_scope_verified IS TRUE", lookup_sql)
        self.assertIn("FOR UPDATE", lookup_sql)
        self.assertEqual(lookup_params, (5, 4))
        membership_calls = [item for item in cursor.calls if "UPDATE public.user_company_roles" in item[0]]
        self.assertEqual(len(membership_calls), 1)
        self.assertIn("membership.staff_id=%s", membership_calls[0][0])
        self.assertEqual(membership_calls[0][1], (4, 5, []))
        global_email_updates = [
            item for item in cursor.calls
            if item[0].startswith("UPDATE users SET active=FALSE")
            and "NOT EXISTS" not in item[0]
        ]
        self.assertEqual(global_email_updates, [])
        revoke.assert_not_called()
        self.assertEqual(conn.commits, 1)

    def test_foreign_or_quarantined_staff_profile_is_not_found(self):
        app, conn, cursor = build([{"row": None}])
        with self.assertRaises(HTTPException) as ctx:
            call(app.routes[("GET", "/staff/{staff_id}/profile")], staff_id=99)
        self.assertEqual(ctx.exception.status_code, 404)
        sql, params = cursor.calls[0]
        self.assertIn("company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (99, 4))
        self.assertTrue(conn.closed)

    def test_document_create_locks_exact_staff_owner(self):
        app, conn, cursor = build([
            {"row": {"id": 5}},
            {"row": {"id": 8}},
        ])
        result = call(
            app.routes[("POST", "/staff/{staff_id}/documents")],
            staff_id=5,
            data={"title": "Паспорт", "createdBy": "ПОДМЕНА"},
        )
        self.assertEqual(result, {"id": 8, "ok": True})
        staff_sql, staff_params = cursor.calls[0]
        _insert_sql, insert_params = cursor.calls[1]
        self.assertIn("company_id=%s", staff_sql)
        self.assertIn("company_scope_verified IS TRUE", staff_sql)
        self.assertIn("FOR SHARE", staff_sql)
        self.assertEqual(staff_params, (5, 4))
        self.assertIn("Директор компании", insert_params)
        self.assertNotIn("ПОДМЕНА", insert_params)
        self.assertEqual(conn.commits, 1)

    def test_document_delete_verifies_parent_company_before_delete(self):
        app, conn, cursor = build([
            {"row": {"id": 8, "staff_id": 5}},
            {"rowcount": 1},
        ])
        self.assertEqual(
            call(app.routes[("DELETE", "/staff-documents/{doc_id}")], doc_id=8),
            {"ok": True},
        )
        lookup_sql, lookup_params = cursor.calls[0]
        _delete_sql, delete_params = cursor.calls[1]
        self.assertIn("JOIN public.staff", lookup_sql)
        self.assertIn("company_id=%s", lookup_sql)
        self.assertIn("company_scope_verified IS TRUE", lookup_sql)
        self.assertIn("FOR UPDATE", lookup_sql)
        self.assertEqual(lookup_params, (8, 4))
        self.assertEqual(delete_params, (8, 5))
        self.assertEqual(conn.commits, 1)

    def test_aggregate_mode_is_rejected_before_query(self):
        app, _conn, cursor = build(context={"mode": "all_companies"})
        with self.assertRaises(HTTPException) as ctx:
            call(app.routes[("GET", "/staff")])
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
