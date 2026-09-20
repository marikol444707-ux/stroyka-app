import unittest
from contextlib import contextmanager

from backend.features.company_documents.routes import register_company_documents_module
from backend.features.project_checklists.routes import register_project_checklists_module
from backend.features.project_stages.routes import register_project_stages_module


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


def common_deps(cursor, access_calls=None):
    connection = FakeConnection(cursor)
    access_log = access_calls if access_calls is not None else []
    class StageScope:
        @contextmanager
        def transaction(self, user, request, roles, write=False):
            yield cursor, [{'companyId': 1, 'role': 'директор'}]
            if write:
                connection.commit()

        def visible(self, actors, roles):
            return 'p.company_id=%s AND p.name=ANY(%s)', [1, ['Объект']]

        def parent(self, cur, actor, data, roles):
            access_log.append(data['projectName'])
            return {'id': 7, 'companyId': 1, 'name': data['projectName']}

    return connection, {
        'record_scope': StageScope(),
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "require_roles": lambda *roles: (lambda: None),
        "finance_roles": ("директор",),
        "read_roles": ("директор",),
        "write_roles": ("директор",),
        "visible_project_names": lambda user: ["Объект"],
        "project_name_from_payload": lambda cur, data: data.get("projectName", "Объект"),
        "require_project_access": lambda user, project: access_log.append(project),
        "require_row_project_access": lambda cur, table, row_id, user, col: access_log.append((table, row_id)),
    }


class RegionRoutesTest(unittest.TestCase):
    def test_company_documents_hidden_from_non_finance(self):
        cursor = FakeCursor(rows=[(1, 2, "Устав", "устав", "/f.pdf", "", "Тест")])
        app = FakeApp()
        connection, deps = common_deps(cursor)
        register_company_documents_module(app, deps)
        self.assertEqual(app.routes[("GET", "/company-documents")](current_user={"role": "мастер"}), [])
        self.assertEqual(cursor.calls, [])
        rows = app.routes[("GET", "/company-documents")](current_user={"role": "директор"})
        self.assertEqual(rows[0]["docType"], "устав")

    def test_stage_create_resolves_and_checks_project(self):
        calls = []
        cursor = FakeCursor(row=(4,))
        app = FakeApp()
        connection, deps = common_deps(cursor, calls)
        register_project_stages_module(app, deps)
        result = app.routes[("POST", "/project-stages")](
            {"projectName": "Объект", "name": "Черновая"}, current_user={}
        )
        self.assertEqual(result, {"id": 4, "ok": True})
        self.assertEqual(calls, ["Объект"])
        self.assertTrue(connection.committed)
        self.assertEqual(cursor.calls[0][1][:2], (7, 'Объект'))

    def test_stage_list_scopes_to_visible_projects(self):
        cursor = FakeCursor(rows=[])
        app = FakeApp()
        _conn, deps = common_deps(cursor)
        register_project_stages_module(app, deps)
        app.routes[("GET", "/project-stages")](current_user={})
        self.assertIn('JOIN projects p ON p.id=s.project_id', cursor.calls[0][0])
        self.assertIn('p.company_id=%s', cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (1, ['Объект']))

    def test_checklist_delete_cascades_items_first(self):
        calls = []
        cursor = FakeCursor()
        app = FakeApp()
        connection, deps = common_deps(cursor, calls)
        register_project_checklists_module(app, deps)
        result = app.routes[("DELETE", "/project-checklists/{id}")](id=9, _current_user={})
        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls, [("project_checklists", 9)])
        self.assertIn("DELETE FROM checklist_items WHERE checklist_id=%s", cursor.calls[0][0])
        self.assertIn("DELETE FROM project_checklists WHERE id=%s", cursor.calls[1][0])
        self.assertTrue(connection.committed)

    def test_all_urls_registered(self):
        app = FakeApp()
        _conn, deps = common_deps(FakeCursor())
        register_company_documents_module(app, deps)
        register_project_stages_module(app, deps)
        register_project_checklists_module(app, deps)
        expected = [
            ("GET", "/company-documents"), ("POST", "/company-documents"), ("DELETE", "/company-documents/{id}"),
            ("GET", "/project-stages"), ("POST", "/project-stages"), ("PUT", "/project-stages/{id}"), ("DELETE", "/project-stages/{id}"),
            ("GET", "/project-checklists"), ("POST", "/project-checklists"), ("DELETE", "/project-checklists/{id}"),
        ]
        for key in expected:
            self.assertIn(key, app.routes)


if __name__ == "__main__":
    unittest.main()
