import ast
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException


MAIN_PATH = Path(__file__).resolve().parent / "main.py"


class _App:
    def post(self, _path):
        return lambda function: function


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params or ())))

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, cursor, events):
        self.cursor_value = cursor
        self.events = events
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.events.append("commit")

    def close(self):
        self.closed = True


def _password_reset_function(namespace):
    tree = ast.parse(
        MAIN_PATH.read_text(encoding="utf-8"),
        filename=str(MAIN_PATH),
    )
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "password_reset"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(MAIN_PATH), "exec"), namespace)
    return namespace["password_reset"]


class PasswordResetSessionRevocationTests(unittest.TestCase):
    def test_successful_reset_revokes_existing_sessions_before_commit(self):
        events = []
        cursor = _Cursor((17, "stored-token", datetime.now() + timedelta(minutes=5)))
        connection = _Connection(cursor, events)

        reset = _password_reset_function({
            "app": _App(),
            "HTTPException": HTTPException,
            "get_db": lambda: connection,
            "_verify_password_reset_token": lambda *_args: True,
            "hash_password": lambda value: "hash:" + value,
            "_close_password_reset_task": lambda _cur, user_id: events.append(
                ("close_reset_task", user_id)
            ),
            "_revoke_user_sessions": lambda _cur, user_id: events.append(
                ("revoke_sessions", user_id)
            ),
            "log_audit": lambda **_kwargs: None,
        })

        result = reset({
            "email": " USER@Example.Test ",
            "code": "123456",
            "newPassword": "new-secret",
        })

        self.assertTrue(result["ok"])
        self.assertIn(("revoke_sessions", 17), events)
        self.assertLess(events.index(("revoke_sessions", 17)), events.index("commit"))
        self.assertEqual(
            cursor.calls[0][1],
            ("user@example.test",),
        )
        self.assertIn("reset_token=NULL", cursor.calls[1][0])
        self.assertEqual(cursor.calls[1][1], ("hash:new-secret", 17))
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
