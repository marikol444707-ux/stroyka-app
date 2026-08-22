import unittest

from fastapi import HTTPException

from backend.features.expenses.routes import register_expenses_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, result_sets=()):
        self.result_sets = [list(rows) for rows in result_sets]
        self.calls = []
        self.closed = False
        self._active = []

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


def build(cursor, *, company_id=7, actors=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    selected_actors = actors if actors is not None else [{
        "id": 91,
        "name": "Финансист",
        "role": "директор",
        "companyId": company_id,
    }]
    register_expenses_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {"id": 91, "name": "Финансист"},
        "resolve_work_company_context": lambda *_args, **_kwargs: {
            "mode": "company",
            "companyId": company_id,
        },
        "effective_company_actors": lambda _user, _context: selected_actors,
        "finance_roles": ("директор", "бухгалтер"),
    })
    return app, connection


class ExpensesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        self.assertIn(("GET", "/expenses"), app.routes)
        self.assertIn(("POST", "/expenses"), app.routes)

    def test_list_is_scoped_to_verified_selected_company(self):
        cursor = FakeCursor(result_sets=[[
            {
                "id": 1,
                "project": "Объект",
                "category": "materials",
                "amount": "150.5",
                "note": "заметка",
                "date": "2026-07-28",
                "added_by": "Тест",
                "own_expense_id": None,
                "source": "manual",
                "photo_url": "",
            }
        ]])
        app, connection = build(cursor)
        rows = app.routes[("GET", "/expenses")](
            project_id=None,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 91},
        )
        self.assertEqual(rows[0]["amount"], 150.5)
        sql, params = cursor.calls[-1]
        self.assertIn("WHERE company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (7,))
        self.assertTrue(connection.closed)

    def test_list_resolves_project_id_inside_selected_company(self):
        cursor = FakeCursor(result_sets=[
            [{"id": 41, "name": "Объект"}],
            [],
        ])
        app, _connection = build(cursor)
        app.routes[("GET", "/expenses")](
            project_id=41,
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 91},
        )
        project_sql, project_params = cursor.calls[0]
        expense_sql, expense_params = cursor.calls[1]
        self.assertIn("FROM public.projects", project_sql)
        self.assertEqual(project_params, (41, 7))
        self.assertIn("AND project_id=%s", expense_sql)
        self.assertEqual(expense_params, (7, 41))

    def test_create_stamps_server_owned_company_project_and_actor(self):
        cursor = FakeCursor(result_sets=[
            [{"id": 41, "name": "Объект"}],
            [{"id": 501}],
        ])
        app, connection = build(cursor)
        result = app.routes[("POST", "/expenses")](
            {
                "projectId": 41,
                "project": "Чужое имя",
                "amount": 100,
                "addedBy": "Подмена",
                "photoUrl": "u",
            },
            x_company_id="7",
            x_company_mode="company",
            current_user={"id": 91},
        )
        self.assertEqual(result, {"id": 501, "ok": True})
        self.assertTrue(connection.committed)
        sql, params = cursor.calls[-1]
        self.assertIn("company_id,project_id,company_scope_verified", sql)
        self.assertEqual(params[:4], (7, 41, True, "Объект"))
        self.assertIn("Финансист", params)
        self.assertNotIn("Подмена", params)
        self.assertNotIn("Чужое имя", params)

    def test_create_rejects_foreign_project_without_insert(self):
        cursor = FakeCursor(result_sets=[[]])
        app, connection = build(cursor)
        with self.assertRaises(HTTPException) as caught:
            app.routes[("POST", "/expenses")](
                {"projectId": 999, "amount": 100},
                x_company_id="7",
                x_company_mode="company",
                current_user={"id": 91},
            )
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(len(cursor.calls), 1)
        self.assertTrue(connection.rolled_back)

    def test_create_rejects_nonpositive_and_nonfinite_amounts(self):
        for amount in (0, -1, float("nan"), float("inf"), "100"):
            with self.subTest(amount=amount):
                cursor = FakeCursor(result_sets=[[{"id": 41, "name": "Объект"}]])
                app, connection = build(cursor)
                with self.assertRaises(HTTPException) as caught:
                    app.routes[("POST", "/expenses")](
                        {"projectId": 41, "amount": amount},
                        x_company_id="7",
                        x_company_mode="company",
                        current_user={"id": 91},
                    )
                self.assertEqual(caught.exception.status_code, 400)
                self.assertTrue(connection.rolled_back)
                self.assertEqual(len(cursor.calls), 1)

    def test_selected_company_finance_actor_is_required(self):
        app, connection = build(FakeCursor(), actors=[])
        with self.assertRaises(HTTPException) as caught:
            app.routes[("GET", "/expenses")](
                project_id=None,
                x_company_id="7",
                x_company_mode="company",
                current_user={"id": 91},
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
