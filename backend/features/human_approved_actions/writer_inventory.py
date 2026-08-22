"""Read-only A12.1 inventory for the closed action contract boundary."""

import ast
import re
from pathlib import Path

from .contract import ACTION_POLICIES


INVENTORY_VERSION = 1

_PRODUCTION_FILES = (
    "backend/features/human_approved_actions/__init__.py",
    "backend/features/human_approved_actions/action_kernel.py",
    "backend/features/human_approved_actions/contract.py",
    "backend/features/human_approved_actions/runtime_routes.py",
    "backend/features/human_approved_actions/schema_contract.py",
    "backend/features/human_approved_actions/writer_inventory.py",
)

_MIGRATION_FILES = (
    "backend/features/human_approved_actions/schema_contract.py",
)

_KERNEL_FILES = (
    "backend/features/human_approved_actions/action_kernel.py",
)

_ROUTE_FILES = (
    "backend/features/human_approved_actions/runtime_routes.py",
)

_RUNTIME_SAFE_FILES = tuple(
    module for module in _PRODUCTION_FILES
    if (
        module not in _MIGRATION_FILES
        and module not in _KERNEL_FILES
        and module not in _ROUTE_FILES
    )
)

_EXPECTED_RUNTIME_REGISTRATIONS = (
    {
        "module": "backend/features/human_approved_actions/runtime_routes.py",
        "kind": "registration_function",
        "callable": "register_human_approved_action_routes",
    },
    {
        "module": "backend/features/human_approved_actions/runtime_routes.py",
        "kind": "route",
        "method": "GET",
        "path": "/human-approved-actions/history",
    },
    {
        "module": "backend/features/human_approved_actions/runtime_routes.py",
        "kind": "route",
        "method": "POST",
        "path": "/human-approved-actions/decisions",
    },
    {
        "module": "backend/features/human_approved_actions/runtime_routes.py",
        "kind": "route",
        "method": "POST",
        "path": "/human-approved-actions/proposals",
    },
)

_KERNEL_ALLOWED_IMPORTS = frozenset({
    "datetime",
    "psycopg2",
    "psycopg2.extras",
    "backend.features.human_approved_actions.contract",
    "backend.features.warehouse_recommendation_preview",
    "backend.features.warehouse_recommendation_preview.content_contract",
    "backend.features.warehouse_recommendation_preview.content_preview",
})
_ROUTE_ALLOWED_IMPORTS = frozenset({
    "json",
    "math",
    "re",
    "threading",
    "time",
    "collections",
    "typing",
    "fastapi",
    "fastapi.responses",
    "backend.auth",
    ".contract",
})
_ROUTE_DATABASE_ATTRIBUTES = frozenset({
    "commit", "connect", "cursor", "execute", "executemany", "rollback",
    "set_session",
})
_KERNEL_WRITE_TARGETS = frozenset({
    "human_action_proposals", "human_action_events", "audit_log",
})
_INSERT_TARGET_RE = re.compile(
    r"\bINSERT\s+INTO\s+(?:public\.)?([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _kernel_sql_inventory(tree):
    targets = set()
    forbidden = False
    if tree is None:
        return targets, forbidden
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or type(node.value) is not str:
            continue
        compact = " ".join(node.value.split())
        targets.update(
            target.lower() for target in _INSERT_TARGET_RE.findall(compact)
        )
        if "public." in compact and compact.upper().startswith((
            "ALTER ", "CREATE ", "DELETE ", "DROP ", "TRUNCATE ",
            "UPDATE ",
        )):
            forbidden = True
    return targets, forbidden

ACTION_SOURCE_SURFACES = (
    (
        "backend/features/warehouse_recommendation_preview/content_preview.py",
        "run_warehouse_anomaly_content_preview",
    ),
)

PROTECTED_WRITER_SURFACES = (
    (
        "backend/features/accounting_exception_checks/"
        "ownership_remediation_runner.py",
        "run_accounting_ownership_remediation",
    ),
    (
        "backend/features/project_budget_adjustments/approval.py",
        "apply_budget_adjustment",
    ),
    (
        "backend/features/supply_recommendation_preview/"
        "material_capability_writer.py",
        "run_material_capability_confirmation_write",
    ),
    (
        "backend/features/supply_recommendation_preview/"
        "material_capability_writer.py",
        "run_material_capability_revocation_write",
    ),
)

PROTECTED_WRITER_MODULES = (
    "backend/features/accountable_payments/routes.py",
    "backend/features/contracts/routes.py",
    "backend/features/estimate_changes/routes.py",
    "backend/features/estimate_reconciliations/routes.py",
    "backend/features/estimate_row_transfer/routes.py",
    "backend/features/estimate_versions/routes.py",
    "backend/features/expense_reports/routes.py",
    "backend/features/expenses/routes.py",
    "backend/features/interim_acts/routes.py",
    "backend/features/material_aliases/routes.py",
    "backend/features/material_packaging/routes.py",
    "backend/features/material_traceability/receipt_lots.py",
    "backend/features/materials/routes.py",
    "backend/features/own_expenses/routes.py",
    "backend/features/project_budget_adjustments/approval.py",
    "backend/features/salary_payments/routes.py",
    "backend/features/supply_history/routes.py",
    "backend/features/supply_recommendation_preview/"
    "material_capability_writer.py",
    "backend/features/supervisor_acts/routes.py",
)

_FORBIDDEN_IMPORT_ROOTS = frozenset({
    "fastapi",
    "psycopg2",
    "requests",
    "socket",
    "subprocess",
    "urllib",
})
_FORBIDDEN_IMPORT_FRAGMENTS = (
    "backend.db",
    ".routes",
    ".runtime",
    ".writer",
    ".schema",
    ".migration",
)
_DATABASE_ATTRIBUTES = frozenset({
    "add_api_route",
    "commit",
    "connect",
    "cursor",
    "delete",
    "execute",
    "executemany",
    "patch",
    "post",
    "put",
    "rollback",
    "set_session",
})
_SQL_RE = re.compile(
    r"\b(?:ALTER|CREATE|DELETE|DROP|INSERT|LOCK|SELECT|TRUNCATE|UPDATE)\b",
    re.IGNORECASE,
)


def _read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _parse(module, source, violations):
    if source is None:
        violations.append({
            "reasonCode": "module_missing",
            "module": module,
        })
        return None
    try:
        return ast.parse(source, filename=module)
    except (SyntaxError, ValueError):
        violations.append({
            "reasonCode": "source_parse_error",
            "module": module,
        })
        return None


def _defined_callables(tree):
    if tree is None:
        return frozenset()
    return frozenset(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )


def _import_names(tree):
    names = []
    if tree is None:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            names.append(prefix + (node.module or ""))
    return names


def _forbidden_import(name):
    root = name.lstrip(".").split(".", 1)[0]
    return (
        root in _FORBIDDEN_IMPORT_ROOTS
        or name == "backend.db"
        or any(fragment in name for fragment in _FORBIDDEN_IMPORT_FRAGMENTS)
    )


def _database_calls(module, tree, attributes=_DATABASE_ATTRIBUTES):
    calls = []
    if tree is None:
        return calls
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in attributes
        ):
            calls.append({
                "module": module,
                "line": node.lineno,
                "attribute": node.func.attr,
            })
    return calls


def _runtime_registrations(module, tree):
    registrations = []
    if tree is None:
        return registrations
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("register_"):
                registrations.append({
                    "module": module,
                    "kind": "registration_function",
                    "callable": node.name,
                })
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {
                        "get", "post", "put", "patch", "delete",
                    }
                ):
                    path = None
                    if (
                        len(decorator.args) == 1
                        and isinstance(decorator.args[0], ast.Constant)
                        and type(decorator.args[0].value) is str
                    ):
                        path = decorator.args[0].value
                    registrations.append({
                        "module": module,
                        "kind": "route",
                        "method": decorator.func.attr.upper(),
                        "path": path,
                    })
    return registrations


def _has_forbidden_sql(tree):
    if tree is None:
        return False
    return any(
        isinstance(node, ast.Constant)
        and type(node.value) is str
        and _SQL_RE.search(node.value) is not None
        for node in ast.walk(tree)
    )


def audit_human_approved_action_inventory(root):
    """Return a bounded static proof; never import or invoke reviewed writers."""

    root = Path(root)
    violations = []
    forbidden_imports = set()
    database_calls = []
    runtime_registrations = []
    kernel_write_targets = set()

    package = root / "backend/features/human_approved_actions"
    actual_production_files = tuple(sorted(
        path.relative_to(root).as_posix()
        for path in package.glob("*.py")
        if not path.name.startswith("test_")
    )) if package.is_dir() else ()
    for module in sorted(set(actual_production_files) - set(_PRODUCTION_FILES)):
        violations.append({
            "reasonCode": "unexpected_production_file",
            "module": module,
        })
    for module in sorted(set(_PRODUCTION_FILES) - set(actual_production_files)):
        violations.append({
            "reasonCode": "module_missing",
            "module": module,
        })

    for module in sorted(set(actual_production_files) | set(_PRODUCTION_FILES)):
        source = _read(root / module)
        tree = _parse(module, source, violations)
        if module in _RUNTIME_SAFE_FILES:
            imports = _import_names(tree)
            forbidden_imports.update(
                name for name in imports if _forbidden_import(name)
            )
            database_calls.extend(_database_calls(module, tree))
        if module in _KERNEL_FILES:
            imports = set(_import_names(tree))
            for name in sorted(imports - _KERNEL_ALLOWED_IMPORTS):
                violations.append({
                    "reasonCode": "kernel_import_not_allowlisted",
                    "module": module,
                    "detail": name,
                })
            module_targets, forbidden_mutation = _kernel_sql_inventory(tree)
            kernel_write_targets.update(module_targets)
            if forbidden_mutation:
                violations.append({
                    "reasonCode": "kernel_forbidden_mutation",
                    "module": module,
                })
        if module in _ROUTE_FILES:
            imports = set(_import_names(tree))
            for name in sorted(imports - _ROUTE_ALLOWED_IMPORTS):
                violations.append({
                    "reasonCode": "route_import_not_allowlisted",
                    "module": module,
                    "detail": name,
                })
            database_calls.extend(_database_calls(
                module, tree, _ROUTE_DATABASE_ATTRIBUTES,
            ))
            if _has_forbidden_sql(tree):
                violations.append({
                    "reasonCode": "route_sql_present",
                    "module": module,
                })
        runtime_registrations.extend(_runtime_registrations(module, tree))
        if module in _RUNTIME_SAFE_FILES and module.endswith((
            "/__init__.py", "/contract.py",
        )) and _has_forbidden_sql(tree):
            violations.append({
                "reasonCode": "forbidden_sql_text",
                "module": module,
            })

    reviewed_surfaces = ACTION_SOURCE_SURFACES + PROTECTED_WRITER_SURFACES
    parsed_reviewed = {}
    for module, callable_name in reviewed_surfaces:
        if module not in parsed_reviewed:
            parsed_reviewed[module] = _parse(
                module,
                _read(root / module),
                violations,
            )
        if callable_name not in _defined_callables(parsed_reviewed[module]):
            violations.append({
                "reasonCode": "reviewed_callable_missing",
                "module": module,
                "callable": callable_name,
            })

    for module in PROTECTED_WRITER_MODULES:
        if not (root / module).is_file():
            violations.append({
                "reasonCode": "protected_writer_module_missing",
                "module": module,
            })

    runtime_registrations.sort(key=lambda item: (
        item.get("module", ""),
        item.get("kind", ""),
        item.get("method", ""),
        item.get("path", ""),
        item.get("callable", ""),
    ))
    expected_registrations = sorted(
        (dict(item) for item in _EXPECTED_RUNTIME_REGISTRATIONS),
        key=lambda item: (
            item.get("module", ""),
            item.get("kind", ""),
            item.get("method", ""),
            item.get("path", ""),
            item.get("callable", ""),
        ),
    )
    if runtime_registrations != expected_registrations:
        violations.append({
            "reasonCode": "runtime_registration_mismatch",
            "module": "backend/features/human_approved_actions/runtime_routes.py",
        })

    main_source = _read(root / "backend/main.py")
    if main_source is None:
        violations.append({
            "reasonCode": "module_missing",
            "module": "backend/main.py",
        })
    else:
        required_main_fragments = (
            'os.getenv("HUMAN_APPROVED_ACTIONS_HTTP_ENABLED") == "true"',
            "HUMAN_APPROVED_ACTIONS_COMPANY_IDS",
            "register_human_approved_action_routes(app",
        )
        if any(
            fragment not in main_source for fragment in required_main_fragments
        ):
            violations.append({
                "reasonCode": "main_registration_missing",
                "module": "backend/main.py",
            })

    for name in sorted(forbidden_imports):
        violations.append({
            "reasonCode": "forbidden_import",
            "module": name,
        })
    if kernel_write_targets != _KERNEL_WRITE_TARGETS:
        violations.append({
            "reasonCode": "kernel_write_inventory_mismatch",
            "module": "backend/features/human_approved_actions/action_kernel.py",
            "detail": ",".join(sorted(kernel_write_targets)),
        })
    for item in database_calls:
        violations.append({
            "reasonCode": "database_or_route_call",
            "module": item["module"],
            "detail": item["attribute"],
        })
    violations.sort(key=lambda item: (
        item.get("reasonCode", ""),
        item.get("module", ""),
        item.get("callable", ""),
        item.get("detail", ""),
    ))
    return {
        "inventoryVersion": INVENTORY_VERSION,
        "ok": not violations,
        "actionKinds": sorted(ACTION_POLICIES),
        "effectKinds": sorted({
            policy.effect_kind for policy in ACTION_POLICIES.values()
        }),
        "productionFiles": list(_PRODUCTION_FILES),
        "migrationFiles": list(_MIGRATION_FILES),
        "kernelFiles": list(_KERNEL_FILES),
        "kernelWriteTargets": sorted(kernel_write_targets),
        "actionSourceSurfaces": [
            {"module": module, "callable": callable_name}
            for module, callable_name in ACTION_SOURCE_SURFACES
        ],
        "protectedWriterSurfaces": [
            {"module": module, "callable": callable_name}
            for module, callable_name in PROTECTED_WRITER_SURFACES
        ],
        "protectedWriterModules": list(PROTECTED_WRITER_MODULES),
        "runtimeRegistrations": runtime_registrations,
        "forbiddenImports": sorted(forbidden_imports),
        "databaseCalls": database_calls,
        "violations": violations,
    }


__all__ = []
