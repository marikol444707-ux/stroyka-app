"""Static E5 writer boundary and PostgreSQL integration-check inventory."""

import ast
import re
import textwrap
from collections import Counter
from pathlib import Path


MAX_VIOLATIONS = 100
_MAIN_PATH = "backend/main.py"
_MAIN_FUNCTIONS = {
    "_generate_material_norm_suggestions",
    "_refresh_open_supply_controls_after_estimate_change",
    "_refresh_open_supply_controls_for_estimate",
    "_run_project_ai_control",
    "_supply_linked_work_estimate_control",
    "_supply_material_estimate_control",
    "create_supply_request",
    "update_estimate_status",
}
_PACKAGE_PREFIXES = (
    "backend/features/material_control_ownership/",
    "backend/features/supply_estimate_refresh/",
    "backend/features/supply_lineage/",
)
_PROTECTED_HISTORY_TABLES = {
    "audit_log",
    "brigade_acts",
    "brigade_payments",
    "hidden_works_acts",
    "project_payments",
    "supplier_invoices",
    "supplier_offers",
    "supply_claims",
    "supply_deliveries",
    "supply_history",
    "warehouse_history",
    "warehouse_invoices",
    "work_journal",
}
_ALLOWED_WRITERS = Counter({
    (_MAIN_PATH, "create_supply_request", "insert", "supply_requests"): 1,
    (_MAIN_PATH, "create_supply_request", "update", "supply_requests"): 1,
    (_MAIN_PATH, "update_estimate_status", "update", "estimates"): 2,
    (
        "backend/features/supply_estimate_refresh/service.py",
        "refresh_open_supply_request_controls",
        "update",
        "supply_requests",
    ): 1,
})
_REQUIRED_INTEGRATION_CHECKS = (
    "test_same_name_cross_company_fixture_is_ready_and_unchanged",
    "test_zz_same_name_runtime_queries_are_owner_isolated",
    "test_zzz_foreign_lineage_rolls_back_without_protected_history_changes",
    "test_zzzz_concurrent_lineage_requests_serialize_without_duplicate",
    "test_zzzzz_final_cutover_report_is_read_only_and_exact",
)
_DML_RE = re.compile(
    r"\b(insert\s+into|update|delete\s+from)\s+(?:public\.)?"
    r"([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _repository_sources(repo_root):
    root = Path(repo_root).resolve()
    paths = [root / _MAIN_PATH]
    for prefix in _PACKAGE_PREFIXES:
        directory = root / prefix
        paths.extend(
            path
            for path in sorted(directory.rglob("*.py"))
            if not path.name.startswith("test_") and path.name != "__init__.py"
        )
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in paths
    }


def _scoped_functions(path, source, violations):
    try:
        tree = ast.parse(textwrap.dedent(source or ""), filename=path)
    except (SyntaxError, ValueError):
        violations.append({
            "reasonCode": "source_parse_error",
            "file": path,
        })
        return []
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if path == _MAIN_PATH:
        return [node for node in functions if node.name in _MAIN_FUNCTIONS]
    if path.startswith(_PACKAGE_PREFIXES):
        return functions
    return []


def _function_writers(path, function):
    writers = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        sql = " ".join(node.value.split())
        for match in _DML_RE.finditer(sql):
            operation = match.group(1).lower().split()[0]
            writers.append({
                "file": path,
                "symbol": function.name,
                "line": node.lineno,
                "operation": operation,
                "table": match.group(2).lower(),
            })
    return writers


def _integration_names(source):
    try:
        tree = ast.parse(source or "", filename="test_postgres_readiness.py")
    except (SyntaxError, ValueError):
        return set()
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def audit_cutover_inventory(
    repo_root=None,
    *,
    source_files=None,
    integration_test_source=None,
    enforce_complete_inventory=None,
):
    """Return bounded import-free proof of the reviewed E5 mutation surface."""

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    if enforce_complete_inventory is None:
        enforce_complete_inventory = source_files is None
    if source_files is None:
        source_files = _repository_sources(repo_root)
    if integration_test_source is None:
        test_path = (
            Path(repo_root).resolve()
            / "backend/features/material_control_ownership/test_postgres_readiness.py"
        )
        integration_test_source = test_path.read_text(encoding="utf-8")

    violations = []
    actual = Counter()
    for raw_path, source in sorted(source_files.items()):
        path = Path(raw_path).as_posix()
        for function in _scoped_functions(path, source, violations):
            for writer in _function_writers(path, function):
                signature = (
                    path,
                    writer["symbol"],
                    writer["operation"],
                    writer["table"],
                )
                actual[signature] += 1
                if writer["table"] in _PROTECTED_HISTORY_TABLES:
                    violations.append({
                        "reasonCode": "protected_history_mutation",
                        **writer,
                    })
                elif signature not in _ALLOWED_WRITERS:
                    violations.append({
                        "reasonCode": "writer_not_allowlisted",
                        **writer,
                    })

    if enforce_complete_inventory and actual != _ALLOWED_WRITERS:
        violations.append({
            "reasonCode": "writer_inventory_mismatch",
            "expected": sum(_ALLOWED_WRITERS.values()),
            "actual": sum(actual.values()),
        })

    present_checks = _integration_names(integration_test_source)
    missing_checks = [
        name
        for name in _REQUIRED_INTEGRATION_CHECKS
        if name not in present_checks
    ]
    for name in missing_checks:
        violations.append({
            "reasonCode": "integration_check_missing",
            "check": name,
        })

    ready = not violations
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "writerInventoryReady": ready,
        "dmlStatements": sum(actual.values()),
        "expectedDmlStatements": sum(_ALLOWED_WRITERS.values()),
        "requiredIntegrationChecks": len(_REQUIRED_INTEGRATION_CHECKS),
        "missingIntegrationChecks": missing_checks,
        "violationCount": len(violations),
        "violations": violations[:MAX_VIOLATIONS],
        "violationsTruncated": len(violations) > MAX_VIOLATIONS,
    }


__all__ = ["audit_cutover_inventory"]
