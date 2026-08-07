import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.features.project_budget_adjustments.preview import (
    BudgetAdjustmentPreviewError,
)
from backend.features.project_budget_adjustments.preview_routes import (
    register_project_budget_adjustment_preview_module,
)


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def decorator(func):
            self.routes[("GET", path)] = func
            return func
        return decorator


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_value = FakeCursor()
        self.session = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = kwargs

    def cursor(self, **_kwargs):
        return self.cursor_value

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1
        raise AssertionError("E6.3 preview must never commit")

    def close(self):
        self.closed = True


class BudgetAdjustmentPreviewRouteTests(unittest.TestCase):
    def build(self, *, actors=None, preview=None, preview_error=None):
        app = FakeApp()
        connection = FakeConnection()
        calls = []
        selected_actors = actors if actors is not None else [{
            "id": 9,
            "companyId": 10,
            "name": "Директор",
            "role": "директор",
        }]

        def build_preview(cur, reconciliation_id, company_id):
            calls.append((cur, reconciliation_id, company_id))
            if preview_error:
                raise BudgetAdjustmentPreviewError(preview_error)
            return preview or {"reconciliationId": reconciliation_id}

        register_project_budget_adjustment_preview_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": (
                lambda _cur, _user, _requested, mode, **_kwargs: {
                    "mode": "company",
                    "companyId": 10,
                    "actionMode": mode,
                }
            ),
            "effective_company_actors": lambda _user, _context: selected_actors,
            "leadership_roles": ("директор", "зам_директора"),
            "build_budget_adjustment_preview": build_preview,
        })
        return app, connection, calls

    @staticmethod
    def call(app, reconciliation_id=7):
        return app.routes[(
            "GET",
            "/estimate-reconciliations/{reconciliation_id}/budget-adjustment-preview",
        )](
            reconciliation_id,
            x_company_id="10",
            x_company_mode="company",
            current_user={"id": 9, "role": "system_owner"},
        )

    def test_leadership_preview_is_read_only_and_always_rolled_back(self):
        expected = {"reconciliationId": 7, "planSha256": "a" * 64}
        app, connection, calls = self.build(preview=expected)

        result = self.call(app)

        self.assertEqual(result, expected)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(calls, [(connection.cursor_value, 7, 10)])
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(connection.cursor_value.closed)
        self.assertTrue(connection.closed)
        self.assertTrue(all(
            sql.startswith("SET LOCAL ")
            for sql, _params in connection.cursor_value.calls
        ))

    def test_aggregate_company_context_fails_before_source_read(self):
        actors = [
            {"id": 9, "companyId": 10, "role": "директор"},
            {"id": 9, "companyId": 11, "role": "директор"},
        ]
        app, connection, calls = self.build(actors=actors)

        with self.assertRaises(HTTPException) as raised:
            self.call(app)

        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(
            raised.exception.detail,
            "budget_adjustment_company_context_ambiguous",
        )
        self.assertEqual(calls, [])
        self.assertEqual(connection.rollbacks, 1)

    def test_non_leadership_role_is_forbidden_before_source_read(self):
        app, connection, calls = self.build(actors=[{
            "id": 15,
            "companyId": 10,
            "role": "сметчик",
        }])

        with self.assertRaises(HTTPException) as raised:
            self.call(app)

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "budget_adjustment_role_forbidden")
        self.assertEqual(calls, [])
        self.assertEqual(connection.rollbacks, 1)

    def test_foreign_id_is_not_found_and_source_conflict_is_409(self):
        for code, status in (
            ("budget_adjustment_not_found", 404),
            ("budget_adjustment_source_drift", 409),
        ):
            with self.subTest(code=code):
                app, connection, _calls = self.build(preview_error=code)
                with self.assertRaises(HTTPException) as raised:
                    self.call(app)
                self.assertEqual(raised.exception.status_code, status)
                self.assertEqual(raised.exception.detail, code)
                self.assertEqual(connection.rollbacks, 1)

    def test_invalid_path_id_is_rejected_before_opening_database(self):
        app, connection, calls = self.build()

        with self.assertRaises(HTTPException) as raised:
            self.call(app, reconciliation_id=0)

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail, "budget_adjustment_identity_invalid")
        self.assertIsNone(connection.session)
        self.assertEqual(calls, [])

    def test_main_and_smoke_register_only_authenticated_get_preview(self):
        root = Path(__file__).resolve().parents[3]
        main = (root / "backend/main.py").read_text(encoding="utf-8")
        smoke = (root / "scripts/prod-smoke-check.sh").read_text(encoding="utf-8")

        self.assertIn("register_project_budget_adjustment_preview_module(app", main)
        self.assertIn('"leadership_roles": LEADERSHIP_ROLES', main)
        self.assertIn("estimate budget adjustment preview route", smoke)
        self.assertIn(
            "$BASE_URL/estimate-reconciliations/1/budget-adjustment-preview",
            smoke,
        )
        self.assertNotIn(
            '@app.post("/estimate-reconciliations/{reconciliation_id}/budget-adjustment',
            main,
        )


if __name__ == "__main__":
    unittest.main()
