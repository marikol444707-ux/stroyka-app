import unittest

from backend.features.ai_control.runtime import run_project_ai_control_safely


class FakeCursor:
    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.autocommit = True
        self.cursor_value = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class AiControlRuntimeTests(unittest.TestCase):
    def test_event_run_uses_exact_owner_and_commits(self):
        connection = FakeConnection()
        calls = []

        def resolve_owner(_cur, name, **kwargs):
            calls.append((name, kwargs))
            return {"id": 10, "companyId": 4, "name": "Объект A"}

        def runner(_cur, name, actor, reason="event", project_owner=None):
            self.assertEqual(actor["companyId"], 4)
            self.assertEqual(project_owner["id"], 10)
            return {"ok": True, "projectName": name, "reason": reason}

        result = run_project_ai_control_safely(
            lambda: connection,
            resolve_owner,
            runner,
            lambda project: {"role": "директор", "companyId": project["companyId"]},
            "Объект A",
            "event:test",
        )

        self.assertTrue(result["ok"])
        self.assertTrue(calls[0][1]["for_update"])
        self.assertFalse(connection.autocommit)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_event_run_rolls_back_and_returns_empty_on_ambiguous_owner(self):
        connection = FakeConnection()
        logged = []

        def fail_owner(*_args, **_kwargs):
            raise RuntimeError("ambiguous project")

        result = run_project_ai_control_safely(
            lambda: connection,
            fail_owner,
            lambda *_args, **_kwargs: {"ok": True},
            lambda _project: {},
            "Объект A",
            "event:test",
            log_error=lambda *parts: logged.append(parts),
        )

        self.assertEqual(result, {})
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertTrue(connection.closed)
        self.assertIn("ambiguous project", " ".join(map(str, logged[0])))


if __name__ == "__main__":
    unittest.main()
