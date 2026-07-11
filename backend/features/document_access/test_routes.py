import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from backend.features.document_access.routes import register_document_access_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def delete(self, path):
        return self._register("DELETE", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, row):
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, row):
        self.cursor_value = FakeCursor(row)
        self.autocommit = True
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class DocumentAccessRouteTests(unittest.TestCase):
    def _register(self, connection, upload_dir, *, resolver=None, s3_enabled=False):
        app = FakeApp()
        resolver_calls = []
        project_calls = []
        access_calls = []
        s3_delete_calls = []

        def resolve_resource(cur, user, company_id, action_mode, **kwargs):
            resolver_calls.append((cur, user, company_id, action_mode, kwargs))
            if resolver:
                return resolver(cur, user, company_id, action_mode, **kwargs)
            return ({"mode": "company", "companyId": company_id}, {"id": user["id"], "role": "прораб", "companyId": company_id})

        def resolve_project(cur, actor, **kwargs):
            project_calls.append((cur, actor, kwargs))
            return {"id": kwargs["project_id"], "companyId": actor["companyId"], "name": "Лицей"}

        def require_project(actor, project_name):
            access_calls.append((actor, project_name))

        register_document_access_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_resource_company_actor": resolve_resource,
            "resolve_project_parent": resolve_project,
            "require_project_access": require_project,
            "leadership_roles": ("директор", "зам_директора"),
            "platform_staff_roles": (),
            "client_account_roles": (),
            "upload_dir": upload_dir,
            "s3_enabled": lambda: s3_enabled,
            "delete_s3_object": lambda key: s3_delete_calls.append(key),
        })
        return app, resolver_calls, project_calls, access_calls, s3_delete_calls

    def test_metadata_read_uses_stored_company_and_project(self):
        with TemporaryDirectory() as upload_dir:
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": 17,
                "file_url": "/uploads/company-4/file.png",
                "storage_key": "",
                "context": "project-documents",
                "original_name": "photo.png",
                "content_type": "image/png",
                "uploaded_by_id": 9,
                "uploaded_by": "Иван",
                "created_at": "2026-07-11",
            })
            app, resolver_calls, project_calls, access_calls, _ = self._register(connection, upload_dir)

            response = app.routes[("GET", "/tenant-files/{file_id}")](
                31,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "прораб"},
            )

            self.assertEqual(response["companyId"], 4)
            self.assertEqual(response["projectId"], 17)
            self.assertEqual(resolver_calls[0][2:4], (4, "read"))
            self.assertEqual(project_calls[0][2], {"project_id": 17})
            self.assertEqual(access_calls[0][1], "Лицей")
            self.assertTrue(connection.closed)

    def test_uploader_can_delete_local_file(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4/file.png",
                "storage_key": "",
                "uploaded_by_id": 9,
            })
            app, resolver_calls, _, _, _ = self._register(connection, upload_dir)

            response = app.routes[("DELETE", "/tenant-files/{file_id}")](
                31,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "прораб"},
            )

            self.assertEqual(response, {"ok": True, "id": 31, "companyId": 4})
            self.assertFalse(local_file.exists())
            self.assertEqual(resolver_calls[0][2:4], (4, "delete"))
            self.assertTrue(any(call[0].startswith("DELETE FROM file_ownership") for call in connection.cursor_value.calls))
            self.assertTrue(connection.committed)

    def test_non_owner_cannot_delete_file(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4/file.png",
                "storage_key": "",
                "uploaded_by_id": 9,
            })
            app, _, _, _, _ = self._register(connection, upload_dir)

            with self.assertRaises(HTTPException) as raised:
                app.routes[("DELETE", "/tenant-files/{file_id}")](
                    31,
                    current_user={"id": 10, "role": "прораб"},
                )

            self.assertEqual(raised.exception.status_code, 403)
            self.assertTrue(local_file.exists())
            self.assertTrue(connection.rolled_back)
            self.assertFalse(any(call[0].startswith("DELETE FROM file_ownership") for call in connection.cursor_value.calls))

    def test_s3_row_is_not_forgotten_when_s3_is_unavailable(self):
        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4/file.png",
            "uploaded_by_id": 9,
        })
        app, _, _, _, s3_delete_calls = self._register(connection, "/tmp/uploads", s3_enabled=False)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("DELETE", "/tenant-files/{file_id}")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(s3_delete_calls, [])
        self.assertFalse(any(call[0].startswith("DELETE FROM file_ownership") for call in connection.cursor_value.calls))
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
