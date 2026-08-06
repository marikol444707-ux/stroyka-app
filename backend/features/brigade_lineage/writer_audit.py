"""Read-only static audit of brigade contract item mutation statements."""

import ast
import re
import textwrap
from pathlib import Path


_INSERT_TOKEN = "insert into brigade_contract_items"
_UPDATE_TOKEN = "update brigade_contract_items"
_EXPECTED_INSERT_STATEMENTS = 4
_EXPECTED_UPDATE_STATEMENTS = 5
_INSERT_WRITERS = {
    "backend/features/brigade_access/item_routes.py",
    "backend/features/brigade_lineage/writer_service.py",
    "backend/features/estimate_row_transfer/assignment_apply.py",
}
_UPDATE_COLUMNS = {
    "backend/features/brigade_lineage/migration.py": {"source_type"},
    "backend/main.py": {"done_quantity"},
    "backend/features/brigade_access/item_routes.py": {
        "quantity",
        "price_brigade",
        "price_smeta",
        "done_quantity",
        "work_package",
    },
    "backend/features/estimate_row_transfer/assignment_apply.py": {"quantity"},
}
_SET_RE = re.compile(r"\bset\b(.*?)\bwhere\b", re.IGNORECASE | re.DOTALL)
_ASSIGNMENT_RE = re.compile(r"(?:^|,)\s*([a-z_][a-z0-9_]*)\s*=", re.IGNORECASE)
_FUZZY_LOOKUP_RE = re.compile(
    r"lower\s*\(\s*trim\s*\(\s*coalesce\s*\(\s*bci\.description",
    re.IGNORECASE,
)


def _default_source_files(repo_root):
    root = Path(repo_root).resolve()
    result = {}
    for path in sorted((root / "backend").rglob("*.py")):
        if path.name.startswith("test_") or "__pycache__" in path.parts:
            continue
        result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return result


def _sql_calls(path, source, violations):
    try:
        tree = ast.parse(textwrap.dedent(source), filename=path)
    except (SyntaxError, ValueError):
        violations.append({"code": "source_parse_error", "file": path, "line": None})
        return []
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "execute":
            continue
        sql_node = node.args[0]
        if not isinstance(sql_node, ast.Constant) or not isinstance(sql_node.value, str):
            continue
        normalized = " ".join(sql_node.value.split())
        lowered = re.sub(
            r"\b(insert\s+into|update)\s+public\.",
            lambda match: match.group(1) + " ",
            normalized.lower(),
        )
        if _INSERT_TOKEN in lowered or _UPDATE_TOKEN in lowered:
            calls.append((node.lineno, normalized, lowered))
    return calls


def audit_brigade_contract_item_writers(repo_root=None, *, source_files=None):
    """Report unexpected inserts or updates without executing application code."""
    enforce_complete_inventory = source_files is None
    if source_files is None:
        if repo_root is None:
            repo_root = Path(__file__).resolve().parents[3]
        source_files = _default_source_files(repo_root)
    violations = []
    insert_count = 0
    update_count = 0
    for raw_path, source in sorted(source_files.items()):
        path = Path(raw_path).as_posix()
        fuzzy_lookup = _FUZZY_LOOKUP_RE.search(source)
        if fuzzy_lookup:
            violations.append({
                "code": "fuzzy_contract_item_lookup",
                "file": path,
                "line": source.count("\n", 0, fuzzy_lookup.start()) + 1,
            })
        for line, sql, lowered in _sql_calls(path, source, violations):
            if _INSERT_TOKEN in lowered:
                insert_count += 1
                if path not in _INSERT_WRITERS:
                    violations.append({
                        "code": "insert_writer_not_allowlisted",
                        "file": path,
                        "line": line,
                    })
                if "source_type" not in lowered:
                    violations.append({
                        "code": "insert_source_type_missing",
                        "file": path,
                        "line": line,
                    })
            if _UPDATE_TOKEN in lowered:
                update_count += 1
                allowed = _UPDATE_COLUMNS.get(path)
                if allowed is None:
                    violations.append({
                        "code": "update_writer_not_allowlisted",
                        "file": path,
                        "line": line,
                    })
                    allowed = set()
                match = _SET_RE.search(sql)
                columns = set(_ASSIGNMENT_RE.findall(match.group(1) if match else ""))
                for column in sorted(column.lower() for column in columns if column.lower() not in allowed):
                    violations.append({
                        "code": "unsafe_update_column",
                        "file": path,
                        "line": line,
                        "column": column,
                    })
    if enforce_complete_inventory and insert_count != _EXPECTED_INSERT_STATEMENTS:
        violations.append({
            "code": "insert_writer_count_mismatch",
            "expected": _EXPECTED_INSERT_STATEMENTS,
            "actual": insert_count,
        })
    if enforce_complete_inventory and update_count != _EXPECTED_UPDATE_STATEMENTS:
        violations.append({
            "code": "update_writer_count_mismatch",
            "expected": _EXPECTED_UPDATE_STATEMENTS,
            "actual": update_count,
        })
    return {
        "ok": not violations,
        "dryRun": True,
        "writesAttempted": 0,
        "insertStatements": insert_count,
        "updateStatements": update_count,
        "violations": violations,
    }
