"""Static inventory of active-estimate material-control selection paths."""

import ast
import re
import textwrap
from pathlib import Path


MAX_VIOLATIONS = 100
EXPECTED_CANDIDATES = {
    (
        "src/features/estimates/projectEstimateRuntime.jsx",
        "activeEstimatesForProject",
    ),
    ("backend/main.py", "_supply_material_estimate_control"),
    ("backend/main.py", "_supply_linked_work_estimate_control"),
    ("backend/main.py", "_run_project_ai_control"),
    ("backend/main.py", "update_estimate_status"),
    ("backend/main.py", "_generate_material_norm_suggestions"),
    (
        "backend/features/project_budget_adjustments/preview_storage.py",
        "load_budget_adjustment_source",
    ),
}

_ACTIVE_SQL_RE = re.compile(
    r"\b(?:[a-z_][a-z0-9_]*\.)?status\s*=\s*'активная'",
    re.IGNORECASE,
)
_NAME_SQL_RE = re.compile(
    r"\b(?:[a-z_][a-z0-9_]*\.)?project_name\s*=\s*%s",
    re.IGNORECASE,
)
_FRONTEND_OWNER_MATCHER_RE = re.compile(r"\bsameStoredProjectOwner\s*\(")


def _parameterized_owner_sql_predicate(sql, column):
    return bool(re.search(
        rf"\b(?:[a-z_][a-z0-9_]*\.)?{column}\s*=\s*%s",
        sql,
        re.IGNORECASE,
    ))


def _correlated_owner_alias_pairs(sql, column):
    correlated_target = (
        "company_id" if column == "company_id" else "(?:project_id|id)"
    )
    correlated = re.compile(
        rf"\b(?P<left>[a-z_][a-z0-9_]*)\.{column}\s*=\s*"
        rf"(?P<right>[a-z_][a-z0-9_]*)\.{correlated_target}\b",
        re.IGNORECASE,
    )
    return {
        (match.group("left").lower(), match.group("right").lower())
        for match in correlated.finditer(sql)
        if match.group("left").lower() != match.group("right").lower()
    }


def _owner_sql_scope(sql):
    if (
        _parameterized_owner_sql_predicate(sql, "company_id")
        and _parameterized_owner_sql_predicate(sql, "project_id")
    ):
        return True
    return bool(
        _correlated_owner_alias_pairs(sql, "company_id")
        & _correlated_owner_alias_pairs(sql, "project_id")
    )


def _repository_sources(repo_root):
    root = Path(repo_root).resolve()
    sources = {}
    for path in sorted((root / "backend").rglob("*.py")):
        if path.name.startswith("test_") or "__pycache__" in path.parts:
            continue
        sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    for suffix in ("*.js", "*.jsx"):
        for path in sorted((root / "src").rglob(suffix)):
            if ".test." in path.name:
                continue
            sources[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return sources


def _python_candidates(path, source, parse_errors):
    try:
        tree = ast.parse(textwrap.dedent(source), filename=path)
    except (SyntaxError, ValueError):
        parse_errors.append({
            "reasonCode": "active_estimate_source_parse_error",
            "file": path,
        })
        return []
    candidates = []

    def function_strings(function_node):
        values = []

        def visit(node):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    values.append(child.value)
                visit(child)

        for statement in function_node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(statement, ast.Constant) and isinstance(statement.value, str):
                values.append(statement.value)
            visit(statement)
        return values

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        strings = function_strings(node)
        sql = " ".join(" ".join(value.split()) for value in strings).lower()
        if not (
            re.search(r"\bfrom\s+(?:public\.)?estimates\b", sql)
            and _ACTIVE_SQL_RE.search(sql)
            and "sections_json" in sql
            and "smeta_type" in sql
        ):
            continue
        candidates.append({
            "file": path,
            "symbol": node.name,
            "line": node.lineno,
            "surface": "backend_sql",
            "nameScoped": bool(_NAME_SQL_RE.search(sql)),
            "ownerScoped": _owner_sql_scope(sql),
        })
    return candidates


def _javascript_block(source, start):
    arrow = source.find("=>", start)
    opening = source.find("{", arrow + 2) if arrow >= 0 else -1
    if opening < 0:
        end = source.find(";", arrow + 2)
        return source[start:end + 1 if end >= 0 else len(source)]
    depth = 0
    quote = None
    escaped = False
    index = opening
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
        index += 1
    return source[start:]


def _javascript_candidates(path, source):
    candidates = []
    for match in re.finditer(
        r"\b(?:const|let|var)\s+(activeEstimatesForProject)\s*=",
        source,
    ):
        block = _javascript_block(source, match.start())
        candidates.append({
            "file": path,
            "symbol": match.group(1),
            "line": source.count("\n", 0, match.start()) + 1,
            "surface": "frontend_selector",
            "nameScoped": ".projectName" in block,
            "ownerScoped": (
                bool(_FRONTEND_OWNER_MATCHER_RE.search(block))
                or (
                    ".companyId" in block
                    and ".projectId" in block
                    and ".id" in block
                )
            ),
        })
    return candidates


def audit_runtime_inventory(
    repo_root=None,
    *,
    source_files=None,
    expected_candidates=EXPECTED_CANDIDATES,
):
    """Return deterministic source metadata; never import application modules."""

    if source_files is None:
        repo_root = repo_root or Path(__file__).resolve().parents[3]
        source_files = _repository_sources(repo_root)
    parse_errors = []
    candidates = []
    for path, source in sorted(source_files.items()):
        normalized_path = Path(path).as_posix()
        if normalized_path.endswith(".py"):
            candidates.extend(
                _python_candidates(normalized_path, source, parse_errors)
            )
        elif normalized_path.endswith((".js", ".jsx")):
            candidates.extend(_javascript_candidates(normalized_path, source))

    actual = {(item["file"], item["symbol"]) for item in candidates}
    expected = set(expected_candidates)
    violations = list(parse_errors)
    for file_name, symbol in sorted(expected - actual):
        violations.append({
            "reasonCode": "active_estimate_inventory_missing",
            "file": file_name,
            "symbol": symbol,
        })
    for candidate in sorted(
        candidates, key=lambda item: (item["file"], item["line"], item["symbol"])
    ):
        identity = (candidate["file"], candidate["symbol"])
        if identity not in expected:
            violations.append({
                "reasonCode": "active_estimate_inventory_unreviewed",
                "file": candidate["file"],
                "symbol": candidate["symbol"],
                "line": candidate["line"],
            })
        if candidate["nameScoped"]:
            reason = (
                "frontend_active_estimate_name_selector"
                if candidate["surface"] == "frontend_selector"
                else "backend_active_estimate_name_query"
            )
        elif not candidate["ownerScoped"]:
            reason = (
                "frontend_active_estimate_owner_predicate_missing"
                if candidate["surface"] == "frontend_selector"
                else "backend_active_estimate_owner_predicate_missing"
            )
        else:
            reason = None
        if reason:
            violations.append({
                "reasonCode": reason,
                "file": candidate["file"],
                "symbol": candidate["symbol"],
                "line": candidate["line"],
            })

    runtime_ready = not violations
    return {
        "ok": not parse_errors,
        "dryRun": True,
        "writesAttempted": 0,
        "runtimeInventoryReady": runtime_ready,
        "candidateCount": len(candidates),
        "expectedCandidateCount": len(expected),
        "nameScopedCount": sum(
            1 for candidate in candidates if candidate["nameScoped"]
        ),
        "ownerScopedCount": sum(
            1
            for candidate in candidates
            if candidate["ownerScoped"] and not candidate["nameScoped"]
        ),
        "violationCount": len(violations),
        "violations": violations[:MAX_VIOLATIONS],
        "violationsTruncated": len(violations) > MAX_VIOLATIONS,
    }


__all__ = ["EXPECTED_CANDIDATES", "audit_runtime_inventory"]
