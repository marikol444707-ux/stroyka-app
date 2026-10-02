import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


def _module():
    path = Path(__file__).resolve().parents[3] / "migrations/versions/0082_intercompany_warehouse_transfers.py"
    spec = importlib.util.spec_from_file_location("intercompany_transfer_migration", path)
    module = importlib.util.module_from_spec(spec)
    alembic = ModuleType("alembic")
    alembic.op = None
    with patch.dict("sys.modules", {"alembic": alembic}):
        spec.loader.exec_module(module)
    return module


def test_migration_is_after_current_head_and_creates_paired_transfer_registry():
    module = _module()
    statements = []
    with patch.object(module, "op", SimpleNamespace(execute=statements.append)):
        module.upgrade()
    sql = "\n".join(statements)
    assert module.down_revision == "0081_supply_project_id"
    assert "CREATE TABLE intercompany_warehouse_transfers" in sql
    assert "source_company_id" in sql and "destination_company_id" in sql
    assert "source_document_json" in sql and "destination_document_json" in sql
    assert "decision_company_id=destination_company_id" in sql
    assert "decision_company_id=source_company_id" in sql
    assert "CREATE TABLE intercompany_warehouse_transfer_events" in sql
    assert "source_company_id<>destination_company_id" in sql
    assert "cannot be deleted" in sql.lower()


def test_downgrade_refuses_to_discard_recorded_transfers():
    module = _module()
    statements = []
    with patch.object(module, "op", SimpleNamespace(execute=statements.append)):
        module.downgrade()
    sql = "\n".join(statements)
    assert "EXISTS(SELECT 1 FROM intercompany_warehouse_transfers)" in sql
    assert "Cannot discard intercompany warehouse transfer history" in sql
