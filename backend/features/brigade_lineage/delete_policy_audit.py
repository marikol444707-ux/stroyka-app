"""Static, read-only audit of estimate deletion lineage protection."""

import ast
import re
from pathlib import Path


_DEPENDENCY_ASSIGNMENT = "DEPENDENCY_CHECKS"
_DEFAULT_PATH = Path("backend/features/estimate_deletion/service.py")


def _normalized_sql(value):
    return " ".join(str(value or "").lower().replace('"', "").split())


def _dependency_queries(source):
    tree = ast.parse(source)
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not any(
            isinstance(target, ast.Name) and target.id == _DEPENDENCY_ASSIGNMENT
            for target in targets
        ):
            continue
        raw = ast.literal_eval(value)
        queries = []
        for item in raw or ():
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                if isinstance(item[1], str):
                    queries.append(_normalized_sql(item[1]))
        return queries
    return None


def _has_exact_version_blocker(query):
    if not all(token in query for token in (
        "brigade_contract_items",
        "estimate_versions",
        "source_estimate_version_id",
        "estimate_id",
        "%s",
    )):
        return False
    bci_alias = _table_alias(query, "brigade_contract_items")
    version_alias = _table_alias(query, "estimate_versions")
    if not bci_alias or not version_alias or bci_alias == version_alias:
        return False
    bci = re.escape(bci_alias)
    version = re.escape(version_alias)
    join = re.search(
        rf"\b{version}\.id\s*=\s*{bci}\.source_estimate_version_id\b"
        rf"|\b{bci}\.source_estimate_version_id\s*=\s*{version}\.id\b",
        query,
    )
    estimate_filter = re.search(
        rf"\b{version}\.estimate_id\s*=\s*%s",
        query,
    )
    return bool(join and estimate_filter)


def _table_alias(query, table):
    reserved = "where|join|inner|left|right|full|cross|on|group|order|limit"
    match = re.search(
        rf"\b(?:from|join)\s+(?:public\.)?{re.escape(table)}\b"
        rf"(?:\s+(?:as\s+)?((?!(?:{reserved})\b)[a-z_][a-z0-9_]*))?",
        query,
    )
    if not match:
        return None
    return match.group(1) or table


def _legacy_fallback_scoped(query):
    return bool(re.search(
        r"(?:\w+\.)?source_type\s*=\s*'legacy'",
        query,
    ))


def _result(violations):
    ordered = [
        code
        for code in (
            "sourceParseError",
            "sourceReadError",
            "dependencyInventoryMissing",
            "exactEstimateVersionBlockerMissing",
            "legacyFallbackNotScoped",
        )
        if code in violations
    ]
    ready = not ordered
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "deleteRestrictionsReady": ready,
        "violations": ordered,
    }


def audit_estimate_delete_policy(repo_root=None, *, source=None):
    """Audit static dependency SQL without importing or executing route code."""
    if source is None:
        root = Path(repo_root).resolve() if repo_root is not None else Path(
            __file__
        ).resolve().parents[3]
        try:
            source = (root / _DEFAULT_PATH).read_text(encoding="utf-8")
        except OSError:
            return _result(["sourceReadError"])
    try:
        queries = _dependency_queries(source)
    except (SyntaxError, ValueError, TypeError):
        return _result(["sourceParseError"])
    if queries is None:
        return _result(["dependencyInventoryMissing"])

    violations = []
    if not any(_has_exact_version_blocker(query) for query in queries):
        violations.append("exactEstimateVersionBlockerMissing")
    fuzzy = [
        query
        for query in queries
        if "estimate_item_key" in query and " like " in query
    ]
    if any(not _legacy_fallback_scoped(query) for query in fuzzy):
        violations.append("legacyFallbackNotScoped")
    return _result(violations)
