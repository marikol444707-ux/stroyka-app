import asyncio
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from backend.features.document_access.routes import (
    OwnedStreamingResponse,
    _bounded_stream,
    register_document_access_module,
)
from backend.features.document_access.service import delete_document_local_file, open_document_local_file


def response_body(response):
    async def collect():
        return b"".join([chunk async for chunk in response.body_iterator])

    return asyncio.run(collect())


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
    def __init__(self, row, fail_commit_numbers=()):
        self.cursor_value = FakeCursor(row)
        self.cursor_factory = None
        self.autocommit = True
        self.committed = False
        self.commit_count = 0
        self.fail_commit_numbers = set(fail_commit_numbers)
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        self.cursor_factory = cursor_factory
        return self.cursor_value

    def commit(self):
        self.commit_count += 1
        if self.commit_count in self.fail_commit_numbers:
            raise RuntimeError("database commit failed")
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class DocumentAccessRouteTests(unittest.TestCase):
    def test_stream_source_closes_when_asgi_send_fails(self):
        stream = io.BytesIO(b"data")
        response = OwnedStreamingResponse(
            stream,
            len(b"data"),
            1024,
            media_type="application/octet-stream",
            headers={},
        )

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(_message):
            raise RuntimeError("client disconnected")

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/tenant-files/31/content",
            "raw_path": b"/tenant-files/31/content",
            "query_string": b"",
            "headers": [],
            "client": None,
            "server": None,
        }
        with self.assertRaises(RuntimeError):
            asyncio.run(response(scope, receive, send))
        self.assertTrue(stream.closed)

    def test_bounded_stream_closes_source_on_limit_or_size_mismatch(self):
        for expected_size, max_bytes in ((4, 3), (5, 10)):
            stream = io.BytesIO(b"data")
            with self.subTest(expected_size=expected_size, max_bytes=max_bytes):
                with self.assertRaises(RuntimeError):
                    list(_bounded_stream(stream, expected_size, max_bytes, chunk_size=2))
                self.assertTrue(stream.closed)

    def _register(
        self,
        connection,
        upload_dir,
        *,
        resolver=None,
        project_access=None,
        s3_enabled=False,
        s3_reader=None,
        s3_deleter=None,
    ):
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

        def require_project(cur, actor, project, full_view_roles):
            access_calls.append((actor, project["name"]))
            if project_access:
                return project_access(cur, actor, project, full_view_roles)
            return project

        register_document_access_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_resource_company_actor": resolve_resource,
            "resolve_project_parent": resolve_project,
            "require_project_parent_access": require_project,
            "project_full_view_roles": ("директор", "зам_директора"),
            "leadership_roles": ("директор", "зам_директора"),
            "platform_staff_roles": (),
            "client_account_roles": (),
            "upload_dir": upload_dir,
            "s3_prefixes": ("uploads",),
            "s3_urls_for_key": lambda _key: ("https://storage.example/file.png",),
            "s3_enabled": lambda: s3_enabled,
            "open_local_file": lambda file_url: open_document_local_file(upload_dir, file_url, 1024),
            "delete_local_file": lambda file_url, missing_ok=False: delete_document_local_file(
                upload_dir,
                file_url,
                missing_ok=missing_ok,
            ),
            "open_s3_object": s3_reader or (lambda _key: (io.BytesIO(b"s3-content"), len(b"s3-content"))),
            "max_upload_bytes": 1024,
            "delete_s3_object": s3_deleter or (lambda key: s3_delete_calls.append(key)),
        })
        return app, resolver_calls, project_calls, access_calls, s3_delete_calls

    def test_metadata_read_uses_stored_company_and_project(self):
        with TemporaryDirectory() as upload_dir:
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": 17,
                "file_url": "/uploads/company-4-project-17-project-documents/project-documents/file.png",
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
            self.assertEqual(response["contentUrl"], "/tenant-files/31/content")
            self.assertEqual(resolver_calls[0][2:4], (4, "read"))
            self.assertEqual(project_calls[0][2], {"project_id": 17})
            self.assertEqual(access_calls[0][1], "Лицей")
            self.assertIsNotNone(connection.cursor_factory)
            self.assertTrue(connection.closed)

    def test_uploader_can_delete_local_file(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/file.png",
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
            self.assertEqual(connection.commit_count, 2)

    def test_non_owner_cannot_delete_file(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/file.png",
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
            "storage_key": "uploads/company-4-common-general/general/file.png",
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

    def test_local_content_read_uses_stored_company_and_project(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-project-17-general" / "general" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png-content")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": 17,
                "file_url": "/uploads/company-4-project-17-general/general/file.png",
                "storage_key": "",
                "original_name": "photo report.png",
                "content_type": "image/png",
                "uploaded_by_id": 9,
            })
            app, resolver_calls, project_calls, access_calls, _ = self._register(connection, upload_dir)

            response = app.routes[("GET", "/tenant-files/{file_id}/content")](
                31,
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 9, "role": "прораб"},
            )

            self.assertIsInstance(response, StreamingResponse)
            self.assertEqual(response_body(response), b"png-content")
            self.assertEqual(response.media_type, "image/png")
            self.assertEqual(response.headers["content-length"], str(len(b"png-content")))
            self.assertEqual(response.headers["cache-control"], "private, no-store")
            self.assertEqual(response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(response.headers["content-security-policy"], "sandbox; default-src 'none'")
            self.assertEqual(response.headers["cross-origin-resource-policy"], "same-origin")
            self.assertIn("photo%20report.png", response.headers["content-disposition"])
            self.assertEqual(resolver_calls[0][2:4], (4, "read"))
            self.assertEqual(project_calls[0][2], {"project_id": 17})
            self.assertEqual(access_calls[0][1], "Лицей")

    def test_s3_content_read_returns_authorized_bytes(self):
        s3_read_calls = []

        def read_s3_object(key):
            s3_read_calls.append(key)
            return io.BytesIO(b"png-content"), len(b"png-content")

        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-common-general/general/file.png",
            "original_name": "photo.png",
            "content_type": "application/octet-stream",
            "uploaded_by_id": 9,
        })
        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            s3_enabled=True,
            s3_reader=read_s3_object,
        )

        response = app.routes[("GET", "/tenant-files/{file_id}/content")](
            31,
            current_user={"id": 9, "role": "прораб"},
        )

        self.assertIsInstance(response, StreamingResponse)
        self.assertEqual(response_body(response), b"png-content")
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["content-length"], str(len(b"png-content")))
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(s3_read_calls, ["uploads/company-4-common-general/general/file.png"])

    def test_active_content_is_downloaded_instead_of_opened_inline(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-common-general" / "general" / "attack.html"
            local_file.parent.mkdir(parents=True)
            local_file.write_text("<script>alert(1)</script>", encoding="utf-8")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/attack.html",
                "storage_key": "",
                "original_name": "../attack.html",
                "content_type": "text/html",
                "uploaded_by_id": 9,
            })
            app, _, _, _, _ = self._register(connection, upload_dir)

            response = app.routes[("GET", "/tenant-files/{file_id}/content")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

            self.assertIsInstance(response, StreamingResponse)
            self.assertEqual(response_body(response), b"<script>alert(1)</script>")
            self.assertEqual(response.media_type, "application/octet-stream")
            self.assertTrue(response.headers["content-disposition"].startswith("attachment;"))
            self.assertNotIn("..%2F", response.headers["content-disposition"])

    def test_content_read_stops_when_stored_company_is_not_authorized(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png-content")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/file.png",
                "storage_key": "",
                "original_name": "photo.png",
                "content_type": "image/png",
                "uploaded_by_id": 9,
            })

            def reject_company(*_args, **_kwargs):
                raise HTTPException(status_code=403, detail="Нет доступа к выбранной компании")

            app, _, _, _, _ = self._register(connection, upload_dir, resolver=reject_company)

            with self.assertRaises(HTTPException) as raised:
                app.routes[("GET", "/tenant-files/{file_id}/content")](
                    31,
                    current_user={"id": 10, "role": "прораб"},
                )

            self.assertEqual(raised.exception.status_code, 403)
            self.assertTrue(connection.closed)

    def test_missing_local_content_returns_not_found(self):
        with TemporaryDirectory() as upload_dir:
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/missing.png",
                "storage_key": "",
                "uploaded_by_id": 9,
            })
            app, _, _, _, _ = self._register(connection, upload_dir)

            with self.assertRaises(HTTPException) as raised:
                app.routes[("GET", "/tenant-files/{file_id}/content")](
                    31,
                    current_user={"id": 9, "role": "прораб"},
                )

            self.assertEqual(raised.exception.status_code, 404)

    def test_s3_content_read_fails_closed_when_s3_is_unavailable(self):
        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-common-general/general/file.png",
            "uploaded_by_id": 9,
        })
        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            s3_enabled=False,
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/tenant-files/{file_id}/content")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 503)

    def test_content_is_not_read_before_company_authorization(self):
        s3_read_calls = []

        def deny_other_company(_cur, _user, _company_id, _action_mode, **_kwargs):
            raise HTTPException(status_code=403, detail="Нет доступа к компании файла")

        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-common-general/general/file.png",
            "original_name": "photo.png",
            "uploaded_by_id": 9,
        })
        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            resolver=deny_other_company,
            s3_enabled=True,
            s3_reader=lambda key: s3_read_calls.append(key),
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/tenant-files/{file_id}/content")](
                31,
                current_user={"id": 10, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(s3_read_calls, [])

    def test_content_is_not_read_when_project_assignment_is_ambiguous(self):
        s3_read_calls = []

        def reject_ambiguous_project(_cur, _actor, _project, _full_view_roles):
            raise HTTPException(status_code=409, detail="Назначение объекта неоднозначно")

        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": 17,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-project-17-general/general/file.png",
            "context": "general",
            "original_name": "photo.png",
            "uploaded_by_id": 9,
        })
        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            project_access=reject_ambiguous_project,
            s3_enabled=True,
            s3_reader=lambda key: s3_read_calls.append(key),
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/tenant-files/{file_id}/content")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(s3_read_calls, [])

    def test_mismatched_storage_namespace_is_neither_read_nor_deleted(self):
        for method, route in (
            ("GET", "/tenant-files/{file_id}"),
            ("GET", "/tenant-files/{file_id}/content"),
            ("DELETE", "/tenant-files/{file_id}"),
        ):
            with self.subTest(method=method):
                s3_read_calls = []
                connection = FakeConnection({
                    "id": 31,
                    "company_id": 4,
                    "project_id": None,
                    "file_url": "https://storage.example/file.png",
                    "storage_key": "uploads/company-5-common-general/general/file.png",
                    "context": "general",
                    "original_name": "photo.png",
                    "uploaded_by_id": 9,
                })
                app, _, _, _, s3_delete_calls = self._register(
                    connection,
                    "/tmp/uploads",
                    s3_enabled=True,
                    s3_reader=lambda key: s3_read_calls.append(key),
                )

                with self.assertRaises(HTTPException) as raised:
                    app.routes[(method, route)](
                        31,
                        current_user={"id": 9, "role": "прораб"},
                    )

                self.assertEqual(raised.exception.status_code, 409)
                self.assertEqual(s3_read_calls, [])
                self.assertEqual(s3_delete_calls, [])

    def test_first_delete_commit_failure_keeps_physical_file(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/file.png",
                "storage_key": "",
                "uploaded_by_id": 9,
            }, fail_commit_numbers={1})
            app, _, _, _, _ = self._register(connection, upload_dir)

            with self.assertRaises(RuntimeError):
                app.routes[("DELETE", "/tenant-files/{file_id}")](
                    31,
                    current_user={"id": 9, "role": "прораб"},
                )

            self.assertTrue(local_file.exists())
            self.assertFalse(any(call[0].startswith("DELETE FROM file_ownership") for call in connection.cursor_value.calls))

    def test_final_delete_commit_failure_is_retryable_after_file_is_gone(self):
        with TemporaryDirectory() as upload_dir:
            local_file = Path(upload_dir) / "company-4-common-general" / "general" / "file.png"
            local_file.parent.mkdir(parents=True)
            local_file.write_bytes(b"png")
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/file.png",
                "storage_key": "",
                "uploaded_by_id": 9,
            }, fail_commit_numbers={2})
            app, _, _, _, _ = self._register(connection, upload_dir)

            with self.assertRaises(RuntimeError):
                app.routes[("DELETE", "/tenant-files/{file_id}")](
                    31,
                    current_user={"id": 9, "role": "прораб"},
                )
            self.assertFalse(local_file.exists())
            connection.cursor_value.row["deletion_status"] = "deleting"

            response = app.routes[("DELETE", "/tenant-files/{file_id}")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )
            self.assertTrue(response["ok"])
            self.assertEqual(connection.commit_count, 4)

    def test_first_delete_does_not_forget_missing_local_file(self):
        with TemporaryDirectory() as upload_dir:
            connection = FakeConnection({
                "id": 31,
                "company_id": 4,
                "project_id": None,
                "file_url": "/uploads/company-4-common-general/general/missing.png",
                "storage_key": "",
                "uploaded_by_id": 9,
                "deletion_status": "active",
            })
            app, _, _, _, _ = self._register(connection, upload_dir)

            with self.assertRaises(HTTPException) as raised:
                app.routes[("DELETE", "/tenant-files/{file_id}")](
                    31,
                    current_user={"id": 9, "role": "прораб"},
                )

            self.assertEqual(raised.exception.status_code, 409)
            sql_calls = [call[0] for call in connection.cursor_value.calls]
            self.assertTrue(any("deletion_status='cleanup_failed'" in sql for sql in sql_calls))
            self.assertFalse(any(sql.startswith("DELETE FROM file_ownership") for sql in sql_calls))

    def test_first_delete_does_not_forget_missing_s3_file(self):
        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-common-general/general/file.png",
            "uploaded_by_id": 9,
            "deletion_status": "active",
        })
        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            s3_enabled=True,
            s3_deleter=lambda _key: False,
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("DELETE", "/tenant-files/{file_id}")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 409)
        sql_calls = [call[0] for call in connection.cursor_value.calls]
        self.assertTrue(any("deletion_status='cleanup_failed'" in sql for sql in sql_calls))
        self.assertFalse(any(sql.startswith("DELETE FROM file_ownership") for sql in sql_calls))

    def test_storage_failure_is_recorded_for_retry(self):
        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-common-general/general/file.png",
            "uploaded_by_id": 9,
        })

        def fail_s3_delete(_key):
            raise HTTPException(status_code=502, detail="storage failed")

        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            s3_enabled=True,
            s3_deleter=fail_s3_delete,
        )
        with self.assertRaises(HTTPException) as raised:
            app.routes[("DELETE", "/tenant-files/{file_id}")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 502)
        sql_calls = [call[0] for call in connection.cursor_value.calls]
        self.assertTrue(any("deletion_status='deleting'" in sql for sql in sql_calls))
        self.assertTrue(any("deletion_status='cleanup_failed'" in sql for sql in sql_calls))
        self.assertFalse(any(sql.startswith("DELETE FROM file_ownership") for sql in sql_calls))
        self.assertEqual(connection.commit_count, 2)

    def test_deleting_file_cannot_be_read(self):
        s3_read_calls = []
        connection = FakeConnection({
            "id": 31,
            "company_id": 4,
            "project_id": None,
            "file_url": "https://storage.example/file.png",
            "storage_key": "uploads/company-4-common-general/general/file.png",
            "original_name": "photo.png",
            "uploaded_by_id": 9,
            "deletion_status": "deleting",
        })
        app, _, _, _, _ = self._register(
            connection,
            "/tmp/uploads",
            s3_enabled=True,
            s3_reader=lambda key: s3_read_calls.append(key),
        )

        with self.assertRaises(HTTPException) as raised:
            app.routes[("GET", "/tenant-files/{file_id}/content")](
                31,
                current_user={"id": 9, "role": "прораб"},
            )

        self.assertEqual(raised.exception.status_code, 410)
        self.assertEqual(s3_read_calls, [])


if __name__ == "__main__":
    unittest.main()
