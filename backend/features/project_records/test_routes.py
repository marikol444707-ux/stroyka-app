import unittest

from backend.features.project_records.routes import register_project_records_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(handler):
            self.routes[("GET", path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchall(self):
        return []

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cur = cursor

    def cursor(self):
        return self._cur

    def close(self):
        pass


class ProjectDocumentsRouteTests(unittest.TestCase):
    def test_all_projects_scoped_by_company(self):
        cur = FakeCursor()
        conn = FakeConnection(cur)
        app = FakeApp()

        deps = {
            "get_db": lambda: conn,
            "require_roles": (lambda *r: (lambda: None)),
            "require_project_access": lambda *a, **k: None,
            "require_row_project_access": lambda *a, **k: None,
            "visible_project_names": (lambda user: None),
            "read_roles": (),
            "write_roles": (),
            "worker_execution_roles": (),
        }

        register_project_records_module(app, deps)

        # simulate calling the route with a user who has a company_id
        handler = app.routes[("GET", "/project-documents")]
        handler_params = {"project_name": None, "_current_user": {"company_id": 4, "role": "директор"}}
        # call the handler
        handler(**handler_params)

        # the executed SQL should include company_id=%s
        executed = cur.calls[0][0]
        self.assertIn("company_id=%s", executed)


if __name__ == "__main__":
    unittest.main()
