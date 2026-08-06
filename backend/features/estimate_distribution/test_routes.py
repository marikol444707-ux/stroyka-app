import unittest

from fastapi import HTTPException

from backend.features.brigade_lineage.snapshot_service import EstimateSnapshotLineage
from backend.features.brigade_lineage.writer_service import write_estimate_contract_item
from backend.features.estimate_distribution.routes import register_estimate_distribution_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorator(handler):
            self.routes[("POST", path)] = handler
            return handler
        return decorator


class FakeCursor:
    def __init__(self, *, existing_contract=False, existing_item=None):
        self.calls = []
        self.result = None
        self.rows = []
        self.existing_contract = existing_contract
        self.existing_item = existing_item
        self.closed = False

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        self.result = None
        self.rows = []
        if "FROM estimates WHERE id=%s AND company_id=%s" in normalized:
            self.result = (9, "Смета", 19, "Лицей", "Отделка")
        elif "SELECT id, coefficient FROM pricelists" in normalized:
            self.rows = [(3, 0.6)]
        elif normalized.startswith("SELECT id FROM brigade_contracts"):
            self.result = (77,) if self.existing_contract else None
        elif normalized.startswith("INSERT INTO brigade_contracts"):
            self.result = (77,)
        elif normalized.startswith("UPDATE brigade_contracts") and "RETURNING id" in normalized:
            self.result = (77,)
        elif "FROM brigade_contract_items" in normalized and normalized.startswith("SELECT id"):
            self.result = self.existing_item
        elif normalized.startswith("INSERT INTO brigade_contract_items"):
            self.result = (88,)

    def fetchone(self):
        return self.result

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.autocommit = True
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


class EstimateDistributionRouteTests(unittest.TestCase):
    def _register(self, connection):
        app = FakeApp()
        lineage_calls = []
        contractor_calls = []
        grant_calls = []

        def resolve_lineages(cur, **kwargs):
            lineage_calls.append((cur, kwargs))
            result = []
            for coordinate in kwargs["coordinates"]:
                if coordinate.expected_item_key != "work-1":
                    raise ValueError("source_item_key_mismatch")
                result.append(EstimateSnapshotLineage(
                    source_type="estimate",
                    source_estimate_version_id=71,
                    source_section_index=coordinate.section_index,
                    source_item_index=coordinate.item_index,
                    source_item_key="work-1",
                    sections_sha256="a" * 64,
                    section={"name": "Отделка"},
                    item={
                        "name": "Штукатурка",
                        "unit": "м2",
                        "quantity": 12,
                        "priceWork": 1000,
                        "estimateItemKey": "work-1",
                    },
                    snapshot_created=False,
                ))
            return result

        def resolve_contractor(cur, company_id, contractor_id, brigade_name):
            contractor_calls.append((company_id, contractor_id, brigade_name))
            return 41

        def grant_scope(cur, company_id, user_id, project_name, work_package, **kwargs):
            grant_calls.append((company_id, user_id, project_name, work_package, kwargs))

        register_estimate_distribution_module(app, {
            "get_db": lambda: connection,
            "get_current_user": lambda: {},
            "resolve_estimate_mutation_actor": lambda conn, user, estimate_id, roles, **headers: (
                {"name": "Директор", "role": "директор"},
                {"companyId": 4, "projectId": 19, "projectName": "Лицей", "workPackage": "Отделка"},
            ),
            "resolve_brigade_contractor_user": resolve_contractor,
            "grant_brigade_contractor_scope": grant_scope,
            "ensure_estimate_snapshot_lineages": resolve_lineages,
            "write_estimate_contract_item": write_estimate_contract_item,
            "assign_roles": ("директор",),
            "project_scoped_roles": ("мастер",),
            "package_required_roles": ("мастер",),
        })
        return app.routes[("POST", "/estimates/{estimate_id}/distribute")], lineage_calls, contractor_calls, grant_calls

    @staticmethod
    def _payload(key="work-1"):
        return {
            "defaultCoefficient": 0.5,
            "assignments": [{
                "sectionIndex": 0,
                "itemIndex": 0,
                "estimateItemKey": key,
                "brigadeName": "Бригада 1",
                "contractorId": 41,
                "pricelistId": 3,
                "workPackage": "Отделка",
            }],
        }

    def test_distribution_resolves_exact_snapshot_and_inserts_full_lineage(self):
        connection = FakeConnection(FakeCursor())
        handler, lineage_calls, contractor_calls, grant_calls = self._register(connection)

        result = handler(
            9,
            self._payload(),
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 5, "role": "директор"},
        )

        self.assertEqual(lineage_calls[0][1]["estimate_id"], 9)
        self.assertEqual(lineage_calls[0][1]["company_id"], 4)
        self.assertEqual(lineage_calls[0][1]["project_id"], 19)
        insert = next(call for call in connection.cursor_value.calls if call[0].startswith("INSERT INTO brigade_contract_items"))
        self.assertEqual(insert[1][10:], ("estimate", 71, 0, 0, "work-1"))
        self.assertEqual(contractor_calls, [(4, 41, "Бригада 1")])
        self.assertEqual(grant_calls[0][:4], (4, 41, "Лицей", "Отделка"))
        self.assertEqual(result["createdContracts"][0]["inserted"], 1)
        self.assertEqual(result["createdContracts"][0]["reused"], 0)
        self.assertTrue(connection.committed)
        self.assertTrue(connection.closed)

    def test_exact_repeat_reuses_contract_item_without_overwriting_values(self):
        stored = (88, "Отделка", "Выданная штукатурка", "м2", 7.5, 1000, 777, "work-1")
        connection = FakeConnection(FakeCursor(existing_contract=True, existing_item=stored))
        handler, *_ = self._register(connection)

        result = handler(
            9,
            self._payload(),
            x_company_id="4",
            x_company_mode="company",
            current_user={"id": 5, "role": "директор"},
        )

        contract = result["createdContracts"][0]
        self.assertFalse(contract["created"])
        self.assertEqual(contract["inserted"], 0)
        self.assertEqual(contract["reused"], 1)
        self.assertEqual(contract["totalAmount"], 7.5 * 777)
        self.assertFalse(any(call[0].startswith("INSERT INTO brigade_contract_items") for call in connection.cursor_value.calls))
        self.assertFalse(any(call[0].startswith("UPDATE brigade_contract_items") for call in connection.cursor_value.calls))

    def test_mismatched_coordinate_key_rolls_back_before_contract_write(self):
        connection = FakeConnection(FakeCursor())
        handler, *_ = self._register(connection)

        with self.assertRaises(HTTPException) as raised:
            handler(
                9,
                self._payload("wrong"),
                x_company_id="4",
                x_company_mode="company",
                current_user={"id": 5, "role": "директор"},
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(any("brigade_contracts" in call[0] for call in connection.cursor_value.calls))
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
