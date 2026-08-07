"""Static E6 route, entrypoint, smoke and integration-proof inventory."""

import ast
import re
from collections import Counter
from pathlib import Path


MAX_VIOLATIONS = 100
EXPECTED_ROUTES = Counter({
    (
        "backend/features/project_budget_adjustments/preview_routes.py",
        "get_budget_adjustment_preview",
        "get",
        "/estimate-reconciliations/{reconciliation_id}/budget-adjustment-preview",
    ): 1,
    (
        "backend/features/project_budget_adjustments/runtime_routes.py",
        "approve_budget_adjustment",
        "post",
        "/estimate-reconciliations/{reconciliation_id}/budget-adjustment-approval",
    ): 1,
    (
        "backend/features/project_budget_adjustments/runtime_routes.py",
        "get_project_budget_adjustments",
        "get",
        "/projects/{project_id}/budget-adjustments",
    ): 1,
})
EXPECTED_REGISTRATIONS = Counter({
    "register_project_budget_adjustment_preview_module": 1,
    "register_project_budget_adjustment_runtime_module": 1,
})
EXPECTED_SMOKE_CHECKS = Counter({
    (
        "check_not_spa_fallback",
        "estimate budget adjustment preview route",
        "/estimate-reconciliations/1/budget-adjustment-preview",
        "401 403",
    ): 1,
    (
        "check_post_not_spa_fallback",
        "estimate budget adjustment approval route",
        "/estimate-reconciliations/1/budget-adjustment-approval",
        "401 403 422",
    ): 1,
    (
        "check_not_spa_fallback",
        "project budget adjustment history route",
        "/projects/1/budget-adjustments",
        "401 403",
    ): 1,
})
EXPECTED_KERNEL_ENTRYPOINTS = Counter({
    (
        "backend/features/project_budget_adjustments/runtime_routes.py",
        "approve_budget_adjustment",
        "apply_adjustment",
    ): 1,
})
EXPECTED_KERNEL_IMPORTS = Counter({
    (
        "backend/features/project_budget_adjustments/runtime_routes.py",
        "apply_budget_adjustment",
        "apply_budget_adjustment",
    ): 1,
})
REQUIRED_INTEGRATION_CHECKS = {
    "backend/features/project_budget_adjustments/test_postgres_schema.py": (
        "test_transactional_kernel_applies_delta_once_and_is_idempotent",
        "test_stale_hash_and_source_drift_roll_back_without_receipt",
        "test_budget_conflict_after_receipt_insert_rolls_back_both_writes",
        "test_apply_preserves_protected_history_byte_for_byte",
        "test_concurrent_double_approval_changes_budget_once",
        "test_zzz_readiness_gate_is_read_only_and_green",
    ),
    "backend/features/project_budget_adjustments/test_runtime_routes.py": (
        "test_missing_approval_body_uses_fixed_public_error_code",
        "test_invalid_history_range_uses_fixed_public_error_code",
        "test_exact_approval_commits_once_in_serializable_transaction",
        "test_idempotent_approval_rolls_back_without_commit",
        "test_invalid_identity_and_non_leader_never_reach_approval_kernel",
        "test_approval_maps_fixed_domain_and_write_conflicts",
        "test_history_is_tenant_bound_newest_first_bounded_and_read_only",
    ),
}
_SMOKE_RE = re.compile(
    r'\b(check_(?:post_)?not_spa_fallback)\s+"([^"]+)"\s+'
    r'"\$BASE_URL([^"]+)"\s+"([^"]+)"'
)


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _repository_sources(root):
    return {
        path.relative_to(root).as_posix(): _read(path)
        for path in sorted((root / "backend").rglob("*.py"))
        if not path.name.startswith("test_")
        and "__pycache__" not in path.parts
    }


def _parse(path, source, violations):
    try:
        return ast.parse(source or "", filename=path)
    except (SyntaxError, ValueError):
        violations.append({
            "reasonCode": "source_parse_error",
            "file": path,
        })
        return None


def _literal_string(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(
        node.value, str
    ) else None


def _route_inventory(path, tree):
    routes = Counter()
    if tree is None:
        return routes
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                not isinstance(decorator, ast.Call)
                or not isinstance(decorator.func, ast.Attribute)
                or decorator.func.attr.lower() not in {"get", "post"}
                or not decorator.args
            ):
                continue
            route = _literal_string(decorator.args[0])
            if route is not None:
                routes[(path, node.name, decorator.func.attr.lower(), route)] += 1
    return routes


def _function_owners(tree):
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    owners = {}
    for node in ast.walk(tree):
        parent = parents.get(node)
        while parent is not None and not isinstance(
            parent, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            parent = parents.get(parent)
        owners[node] = parent.name if parent is not None else "<module>"
    return owners


def _kernel_entrypoints(path, tree):
    entries = Counter()
    if tree is None:
        return entries
    owners = _function_owners(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name in {"apply_adjustment", "apply_budget_adjustment"}:
            entries[(path, owners.get(node, "<module>"), name)] += 1
    return entries


def _kernel_imports(path, tree):
    imports = Counter()
    if tree is None:
        return imports
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            if alias.name == "apply_budget_adjustment":
                imports[(
                    path,
                    alias.name,
                    alias.asname or alias.name,
                )] += 1
    return imports


def _registration_inventory(source, violations):
    tree = _parse("backend/main.py", source, violations)
    registrations = Counter()
    if tree is None:
        return registrations
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue
        if name.startswith("register_project_budget_adjustment"):
            registrations[name] += 1
    return registrations


def _smoke_inventory(source):
    return Counter(
        tuple(match)
        for match in _SMOKE_RE.findall(source or "")
        if "budget adjustment" in match[1]
    )


def _integration_names(path, source, violations):
    tree = _parse(path, source, violations)
    if tree is None:
        return set()
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def audit_cutover_inventory(
    repo_root=None,
    *,
    route_sources=None,
    application_sources=None,
    main_source=None,
    smoke_source=None,
    integration_test_sources=None,
):
    """Return deterministic evidence that E6 has one reviewed runtime path."""

    root = Path(repo_root or Path(__file__).resolve().parents[3]).resolve()
    injected_routes = route_sources is not None
    if route_sources is None:
        route_sources = {
            path.relative_to(root).as_posix(): _read(path)
            for path in sorted(
                (root / "backend/features/project_budget_adjustments").glob(
                    "*.py"
                )
            )
            if not path.name.startswith("test_")
        }
    if application_sources is None:
        application_sources = (
            route_sources if injected_routes else _repository_sources(root)
        )
    if main_source is None:
        main_source = _read(root / "backend/main.py")
    if smoke_source is None:
        smoke_source = _read(root / "scripts/prod-smoke-check.sh")
    if integration_test_sources is None:
        integration_test_sources = {
            path: _read(root / path)
            for path in REQUIRED_INTEGRATION_CHECKS
        }

    violations = []
    routes = Counter()
    route_trees = {}
    for raw_path, source in sorted(route_sources.items()):
        path = Path(raw_path).as_posix()
        tree = _parse(path, source, violations)
        route_trees[path] = tree
        routes.update(_route_inventory(path, tree))
    route_inventory_ready = routes == EXPECTED_ROUTES
    if not route_inventory_ready:
        violations.append({
            "reasonCode": "budget_adjustment_route_inventory_mismatch",
            "expected": sum(EXPECTED_ROUTES.values()),
            "actual": sum(routes.values()),
        })

    registrations = _registration_inventory(main_source, violations)
    registration_ready = registrations == EXPECTED_REGISTRATIONS
    if not registration_ready:
        violations.append({
            "reasonCode": "budget_adjustment_registration_inventory_mismatch",
            "expected": sum(EXPECTED_REGISTRATIONS.values()),
            "actual": sum(registrations.values()),
        })

    smoke_checks = _smoke_inventory(smoke_source)
    smoke_ready = smoke_checks == EXPECTED_SMOKE_CHECKS
    if not smoke_ready:
        violations.append({
            "reasonCode": "budget_adjustment_smoke_inventory_mismatch",
            "expected": sum(EXPECTED_SMOKE_CHECKS.values()),
            "actual": sum(smoke_checks.values()),
        })

    entrypoints = Counter()
    kernel_imports = Counter()
    for raw_path, source in sorted(application_sources.items()):
        path = Path(raw_path).as_posix()
        tree = (
            route_trees[path]
            if path in route_trees and route_sources.get(raw_path) == source
            else _parse(path, source, violations)
        )
        entrypoints.update(_kernel_entrypoints(path, tree))
        kernel_imports.update(_kernel_imports(path, tree))
    kernel_boundary_ready = bool(
        entrypoints == EXPECTED_KERNEL_ENTRYPOINTS
        and kernel_imports == EXPECTED_KERNEL_IMPORTS
    )
    if not kernel_boundary_ready:
        violations.append({
            "reasonCode": "budget_adjustment_kernel_entrypoint_mismatch",
            "expectedCalls": sum(EXPECTED_KERNEL_ENTRYPOINTS.values()),
            "actualCalls": sum(entrypoints.values()),
            "expectedImports": sum(EXPECTED_KERNEL_IMPORTS.values()),
            "actualImports": sum(kernel_imports.values()),
        })

    missing_checks = []
    for path, required_names in REQUIRED_INTEGRATION_CHECKS.items():
        present = _integration_names(
            path,
            integration_test_sources.get(path, ""),
            violations,
        )
        missing_checks.extend(
            name for name in required_names if name not in present
        )
    for name in missing_checks:
        violations.append({
            "reasonCode": "integration_check_missing",
            "check": name,
        })
    integration_ready = not missing_checks and not any(
        item.get("reasonCode") == "source_parse_error"
        and str(item.get("file") or "").startswith(
            "backend/features/project_budget_adjustments/test_"
        )
        for item in violations
    )

    route_ready = bool(
        route_inventory_ready
        and registration_ready
        and smoke_ready
        and kernel_boundary_ready
        and not any(
            item.get("reasonCode") == "source_parse_error"
            and not str(item.get("file") or "").startswith(
                "backend/features/project_budget_adjustments/test_"
            )
            for item in violations
        )
    )
    ready = route_ready and integration_ready and not violations
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "routeInventoryReady": route_ready,
        "integrationInventoryReady": integration_ready,
        "routeCount": sum(routes.values()),
        "expectedRouteCount": sum(EXPECTED_ROUTES.values()),
        "registrationCount": sum(registrations.values()),
        "expectedRegistrationCount": sum(EXPECTED_REGISTRATIONS.values()),
        "smokeCheckCount": sum(smoke_checks.values()),
        "expectedSmokeCheckCount": sum(EXPECTED_SMOKE_CHECKS.values()),
        "kernelEntrypointCount": sum(entrypoints.values()),
        "expectedKernelEntrypointCount": sum(
            EXPECTED_KERNEL_ENTRYPOINTS.values()
        ),
        "kernelImportCount": sum(kernel_imports.values()),
        "expectedKernelImportCount": sum(EXPECTED_KERNEL_IMPORTS.values()),
        "requiredIntegrationChecks": sum(
            len(names) for names in REQUIRED_INTEGRATION_CHECKS.values()
        ),
        "missingIntegrationChecks": missing_checks,
        "violationCount": len(violations),
        "violations": violations[:MAX_VIOLATIONS],
        "violationsTruncated": len(violations) > MAX_VIOLATIONS,
    }


__all__ = [
    "EXPECTED_KERNEL_ENTRYPOINTS",
    "EXPECTED_KERNEL_IMPORTS",
    "EXPECTED_REGISTRATIONS",
    "EXPECTED_ROUTES",
    "EXPECTED_SMOKE_CHECKS",
    "REQUIRED_INTEGRATION_CHECKS",
    "audit_cutover_inventory",
]
