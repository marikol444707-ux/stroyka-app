import unittest

from backend.features.document_versions.routes import register_document_versions_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(handler):
            self.routes[("GET", path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, rows=(), row=None):
        self.rows = list(rows)
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self, **_kwargs):
        return self._cursor

    def close(self):
        self.closed = True


def build(cursor):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_document_versions_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "project_document_roles": ("директор",),
    })
    return app, connection


class DocumentVersionsRoutesTest(unittest.TestCase):
    def test_registers_same_urls(self):
        app, _conn = build(FakeCursor())
        self.assertIn(("GET", "/document-versions"), app.routes)
        self.assertIn(("GET", "/document-versions/{vid}"), app.routes)

    def test_list_filters_by_type_and_id_and_maps_fields(self):
        cursor = FakeCursor(rows=[(1, "act", 7, "v2", "Тест", "правка", "2026-07-27")])
        app, connection = build(cursor)
        rows = app.routes[("GET", "/document-versions")](
            document_type="act", document_id=7, _current_user={}
        )
        self.assertEqual(rows, [{
            "id": 1, "documentType": "act", "documentId": 7, "versionLabel": "v2",
            "changedBy": "Тест", "changeReason": "правка", "createdAt": "2026-07-27",
        }])
        sql, params = cursor.calls[0]
        self.assertIn("WHERE document_type=%s AND document_id=%s", sql)
        self.assertEqual(params, ("act", 7))
        self.assertTrue(connection.closed)

    def test_detail_parses_snapshot_and_handles_missing(self):
        found = FakeCursor(row=(1, "act", 7, "v2", '{"a": 1}', "Тест", "", "2026-07-27"))
        app, _conn = build(found)
        result = app.routes[("GET", "/document-versions/{vid}")](vid=1, _current_user={})
        self.assertEqual(result["snapshot"], {"a": 1})
        self.assertEqual(result["versionLabel"], "v2")

        missing = FakeCursor(row=None)
        app2, _conn2 = build(missing)
        self.assertEqual(
            app2.routes[("GET", "/document-versions/{vid}")](vid=99, _current_user={}),
            {"error": "not found"},
        )


if __name__ == "__main__":
    unittest.main()
