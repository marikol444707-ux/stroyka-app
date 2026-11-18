import ast
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.company_context.service import effective_company_user
from backend.features.room_ownership.access import FULL_COMPANY_VIEW_ROLES
from backend.features.rooms.routes import RoomModel, register_rooms_module


ROOT = Path(__file__).resolve().parents[3]


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

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
        self.description = [("id",)]

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if "project_name" in normalized.lower():
            self.description = [("company_id",), ("project_id",), ("project_name",)]
        else:
            self.description = [("id",)]

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


class RequestHeaders:
    def __init__(self, headers):
        self.headers = headers


def company_context(company_id):
    return {
        "mode": "company",
        "companyId": company_id,
        "company_id": company_id,
        "role": "директор",
        "effectiveRole": "директор",
        "active": True,
        "companyActive": True,
        "assignedProjects": [],
    }


def build(cursor, ai_calls=None, company_id=4):
    app = FakeApp()
    connection = FakeConnection(cursor)
    ai_log = ai_calls if ai_calls is not None else []
    calls = []

    def resolve(_cur, user, _requested, action, x_company_id=None, x_company_mode=None):
        calls.append((action, x_company_id, x_company_mode, user.get("role")))
        if user.get("role") == "system_owner":
            raise HTTPException(status_code=403, detail="Платформенная роль не может выполнять рабочее действие без support-сессии компании")
        if x_company_mode == "all_companies" and action == "write":
            raise HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию")
        selected = int(x_company_id or company_id)
        if selected == 3:
            raise HTTPException(status_code=403, detail="Нет доступа к выбранной компании")
        return company_context(selected)

    register_rooms_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "read_roles": ("директор", "system_owner"),
        "write_roles": ("директор",),
        "resolve_work_company_context": resolve,
        "effective_company_actors": lambda user, context: [effective_company_user(user, context)],
        "full_view_roles": FULL_COMPANY_VIEW_ROLES,
        "platform_staff_roles": ("system_owner", "platform_admin", "platform_support", "billing_admin"),
        "run_project_ai_control_safely": lambda project, reason: ai_log.append((project, reason)),
    })
    return app, connection, calls


class RoomsRoutesTest(unittest.TestCase):
    def test_all_twelve_urls_registered(self):
        app, _conn, _calls = build(FakeCursor())
        expected = []
        for base in ("/rooms", "/room-windows", "/room-doors"):
            expected += [("GET", base), ("POST", base), ("PUT", base + "/{id}"), ("DELETE", base + "/{id}")]
        for key in expected:
            self.assertIn(key, app.routes)

    def test_room_list_is_limited_to_the_selected_company(self):
        cursor = FakeCursor(rows=[])
        app, _conn, _calls = build(cursor, company_id=2)
        app.routes[("GET", "/rooms")](
            current_user={"id": 1, "role": "директор"},
            request=RequestHeaders({"x-company-id": "2", "x-company-mode": "company"}),
        )
        sql, params = cursor.calls[0]
        self.assertIn("JOIN projects p ON p.id=r.project_id AND p.company_id=r.company_id", sql)
        self.assertIn("p.company_id=%s", sql)
        self.assertEqual(params, (2,))
        self.assertNotIn("project = ANY", sql)
        self.assertNotIn("IS NULL", sql)

    def test_same_project_name_uses_the_company_in_the_header(self):
        first = FakeCursor(rows=[])
        second = FakeCursor(rows=[])
        app, _conn, _calls = build(first)
        app.routes[("GET", "/rooms")](
            current_user={"id": 1, "role": "директор"},
            request=RequestHeaders({"x-company-id": "2"}),
        )
        build_second, _conn2, _calls2 = build(second)
        build_second.routes[("GET", "/rooms")](
            current_user={"id": 9, "role": "директор"},
            request=RequestHeaders({"x-company-id": "4"}),
        )
        self.assertEqual(first.calls[0][1], (2,))
        self.assertEqual(second.calls[0][1], (4,))

    def test_platform_review_sees_only_unowned_rows(self):
        cursor = FakeCursor(rows=[])
        app, _conn, calls = build(cursor)
        app.routes[("GET", "/rooms")](current_user={"id": 1, "role": "system_owner"})
        sql, params = cursor.calls[0]
        self.assertIn("r.company_id IS NULL", sql)
        self.assertNotIn("JOIN projects", sql)
        self.assertEqual(params, ())
        self.assertEqual(calls, [])

    def test_room_create_stores_verified_owner_and_recalculates(self):
        ai = []
        cursor = FakeCursor(rows=[(7, 4, "Объект")], fetchone_results=[{"id": 1, "project": "Объект", "name": "Кухня"}])
        app, _conn, _calls = build(cursor, ai_calls=ai)
        app.routes[("POST", "/rooms")](
            RoomModel(project="Объект", name="Кухня", projectId=None),
            _current_user={"id": 1, "role": "директор"},
            request=RequestHeaders({"x-company-id": "4"}),
        )
        insert = next(call for call in cursor.calls if call[0].startswith("INSERT INTO rooms"))
        self.assertEqual(insert[1][-2:], (4, 7))
        self.assertNotIn(99, insert[1])
        self.assertEqual(ai, [("Объект", "room:create")])

    def test_ambiguous_project_name_is_rejected(self):
        cursor = FakeCursor(rows=[(7, 4, "Объект"), (8, 4, "Объект")])
        app, _conn, _calls = build(cursor)
        with self.assertRaises(HTTPException) as error:
            app.routes[("POST", "/rooms")](
                RoomModel(project="Объект", name="Кухня"),
                _current_user={"id": 1, "role": "директор"},
            )
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(any(call[0].startswith("INSERT") for call in cursor.calls))

    def test_other_company_header_is_rejected_before_insert(self):
        cursor = FakeCursor(rows=[(7, 4, "Объект")])
        app, _conn, _calls = build(cursor)
        with self.assertRaises(HTTPException) as error:
            app.routes[("POST", "/rooms")](
                RoomModel(project="Объект", name="Кухня"),
                _current_user={"id": 1, "role": "директор"},
                request=RequestHeaders({"x-company-id": "3"}),
            )
        self.assertEqual(error.exception.status_code, 403)

    def test_all_companies_write_is_rejected(self):
        cursor = FakeCursor()
        app, _conn, _calls = build(cursor)
        with self.assertRaises(HTTPException) as error:
            app.routes[("POST", "/rooms")](
                RoomModel(project="Объект", name="Кухня"),
                _current_user={"id": 1, "role": "директор"},
                request=RequestHeaders({"x-company-mode": "all_companies"}),
            )
        self.assertEqual(error.exception.status_code, 400)

    def test_room_delete_cascades_children_after_owner_check(self):
        cursor = FakeCursor(fetchone_results=[(4, 7, "Объект")])
        app, _conn, _calls = build(cursor)
        result = app.routes[("DELETE", "/rooms/{id}")](
            id=5, _current_user={"id": 1, "role": "директор"},
        )
        self.assertEqual(result, {"ok": True})
        tables = [call[0].split("DELETE FROM ")[1].split(" ")[0] for call in cursor.calls if "DELETE FROM " in call[0]]
        self.assertEqual(tables, ["room_windows", "room_doors", "room_works", "rooms"])

    def test_window_create_copies_room_owner_and_ignores_forged_company(self):
        ai = []
        cursor = FakeCursor(fetchone_results=[(4, 7, "Объект"), (9, 5, "Окно")])
        app, connection, _calls = build(cursor, ai_calls=ai)
        app.routes[("POST", "/room-windows")](
            {"roomId": 5, "name": "Окно", "width": 1.2, "height": 1.4, "companyId": 99},
            _current_user={"id": 1, "role": "директор"},
        )
        self.assertTrue(connection.committed)
        insert = next(call for call in cursor.calls if "INSERT INTO room_windows" in call[0])
        self.assertEqual(insert[1][-2:], (4, 7))
        self.assertNotIn(99, insert[1])
        self.assertEqual(ai, [("Объект", "room_window:create")])

    def test_door_update_resolves_room_from_row_when_missing(self):
        cursor = FakeCursor(fetchone_results=[(5,), (4, 7, "Объект"), (4, 7, "Объект")])
        app, _conn, _calls = build(cursor)
        result = app.routes[("PUT", "/room-doors/{id}")](
            id=3, data={"name": "Дверь", "width": 0.9, "height": 2.1},
            _current_user={"id": 1, "role": "директор"},
        )
        self.assertEqual(result, {"ok": True})
        self.assertIn("SELECT room_id FROM room_doors WHERE id=%s", cursor.calls[0][0])

    def test_full_view_roles_match_company_wide_visibility(self):
        tree = ast.parse((ROOT / "backend" / "main.py").read_text(encoding="utf-8"))
        roles = None
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "can_see_all_company_data":
                roles = tuple(item.value for item in node.body[0].value.comparators[0].elts)
        self.assertEqual(roles, FULL_COMPANY_VIEW_ROLES)


if __name__ == "__main__":
    unittest.main()
