import json
import unittest

from fastapi import HTTPException

from backend.features.work_assignment.routes import register_work_assignment_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorator(handler):
            self.routes[path] = handler
            return handler

        return decorator


class FakeCursor:
    def __init__(self, existing_contract_id=None):
        self.calls = []
        self.result = None
        self.closed = False
        self.existing_contract_id = existing_contract_id

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        normalized = " ".join(sql.split())
        if "FROM estimates WHERE id=%s AND company_id=%s FOR UPDATE" in normalized:
            sections = [{
                "name": "Отделка",
                "items": [{
                    "name": "Штукатурка",
                    "unit": "м2",
                    "quantity": 12,
                    "priceWork": 1000,
                    "estimateItemKey": "work-1",
                }, {
                    "name": "Грунтовка",
                    "unit": "м2",
                    "quantity": 12,
                    "priceWork": 200,
                    "estimateItemKey": "work-2",
                }],
            }]
            self.result = (9, "Смета", 19, "Лицей", "Отделка", json.dumps(sections), "Активная")
        elif normalized.startswith("SELECT id FROM brigade_contracts"):
            self.result = (self.existing_contract_id,) if self.existing_contract_id else None
        elif normalized.startswith("UPDATE brigade_contracts SET brigade_name"):
            self.result = (self.existing_contract_id,) if self.existing_contract_id else None
        elif "INSERT INTO brigade_contracts" in normalized:
            self.result = (77,)
        elif normalized.startswith("SELECT id FROM brigade_contract_items"):
            self.result = None
        elif "INSERT INTO brigade_contract_items" in normalized:
            self.result = (88,)
        else:
            self.result = None

    def fetchone(self):
        return self.result

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, existing_contract_id=None):
        self.autocommit = True
        self.cursor_value = FakeCursor(existing_contract_id=existing_contract_id)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class WorkAssignmentTenantRouteTests(unittest.TestCase):
    def _register(self, connection, *, resolver=None):
        app = FakeApp()
        resolver_calls = []
        contractor_calls = []
        grant_calls = []

        def resolve_estimate_mutation_actor(conn, user, estimate_id, roles, **headers):
            resolver_calls.append((conn, user, estimate_id, roles, headers))
            if resolver:
                return resolver(conn, user, estimate_id, roles, **headers)
            return (
                {"id": user["id"], "role": "директор", "companyId": 4, "company_id": 4},
                {
                    "id": estimate_id,
                    "companyId": 4,
                    "projectId": 19,
                    "projectName": "Лицей",
                    "workPackage": "Отделка",
                },
            )

        def resolve_contractor(cur, company_id, contractor_id, contractor_name):
            contractor_calls.append((company_id, contractor_id, contractor_name))
            return 41

        def grant_scope(cur, company_id, user_id, project_name, work_package, **roles):
            grant_calls.append((company_id, user_id, project_name, work_package, roles))

        register_work_assignment_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: None,
            "resolve_estimate_mutation_actor": resolve_estimate_mutation_actor,
            "resolve_brigade_contractor_user": resolve_contractor,
            "grant_brigade_contractor_scope": grant_scope,
            "assign_roles": ("директор", "зам_директора"),
            "project_scoped_roles": ("мастер", "бригадир"),
            "package_required_roles": ("мастер", "бригадир"),
            "log_audit": lambda *args: None,
        })
        return (
            app.routes["/estimates/{estimate_id}/work-assignment"],
            resolver_calls,
            contractor_calls,
            grant_calls,
        )

    def test_assignment_uses_estimate_company_for_contract_and_contractor(self):
        connection = FakeConnection()
        handler, resolver_calls, contractor_calls, grant_calls = self._register(connection)
        payload = {
            "assignee": {
                "contractorId": 41,
                "brigadeName": "Иван Иванов",
                "contractorType": "Мастер",
            },
            "priceMode": "coefficient",
            "coefficient": 0.6,
            "items": [{"sectionIndex": 0, "itemIndex": 0, "estimateItemKey": "work-1"}],
        }

        response = handler(
            9,
            payload,
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 5, "role": "account_owner"},
        )

        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)
        self.assertEqual(response["companyId"], 4)
        self.assertEqual(response["projectId"], 19)
        self.assertEqual(resolver_calls[0][4], {"x_company_id": "4", "x_company_mode": "company"})
        self.assertEqual(contractor_calls, [(4, 41, "Иван Иванов")])
        self.assertEqual(grant_calls[0][:4], (4, 41, "Лицей", "Отделка"))

        lookup_sql, lookup_params = next(
            call for call in connection.cursor_value.calls
            if "SELECT id FROM brigade_contracts" in call[0]
        )
        self.assertIn("company_id=%s", lookup_sql)
        self.assertIn("project_id=%s", lookup_sql)
        self.assertEqual(lookup_params[:2], (4, 19))

        insert_sql, insert_params = next(
            call for call in connection.cursor_value.calls
            if "INSERT INTO brigade_contracts" in call[0]
        )
        self.assertIn("company_id, project_id", insert_sql)
        self.assertEqual(insert_params[:3], (4, 19, "Лицей"))

    def test_resolver_rejection_rolls_back_and_closes_connection(self):
        connection = FakeConnection()

        def reject(*_args, **_kwargs):
            raise HTTPException(status_code=400, detail="Для изменения данных выберите конкретную компанию")

        handler, _resolver_calls, _contractor_calls, _grant_calls = self._register(
            connection,
            resolver=reject,
        )

        with self.assertRaises(HTTPException) as raised:
            handler(
                9,
                {"assignee": {"brigadeName": "Бригада"}, "items": [{"sectionIndex": 0, "itemIndex": 0}]},
                x_company_mode="all_companies",
                current_user={"id": 5, "role": "account_owner"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)
        self.assertTrue(connection.closed)

    def test_existing_contract_update_keeps_company_and_project_guards(self):
        connection = FakeConnection(existing_contract_id=77)
        handler, _resolver_calls, _contractor_calls, _grant_calls = self._register(connection)

        response = handler(
            9,
            {
                "assignee": {"contractorId": 41, "brigadeName": "Иван Иванов"},
                "items": [{"sectionIndex": 0, "itemIndex": 0}],
            },
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 5, "role": "директор"},
        )

        self.assertFalse(response["createdContract"])
        update_sql, update_params = next(
            call for call in connection.cursor_value.calls
            if "UPDATE brigade_contracts" in call[0] and "SET brigade_name" in call[0]
        )
        self.assertIn("id=%s AND company_id=%s AND project_id=%s", update_sql)
        self.assertEqual(update_params[-3:], (77, 4, 19))
        self.assertFalse(any("INSERT INTO brigade_contracts" in call[0] for call in connection.cursor_value.calls))

    def test_assignment_accepts_manual_override_for_one_coefficient_row(self):
        connection = FakeConnection()
        handler, _resolver_calls, _contractor_calls, _grant_calls = self._register(connection)

        response = handler(
            9,
            {
                "assignee": {"contractorId": 41, "brigadeName": "Иван Иванов"},
                "priceMode": "coefficient",
                "coefficient": 0.4,
                "items": [
                    {
                        "sectionIndex": 0,
                        "itemIndex": 0,
                        "estimateItemKey": "work-1",
                        "priceMode": "manual",
                        "manualPrice": 700,
                    },
                    {
                        "sectionIndex": 0,
                        "itemIndex": 1,
                        "estimateItemKey": "work-2",
                        "priceMode": "coefficient",
                    },
                ],
            },
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 5, "role": "директор"},
        )

        inserted_items = [
            params for sql, params in connection.cursor_value.calls
            if "INSERT INTO brigade_contract_items" in sql
        ]
        self.assertEqual(response["inserted"], 2)
        self.assertEqual([params[8] for params in inserted_items], [700, 80.0])

    def test_non_finite_coefficient_is_rejected_before_database_write(self):
        connection = FakeConnection()
        handler, _resolver_calls, _contractor_calls, _grant_calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            handler(
                9,
                {
                    "assignee": {"brigadeName": "Бригада"},
                    "priceMode": "coefficient",
                    "coefficient": "NaN",
                    "items": [{"sectionIndex": 0, "itemIndex": 0}],
                },
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 5, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse(connection.committed)

    def test_zero_coefficient_is_rejected_instead_of_using_default(self):
        connection = FakeConnection()
        handler, _resolver_calls, _contractor_calls, _grant_calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            handler(
                9,
                {
                    "assignee": {"brigadeName": "Бригада"},
                    "priceMode": "coefficient",
                    "coefficient": 0,
                    "items": [{"sectionIndex": 0, "itemIndex": 0}],
                },
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 5, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse(connection.committed)

    def test_zero_item_coefficient_does_not_fall_back_to_request_coefficient(self):
        connection = FakeConnection()
        handler, _resolver_calls, _contractor_calls, _grant_calls = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            handler(
                9,
                {
                    "assignee": {"brigadeName": "Бригада"},
                    "priceMode": "coefficient",
                    "coefficient": 0.6,
                    "items": [{"sectionIndex": 0, "itemIndex": 0, "coefficient": 0}],
                },
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 5, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
