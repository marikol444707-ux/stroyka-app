"""Read-only inventory of provider-specific model access in production code."""

import ast
from pathlib import Path

from backend.features.model_gateway.policies import MODEL_CAPABILITIES


_EXPECTED_ACCESS = (
    ("backend/main.py", "_repair_invoice_scan_json", "invoice_scan"),
    ("backend/main.py", "_retry_invoice_scan_compact_json", "invoice_scan"),
    ("backend/main.py", "scan_invoice", "invoice_scan"),
)

_EXPECTED_BY_KEY = {
    (path, symbol): capability
    for path, symbol, capability in _EXPECTED_ACCESS
}
_PROVIDER_HOSTS = (
    "ai.api.cloud.yandex.net",
    "llm.api.cloud.yandex.net",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
)
_PROVIDER_IMPORT_ROOTS = frozenset({
    "anthropic",
    "groq",
    "mistralai",
    "ollama",
    "openai",
})
_PROVIDER_IMPORT_PREFIXES = (
    "google.genai",
    "google.generativeai",
)


def _definitions(tree):
    definitions = []

    def visit(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol = f"{prefix}.{node.name}" if prefix else node.name
                definitions.append((symbol, node))
                visit(node.body, symbol)
            elif isinstance(node, ast.ClassDef):
                class_name = f"{prefix}.{node.name}" if prefix else node.name
                visit(node.body, class_name)

    visit(tree.body)
    return definitions


def _dotted_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _provider_constant_names(tree):
    names = set()
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not isinstance(value, ast.Constant) or type(value.value) is not str:
            continue
        if not any(host in value.value for host in _PROVIDER_HOSTS):
            continue
        names.update(target.id for target in targets if isinstance(target, ast.Name))
    return frozenset(names)


def _node_is_provider_access(node, provider_constants):
    if isinstance(node, ast.Import):
        return any(
            alias.name.split(".")[0] in _PROVIDER_IMPORT_ROOTS
            or alias.name.startswith(_PROVIDER_IMPORT_PREFIXES)
            for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return (
            module.split(".")[0] in _PROVIDER_IMPORT_ROOTS
            or module.startswith(_PROVIDER_IMPORT_PREFIXES)
        )
    if isinstance(node, ast.Call):
        name = _dotted_name(node.func)
        if name == "OpenAI" or name.endswith(".OpenAI"):
            return True
        if name.endswith(".responses.create"):
            return True
    if isinstance(node, ast.Name) and node.id in provider_constants:
        return True
    if isinstance(node, ast.Constant) and type(node.value) is str:
        return any(host in node.value for host in _PROVIDER_HOSTS)
    return False


def _innermost_symbol(definitions, line_number):
    matches = [
        (symbol, node)
        for symbol, node in definitions
        if node.lineno <= line_number <= getattr(node, "end_lineno", node.lineno)
    ]
    if not matches:
        return "<module>"
    return min(
        matches,
        key=lambda item: getattr(item[1], "end_lineno", item[1].lineno) - item[1].lineno,
    )[0]


def _scan_source(path, source):
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError):
        return {(path, "<parse_error>")}
    definitions = _definitions(tree)
    provider_constants = _provider_constant_names(tree)
    found = set()
    for node in ast.walk(tree):
        if not _node_is_provider_access(node, provider_constants):
            continue
        symbol = _innermost_symbol(definitions, getattr(node, "lineno", 0))
        if symbol != "<module>" or isinstance(node, ast.Call):
            found.add((path, symbol))
    return found


def scan_model_access_sources(sources, *, require_expected=False):
    found = set()
    for path, source in sorted(sources.items()):
        if path.startswith("backend/features/model_gateway/"):
            continue
        found.update(_scan_source(path, source))
    expected = set(_EXPECTED_BY_KEY)
    unexpected_keys = sorted(found - expected)
    missing_keys = sorted(expected - found) if require_expected else []
    access_points = [
        {
            "file": path,
            "symbol": symbol,
            "capability": _EXPECTED_BY_KEY[(path, symbol)],
        }
        for path, symbol in sorted(found & expected)
    ]
    return {
        "complete": not unexpected_keys and not missing_keys,
        "logicalCapabilityCount": len(MODEL_CAPABILITIES),
        "directAccessCount": len(found),
        "accessPoints": access_points,
        "unexpected": [
            {"file": path, "symbol": symbol}
            for path, symbol in unexpected_keys
        ],
        "missing": [
            {
                "file": path,
                "symbol": symbol,
                "capability": _EXPECTED_BY_KEY[(path, symbol)],
            }
            for path, symbol in missing_keys
        ],
        "writesAttempted": 0,
    }


def run_model_access_inventory(repo_root):
    root = Path(repo_root).resolve()
    backend_root = root / "backend"
    sources = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(backend_root.rglob("*.py"))
        if "__pycache__" not in path.parts
        and not path.name.startswith("test_")
    }
    return scan_model_access_sources(sources, require_expected=True)
