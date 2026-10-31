import unittest
from contextlib import contextmanager

from fastapi import HTTPException

from backend.features.checklist_items.routes import register_checklist_items_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def build(cursor, access_calls, deny_id=None):
    app = FakeApp()
    connection = FakeConnection(cursor)

    class Scope:
        @contextmanager
        def transaction(self, user, request, roles, write=False):
            yield cursor, [{'companyId': 2, 'role': 'директор'}]
            if write:
                connection.commit()
        def visible(self, actors, roles):
            return 'p.company_id=%s', [2]
    register_checklist_items_module(app, {
        'record_scope': Scope(), 'get_current_user': lambda: {},
        'project_document_roles': ('директор',),
        'project_write_roles': ('директор',),
    })
    return app, connection


class ChecklistItemsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor(), [])
        for key in [("GET", "/checklist-items/{checklist_id}"), ("POST", "/checklist-items"), ("PUT", "/checklist-items/{id}")]:
            self.assertIn(key, app.routes)

    def test_list_checks_access_and_maps_rows(self):
        calls = []
        cursor = FakeCursor(row=(4,), rows=[(1, 4, "Проверка", True, "Тест", "2026-07-28", 1)])
        app, _conn = build(cursor, calls)
        rows = app.routes[("GET", "/checklist-items/{checklist_id}")](checklist_id=4, request=None, current_user={})
        self.assertIn("p.company_id=%s", cursor.calls[0][0])
        self.assertEqual(rows[0]["checklistId"], 4)
        self.assertEqual(rows[0]["checkedBy"], "Тест")

    def test_create_denied_before_insert_for_foreign_checklist(self):
        calls = []
        cursor = FakeCursor()
        app, _conn = build(cursor, calls, deny_id=9)
        with self.assertRaises(HTTPException):
            app.routes[("POST", "/checklist-items")]({"checklistId": 9, "name": "x"}, request=None, current_user={})
        self.assertEqual(len(cursor.calls), 1)
        self.assertNotIn("INSERT", cursor.calls[0][0])

    def test_update_toggles_checked_state(self):
        calls = []
        cursor = FakeCursor(row=(3,))
        app, connection = build(cursor, calls)
        result = app.routes[("PUT", "/checklist-items/{id}")](id=3, data={"checked": True, "checkedBy": "Тест"}, request=None, current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertIn("p.company_id=%s", cursor.calls[0][0])
        self.assertTrue(connection.committed)
        self.assertIn("UPDATE checklist_items SET checked=%s", cursor.calls[1][0])


if __name__ == "__main__":
    unittest.main()
