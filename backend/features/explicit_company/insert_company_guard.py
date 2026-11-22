"""Find inserts into owned tables that leave company_id to a default."""

import ast
from pathlib import Path

from backend.features.explicit_company.company_backfill import TABLES

OWNED_TABLES = {table.lower() for table in TABLES}


def _is_test(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def _string_assignments(tree):
    strings = {}
    tuples = {}
    dict_keys = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            strings[target.id] = value.value
        elif (
            isinstance(value, ast.Tuple)
            and value.elts
            and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in value.elts)
        ):
            tuples[target.id] = [item.value for item in value.elts]
        elif isinstance(value, ast.DictComp) and value.generators:
            source = value.generators[0].iter
            if isinstance(source, ast.Name) and source.id in tuples:
                dict_keys[target.id] = tuples[source.id]
    return strings, tuples, dict_keys


def _flatten(expr, strings, tuples, dict_keys):
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.JoinedStr):
        return "".join(
            value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else "{expr}"
            for value in expr.values
        )
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        return _flatten(expr.left, strings, tuples, dict_keys) + _flatten(expr.right, strings, tuples, dict_keys)
    if isinstance(expr, ast.Name):
        if expr.id in strings:
            return strings[expr.id]
        if expr.id in tuples:
            return ",".join(tuples[expr.id])
        if expr.id in dict_keys:
            return ",".join(dict_keys[expr.id])
    if isinstance(expr, ast.Call) and expr.args:
        func = expr.func
        if isinstance(func, ast.Attribute) and func.attr == "join":
            return _flatten(expr.args[0], strings, tuples, dict_keys)
    return ""


def _column_list(sql, start):
    index = start
    while index < len(sql) and sql[index].isspace():
        index += 1
    if index >= len(sql) or sql[index] != "(":
        return None
    depth = 0
    chars = []
    for cursor in range(index, len(sql)):
        char = sql[cursor]
        if char == "(":
            depth += 1
            if depth > 1:
                chars.append(char)
        elif char == ")":
            depth -= 1
            if depth == 0:
                return "".join(chars)
            chars.append(char)
        else:
            chars.append(char)
    return None


def _column_names(columns):
    names = []
    for part in (columns or "").split(","):
        token = part.strip().strip('"').split()
        if token and not token[0].startswith("{") and token[0] != "{expr}":
            names.append(token[0].lower())
    return names


def missing_company_inserts_in_sql(sql):
    """Return owned tables whose INSERT or COPY column list omits company_id."""
    import re
    missing = []
    text = sql or ""
    insert_pattern = re.compile(
        r"\bINSERT\s+INTO\s+(?:ONLY\s+)?(?:public\.)?([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    )
    copy_pattern = re.compile(
        r"\bCOPY\s+(?:public\.)?([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    )
    for pattern in (insert_pattern, copy_pattern):
        for match in pattern.finditer(text):
            table = match.group(1).lower()
            if table not in OWNED_TABLES:
                continue
            columns = _column_list(text, match.end())
            if columns is None or "company_id" not in _column_names(columns):
                missing.append(table)
    return missing


def scan_backend_inserts(root: Path):
    findings = []
    for path in sorted(root.rglob("*.py")):
        if _is_test(path) or path.name == "insert_company_guard.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        strings, tuples, dict_keys = _string_assignments(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            arguments = list(node.args) + [keyword.value for keyword in node.keywords]
            for arg in arguments:
                sql = _flatten(arg, strings, tuples, dict_keys)
                upper = sql.upper()
                if "INSERT INTO" not in upper and "COPY " not in upper:
                    continue
                for table in missing_company_inserts_in_sql(sql):
                    findings.append(f"{path}:{getattr(node, 'lineno', 0)} {table}")
    return sorted(set(findings))
