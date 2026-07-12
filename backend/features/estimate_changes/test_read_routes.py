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
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return {"id": 77}

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class EstimateChangeReadRouteTests(unittest.TestCase):
    def _register(self, connection, actors, *, context_error=None):
        app = FakeApp()
        calls = {"context": []}

        def resolve_context(cur, user, requested_company_id, action_mode, **kwargs):
            calls["context"].append((cur, user, requested_company_id, action_mode, kwargs))
            if context_error:
                raise context_error
            return {"mode": kwargs.get("x_company_mode") or "company"}

        register_estimate_changes_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: list(actors),
            "require_project_write_actor": lambda company_actors, _roles: list(company_actors)[0],
            "require_project_row_company": lambda _actor, company_id: company_id,
            "resolve_project_parent": lambda _cur, _actor, **_kwargs: {
                "id": 14,
                "companyId": 4,
                "name": "Лицей",
            },
            "require_project_parent_access": lambda _cur, _actor, project, _roles: project,
            "resolve_estimate_parent": lambda _cur, _actor, estimate_id: {
                "id": estimate_id,
                "companyId": 4,
                "projectId": 14,
            },
            "has_package_access": lambda _actor, _package: True,
            "visibility_filter": estimate_change_visibility_filter,
            "project_document_roles": (
                "директор",
                "зам_директора",
                "бухгалтер",
                "прораб",
                "главный_инженер",
                "сметчик",
                "мастер",
                "субподрядчик",
                "бригадир",
                "кладовщик",
                "снабженец",
                "технадзор",
                "заказчик",
                "стройконтроль",
            ),
            "journal_write_roles": ("директор", "прораб", "мастер"),
            "project_write_roles": ("директор", "зам_директора", "прораб", "главный_инженер", "сметчик"),
            "full_view_roles": ("директор", "зам_директора", "бухгалтер", "главный_инженер", "сметчик"),
            "package_limit_roles": ("прораб", "мастер", "субподрядчик", "бригадир"),
            "package_unrestricted_roles": ("прораб",),
            "customer_roles": ("заказчик",),
            "customer_statuses": (
                "Ожидает согласования",
                "Утверждено",
                "Утверждено отдельной допработой",
                "Включено в новую смету",
            ),
            "worker_execution_roles": ("мастер", "субподрядчик", "бригадир"),
            "approved_statuses": ("Утверждено", "Утверждено отдельной допработой"),
            "leadership_roles": ("директор", "зам_директора"),
            "estimate_write_roles": ("директор", "зам_директора", "прораб", "главный_инженер", "сметчик"),
            "log_audit": lambda **_kwargs: None,
        })
        return app.routes[("GET", "/unexpected-works")], calls

    @staticmethod
    def _row(company_id, row_id, price=250, total=500):
        return {
            "id": row_id,
            "project_name": "Лицей",
            "description": "Дополнительная работа",
            "unit": "шт",
            "quantity": 2,
            "price": price,
            "total": total,
            "added_by": "Иванов",
            "added_by_role": "мастер",
            "status": "Ожидает согласования",
            "approved_by": "",
            "approved_at": None,
            "notes": "",
            "photo_url": "",
            "change_type": "Работа вне сметы",
            "estimate_id": None,
            "section_name": "Основная",
            "estimate_item_name": "",
            "base_quantity": 0,
            "new_required_quantity": 2,
            "delta_quantity": 2,
            "included_in_estimate_id": None,
            "reason": "",
            "company_id": company_id,
        }

    def test_selected_company_read_uses_only_stored_owner_join(self):
        cursor = FakeCursor(rows=[self._row(4, 11)])
        connection = FakeConnection(cursor)
        handler, calls = self._register(connection, [{"companyId": 4, "role": "директор"}])

        response = handler(
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "account_owner"},
        )

        self.assertEqual(calls["context"][0][3], "read")
        self.assertEqual(calls["context"][0][4], {
            "x_company_id": "4",
            "x_company_mode": "company",
        })
        sql, params = cursor.calls[0]
        self.assertIn("JOIN projects p ON p.id=uw.project_id AND p.company_id=uw.company_id", sql)
        self.assertNotIn("uw.project_name = ANY", sql)
        self.assertNotIn("uw.company_id IS NULL", sql)
        self.assertIn("ORDER BY uw.id DESC", sql)
        self.assertEqual(params, (4,))
        self.assertEqual(response[0]["id"], 11)
        self.assertEqual(response[0]["projectName"], "Лицей")
        self.assertEqual(response[0]["price"], 250.0)
        self.assertEqual(set(response[0]), {
            "id", "projectName", "description", "unit", "quantity", "price", "total",
            "addedBy", "addedByRole", "status", "approvedBy", "approvedAt", "notes",
            "photoUrl", "changeType", "estimateId", "sectionName", "estimateItemName",
            "baseQuantity", "newRequiredQuantity", "deltaQuantity", "includedInEstimateId",
            "reason",
        })
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_all_companies_masks_money_by_effective_row_role(self):
        cursor = FakeCursor(rows=[self._row(4, 11), self._row(8, 12)])
        connection = FakeConnection(cursor)
        handler, _calls = self._register(connection, [
            {"companyId": 4, "role": "директор"},
            {
                "companyId": 8,
                "role": "мастер",
                "assignedProjects": ["Лицей"],
                "assignedPackages": ["Основная"],
            },
        ])

        response = handler(
            x_company_id=None,
            x_company_mode="all_companies",
            current_user={"id": 9, "role": "директор"},
        )

        by_id = {row["id"]: row for row in response}
        self.assertEqual(by_id[11]["price"], 250.0)
        self.assertEqual(by_id[11]["total"], 500.0)
        self.assertEqual(by_id[12]["price"], 0)
        self.assertEqual(by_id[12]["total"], 0)
        self.assertEqual(cursor.calls[0][1], (4, 8, ["Лицей"], ["Основная"]))

    def test_row_without_effective_company_actor_is_not_returned(self):
        cursor = FakeCursor(rows=[self._row(99, 77)])
        connection = FakeConnection(cursor)
        handler, _calls = self._register(connection, [{"companyId": 4, "role": "директор"}])

        response = handler(
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 9, "role": "директор"},
        )

        self.assertEqual(response, [])

    def test_non_document_membership_fails_closed(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        handler, _calls = self._register(connection, [{
            "companyId": 4,
            "role": "поставщик",
            "assignedProjects": ["Лицей"],
        }])

        response = handler(
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 14, "role": "поставщик"},
        )

        self.assertEqual(response, [])
        self.assertIn("WHERE FALSE", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], ())

    def test_unavailable_company_rejection_closes_connection(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        handler, _calls = self._register(
            connection,
            [],
            context_error=HTTPException(status_code=403, detail="Нет доступа к выбранной компании"),
        )

        with self.assertRaises(HTTPException) as raised:
            handler(
                x_company_id="99",
                x_company_mode="company",
                current_user={"id": 9, "role": "account_owner"},
            )

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(cursor.calls, [])
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
