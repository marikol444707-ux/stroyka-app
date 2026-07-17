import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.features.document_versions.routes import register_document_versions_module
from backend.features.document_versions.service import save_document_version


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(func):
            self.routes[("GET", path)] = func
            return func

        return decorator


class FakeCursor:
    def __init__(self, rows=None, row=None):
        self.rows = list(rows or [])
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
        self.fake_cursor = cursor
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class DocumentVersionTests(unittest.TestCase):
    def build_app(self, cursor):
        app = FakeApp()
        connection = FakeConnection(cursor)

        def require_roles(*_roles):
            return lambda: {}

        register_document_versions_module(app, {
            "get_db": lambda: connection,
            "require_roles": require_roles,
            "project_document_roles": ("директор", "прораб"),
        })
        return app, connection

    def test_registers_original_route_contract(self):
        app, _connection = self.build_app(FakeCursor())
        self.assertEqual(set(app.routes), {
            ("GET", "/document-versions"),
            ("GET", "/document-versions/{vid}"),
        })

    def test_list_versions_filters_by_type_and_document(self):
        rows = [(5, "hidden_works_act", 9, "v1", "Директор", "Правка", "2026-07-17")]
        cursor = FakeCursor(rows=rows)
        app, connection = self.build_app(cursor)
        result = app.routes[("GET", "/document-versions")](
            document_type="hidden_works_act",
            document_id=9,
            _current_user={"role": "директор"},
        )
        self.assertIn("document_type=%s AND document_id=%s", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ("hidden_works_act", 9))
        self.assertEqual(result[0]["versionLabel"], "v1")
        self.assertTrue(connection.closed)

    def test_get_version_parses_snapshot(self):
        cursor = FakeCursor(row=(5, "hidden_works_act", 9, "v1", '{"status":"draft"}', "Директор", "Правка", "2026-07-17"))
        app, connection = self.build_app(cursor)
        result = app.routes[("GET", "/document-versions/{vid}")](5, _current_user={"role": "директор"})
        self.assertEqual(result["snapshot"], {"status": "draft"})
        self.assertEqual(result["documentId"], 9)
        self.assertTrue(connection.closed)

    def test_save_document_version_keeps_label_and_snapshot_format(self):
        cursor = FakeCursor(row=(2,))
        connection = FakeConnection(cursor)
        with patch("backend.features.document_versions.service.datetime") as mocked_datetime:
            mocked_datetime.now.return_value.strftime.return_value = "20260717_120000"
            result = save_document_version(
                lambda: connection,
                "hidden_works_act",
                9,
                {"status": "draft"},
                changed_by="Директор",
                change_reason="Правка",
            )
        self.assertEqual(result, "v3_20260717_120000")
        self.assertEqual(json.loads(cursor.calls[1][1][3]), {"status": "draft"})
        self.assertEqual(connection.commits, 1)
        self.assertTrue(connection.closed)

    def test_hidden_works_act_uses_extracted_version_service(self):
        main_source = (Path(__file__).resolve().parents[2] / "main.py").read_text()
        self.assertNotIn("def save_doc_version(", main_source)
        self.assertIn(
            'save_document_version(\n                get_db,\n                "hidden_works_act",',
            main_source,
        )


if __name__ == "__main__":
    unittest.main()
