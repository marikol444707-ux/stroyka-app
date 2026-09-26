import unittest

from backend.features.project_records.routes import register_project_records_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def delete(self, path):
        return self._register("DELETE", path)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return []

    def fetchone(self):
        return (1,)

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def commit(self):
        pass

    def close(self):
        pass


def build_handler(visible_projects):
    cur = FakeCursor()
    conn = FakeConnection(cur)
    app = FakeApp()
    deps = {
        "get_db": lambda: conn,
        "require_roles": (lambda *roles: (lambda: None)),
        "require_project_access": lambda *args, **kwargs: None,
        "require_row_project_access": lambda *args, **kwargs: None,
        "visible_project_names": (lambda _user: visible_projects),
        "read_roles": (),
        "write_roles": (),
        "worker_execution_roles": (),
    }
    register_project_records_module(app, deps)
    return app.routes[("GET", "/project-documents")], cur


class ProjectDocumentsRouteTests(unittest.TestCase):
    def test_broad_project_documents_are_scoped_by_company(self):
        handler, cur = build_handler(None)
        handler(project_name=None, _current_user={"companyId": 4, "role": "директор"})
        sql, params = cur.calls[0]
        self.assertIn("WHERE company_id=%s", sql)
        self.assertEqual(4, params[0])

    def test_named_project_document_is_scoped_by_company_even_with_same_name(self):
        handler, cur = build_handler(None)
        handler(project_name="Одинаковое имя", _current_user={"company_id": 7, "role": "директор"})
        sql, params = cur.calls[0]
        self.assertIn("WHERE company_id=%s AND project_name=%s", sql)
        self.assertEqual((7, "Одинаковое имя"), params[:2])


if __name__ == "__main__":
    unittest.main()
