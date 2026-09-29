"""Shared tool-custody fixture, with no collected tests or domain mocks."""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from backend.features.work_material_accounting import test_postgres as materials


class ToolCustodyPostgresSupport:
    sql = materials.WorkMaterialAccountingPostgresTests.sql
    api = materials.WorkMaterialAccountingPostgresTests.api
    payload = materials.WorkMaterialAccountingPostgresTests.payload
    balance = materials.WorkMaterialAccountingPostgresTests.balance
    work_payload = materials.WorkMaterialAccountingPostgresTests.work_payload
    request = materials.WorkMaterialAccountingPostgresTests.request
    consumption_payload = materials.WorkMaterialAccountingPostgresTests.consumption_payload
    create_consumption = materials.WorkMaterialAccountingPostgresTests.create_consumption
    stock_quantity = materials.WorkMaterialAccountingPostgresTests.stock_quantity

    @classmethod
    def setUpClass(cls):
        materials.WorkMaterialAccountingPostgresTests.setUpClass.__func__(cls)
        flags = patch.dict(os.environ, {"TOOL_CUSTODY_ENABLED": "1", "WORK_ACCEPTANCE_ENABLED": "0"})
        flags.start()
        cls.addClassCleanup(flags.stop)
        conn = cls.main.get_db()
        try:
            with conn, conn.cursor() as cur:
                # The supply-chain fixture bootstraps legacy tables but omits
                # the separately released inventory-owner migration. Apply its
                # real schema helper to the empty synthetic inventory tables;
                # no historical ownership attribution is fabricated.
                from backend.features.inventory_ownership.migration import _ensure_schema
                _ensure_schema(cur)
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                before = {row[0] for row in cur.fetchall()}
                for filename in ("0028_work_acceptance.py", "0029_tool_custody.py"):
                    path = Path(__file__).resolve().parents[3] / "migrations/versions" / filename
                    spec = importlib.util.spec_from_file_location("tool_custody_test_migration", path)
                    migration = importlib.util.module_from_spec(spec)
                    alembic = ModuleType("alembic")
                    alembic.op = None
                    with patch.dict(sys.modules, {"alembic": alembic}):
                        spec.loader.exec_module(migration)
                    with patch.object(migration, "op", SimpleNamespace(execute=cur.execute)):
                        migration.upgrade()
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                cls.new_tables = sorted(set(cls.new_tables) | ({row[0] for row in cur.fetchall()} - before))
        finally:
            conn.close()

    def setUp(self):
        materials.WorkMaterialAccountingPostgresTests.setUp(self)
        for table in ("tool_history", "tools", "brigade_payments", "project_payments", "interim_acts", "piecework"):
            self.sql("DELETE FROM " + table)
        self.contract_id = self.sql("SELECT contract_id FROM brigade_contract_items WHERE id=%s",
                                    (self.contract_item,))[0][0]
        contract_type = getattr(getattr(self, self._testMethodName), "initial_contract_type", "Субподрядчик")
        self.sql("UPDATE brigade_contracts SET contractor_type=%s,status='Подписан' WHERE id=%s",
                 (contract_type, self.contract_id))
        self.tool_card = {"name": "Synthetic drill", "inventoryNumber": "CUSTODY-" + uuid4().hex,
                          "cost": 1250, "status": "На складе", "location": "Основной склад"}
        self.tool_id = self.api("director", "POST", "/tools", self.tool_card)["id"]
        self.tool_path = "/tools/" + str(self.tool_id)
        self.custody_path = self.tool_path + "/custody"

    def snapshot(self):
        tables = ("tools", "tool_history", "brigade_contracts", "brigade_acts", "brigade_payments",
                  "project_payments", "interim_acts", "piecework")
        return materials.WorkMaterialAccountingPostgresTests.snapshot(self) + tuple(
            (table, self.sql("SELECT row_to_json(t)::text FROM " + table + " t ORDER BY 1"))
            for table in tables)

    def custody_view(self, actor="director", tool_id=None):
        return self.api(actor, "GET", f"/tools/{tool_id or self.tool_id}/custody")

    def tool_command_payload(self, action, tool_id=None, **changes):
        return {"requestId": str(uuid4()), "expectedState": self.custody_view(tool_id=tool_id)["expectedState"],
                "action": action, **changes}

    def tool_command(self, action, actor="director", tool_id=None, **changes):
        payload = self.tool_command_payload(action, tool_id=tool_id, **changes)
        result = self.api(actor, "POST", f"/tools/{tool_id or self.tool_id}/custody", payload)
        self.assertTrue(result["ok"])
        self.assertEqual(result["toolId"], tool_id or self.tool_id)
        self.assertTrue(result["eventId"])
        return result

    def issue_tool(self, actor="director", **changes):
        return self.tool_command("issue", actor=actor, **{
            "recipientId": self.f["users"]["worker"]["id"], "projectId": self.f["projectId"],
            "contractId": self.contract_id, **changes,
        })

    def assert_rejected_unchanged(self, actor, method, path, payload=None, expected=409):
        before = self.snapshot()
        self.api(actor, method, path, payload, expected=expected)
        self.assertEqual(self.snapshot(), before)
