"""Static E4 writer and PostgreSQL integration-check inventory."""

import ast
import re
import textwrap
from collections import Counter
from pathlib import Path


_E4_PREFIX = "backend/features/estimate_row_transfer/"
_LEDGER_TABLES = {
    "estimate_row_transfer_plans",
    "estimate_row_transfer_entries",
    "estimate_row_assignment_transfers",
    "estimate_row_supply_allocations",
}
_PROTECTED_TABLES = {
    "work_journal",
    "hidden_works_acts",
    "brigade_acts",
    "brigade_payments",
    "supply_requests",
    "supply_deliveries",
    "supplier_offers",
    "supplier_invoices",
    "warehouse_invoices",
    "warehouse_history",
    "supply_history",
    "supply_claims",
    "project_payments",
}
_ALLOWED = Counter({
    ("backend/features/estimate_row_transfer/storage.py", "insert", "estimate_row_transfer_plans"): 1,
    ("backend/features/estimate_row_transfer/storage.py", "insert", "estimate_row_transfer_entries"): 1,
    ("backend/features/estimate_row_transfer/storage.py", "update", "estimate_row_transfer_plans"): 1,
    ("backend/features/estimate_row_transfer/assignment_apply.py", "update", "brigade_contract_items"): 1,
    ("backend/features/estimate_row_transfer/assignment_apply.py", "insert", "brigade_contract_items"): 1,
    ("backend/features/estimate_row_transfer/assignment_apply.py", "update", "brigade_contracts"): 1,
    ("backend/features/estimate_row_transfer/assignment_apply.py", "insert", "estimate_row_assignment_transfers"): 1,
    ("backend/features/estimate_row_transfer/supply_apply.py", "insert", "estimate_row_supply_allocations"): 1,
})
_DML_RE = re.compile(
    r"^(insert\s+into|update|delete\s+from)\s+(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)
_REQUIRED_INTEGRATION_CHECKS = (
    "test_zz_assignment_apply_preserves_history_and_is_idempotent",
    "test_zz_supply_apply_preserves_history_and_is_idempotent",
    "test_zzz_concurrent_apply_never_duplicates_the_split",
    "test_zzz_concurrent_supply_apply_never_duplicates_allocation",
    "test_zzzz_stale_confirmed_quantity_rolls_back_every_apply_write",
    "test_zzzz_supply_delivery_drift_rolls_back_allocation",
)


def _repository_sources(repo_root):
    root = Path(repo_root).resolve()
    result = {}
    for path in sorted((root / "backend").rglob("*.py")):
        if path.name.startswith("test_") or "__pycache__" in path.parts:
            continue
        result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return result


def _sql_statements(path, source, violations):
    try:
        tree = ast.parse(textwrap.dedent(source), filename=path)
    except (SyntaxError, ValueError):
        violations.append({
            "reasonCode": "source_parse_error",
            "file": path,
            "line": None,
        })
        return []
    statements = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or not node.args
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "execute"
        ):
            continue
        sql_node = node.args[0]
        if not isinstance(sql_node, ast.Constant) or not isinstance(sql_node.value, str):
            continue
        for match in _DML_RE.finditer(" ".join(sql_node.value.split())):
            operation = match.group(1).lower().split()[0]
            statements.append((node.lineno, operation, match.group(2).lower()))
    return statements


def _integration_names(source):
    try:
        tree = ast.parse(source or "", filename="test_postgres_audit.py")
    except (SyntaxError, ValueError):
        return set()
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def audit_cutover_inventory(
    repo_root=None,
    *,
    source_files=None,
    integration_test_source=None,
    enforce_complete_inventory=None,
):
    """Return a deterministic, import-free inventory of E4 mutation paths."""

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    if enforce_complete_inventory is None:
        enforce_complete_inventory = source_files is None
    if source_files is None:
        source_files = _repository_sources(repo_root)
    if integration_test_source is None:
        integration_path = (
            Path(repo_root).resolve()
            / "backend/features/estimate_row_transfer/test_postgres_audit.py"
        )
        integration_test_source = integration_path.read_text(encoding="utf-8")

    violations = []
    actual = Counter()
    for raw_path, source in sorted(source_files.items()):
        path = Path(raw_path).as_posix()
        for line, operation, table in _sql_statements(path, source, violations):
            relevant = path.startswith(_E4_PREFIX) or table in _LEDGER_TABLES
            if not relevant:
                continue
            signature = (path, operation, table)
            actual[signature] += 1
            if table in _PROTECTED_TABLES:
                violations.append({
                    "reasonCode": "protected_table_mutation",
                    "file": path,
                    "line": line,
                    "operation": operation,
                    "table": table,
                })
            elif signature not in _ALLOWED:
                violations.append({
                    "reasonCode": "writer_not_allowlisted",
                    "file": path,
                    "line": line,
                    "operation": operation,
                    "table": table,
                })

    if enforce_complete_inventory and actual != _ALLOWED:
        violations.append({
            "reasonCode": "writer_inventory_mismatch",
            "expected": sum(_ALLOWED.values()),
            "actual": sum(actual.values()),
        })

    present_checks = _integration_names(integration_test_source)
    missing_checks = [
        name for name in _REQUIRED_INTEGRATION_CHECKS
        if name not in present_checks
    ]
    for name in missing_checks:
        violations.append({
            "reasonCode": "integration_check_missing",
            "check": name,
        })

    return {
        "ok": not violations,
        "dryRun": True,
        "writesAttempted": 0,
        "dmlStatements": sum(actual.values()),
        "requiredIntegrationChecks": len(_REQUIRED_INTEGRATION_CHECKS),
        "missingIntegrationChecks": missing_checks,
        "violations": violations,
    }


__all__ = ["audit_cutover_inventory"]
