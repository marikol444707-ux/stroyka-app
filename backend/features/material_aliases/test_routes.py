import unittest

from fastapi import HTTPException

from backend.features.material_aliases.routes import MaterialAliasModel, register_material_aliases_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def delete(self, path):
        return self._register("DELETE", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), fetchone_results=()):
        self.rows = list(rows)
        self.fetchone_results = list(fetchone_results)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

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


ROW = {"id": 1, "project_name": "Объект", "alias_name": "Цемент М500 мешок",
       "canonical_name": "Цемент", "canonical_unit": "кг", "source": "manual",
       "active": True, "updated_by": "Тест", "updated_at": "2026-07-28"}


def build(cursor, visible=None, access_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    access_log = access_calls if access_calls is not None else []

    def resolve(_cur, user, _requested, action, x_company_id=None, x_company_mode=None):
        company_id = int(x_company_id or 1)
        return {
            "mode": "company", "companyId": company_id, "companyIds": [company_id],
            "role": "директор", "effectiveRole": "директор", "active": True, "companyActive": True,
            "assignedProjects": visible or [],
        }

    register_material_aliases_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "resolve_work_company_context": resolve,
        "effective_company_actors": lambda user, context: [{
            **user, "role": "директор", "companyId": context["companyId"],
            "active": True, "companyActive": True, "assignedProjects": context["assignedProjects"],
        }],
        "company_id_scope_filter": lambda context, column="company_id": (f" AND {column}=%s", [context["companyId"]]),
        "can_see_all_company_data": lambda user: visible is None,
        "user_project_names": lambda user: visible or [],
        "read_roles": ("директор",),
        "write_roles": ("директор",),
        "require_project_access": lambda user, project: access_log.append(project),
    })
    return app, connection


class MaterialAliasesRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/material-aliases"), ("POST", "/material-aliases"), ("DELETE", "/material-aliases/{id}")]:
            self.assertIn(key, app.routes)

    def test_list_limits_to_visible_projects(self):
        cursor = FakeCursor(rows=[dict(ROW)])
        app, _conn = build(cursor, visible=["Объект"])
        rows = app.routes[("GET", "/material-aliases")](
            project_name=None, current_user={"role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual(rows[0]["aliasName"], "Цемент М500 мешок")
        sql, params = cursor.calls[0]
        self.assertIn("project_name = ANY(%s)", sql)
        self.assertIn("company_id=%s", sql)
        self.assertEqual(params[0], ["Объект"])
        self.assertEqual(params[-1], 1)

    def test_create_requires_both_names(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/material-aliases")](
                MaterialAliasModel(aliasName="  ", canonicalName=""),
            current_user={"name": "Тест", "role": "директор"}, x_company_id="1", x_company_mode="company",
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_soft_replaces_previous_alias(self):
        cursor = FakeCursor(fetchone_results=[dict(ROW)])
        app, _conn = build(cursor)
        result = app.routes[("POST", "/material-aliases")](
            MaterialAliasModel(aliasName="Цемент М500 мешок", canonicalName="Цемент"),
            current_user={"name": "Тест", "role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual(result["canonicalName"], "Цемент")
        self.assertIn("SET active=FALSE", cursor.calls[0][0])
        self.assertIn("INSERT INTO material_aliases", cursor.calls[1][0])

    def test_delete_checks_project_access_then_soft_deletes(self):
        calls = []
        cursor = FakeCursor(fetchone_results=[{"project_name": "Объект"}])
        app, _conn = build(cursor, access_calls=calls)
        result = app.routes[("DELETE", "/material-aliases/{id}")](
            id=1, current_user={"name": "Тест", "role": "директор"}, x_company_id="1", x_company_mode="company",
        )
        self.assertEqual(result, {"ok": True})
        self.assertIn("company_id=%s", cursor.calls[0][0])
        self.assertIn("SET active=FALSE", cursor.calls[1][0])
        self.assertIn("company_id=%s", cursor.calls[1][0])


if __name__ == "__main__":
    unittest.main()
