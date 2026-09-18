import unittest

from fastapi import HTTPException

from backend.features.supplier_documents.routes import register_supplier_documents_module


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


def build(cursor, own_ids=(), related=None, company_id=12, effective_role=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    register_supplier_documents_module(app, {
        "get_db": lambda: connection,
        "get_current_user": lambda: {},
        "current_supplier_ids": lambda cur, user: list(own_ids),
        "supplier_related_ids": lambda cur, sid: related or [sid],
        "resolve_work_company_context": lambda cur, user, requested=None, action="read", **kw: {
            "mode": "company", "companyId": company_id,
            "role": effective_role or user.get("role"),
        },
        "effective_company_actors": lambda user, context: [{
            **user, "companyId": context["companyId"], "role": context["role"],
        }],
    })
    return app, connection


class SupplierDocumentsTest(unittest.TestCase):
    def test_supplier_cannot_claim_customer_company_on_upload(self):
        cursor = FakeCursor()
        app, _ = build(cursor, own_ids=[5])
        with self.assertRaises(HTTPException) as error:
            app.routes[("POST", "/supplier-documents")](
                {"supplierId": 5, "companyId": 12}, current_user={"role": "поставщик"})
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(cursor.calls)

    def test_supplier_cannot_archive_customer_owned_document(self):
        cursor = FakeCursor(fetchone_results=[(5, 12)])
        app, _ = build(cursor, own_ids=[5])
        with self.assertRaises(HTTPException) as error:
            app.routes[("DELETE", "/supplier-documents/{id}")](id=1, current_user={"role": "поставщик"})
        self.assertEqual(error.exception.status_code, 403)

    def test_archive_preserves_row_and_commits(self):
        cursor = FakeCursor(fetchone_results=[(5, 12)])
        app, conn = build(cursor)
        result = app.routes[("DELETE", "/supplier-documents/{id}")](id=1, current_user={"role": "бухгалтер"})
        self.assertTrue(result['archived'])
        self.assertIn('UPDATE supplier_documents SET archived_at=NOW()', cursor.calls[-1][0])
        self.assertTrue(conn.committed)

    def test_foreign_company_file_cannot_be_attached(self):
        cursor = FakeCursor(fetchone_results=[(5,), (99, None)])
        app, conn = build(cursor)
        with self.assertRaises(HTTPException) as error:
            app.routes[("POST", "/supplier-documents")](
                {"supplierId": 5, "fileUrl": "/tenant-files/7/content"},
                current_user={"role": "бухгалтер"})
        self.assertEqual(error.exception.status_code, 403)
        self.assertFalse(conn.committed)

    def test_project_file_cannot_escape_project_scope_via_company_archive(self):
        cursor = FakeCursor(fetchone_results=[(5,), (12, 44)])
        app, conn = build(cursor)
        with self.assertRaises(HTTPException) as error:
            app.routes[("POST", "/supplier-documents")](
                {"supplierId": 5, "fileUrl": "/tenant-files/7/content"},
                current_user={"role": "бухгалтер"})
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(conn.committed)

    def test_raw_storage_url_is_rejected(self):
        cursor = FakeCursor(fetchone_results=[(5,)])
        app, conn = build(cursor)
        with self.assertRaises(HTTPException):
            app.routes[("POST", "/supplier-documents")](
                {"supplierId": 5, "fileUrl": "/uploads/other-company.pdf"},
                current_user={"role": "бухгалтер"})
        self.assertFalse(conn.committed)

    def test_invalid_supplier_id_is_a_client_error(self):
        for value in [True, -1, 'abc', 1.5, None]:
            with self.subTest(value=value):
                app, _ = build(FakeCursor())
                with self.assertRaises(HTTPException) as error:
                    app.routes[("POST", "/supplier-documents")](
                        {"supplierId": value}, current_user={"role": "бухгалтер"})
                self.assertEqual(error.exception.status_code, 400)

    def test_company_archive_is_scoped_even_without_supplier_filter(self):
        cursor = FakeCursor()
        app, _ = build(cursor)
        app.routes[("GET", "/supplier-documents")](supplier_id=None, current_user={"role": "бухгалтер"})
        self.assertIn("company_id = ANY(%s)", cursor.calls[-1][0])
        self.assertIn([12], cursor.calls[-1][1])

    def test_company_role_not_global_role_controls_read(self):
        cursor = FakeCursor()
        app, _ = build(cursor, effective_role="мастер")
        rows = app.routes[("GET", "/supplier-documents")](supplier_id=None, current_user={"role": "директор"})
        self.assertEqual(rows, [])
        self.assertFalse(cursor.calls)

    def test_cannot_delete_another_company_document(self):
        cursor = FakeCursor(fetchone_results=[(5, 99)])
        app, _ = build(cursor)
        with self.assertRaises(HTTPException) as error:
            app.routes[("DELETE", "/supplier-documents/{id}")](id=1, current_user={"role": "бухгалтер"})
        self.assertEqual(error.exception.status_code, 403)
        self.assertFalse(any(sql.startswith("DELETE") for sql, _ in cursor.calls))

    def test_unassigned_legacy_document_cannot_be_deleted_by_customer(self):
        cursor = FakeCursor(fetchone_results=[(5, None)])
        app, _ = build(cursor)
        with self.assertRaises(HTTPException):
            app.routes[("DELETE", "/supplier-documents/{id}")](id=1, current_user={"role": "директор"})
        self.assertFalse(any(sql.startswith("DELETE") for sql, _ in cursor.calls))

    def test_create_uses_selected_company_and_server_actor(self):
        cursor = FakeCursor(fetchone_results=[(5,), (81,)])
        app, _ = build(cursor)
        app.routes[("POST", "/supplier-documents")](
            {"supplierId": 5, "title": "Договор", "uploadedBy": "Другой сотрудник"},
            current_user={"role": "бухгалтер", "name": "Анна"},
        )
        sql, params = cursor.calls[-1]
        self.assertIn("company_id", sql)
        self.assertIn(12, params)
        self.assertIn("Анна", params)
        self.assertNotIn("Другой сотрудник", params)

    def test_all_urls_registered(self):
        app, _conn = build(FakeCursor())
        for key in [("GET", "/supplier-documents"), ("POST", "/supplier-documents"),
                    ("DELETE", "/supplier-documents/{id}")]:
            self.assertIn(key, app.routes)

    def test_supplier_reads_only_own_documents(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, own_ids=[5])
        app.routes[("GET", "/supplier-documents")](supplier_id=None, current_user={"role": "поставщик"})
        self.assertIn("WHERE supplier_id = ANY(%s) AND company_id IS NULL", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ([5],))

    def test_read_widens_to_duplicate_group_for_admin(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor, related=[7, 99])
        app.routes[("GET", "/supplier-documents")](supplier_id=7, current_user={"role": "директор"})
        self.assertEqual(cursor.calls[0][1], ([12], [7, 99]))

    def test_supplier_cannot_upload_for_foreign_card(self):
        app, connection = build(FakeCursor(), own_ids=[5])
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("POST", "/supplier-documents")](
                {"supplierId": 9, "title": "Договор"}, current_user={"role": "поставщик"}
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse(connection.committed)

    def test_foreign_role_cannot_delete(self):
        app, _conn = build(FakeCursor())
        with self.assertRaises(HTTPException) as ctx:
            app.routes[("DELETE", "/supplier-documents/{id}")](id=1, current_user={"role": "мастер"})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
