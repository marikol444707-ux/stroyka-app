import unittest

from fastapi import HTTPException

from backend.features.own_expenses.routes import register_own_expenses_module


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
    def __init__(self, result_sets=()):
        self.result_sets = [list(rows) for rows in result_sets]
        self.calls = []
        self._active = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))
        self._active = self.result_sets.pop(0) if self.result_sets else []

    def fetchall(self):
        return list(self._active)

    def fetchone(self):
        return self._active[0] if self._active else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def build(
    cursor,
    *,
    role="мастер",
    company_id=7,
    invoice_results=None,
    actor_overrides=None,
):
    app = FakeApp()
    connection = FakeConnection(cursor)
    actor = {
        "id": 42,
        "name": "Финансист" if role in ("директор", "бухгалтер") else "Мастер",
        "email": "master@example.test",
        "role": role,
        "companyId": company_id,
    }
    actor.update(actor_overrides or {})
    register_own_expenses_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: dict(actor),
        "resolve_work_company_context": lambda *_args, **_kwargs: {
            "mode": "company",
            "companyId": company_id,
        },
        "effective_company_actors": lambda _user, _context: [dict(actor)],
        "require_roles": lambda *roles: (lambda: None),
        "own_expense_roles": (
            "директор", "бухгалтер", "прораб", "главный_инженер", "мастер",
        ),
        "own_expense_review_roles": ("директор", "бухгалтер"),
        "finance_roles": ("директор", "бухгалтер"),
        "leadership_roles": ("директор",),
        "worker_execution_roles": ("мастер",),
        "warehouse_roles": ("кладовщик",),
        "own_expense_no_project_category": "personal_no_project",
        "require_project_access": lambda user, project: None,
        "user_project_names": lambda user: ["Объект"],
        "safe_project_list": lambda value: value if isinstance(value, list) else [],
        "safe_float": lambda value, default=None: float(value) if value not in (None, "") else default,
        "supply_work_package": lambda value=None: (value or "Основная"),
        "create_warehouse_invoice_record": (
            lambda payload, employee: dict(invoice_results or {"ok": True, "id": 1})
        ),
    })
    return app, connection


class OwnExpensesRoutesTest(unittest.TestCase):
    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [
            ("GET", "/own-expenses"),
            ("POST", "/own-expenses"),
            ("PUT", "/own-expenses/{id}"),
            ("DELETE", "/own-expenses/{id}"),
            ("POST", "/telegram/own-expenses"),
            ("POST", "/telegram/warehouse-invoices"),
        ]:
            self.assertIn(key, app.routes)

    def test_worker_list_uses_verified_company_and_exact_staff_id(self):
        cursor = FakeCursor(result_sets=[
            [{"id": 23, "name": "Мастер"}],
            [],
        ])
        app, connection = build(cursor)
        rows = app.routes[("GET", "/own-expenses")](
            project_id=None,
            employee_id=None,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42, "email": "master@example.test"},
        )
        self.assertEqual(rows, [])
        sql, params = cursor.calls[-1]
        self.assertIn("WHERE company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertIn("employee_id=%s", sql)
        self.assertEqual(params, (7, 23))
        self.assertNotIn("employee_name=%s", sql)
        self.assertTrue(connection.closed)

    def test_worker_list_prefers_explicit_membership_staff_link_over_email(self):
        cursor = FakeCursor(result_sets=[
            [{"id": 23, "name": "Мастер"}],
            [],
        ])
        app, connection = build(
            cursor,
            actor_overrides={
                "membershipId": 101,
                "staffId": 23,
                "email": "different@example.test",
            },
        )

        rows = app.routes[("GET", "/own-expenses")](
            project_id=None,
            employee_id=None,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42, "email": "different@example.test"},
        )

        self.assertEqual(rows, [])
        lookup_sql, lookup_params = cursor.calls[0]
        self.assertIn("FROM public.staff", lookup_sql)
        self.assertIn("id=%s AND company_id=%s", lookup_sql)
        self.assertNotIn("email_work", lookup_sql)
        self.assertEqual(lookup_params, (23, 7))
        self.assertTrue(connection.closed)

    def test_reviewer_list_is_company_scoped(self):
        cursor = FakeCursor(result_sets=[[]])
        app, _connection = build(cursor, role="директор")
        app.routes[("GET", "/own-expenses")](
            project_id=None,
            employee_id=None,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42},
        )
        sql, params = cursor.calls[-1]
        self.assertIn("WHERE company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (7,))

    def test_create_stamps_same_owner_on_expense_and_finance_mirror(self):
        cursor = FakeCursor(result_sets=[
            [{"id": 41, "name": "Объект"}],
            [{"id": 23, "name": "Мастер"}],
            [{"id": 9}],
            [],
            [{"id": 33}],
            [],
        ])
        app, connection = build(cursor)
        result = app.routes[("POST", "/own-expenses")](
            {
                "projectId": 41,
                "projectName": "Подмена объекта",
                "employeeId": 999,
                "employeeName": "Подмена сотрудника",
                "description": "бензин",
                "amount": 500,
            },
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42, "email": "master@example.test"},
        )
        self.assertEqual(result, {"ok": True, "id": 9, "expenseId": 33})
        self.assertTrue(connection.committed)
        own_insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.own_expenses"))
        mirror_insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.expenses"))
        self.assertIn("company_id,project_id,company_scope_verified", own_insert[0])
        self.assertEqual(own_insert[1][:6], (7, 41, True, "Объект", "Мастер", 23))
        self.assertIn("company_id,project_id,company_scope_verified", mirror_insert[0])
        self.assertEqual(mirror_insert[1][:4], (7, 41, True, "Объект"))
        self.assertNotIn("Подмена объекта", own_insert[1] + mirror_insert[1])
        self.assertNotIn("Подмена сотрудника", own_insert[1] + mirror_insert[1])

    def test_no_project_expense_remains_verified_company_owned(self):
        cursor = FakeCursor(result_sets=[
            [{"id": 23, "name": "Мастер"}],
            [{"id": 9}],
            [],
            [{"id": 33}],
            [],
        ])
        app, _connection = build(cursor)
        app.routes[("POST", "/own-expenses")](
            {"description": "обед", "amount": 300},
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42, "email": "master@example.test"},
        )
        own_insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.own_expenses"))
        mirror_insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.expenses"))
        self.assertEqual(own_insert[1][:3], (7, None, True))
        self.assertEqual(mirror_insert[1][:3], (7, None, True))
        self.assertIn("personal_no_project", own_insert[1])
        self.assertIn("personal_no_project", mirror_insert[1])

    def test_foreign_project_rejects_before_staff_or_insert(self):
        cursor = FakeCursor(result_sets=[[]])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/own-expenses")](
                {"projectId": 999, "description": "бензин", "amount": 500},
                x_company_id="7",
                x_company_mode="company",
                current_user={"id": 42, "email": "master@example.test"},
            )
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(len(cursor.calls), 1)
        self.assertTrue(connection.rolled_back)

    def test_reject_uses_server_actor_and_scopes_mirror_deletion(self):
        cursor = FakeCursor(result_sets=[[
            {
                "id": 9,
                "company_id": 7,
                "project_id": 41,
                "project_name": "Объект",
                "employee_id": 23,
                "employee_name": "Мастер",
                "description": "бензин",
                "amount": 500,
                "date": "2026-08-22",
                "photo_url": "",
            }
        ]])
        app, connection = build(cursor, role="директор")
        result = app.routes[("PUT", "/own-expenses/{id}")](
            id=9,
            data={"status": "Отклонено", "approvedBy": "Подмена"},
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42},
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        update = next(call for call in cursor.calls if call[0].startswith("UPDATE public.own_expenses SET status"))
        mirror_delete = next(call for call in cursor.calls if call[0].startswith("DELETE FROM public.expenses"))
        self.assertIn("company_id=%s", update[0])
        self.assertIn("company_scope_verified IS TRUE", update[0])
        self.assertIn("Финансист", update[1])
        self.assertNotIn("Подмена", update[1])
        self.assertEqual(mirror_delete[1], (9, 7))
        self.assertIn("company_id=%s", mirror_delete[0])

    def test_delete_locks_and_deletes_only_verified_company_owned_pair(self):
        cursor = FakeCursor(result_sets=[[
            {
                "id": 9,
                "company_id": 7,
                "project_id": None,
                "project_name": "",
                "employee_id": 23,
                "employee_name": "Мастер",
                "description": "обед",
                "amount": 300,
                "date": None,
                "photo_url": "",
            }
        ]])
        app, connection = build(cursor, role="директор")
        result = app.routes[("DELETE", "/own-expenses/{id}")](
            id=9,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 42},
        )
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)
        deletes = [call for call in cursor.calls if call[0].startswith("DELETE FROM public")]
        self.assertEqual(deletes[0][1], (9, 7))
        self.assertEqual(deletes[1][1], (9, 7))
        self.assertTrue(all("company_scope_verified IS TRUE" in call[0] for call in deletes))

    def test_foreign_update_stops_before_any_mutation(self):
        cursor = FakeCursor(result_sets=[[]])
        app, connection = build(cursor, role="директор")
        with self.assertRaises(HTTPException) as caught:
            app.routes[("PUT", "/own-expenses/{id}")](
                id=999,
                data={"status": "Возмещено"},
                x_company_id="7",
                x_company_mode="company",
                current_user={"id": 42},
            )
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(len(cursor.calls), 1)
        self.assertTrue(connection.rolled_back)

    def test_telegram_expense_redirects_warehouse_payload(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/telegram/own-expenses")](
                {
                    "telegramId": "123",
                    "description": "накладная цемент",
                    "amount": 100,
                    "documentType": "warehouse_invoice",
                },
                _bot={"role": "telegram_bot"},
            )
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("складская накладная", caught.exception.detail)

    def test_telegram_expense_resolves_one_verified_company_staff_owner(self):
        cursor = FakeCursor(result_sets=[
            [{
                "id": 23,
                "name": "Мастер",
                "role": "мастер",
                "project": "Объект",
                "company_id": 7,
                "assigned_projects": ["Объект"],
                "assigned_packages": [],
            }],
            [],
            [{"id": 41, "name": "Объект"}],
            [{"id": 9}],
            [],
            [{"id": 33}],
            [],
        ])
        app, connection = build(cursor)
        result = app.routes[("POST", "/telegram/own-expenses")](
            {
                "telegramId": "123",
                "projectId": 41,
                "description": "бензин",
                "amount": 500,
            },
            _bot={"role": "telegram_bot"},
        )
        self.assertEqual(result["id"], 9)
        self.assertEqual(result["expenseId"], 33)
        self.assertEqual(result["companyId"], 7)
        self.assertTrue(connection.committed)
        own_insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.own_expenses"))
        mirror_insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO public.expenses"))
        self.assertEqual(own_insert[1][:6], (7, 41, True, "Объект", "Мастер", 23))
        self.assertEqual(mirror_insert[1][:4], (7, 41, True, "Объект"))

    def test_telegram_employee_ambiguity_fails_closed_without_write(self):
        cursor = FakeCursor(result_sets=[
            [
                {"id": 23, "name": "Первый", "role": "мастер", "project": "", "company_id": 7},
                {"id": 24, "name": "Второй", "role": "мастер", "project": "", "company_id": 8},
            ],
            [],
        ])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/telegram/own-expenses")](
                {"telegramId": "123", "description": "бензин", "amount": 500},
                _bot={"role": "telegram_bot"},
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(any("INSERT INTO" in sql for sql, _params in cursor.calls))
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
