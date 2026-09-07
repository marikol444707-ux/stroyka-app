"""Execute production routes without importing the application or touching a DB.

The small transactional ledger models autocommit, pending writes and rollback.
Recipient/offer insertion and workflow policies are real production code; only
external identity, estimate, audit and notification boundaries are substituted.
"""

import ast
import copy
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException

from backend.features.supplier_access import supply_request_workflow
from backend.features.supply_lineage.service import (
    MaterialControlLineageError,
    material_control_request_intent,
)


MAIN_PATH = Path(__file__).resolve().parents[3] / "backend/main.py"
REQUEST_ID = 81
COMPANY_ID = 17
SUPPLIER_ID = 4
APPROVED_AT = "2026-09-03T12:00:00"


class TransactionLedger:
    def __init__(self, request=None):
        self.committed = {
            "supply_requests": {REQUEST_ID: copy.deepcopy(request)} if request else {},
            "supply_request_recipients": {},
            "supplier_offers": {},
        }
        self.pending = None
        self.autocommit = True
        self.write_autocommit = []
        self.rollback_count = 0
        self.closed = False
        self.fail_request_readback = False
        self.cursor_instance = LedgerCursor(self)

    @property
    def state(self):
        return self.pending if self.pending is not None else self.committed

    def writable_state(self):
        self.write_autocommit.append(self.autocommit)
        if not self.autocommit and self.pending is None:
            self.pending = copy.deepcopy(self.committed)
        return self.state

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        if self.pending is not None:
            self.committed = self.pending
            self.pending = None

    def rollback(self):
        self.rollback_count += 1
        self.pending = None

    def close(self):
        # Closing a real PostgreSQL connection also discards an open transaction.
        self.pending = None
        self.closed = True


class LedgerCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.rowcount = 0
        self.closed = False

    def execute(self, sql, params=()):
        sql = " ".join(sql.split())
        self.rows = []
        self.rowcount = 0
        insert = re.match(r"INSERT INTO (\w+)\s*\(([^)]+)\)", sql)
        if insert:
            table, columns = insert.groups()
            row = dict(zip((column.strip() for column in columns.split(",")), params))
            row["id"] = REQUEST_ID if table == "supply_requests" else 901
            self.connection.writable_state()[table][row["id"]] = row
            self.rows = [{"id": row["id"]}]
            self.rowcount = 1
            return
        if sql.startswith("UPDATE supply_requests"):
            requests = self.connection.writable_state()["supply_requests"]
            request = requests[REQUEST_ID]
            if "status=CASE" in sql:
                if request["status"] == "Утверждена":
                    request["status"] = params[0]
                request["selected_suppliers"] = list(params[1])
            else:
                request["status"] = params[0]
            self.rowcount = 1
            return
        if sql.startswith("SELECT"):
            if "pg_advisory_xact_lock" in sql:
                return
            table_match = re.search(r" FROM (\w+)", sql)
            if table_match is None:
                raise AssertionError("Unexpected ledger query: " + sql)
            table = table_match.group(1)
            rows = list(self.connection.state[table].values())
            if table == "supply_requests":
                if self.connection.fail_request_readback and rows:
                    raise RuntimeError("injected post-insert request SELECT failure")
                rows = [row for row in rows if row["id"] == REQUEST_ID]
            else:
                rows = [row for row in rows if row.get("request_id") == REQUEST_ID]
            # Project the actual SELECT, so missing approval columns cannot be
            # hidden by a fake cursor that returns fields the route never loaded.
            columns = sql[len("SELECT "):table_match.start()]
            if columns != "*":
                names = [column.strip() for column in columns.split(",")]
                rows = [{name: row.get(name) for name in names} for row in rows]
            self.rows = copy.deepcopy(rows)
            return
        raise AssertionError("Unexpected ledger statement: " + sql)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def close(self):
        self.closed = True


class RuntimeHarness:
    def __init__(self, nodes, *, request=None, role="снабженец", visible=True):
        self.connection = TransactionLedger(request)
        self.user = {"id": 71, "name": "Автор заявки", "role": role, "companyId": COMPANY_ID}
        self.notification_rows = [{
            "supplierId": SUPPLIER_ID,
            "visibleToSupplier": True,
            "emailStatus": "Ошибка отправки",
            "emailError": "SMTP unavailable",
            "maxStatus": "MAX не привязан",
        }]
        self.notify = Mock(return_value=self.notification_rows)
        self.audit = Mock()
        self.project_access = Mock()
        self.project_company = Mock(return_value=COMPANY_ID)
        self.company_context = Mock(return_value={"companyId": COMPANY_ID})
        self.estimate_control = Mock(side_effect=lambda _cur, _project, items, **_kwargs: items)

        def company_actor(_cur, user, owner, _action, **kwargs):
            if user.get("companyId") != owner or kwargs.get("claimed_company_id", owner) not in (None, owner):
                raise HTTPException(status_code=403, detail="Нет доступа к компании заявки")
            return {"companyId": owner}, user

        def assert_company_scope(rows, company_id, _label):
            if any(row.get("companyId", row.get("company_id")) != company_id for row in rows):
                raise HTTPException(status_code=403, detail="Получатели другой компании")

        namespace = {
            **vars(supply_request_workflow),
            "HTTPException": HTTPException,
            "json": json,
            "psycopg2": SimpleNamespace(extras=SimpleNamespace(RealDictCursor=object)),
            "get_db": lambda: self.connection,
            "_ensure_supply_runtime_columns": lambda _cur: None,
            "_ensure_supply_request_recipients_table": lambda _cur: None,
            "resolve_resource_company_actor": company_actor,
            "assert_rows_company_scope": assert_company_scope,
            "require_project_or_warehouse_access": self.project_access,
            "_project_company_id": self.project_company,
            "_resolve_work_company_context": self.company_context,
            "SUPPLY_INTERNAL_ROLES": ("директор", "зам_директора", "снабженец", "прораб"),
            "PLATFORM_STAFF_ROLES": (),
            "CLIENT_ACCOUNT_ROLES": (),
            "supplier_group_scope_ids": lambda _cur, ids: list(ids),
            "supplier_offer_targets_for_groups": lambda _cur, ids, *_args: [
                {"requested_id": supplier_id, "target_id": supplier_id, "scope_ids": [supplier_id]}
                for supplier_id in ids
            ],
            "_supplier_visibility_for_scope": lambda _cur, _ids: {
                "visible": visible, "user_id": 401 if visible else None, "reason": "" if visible else "Нет аккаунта",
            },
            "_notify_supply_request_recipients": self.notify,
            "log_audit": self.audit,
            "_norm_base_unit": lambda unit: unit,
            "has_package_access": lambda _user, _package: True,
            "_positive_int_or_none": lambda value: int(value) if value else None,
            "material_control_request_intent": material_control_request_intent,
            "MaterialControlLineageError": MaterialControlLineageError,
            "_attach_supply_estimate_control": self.estimate_control,
            "_enforce_supply_estimate_control": lambda *_args, **_kwargs: None,
            "SUPPLY_SELECT": "SELECT * FROM supply_requests",
            "_supply_response_for_role": lambda row, _user: dict(row),
            # Estimate validation has its own suite. These boundaries let both
            # creation entry paths exercise the real transaction and INSERT.
            "resolve_material_control_project": lambda _cur, **kwargs: {
                "projectId": kwargs["project_id"], "projectName": kwargs["project_name"],
            },
            "validate_material_control_request_lineage": lambda **kwargs: kwargs["items"],
            "load_material_control_estimates": lambda *_args: {},
            "material_control_estimate_ids": lambda _items: [],
            "material_control_lineage_keys": lambda _items: set(),
            "material_control_lineage_conflicts": lambda *_args: [],
            "_json_list_or_empty": lambda value: json.loads(value) if value else [],
        }
        for name in ("_estimate_sections", "_estimate_item_type_backend", "_estimate_material_plan_issue_backend", "_estimate_imported_quantity"):
            namespace[name] = Mock()
        function_names = (
            "_row_get", "_normalize_supplier_ids", "_supply_item_quantity",
            "_supply_work_package", "_normalize_supply_request_items", "_resolve_supply_request_package",
            "_upsert_supply_request_recipients", "_recipient_visibility_error",
            "_create_supplier_offer_requests", "request_kp_from_suppliers", "create_supply_request",
        )
        extracted = []
        for name in function_names:
            node = copy.deepcopy(nodes[name])
            node.decorator_list = []
            # Remove only FastAPI dependency bindings, not business defaults
            # such as recipient status or request-item units.
            node.args.defaults = [
                ast.Constant(None) if isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in ("Header", "Depends") else value
                for value in node.args.defaults
            ]
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                arg.annotation = None
            node.returns = None
            extracted.append(node)
        module = ast.fix_missing_locations(ast.Module(body=extracted, type_ignores=[]))
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        self.dispatch_route = namespace["request_kp_from_suppliers"]
        self.create_route = namespace["create_supply_request"]

    def dispatch(self, **payload):
        return self.dispatch_route(REQUEST_ID, {"supplierIds": [SUPPLIER_ID], **payload}, _current_user=self.user)

    def create(self, *, material_control=False):
        request = SimpleNamespace(
            project="Объект №7", projectId=31, companyId=COMPANY_ID,
            createdBy="", workPackage="Основная", materialName="Труба", quantity=10,
            unit="м", items=[], selectedSuppliers=[SUPPLIER_ID],
            requestSource="estimate_material_control" if material_control else "",
            notes="", date="2026-09-03", urgency="Обычная", category="Материалы",
        )
        return self.create_route(request, _current_user=self.user)


class RfqDeliveryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        cls.nodes = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    def approved_request(self, **overrides):
        return {
            "id": REQUEST_ID, "quantity": 10, "project": "Объект №7",
            "company_id": COMPANY_ID, "status": "Утверждена", "selected_suppliers": [],
            "prorab_confirmed_at": APPROVED_AT, "director_approved_at": APPROVED_AT,
            **overrides,
        }

    def assert_no_dispatch(self, harness):
        self.assertEqual({}, harness.connection.committed["supply_request_recipients"])
        self.assertEqual({}, harness.connection.committed["supplier_offers"])
        harness.notify.assert_not_called()

    def test_status_without_complete_human_approval_is_rejected_before_any_business_write(self):
        for status in ("Утверждена", "КП запрошены"):
            for prorab_at, director_at in ((None, None), (None, APPROVED_AT), (APPROVED_AT, None)):
                with self.subTest(status=status, prorab_at=prorab_at, director_at=director_at):
                    harness = RuntimeHarness(self.nodes, request=self.approved_request(
                        status=status, prorab_confirmed_at=prorab_at, director_approved_at=director_at,
                    ))
                    with self.assertRaises(HTTPException) as error:
                        harness.dispatch()
                    self.assertEqual(409, error.exception.status_code)
                    self.assertEqual([], harness.connection.write_autocommit)
                    self.assert_no_dispatch(harness)
                    self.assertTrue(harness.connection.closed)

    def test_completed_approvals_create_visible_offer_even_if_notification_channels_fail(self):
        harness = RuntimeHarness(self.nodes, request=self.approved_request())

        result = harness.dispatch()

        self.assertTrue(result["ok"])
        self.assertEqual(1, result["created"])
        self.assertEqual("КП запрошены", harness.connection.committed["supply_requests"][REQUEST_ID]["status"])
        self.assertTrue(result["recipients"][0]["visibleToSupplier"])
        self.assertEqual(1, len(harness.connection.committed["supplier_offers"]))
        self.assertEqual("Ошибка отправки", result["notifications"][0]["emailStatus"])
        self.assertEqual("MAX не привязан", result["notifications"][0]["maxStatus"])
        self.assertTrue(harness.connection.write_autocommit)
        self.assertFalse(any(harness.connection.write_autocommit))
        self.assertTrue(harness.connection.closed)

    def test_invisible_recipient_is_rolled_back_without_offer_or_notification(self):
        harness = RuntimeHarness(self.nodes, request=self.approved_request(), visible=False)

        with self.assertRaises(HTTPException) as error:
            harness.dispatch()

        self.assertEqual(400, error.exception.status_code)
        self.assertGreater(harness.connection.rollback_count, 0)
        self.assertEqual("Утверждена", harness.connection.committed["supply_requests"][REQUEST_ID]["status"])
        self.assert_no_dispatch(harness)
        self.assertTrue(harness.connection.closed)
        self.assertTrue(harness.connection.cursor_instance.closed)

    def test_forbidden_role_cannot_dispatch_an_approved_request(self):
        harness = RuntimeHarness(self.nodes, request=self.approved_request(), role="прораб")
        with self.assertRaises(HTTPException) as error:
            harness.dispatch()
        self.assertEqual(403, error.exception.status_code)
        self.assertEqual([], harness.connection.write_autocommit)
        self.assert_no_dispatch(harness)

    def test_cross_company_dispatch_is_rejected_without_disclosure(self):
        harness = RuntimeHarness(self.nodes, request=self.approved_request())
        with self.assertRaises(HTTPException) as error:
            harness.dispatch(companyId=COMPANY_ID + 1)
        self.assertEqual(403, error.exception.status_code)
        self.assertEqual([], harness.connection.write_autocommit)
        self.assert_no_dispatch(harness)

    def test_leadership_creation_starts_new_without_fabricated_approval_or_auto_dispatch(self):
        for role in ("директор", "зам_директора"):
            with self.subTest(role=role):
                harness = RuntimeHarness(self.nodes, role=role)
                result = harness.create()
                row = harness.connection.committed["supply_requests"][result["id"]]
                self.assertEqual("Новая", row["status"])
                for field in ("prorab_id", "prorab_name", "prorab_confirmed_at", "director_id", "director_name", "director_approved_at"):
                    self.assertIsNone(row[field], field)
                self.assert_no_dispatch(harness)

    def test_every_creation_path_disables_autocommit_before_business_writes(self):
        for role in ("директор", "зам_директора", "прораб", "мастер", "снабженец"):
            for material_control in (False, True):
                with self.subTest(role=role, material_control=material_control):
                    harness = RuntimeHarness(self.nodes, role=role)
                    harness.create(material_control=material_control)
                    self.assertTrue(harness.connection.write_autocommit)
                    self.assertFalse(any(harness.connection.write_autocommit))

    def test_post_insert_read_failure_rolls_back_creation_and_closes_resources(self):
        for role in ("директор", "мастер"):
            for material_control in (False, True):
                with self.subTest(role=role, material_control=material_control):
                    harness = RuntimeHarness(self.nodes, role=role)
                    harness.connection.fail_request_readback = True
                    with self.assertRaises((RuntimeError, HTTPException)):
                        harness.create(material_control=material_control)
                    self.assertEqual({}, harness.connection.committed["supply_requests"])
                    self.assertGreater(harness.connection.rollback_count, 0)
                    self.assert_no_dispatch(harness)
                    self.assertTrue(harness.connection.closed)
                    self.assertTrue(harness.connection.cursor_instance.closed)

    def test_creation_estimate_failure_closes_resources_without_persisting_request(self):
        harness = RuntimeHarness(self.nodes, role="мастер")
        harness.estimate_control.side_effect = HTTPException(status_code=400, detail="Сметный контроль не пройден")
        with self.assertRaises(HTTPException) as error:
            harness.create()
        self.assertEqual(400, error.exception.status_code)
        self.assertEqual({}, harness.connection.committed["supply_requests"])
        self.assert_no_dispatch(harness)
        self.assertTrue(harness.connection.closed)
        self.assertTrue(harness.connection.cursor_instance.closed)

    def test_creation_company_mismatch_remains_rejected_without_dispatch(self):
        harness = RuntimeHarness(self.nodes, role="директор")
        harness.project_company.return_value = COMPANY_ID + 1
        with self.assertRaises(HTTPException) as error:
            harness.create()
        self.assertEqual(400, error.exception.status_code)
        self.assertEqual({}, harness.connection.committed["supply_requests"])
        self.assert_no_dispatch(harness)
        self.assertTrue(harness.connection.closed)


if __name__ == "__main__":
    unittest.main()
