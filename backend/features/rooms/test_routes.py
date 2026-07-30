import unittest

from backend.features.rooms.routes import RoomModel, register_rooms_module


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


def build(cursor, ai_calls=None):
    app = FakeApp()
    connection = FakeConnection(cursor)
    ai_log = ai_calls if ai_calls is not None else []
    register_rooms_module(app, {
        "get_db": lambda: connection,
        "require_roles": lambda *roles: (lambda: None),
        "read_roles": ("директор",),
        "write_roles": ("директор",),
        "visible_project_names": lambda user: ["Объект"],
        "require_project_access": lambda user, project: None,
        "require_row_project_access": lambda cur, table, row_id, user, col: None,
        "require_room_access": lambda cur, room_id, user: None,
        "require_room_child_access": lambda cur, table, row_id, user: None,
        "run_project_ai_control_safely": lambda project, reason: ai_log.append((project, reason)),
    })
    return app, connection


class RoomsRoutesTest(unittest.TestCase):
    def test_all_twelve_urls_registered(self):
        app, _conn = build(FakeCursor())
        expected = []
        for base in ("/rooms", "/room-windows", "/room-doors"):
            expected += [("GET", base), ("POST", base), ("PUT", base + "/{id}"), ("DELETE", base + "/{id}")]
        for key in expected:
            self.assertIn(key, app.routes)

    def test_room_list_scopes_to_visible_projects(self):
        cursor = FakeCursor(rows=[])
        app, _conn = build(cursor)
        app.routes[("GET", "/rooms")](current_user={})
        self.assertIn("WHERE project = ANY(%s)", cursor.calls[0][0])

    def test_room_create_triggers_ai_recalc(self):
        ai = []
        cursor = FakeCursor(fetchone_results=[{"id": 1, "project": "Объект", "name": "Кухня"}])
        app, _conn = build(cursor, ai_calls=ai)
        app.routes[("POST", "/rooms")](RoomModel(project="Объект", name="Кухня"), _current_user={})
        self.assertEqual(ai, [("Объект", "room:create")])

    def test_room_delete_cascades_children(self):
        cursor = FakeCursor()
        app, _conn = build(cursor)
        result = app.routes[("DELETE", "/rooms/{id}")](id=5, _current_user={})
        self.assertEqual(result, {"ok": True})
        tables = [c[0].split("DELETE FROM ")[1].split(" ")[0] for c in cursor.calls]
        self.assertEqual(tables, ["room_windows", "room_doors", "room_works", "rooms"])

    def test_window_create_checks_room_access_and_recalcs(self):
        ai = []
        cursor = FakeCursor(fetchone_results=[(9, 5, "Окно"), ("Объект",)])
        app, connection = build(cursor, ai_calls=ai)
        app.routes[("POST", "/room-windows")](
            {"roomId": 5, "name": "Окно", "width": 1.2, "height": 1.4}, _current_user={}
        )
        self.assertTrue(connection.committed)
        self.assertEqual(ai, [("Объект", "room_window:create")])

    def test_door_update_resolves_room_from_row_when_missing(self):
        cursor = FakeCursor(fetchone_results=[(5,), ("Объект",)])
        app, _conn = build(cursor)
        result = app.routes[("PUT", "/room-doors/{id}")](
            id=3, data={"name": "Дверь", "width": 0.9, "height": 2.1}, _current_user={}
        )
        self.assertEqual(result, {"ok": True})
        self.assertIn("SELECT room_id FROM room_doors WHERE id=%s", cursor.calls[0][0])


if __name__ == "__main__":
    unittest.main()
