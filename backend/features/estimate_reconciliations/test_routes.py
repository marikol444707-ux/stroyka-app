import unittest

from fastapi import HTTPException

from backend.features.estimate_reconciliations.routes import register_estimate_reconciliations_module
from backend.features.estimate_reconciliations.service import reconciliation_visibility_filter


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return self._register("GET", path)

    def post(self, path):
        return self._register("POST", path)

    def put(self, path):
        return self._register("PUT", path)

    def _register(self, method, path):
        def decorator(handler):
            self.routes[(method, path)] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, *, reconciliation_visible=True, list_rows=None):
        self.reconciliation_visible = reconciliation_visible
        self.list_rows = list_rows or []
        self.calls = []
        self.result = []
        self.closed = False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if "COUNT(i.id) AS item_count" in normalized:
            self.result = list(self.list_rows)
        elif "FROM estimate_reconciliations r" in normalized and "FOR UPDATE OF r,b,n,p" in normalized:
            self.result = (
                [(7, 100, 101, "Alpha", "Основная", "Черновик")]
                if self.reconciliation_visible
                else []
            )
        elif normalized.startswith("SELECT id,reconciliation_id FROM estimate_reconciliation_items"):
            self.result = [(55, 7)]
        elif "FROM estimates" in normalized and "sections_json" in normalized:
            estimate_id = int(params[0])
            self.result = [(
                estimate_id,
                14,
                "Alpha",
                "База" if estimate_id == 100 else "Новая",
                "1.0" if estimate_id == 100 else "1.1",
                "[]",
                "Заказчик",
                "Основная",
                "Архив" if estimate_id == 100 else "Активная",
                "2026-07-12",
                4,
            )]
        elif normalized.startswith("INSERT INTO estimate_reconciliations"):
            self.result = [(7, "2026-07-12")]
        elif normalized.startswith("UPDATE estimate_reconciliations") and "RETURNING id" in normalized:
            self.result = [(7,)]
        elif normalized.startswith("UPDATE estimate_reconciliation_items") and "RETURNING id" in normalized:
            self.result = [(55,)]
        else:
            self.result = []

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return list(self.result)

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


class EstimateReconciliationRouteTests(unittest.TestCase):
    def _register(self, connection, *, actors=None, parents=None, add_change_calls=None):
        app = FakeApp()
        selected_actors = actors or [{
            "id": 9,
            "name": "Директор выбранной компании",
            "role": "директор",
            "companyId": 4,
            "assignedProjects": [],
            "assignedPackages": [],
        }]
        estimate_parents = parents or {
            100: {"id": 100, "companyId": 4, "projectId": 14, "projectName": "Alpha", "workPackage": "Основная"},
            101: {"id": 101, "companyId": 4, "projectId": 14, "projectName": "Alpha", "workPackage": "Основная"},
        }

        def resolve_context(_cur, _user, _requested, _mode, **_kwargs):
            return {"mode": "company", "companyId": 4, "companyIds": [4]}

        def require_write_actor(company_actors, roles):
            normalized = list(company_actors or [])
            if len(normalized) != 1:
                raise HTTPException(status_code=409, detail="Выберите одну компанию")
            if normalized[0].get("role") not in set(roles):
                raise HTTPException(status_code=403, detail="Недостаточно прав")
            return normalized[0]

        def resolve_estimate(_cur, actor, estimate_id, **_kwargs):
            row = estimate_parents.get(int(estimate_id))
            if not row or int(row["companyId"]) != int(actor["companyId"]):
                raise HTTPException(status_code=404, detail="Смета не найдена")
            return dict(row)

        def add_change_items(*args):
            if add_change_calls is not None:
                add_change_calls.append(args)
            return 0

        register_estimate_reconciliations_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_work_company_context": resolve_context,
            "effective_company_actors": lambda _user, _context: selected_actors,
            "require_project_write_actor": require_write_actor,
            "resolve_project_parent": lambda _cur, _actor, **_kwargs: {"id": 14, "companyId": 4, "name": "Alpha"},
            "require_project_parent_access": lambda _cur, _actor, project, _roles: project,
            "resolve_estimate_parent": resolve_estimate,
            "has_package_access": lambda _actor, _package: True,
            "normalize_sections": lambda sections: (sections, []),
            "sections_total": lambda _sections: 0,
            "build_diff": lambda *_args: {
                "changed": [],
                "added": [],
                "removed": [],
                "baseTotal": 0,
                "nextTotal": 0,
                "impact": 0,
                "nextRows": [],
            },
            "add_change_items": add_change_items,
            "item_payload": lambda row: {"id": row[0]},
            "reconciliation_payload": lambda row, items=None: {
                "id": row[0],
                **({"items": items} if items is not None else {}),
            },
            "safe_float": lambda value: float(value or 0),
            "log_audit": lambda **_kwargs: None,
            "document_roles": ("директор", "прораб", "заказчик"),
            "estimate_write_roles": ("директор", "прораб", "сметчик"),
            "approval_roles": ("директор", "сметчик"),
            "full_view_roles": ("директор", "сметчик"),
            "package_limit_roles": ("прораб",),
            "package_unrestricted_roles": (),
            "customer_roles": ("заказчик",),
        })
        return app

    @staticmethod
    def _user():
        return {"id": 9, "name": "Глобальный директор", "role": "директор"}

    def test_list_joins_both_estimates_and_filters_by_selected_company(self):
        row = tuple([7] + [None] * 24)
        cursor = FakeCursor(list_rows=[row])
        connection = FakeConnection(cursor)
        app = self._register(connection)

        result = app.routes[("GET", "/estimate-reconciliations")](
            project_name=None,
            x_company_id="4",
            x_company_mode="company",
            current_user=self._user(),
        )

        sql, params = cursor.calls[-1]
        self.assertIn("JOIN estimates b ON b.id=r.base_estimate_id", sql)
        self.assertIn("JOIN estimates n ON n.id=r.next_estimate_id", sql)
        self.assertIn("b.company_id=n.company_id", sql)
        self.assertIn("p.company_id=%s", sql)
        self.assertEqual(params, (4,))
        self.assertEqual(result, [{"id": 7}])

    def test_create_uses_verified_owner_for_unexpected_work_candidates(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        add_change_calls = []
        app = self._register(connection, add_change_calls=add_change_calls)

        result = app.routes[("POST", "/estimate-reconciliations")](
            {"baseEstimateId": 100, "nextEstimateId": 101},
            x_company_id="4",
            x_company_mode="company",
            current_user=self._user(),
        )

        insert_sql, insert_params = next(call for call in cursor.calls if call[0].startswith("INSERT INTO estimate_reconciliations"))
        self.assertIn("base_estimate_id,next_estimate_id", insert_sql)
        self.assertEqual(insert_params[0:5], ("Alpha", "Основная", "Заказчик", 100, 101))
        self.assertEqual(add_change_calls[0][2:6], (4, 14, "Основная", 100))
        self.assertEqual(add_change_calls[0][6], 101)
        self.assertEqual(result["id"], 7)
        self.assertTrue(connection.committed)

    def test_create_rejects_estimates_from_different_companies_before_insert(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        parents = {
            100: {"id": 100, "companyId": 4, "projectId": 14, "projectName": "Alpha", "workPackage": "Основная"},
            101: {"id": 101, "companyId": 8, "projectId": 88, "projectName": "Other", "workPackage": "Основная"},
        }
        app = self._register(connection, parents=parents)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("POST", "/estimate-reconciliations")](
                {"baseEstimateId": 100, "nextEstimateId": 101},
                x_company_id="4",
                x_company_mode="company",
                current_user=self._user(),
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse(any(sql.startswith("INSERT INTO estimate_reconciliations") for sql, _ in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_update_rejects_foreign_direct_id_before_write(self):
        cursor = FakeCursor(reconciliation_visible=False)
        connection = FakeConnection(cursor)
        app = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            app.routes[("PUT", "/estimate-reconciliations/{id}")](
                7,
                {"status": "На проверке"},
                x_company_id="4",
                x_company_mode="company",
                current_user=self._user(),
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertFalse(any(sql.startswith("UPDATE estimate_reconciliations") for sql, _ in cursor.calls))
        self.assertTrue(connection.rolled_back)

    def test_update_repeats_parent_ids_and_server_actor(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app = self._register(connection)

        result = app.routes[("PUT", "/estimate-reconciliations/{id}")](
            7,
            {"status": "Утверждена", "approvedBy": "Подмена"},
            x_company_id="4",
            x_company_mode="company",
            current_user=self._user(),
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("UPDATE estimate_reconciliations"))
        self.assertIn("base_estimate_id=%s AND next_estimate_id=%s RETURNING id", sql)
        self.assertIn("Директор выбранной компании", params)
        self.assertNotIn("Подмена", params)
        self.assertEqual(params[-3:], (7, 100, 101))
        self.assertEqual(result, {"ok": True})
        self.assertTrue(connection.committed)

    def test_item_update_repeats_reconciliation_parent(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor)
        app = self._register(connection)

        result = app.routes[("PUT", "/estimate-reconciliation-items/{id}")](
            55,
            {"decision": "Проверено"},
            x_company_id="4",
            x_company_mode="company",
            current_user=self._user(),
        )

        sql, params = next(call for call in cursor.calls if call[0].startswith("UPDATE estimate_reconciliation_items"))
        self.assertIn("WHERE id=%s AND reconciliation_id=%s RETURNING id", sql)
        self.assertEqual(params[-2:], (55, 7))
        self.assertEqual(result, {"ok": True})


class EstimateReconciliationVisibilityTests(unittest.TestCase):
    def test_customer_and_package_roles_are_scoped_per_company_membership(self):
        sql, params = reconciliation_visibility_filter(
            [
                {"companyId": 4, "role": "заказчик", "assignedProjects": ["Alpha"]},
                {
                    "companyId": 8,
                    "role": "прораб",
                    "assignedProjects": ["Beta"],
                    "assignedPackages": ["Электрика"],
                },
            ],
            ("заказчик", "прораб"),
            (),
            ("прораб",),
            (),
            ("заказчик",),
        )

        self.assertIn("p.company_id=%s", sql)
        self.assertIn("r.status='Утверждена'", sql)
        self.assertIn("r.work_package", sql)
        self.assertEqual(params, [4, ["Alpha"], 8, ["Beta"], ["Электрика"]])


if __name__ == "__main__":
    unittest.main()
