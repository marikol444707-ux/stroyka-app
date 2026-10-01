"""Exercise the production notification-context function in isolation."""

import ast
import copy
import json
from pathlib import Path
import unittest

from fastapi import HTTPException

from backend.features.supplier_access.rfq_requester_snapshot import (
    build_rfq_requester_snapshot,
    requester_snapshot_identity,
    validate_rfq_requester_snapshot,
)


MAIN_PATH = Path(__file__).resolve().parents[3] / "backend/main.py"


class Cursor:
    def __init__(self, request, projects):
        self.request = request
        self.projects = projects
        self.rows = []
        self.statements = []

    def execute(self, statement, _params=()):
        normalized = " ".join(statement.split())
        self.statements.append(normalized)
        if "FROM supply_requests" in normalized:
            self.rows = [self.request]
        elif "FROM projects" in normalized:
            self.rows = list(self.projects)
        elif "FROM companies" in normalized:
            raise AssertionError("A frozen notification must not reread mutable company requisites")
        else:
            raise AssertionError("Unexpected query: " + normalized)

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows


class RfqNotificationSnapshotRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
        nodes = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        namespace = {
            "json": json,
            "HTTPException": HTTPException,
            "validate_rfq_requester_snapshot": validate_rfq_requester_snapshot,
            "requester_snapshot_identity": requester_snapshot_identity,
        }
        selected = [copy.deepcopy(nodes[name]) for name in (
            "_row_get", "_json_list_or_empty", "_supply_request_notification_context",
        )]
        for node in selected:
            for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                arg.annotation = None
            node.returns = None
        module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        cls.notification_context = staticmethod(namespace["_supply_request_notification_context"])

    def test_uses_frozen_identity_and_delivery_without_current_company_profile(self):
        snapshot = build_rfq_requester_snapshot(
            request_id=81,
            company_id=17,
            project_id=31,
            project_name="Лицей №4",
            delivery_address="Адрес на дату отправки",
            company={"short_name": "Заказчик на дату отправки", "email": "old@example.test"},
            actor={"id": 71, "name": "Контакт", "email": "contact@example.test"},
            frozen_at="2026-10-01T12:00:00Z",
        )
        cursor = Cursor({
            "id": 81,
            "material_name": "Кабель",
            "quantity": 100,
            "unit": "м",
            "project": "Лицей №4",
            "work_package": "Электрика",
            "notes": "Позвонить",
            "items_json": "[]",
            "company_id": 17,
            "delivery_address": "Изменённый адрес",
            "requester_snapshot_json": snapshot,
        }, projects=[{"id": 31}])

        result = self.notification_context(cursor, 81)

        self.assertEqual(result["companyName"], "Заказчик на дату отправки")
        self.assertEqual(result["companyEmail"], "old@example.test")
        self.assertEqual(result["deliveryAddress"], "Адрес на дату отправки")
        self.assertEqual(result["contactName"], "Контакт")
        self.assertEqual(result["contactEmail"], "contact@example.test")
        self.assertEqual(result["projectId"], 31)
        self.assertFalse(any("FROM companies" in statement for statement in cursor.statements))


if __name__ == "__main__":
    unittest.main()
