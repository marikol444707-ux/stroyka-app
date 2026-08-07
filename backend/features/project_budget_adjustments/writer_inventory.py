"""Static E6.1 project-budget writer and baseline-DML inventory."""

import ast
import re
from collections import Counter, defaultdict
from pathlib import Path


MAX_VIOLATIONS = 100
E6_PACKAGE_PREFIX = "backend/features/project_budget_adjustments/"
EXPECTED_PROJECT_BUDGET_WRITERS = Counter({
    (
        "backend/features/projects/routes.py",
        "create_project",
        "insert",
    ): 1,
    (
        "backend/features/projects/routes.py",
        "update_project",
        "dynamic_update",
    ): 1,
    (
        "backend/features/crm/routes.py",
        "crm_create_project_from_lead",
        "insert",
    ): 1,
})
_PROJECT_INSERT_RE = re.compile(
    r"\binsert\s+into\s+(?:public\.)?projects\s*\(([^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)
_PROJECT_UPDATE_RE = re.compile(
    r"\bupdate\s+(?:public\.)?projects\s+set\b([^;]*)",
    re.IGNORECASE | re.DOTALL,
)
_DML_RE = re.compile(
    r"\b(insert\s+into|update|delete\s+from)\s+(?:public\.)?"
    r"([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _repository_sources(repo_root):
    root = Path(repo_root).resolve()
    backend = root / "backend"
    paths = [
        path for path in sorted(backend.rglob("*.py"))
        if not path.name.startswith("test_")
        and "__pycache__" not in path.parts
    ]
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in paths
    }


def _static_string(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = [_static_string(value) for value in node.values]
        return "".join(parts) if all(part is not None for part in parts) else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        return left + right if left is not None and right is not None else None
    return None


def _string_owners(tree):
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    owned = defaultdict(list)
    for node in ast.walk(tree):
        value = _static_string(node)
        if value is None:
            continue
        parent = parents.get(node)
        if _static_string(parent) is not None and isinstance(
            parent, (ast.BinOp, ast.JoinedStr)
        ):
            continue
        while parent is not None and not isinstance(
            parent, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            parent = parents.get(parent)
        symbol = parent.name if parent is not None else "<module>"
        owned[symbol].append((node.lineno, value))
    return owned


def _project_budget_writers(path, owned_strings):
    writers = []
    for symbol, values in owned_strings.items():
        strings = [value for _line, value in values]
        for line, value in values:
            for match in _PROJECT_INSERT_RE.finditer(value):
                columns = {
                    column.strip().strip('"').lower()
                    for column in match.group(1).split(",")
                }
                if "budget" in columns:
                    writers.append({
                        "file": path,
                        "symbol": symbol,
                        "line": line,
                        "operation": "insert",
                    })
            for match in _PROJECT_UPDATE_RE.finditer(value):
                if re.search(r"\bbudget\s*=", match.group(1), re.IGNORECASE):
                    writers.append({
                        "file": path,
                        "symbol": symbol,
                        "line": line,
                        "operation": "update",
                    })
        if (
            strings.count("budget") >= 2
            and any(
                re.search(
                    r"\bupdate\s+(?:public\.)?projects\s+set\b",
                    value,
                    re.IGNORECASE,
                )
                for value in strings
            )
        ):
            writers.append({
                "file": path,
                "symbol": symbol,
                "line": min(line for line, value in values if value == "budget"),
                "operation": "dynamic_update",
            })
    return writers


def _e6_dml(path, owned_strings):
    if not path.startswith(E6_PACKAGE_PREFIX):
        return []
    statements = []
    for symbol, values in owned_strings.items():
        for line, value in values:
            for match in _DML_RE.finditer(value):
                operation = match.group(1).lower().split()[0]
                table = match.group(2).lower()
                if operation == "update" and table == "or":
                    # PostgreSQL trigger event syntax: BEFORE UPDATE OR DELETE.
                    continue
                statements.append({
                    "file": path,
                    "symbol": symbol,
                    "line": line,
                    "operation": operation,
                    "table": table,
                })
    return statements


def audit_writer_inventory(
    repo_root=None,
    *,
    source_files=None,
    enforce_complete_inventory=None,
):
    """Prove the accepted manual surface and absence of E6 runtime DML."""

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    if enforce_complete_inventory is None:
        enforce_complete_inventory = source_files is None
    if source_files is None:
        source_files = _repository_sources(repo_root)

    violations = []
    writers = []
    e6_dml = []
    for raw_path, source in sorted(source_files.items()):
        path = Path(raw_path).as_posix()
        try:
            tree = ast.parse(source or "", filename=path)
        except (SyntaxError, ValueError):
            violations.append({
                "reasonCode": "source_parse_error",
                "file": path,
            })
            continue
        owned_strings = _string_owners(tree)
        writers.extend(_project_budget_writers(path, owned_strings))
        e6_dml.extend(_e6_dml(path, owned_strings))

    actual = Counter(
        (item["file"], item["symbol"], item["operation"])
        for item in writers
    )
    for item in writers:
        signature = (item["file"], item["symbol"], item["operation"])
        if signature not in EXPECTED_PROJECT_BUDGET_WRITERS:
            violations.append({
                "reasonCode": "project_budget_writer_not_allowlisted",
                **item,
            })
    if enforce_complete_inventory and actual != EXPECTED_PROJECT_BUDGET_WRITERS:
        violations.append({
            "reasonCode": "project_budget_writer_inventory_mismatch",
            "expected": sum(EXPECTED_PROJECT_BUDGET_WRITERS.values()),
            "actual": sum(actual.values()),
        })
    for item in e6_dml:
        violations.append({
            "reasonCode": "e6_baseline_dml_present",
            **item,
        })

    ready = not violations
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "writerInventoryReady": ready,
        "projectBudgetWriters": sum(actual.values()),
        "expectedProjectBudgetWriters": sum(
            EXPECTED_PROJECT_BUDGET_WRITERS.values()
        ),
        "e6DmlStatements": len(e6_dml),
        "violationCount": len(violations),
        "violations": violations[:MAX_VIOLATIONS],
        "violationsTruncated": len(violations) > MAX_VIOLATIONS,
    }


__all__ = ["audit_writer_inventory"]
