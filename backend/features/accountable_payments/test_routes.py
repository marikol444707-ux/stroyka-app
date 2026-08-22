import unittest

from fastapi import HTTPException

from backend.features.accountable_payments.routes import register_accountable_payments_module


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
    def __init__(self, effects=()):
        self.effects = list(effects)
        self.current = {}
        self.calls = []
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params or ())))
        self.current = self.effects.pop(0) if self.effects else {}
        if self.current.get("error"):
            raise self.current["error"]
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


def build(effects=(), context=None, actors=None):
    app = FakeApp()
    cursor = FakeCursor(effects)
    connection = FakeConnection(cursor)
    selected_context = context or {"mode": "company", "companyId": 4}
    selected_actors = actors if actors is not None else [
        {"companyId": 4, "role": "директор", "name": "Системный директор"}
    ]

    def resolve_context(_cur, _user, _project, _action, **_headers):
        return selected_context

    register_accountable_payments_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: None,
        "resolve_work_company_context": resolve_context,
        "effective_company_actors": lambda _user, _context: selected_actors,
        "require_roles": lambda *_roles: (lambda: None),
        "finance_roles": ("директор", "бухгалтер"),
    })
    return app, connection, cursor


def call(handler, *args, **kwargs):
    return handler(
        *args,
        x_company_id="4",
        x_company_mode="company",
        current_user={"id": 8, "name": "Подмена из пользователя"},
        **kwargs,
    )


class AccountablePaymentsRoutesTest(unittest.TestCase):
    def test_registers_same_public_urls(self):
        app, _connection, _cursor = build()
        self.assertEqual(set(app.routes), {
            ("GET", "/accountable-payments"),
            ("POST", "/accountable-payments"),
            ("GET", "/accountable-expenses"),
            ("POST", "/accountable-expenses"),
        })

    def test_payment_list_reads_only_verified_rows_in_selected_company(self):
        app, connection, cursor = build([{"rows": [
            (1, "Объект", 19, "Мастер", 5000, "Наличные", "материалы", None, "Директор", None, 1500)
        ]}])
        rows = call(app.routes[("GET", "/accountable-payments")], project_name="")
        self.assertEqual(rows[0]["projectId"], 19)
        self.assertEqual(rows[0]["amount"], 5000.0)
        sql, params = cursor.calls[-1]
        self.assertIn("company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (4,))
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_project_name_filter_resolves_exact_project_inside_company(self):
        app, _connection, cursor = build([
            {"rows": [{"id": 19, "name": "Точный объект"}]},
            {"rows": []},
        ])
        call(app.routes[("GET", "/accountable-payments")], project_name="Точный объект")
        lookup_sql, lookup_params = cursor.calls[0]
        list_sql, list_params = cursor.calls[1]
        self.assertIn("FROM public.projects", lookup_sql)
        self.assertIn("company_id=%s", lookup_sql)
        self.assertEqual(lookup_params, (4, "Точный объект"))
        self.assertIn("project_id=%s", list_sql)
        self.assertEqual(list_params, (4, 19))

    def test_aggregate_non_finance_and_foreign_actor_are_rejected_before_source_read(self):
        cases = (
            ({"mode": "all_companies"}, [{"companyId": 4, "role": "директор"}], 409),
            ({"mode": "company", "companyId": 4}, [{"companyId": 4, "role": "рабочий"}], 403),
            ({"mode": "company", "companyId": 4}, [{"companyId": 9, "role": "директор"}], 409),
        )
        for context, actors, status in cases:
            with self.subTest(status=status, actors=actors):
                app, _connection, cursor = build(context=context, actors=actors)
                with self.assertRaises(HTTPException) as caught:
                    call(app.routes[("GET", "/accountable-payments")], project_name="")
                self.assertEqual(caught.exception.status_code, status)
                self.assertFalse(any("accountable_payments" in sql for sql, _ in cursor.calls))

    def test_payment_create_derives_project_staff_and_actor_names_on_server(self):
        app, connection, cursor = build([
            {"rows": [{"id": 19, "name": "Точный объект"}]},
            {"row": {"id": 23, "name": "Точный сотрудник"}},
            {"row": {"id": 7}},
        ])
        result = call(app.routes[("POST", "/accountable-payments")], {
            "projectId": 19,
            "givenToId": 23,
            "projectName": "Чужое имя",
            "givenTo": "Подмена сотрудника",
            "addedBy": "Подмена автора",
            "amount": 5000,
        })
        self.assertEqual(result, {"id": 7, "ok": True})
        self.assertIn("FOR SHARE", cursor.calls[0][0])
        self.assertIn("FOR SHARE", cursor.calls[1][0])
        insert_sql, insert_params = cursor.calls[2]
        self.assertIn("company_id", insert_sql)
        self.assertIn("project_id", insert_sql)
        self.assertIn("company_scope_verified", insert_sql)
        self.assertEqual(insert_params[:5], (4, 19, True, "Точный объект", "Точный сотрудник"))
        self.assertIn("Системный директор", insert_params)
        self.assertNotIn("Чужое имя", insert_params)
        self.assertEqual(connection.commits, 1)

    def test_foreign_project_rejection_rolls_back_without_insert(self):
        app, connection, cursor = build([{"rows": []}])
        with self.assertRaises(HTTPException) as caught:
            call(app.routes[("POST", "/accountable-payments")], {
                "projectId": 99, "givenToId": 23, "amount": 5000,
            })
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(connection.rollbacks, 1)
        self.assertFalse(any("INSERT INTO public.accountable_payments" in sql for sql, _ in cursor.calls))

    def test_expense_create_inherits_locked_verified_parent_ownership(self):
        app, connection, cursor = build([
            {"row": {"id": 4, "company_id": 4, "project_id": 19, "project_name": "Точный объект"}},
            {"rows": [{"id": 19, "name": "Точный объект"}]},
            {"row": {"id": 9}},
            {"rowcount": 1},
        ])
        result = call(app.routes[("POST", "/accountable-expenses")], {
            "paymentId": 4,
            "projectName": "Подмена объекта",
            "addedBy": "Подмена автора",
            "amount": 300,
            "description": "бензин",
        })
        self.assertEqual(result, {"ok": True})
        parent_sql, parent_params = cursor.calls[0]
        self.assertIn("company_scope_verified IS TRUE", parent_sql)
        self.assertIn("FOR UPDATE", parent_sql)
        self.assertEqual(parent_params, (4, 4))
        self.assertIn("FOR SHARE", cursor.calls[1][0])
        insert_sql, insert_params = cursor.calls[2]
        self.assertIn("company_scope_verified", insert_sql)
        self.assertEqual((insert_params[1], insert_params[2], insert_params[3]), (4, 19, True))
        update_sql, update_params = cursor.calls[3]
        self.assertIn("company_id=%s", update_sql)
        self.assertIn("project_id=%s", update_sql)
        self.assertIn("company_scope_verified IS TRUE", update_sql)
        self.assertEqual(update_params, (300, 4, 4, 19))
        self.assertEqual(connection.commits, 1)

    def test_unverified_parent_is_rejected_and_rolled_back(self):
        app, connection, cursor = build([{"row": None}])
        with self.assertRaises(HTTPException) as caught:
            call(app.routes[("POST", "/accountable-expenses")], {"paymentId": 4, "amount": 300})
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(len(cursor.calls), 1)

    def test_expense_list_reads_only_verified_rows_in_selected_company(self):
        app, _connection, cursor = build([{"rows": [
            (9, 4, "Объект", 19, "бензин", 300, "", None, "Директор")
        ]}])
        rows = call(app.routes[("GET", "/accountable-expenses")], payment_id=0)
        self.assertEqual(rows[0]["projectId"], 19)
        sql, params = cursor.calls[-1]
        self.assertIn("company_id=%s", sql)
        self.assertIn("company_scope_verified IS TRUE", sql)
        self.assertEqual(params, (4,))


if __name__ == "__main__":
    unittest.main()
