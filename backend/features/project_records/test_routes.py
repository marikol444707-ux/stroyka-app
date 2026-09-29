import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import HTTPException

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


def build_handler(visible_projects, selected_company_id=4, selected_role="директор"):
    cur = FakeCursor()
    conn = FakeConnection(cur)
    app = FakeApp()

    class Scope:
        @contextmanager
        def transaction(self, user, request, roles, **_kwargs):
            headers = request.headers if request else {}
            if headers.get('x-company-mode') == 'all_companies':
                raise HTTPException(400, 'Для документов выберите конкретную компанию')
            company_id = int(headers.get('x-company-id') or selected_company_id)
            yield cur, [{**user, 'companyId': company_id, 'role': selected_role}]

        def visible(self, actors, _roles):
            return 'p.company_id=%s', [actors[0]['companyId']]

    deps = {
        "get_db": lambda: conn,
        "require_roles": (lambda *roles: (lambda: None)),
        "require_project_access": lambda *args, **kwargs: None,
        "require_row_project_access": lambda *args, **kwargs: None,
        "visible_project_names": (lambda _user: visible_projects),
        "resolve_work_company_context": lambda *args, **kwargs: {},
        "effective_company_user": lambda user, context: {
            **user,
            "companyId": context.get("companyId"),
            "company_id": context.get("companyId"),
            "role": context.get("effectiveRole") or user.get("role"),
        },
        "read_roles": (),
        "write_roles": (),
        "worker_execution_roles": (),
        "get_current_user": lambda: {},
        "record_scope": Scope(),
    }
    register_project_records_module(app, deps)
    return app.routes[("GET", "/project-documents")], cur


class ProjectDocumentsRouteTests(unittest.TestCase):
    def test_broad_project_documents_are_scoped_by_company(self):
        handler, cur = build_handler(None)
        handler(
            project_name=None,
            _current_user={"companyId": 99, "role": "директор"},
            request=SimpleNamespace(headers={'x-company-id':'4','x-company-mode':'company'}),
        )
        sql, params = cur.calls[0]
        self.assertIn("p.company_id=%s", sql)
        self.assertEqual(4, params[0])

    def test_all_companies_mode_is_rejected_for_project_documents(self):
        handler, cur = build_handler(None)
        with self.assertRaises(HTTPException) as error:
            handler(
                project_name=None,
                _current_user={"companyId": 4, "role": "директор"},
                request=SimpleNamespace(headers={'x-company-mode':'all_companies'}),
            )
        self.assertEqual(400, error.exception.status_code)
        self.assertEqual([], cur.calls)

    def test_named_project_document_is_scoped_by_company_even_with_same_name(self):
        handler, cur = build_handler(None)
        handler(
            project_name="Одинаковое имя",
            _current_user={"company_id": 99, "role": "директор"},
            request=SimpleNamespace(headers={'x-company-id':'7','x-company-mode':'company'}),
        )
        sql, params = cur.calls[0]
        self.assertIn("p.company_id=%s", sql)
        self.assertIn("p.name=%s", sql)
        self.assertEqual((7, "Одинаковое имя"), params[:2])


if __name__ == "__main__":
    unittest.main()
