import unittest

from fastapi import HTTPException

from backend.features.estimate_changes.routes import register_estimate_changes_module
from backend.features.estimate_changes.service import estimate_change_visibility_filter


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._route("GET", path)

    def post(self, path):
        return self._route("POST", path)

    def put(self, path):
        return self._route("PUT", path)

    def delete(self, path):
        return self._route("DELETE", path)

    def _route(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, row=None, *, existing_journal=None, fail_journal_insert=False):
        self.row = row
        self.existing_journal = existing_journal
        self.fail_journal_insert = fail_journal_insert
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        normalized_sql = " ".join(sql.split())
        self.calls.append((normalized_sql, tuple(params)))
        if self.fail_journal_insert and "INSERT INTO work_journal" in normalized_sql:
            raise RuntimeError("journal unavailable")

    def fetchone(self):
        sql = self.calls[-1][0] if self.calls else ""
        if "FROM unexpected_works" in sql and "FOR UPDATE" in sql:
            return self.row
        if "SELECT id FROM work_journal" in sql:
            return self.existing_journal
        if "INSERT INTO work_journal" in sql:
            return {"id": 901}
        if "UPDATE unexpected_works" in sql and "RETURNING id" in sql:
            return {"id": (self.row or {}).get("id")}
        return None

    def fetchall(self):
        return []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class EstimateChangeMutationRouteTests(unittest.TestCase):
    @staticmethod
    def _row(**overrides):
        row = {
            "id": 21,
            "company_id": 4,
            "project_id": 14,
            "project_name": "Alpha",
            "status": "Ожидает согласования",
            "description": "Дополнительная работа",
            "unit": "шт",
            "quantity": 2,
            "added_by": "Мастер",
            "change_type": "Работа вне сметы",
        }
        row.update(overrides)
        return row

    def _register(
        self,
        connection,
        *,
        actors=None,
        context_error=None,
        project=None,
        estimates=None,
    ):
        app = FakeApp()
        audit_calls = []
        selected_actors = actors if actors is not None else [{
            "id": 9,
            "name": "Директор Alpha",
            "role": "директор",
            "companyId": 4,
            "assignedProjects": [],
            "assignedPackages": [],
        }]
        selected_project = project or {"id": 14, "companyId": 4, "name": "Alpha"}
        estimate_rows = estimates or {
            100: {
                "id": 100,
                "companyId": 4,
                "projectId": 14,
                "projectName": "Alpha",
            },
        }

        def resolve_context(_cur, _user, _requested_company_id, _action_mode, **_kwargs):
            if context_error:
                raise context_error
            return {"mode": "company", "companyId": 4, "companyIds": [4]}

        def require_write_actor(company_actors, allowed_roles):
            normalized = list(company_actors or [])
            if len(normalized) != 1:
                raise HTTPException(status_code=409, detail="Выберите одну компанию")
            actor = normalized[0]
            if actor.get("role") not in set(allowed_roles or ()):
                raise HTTPException(status_code=403, detail="Роль не может менять допработу")
            return actor

        def require_row_company(actor, stored_company_id):
            if not stored_company_id:
                raise HTTPException(status_code=409, detail="Компания изменения не определена")
            if int(actor.get("companyId") or 0) != int(stored_company_id):
                raise HTTPException(status_code=403, detail="Изменение относится к другой компании")
            return int(stored_company_id)

        def resolve_estimate(_cur, _actor, estimate_id, **_kwargs):
            estimate = estimate_rows.get(estimate_id)
            if not estimate:
                raise HTTPException(status_code=404, detail="Смета не найдена")
            return estimate

        register_estimate_changes_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: list(selected_actors),
            "require_project_write_actor": require_write_actor,
            "require_project_row_company": require_row_company,
            "resolve_project_parent": lambda _cur, _actor, **_kwargs: selected_project,
            "require_project_parent_access": lambda _cur, _actor, parent, _roles: parent,
            "resolve_estimate_parent": resolve_estimate,
            "has_package_access": lambda _actor, _package: True,
            "visibility_filter": estimate_change_visibility_filter,
            "project_document_roles": ("директор", "прораб", "мастер", "заказчик"),
            "journal_write_roles": ("директор", "прораб", "мастер"),
            "project_write_roles": ("директор", "зам_директора", "прораб", "главный_инженер", "сметчик"),
            "full_view_roles": ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
            "package_limit_roles": ("прораб", "мастер", "субподрядчик", "бригадир"),
            "package_unrestricted_roles": ("прораб",),
            "customer_roles": ("заказчик",),
            "customer_statuses": ("Ожидает согласования", "Утверждено"),
            "worker_execution_roles": ("мастер", "субподрядчик", "бригадир"),
            "approved_statuses": ("Утверждено", "Утверждено отдельной допработой"),
            "leadership_roles": ("директор", "зам_директора"),
            "estimate_write_roles": ("директор", "зам_директора", "прораб", "главный_инженер", "сметчик"),
            "log_audit": lambda **kwargs: audit_calls.append(kwargs),
        })
        return app, audit_calls

    @staticmethod
    def _call(app, method, payload=None, *, company_id="4", company_mode="company", user=None):
        handler = app.routes[(method, "/unexpected-works/{id}")]
        kwargs = {
            "id": 21,
            "x_company_id": company_id,
            "x_company_mode": company_mode,
            "current_user": user or {"id": 9, "name": "Глобальный владелец", "role": "account_owner"},
        }
        if method == "PUT":
            kwargs["data"] = payload or {}
        return handler(**kwargs)

    def test_update_uses_stored_owner_and_copies_company_to_auto_journal(self):
        cursor = FakeCursor(self._row())
        connection = FakeConnection(cursor)
        app, audit_calls = self._register(connection)

        response = self._call(app, "PUT", {
            "status": "Утверждено",
            "price": 125,
            "total": 250,
            "approvedBy": "Подмена имени",
            "approvedAt": "2026-07-12",
        })

        lock_sql, lock_params = cursor.calls[0]
        self.assertIn("FROM unexpected_works", lock_sql)
        self.assertIn("FOR UPDATE", lock_sql)
        self.assertEqual(lock_params, (21,))
        update_sql, update_params = next(call for call in cursor.calls if "UPDATE unexpected_works" in call[0])
        self.assertIn("company_id=%s", update_sql)
        self.assertIn("project_id=%s", update_sql)
        self.assertEqual(update_params[-3:], (21, 4, 14))
        journal_sql, journal_params = next(call for call in cursor.calls if "INSERT INTO work_journal" in call[0])
        self.assertIn("(company_id,", journal_sql)
        self.assertEqual(journal_params[0], 4)
        self.assertEqual(journal_params[3], "Alpha")
        self.assertEqual(response, {"ok": True, "journalId": 901})
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertEqual(audit_calls[0]["user_name"], "Директор Alpha")
        self.assertEqual(audit_calls[0]["user_role"], "директор")

    def test_update_rejects_cross_company_direct_id_before_write(self):
        cursor = FakeCursor(self._row(company_id=8, project_id=88, project_name="Other"))
        connection = FakeConnection(cursor)
        app, _audit_calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "PUT", {"status": "Утверждено", "price": 10, "total": 20})

        self.assertEqual(raised.exception.status_code, 403)
        self.assertFalse(any("UPDATE unexpected_works" in sql for sql, _ in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_update_keeps_status_change_when_best_effort_journal_insert_fails(self):
        cursor = FakeCursor(self._row(), fail_journal_insert=True)
        connection = FakeConnection(cursor)
        app, _audit_calls = self._register(connection)

        response = self._call(app, "PUT", {
            "status": "Утверждено",
            "price": 125,
            "total": 250,
        })

        sql_calls = [sql for sql, _params in cursor.calls]
        self.assertTrue(any("ROLLBACK TO SAVEPOINT estimate_change_journal" in sql for sql in sql_calls))
        self.assertTrue(any("RELEASE SAVEPOINT estimate_change_journal" in sql for sql in sql_calls))
        self.assertEqual(response, {"ok": True, "journalId": None})
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)

    def test_update_rejects_ownerless_row_fail_closed(self):
        cursor = FakeCursor(self._row(company_id=None, project_id=None))
        connection = FakeConnection(cursor)
        app, _audit_calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "PUT", {"status": "Отклонено"})

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any("UPDATE unexpected_works" in sql for sql, _ in cursor.calls))

    def test_update_rejects_all_companies_and_effective_non_writer(self):
        for actors, expected_status in (
            ([{"companyId": 4, "role": "директор"}, {"companyId": 8, "role": "директор"}], 409),
            ([{"companyId": 4, "role": "мастер", "name": "Мастер"}], 403),
        ):
            with self.subTest(actors=actors):
                cursor = FakeCursor(self._row())
                connection = FakeConnection(cursor)
                app, _audit_calls = self._register(connection, actors=actors)

                with self.assertRaises(HTTPException) as raised:
                    self._call(
                        app,
                        "PUT",
                        {"status": "Утверждено"},
                        company_id=None if len(actors) > 1 else "4",
                        company_mode="all_companies" if len(actors) > 1 else "company",
                    )

                self.assertEqual(raised.exception.status_code, expected_status)
                self.assertEqual(cursor.calls, [])
                self.assertTrue(connection.rolled_back)

    def test_update_rejects_included_estimate_from_another_project(self):
        cursor = FakeCursor(self._row())
        connection = FakeConnection(cursor)
        app, _audit_calls = self._register(connection, estimates={
            100: {"id": 100, "companyId": 4, "projectId": 99, "projectName": "Other"},
        })

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "PUT", {"status": "Включено в новую смету", "includedInEstimateId": 100})

        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(any("UPDATE unexpected_works" in sql for sql, _ in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_delete_soft_annuls_only_the_stored_owner_row(self):
        cursor = FakeCursor(self._row())
        connection = FakeConnection(cursor)
        app, _audit_calls = self._register(connection)

        response = self._call(app, "DELETE")

        update_sql, update_params = next(call for call in cursor.calls if "UPDATE unexpected_works" in call[0])
        self.assertIn("status='Аннулировано'", update_sql)
        self.assertIn("company_id=%s", update_sql)
        self.assertIn("project_id=%s", update_sql)
        self.assertEqual(update_params, (21, 4, 14))
        self.assertEqual(response, {"ok": True})
        self.assertTrue(connection.committed)

    def test_delete_rejects_unavailable_company_without_row_lookup(self):
        cursor = FakeCursor(self._row())
        connection = FakeConnection(cursor)
        app, _audit_calls = self._register(
            connection,
            context_error=HTTPException(status_code=403, detail="Нет доступа к выбранной компании"),
        )

        with self.assertRaises(HTTPException) as raised:
            self._call(app, "DELETE", company_id="99")

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
