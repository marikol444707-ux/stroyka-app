"""Static A7 shadow-execution and integration-proof inventory."""

import ast
import re
import textwrap
from collections import Counter
from pathlib import Path


MAX_VIOLATIONS = 100
_A7_PREFIX = "backend/features/estimate_revision_impact/"
_MAIN_PATH = "backend/main.py"
_REGISTRY_PATH = "backend/features/agent_jobs/handler_registry.py"
_RUNNER_PATH = "backend/features/agent_jobs/runner.py"
_HANDLER_PATH = _A7_PREFIX + "handler.py"
_PRODUCER_PATH = _A7_PREFIX + "producer.py"
_HANDOFF_PATH = _A7_PREFIX + "handoff.py"
_MAIN_HANDOFF_FUNCTIONS = (
    "create_estimate",
    "update_estimate",
    "update_estimate_status",
)
_REQUIRED_INTEGRATION_CHECKS = (
    "test_same_name_readiness_rolls_back_and_preserves_business_tables",
    "test_repeat_and_concurrent_enqueue_create_one_exact_job",
    "test_exact_runner_completes_only_selected_tenant_job",
    "test_failure_rolls_back_queue_and_preserves_business_tables",
    "test_final_readiness_is_read_only_and_exact",
)
_EXPECTED_OPERATIONAL_CALLS = Counter({
    (_PRODUCER_PATH, "prepare_estimate_revision_impact_job", "enqueue_job"): 1,
    (
        _HANDOFF_PATH,
        "handoff_estimate_revision_impact_transition.tracked_enqueue",
        "enqueue_job",
    ): 1,
    (_RUNNER_PATH, "AgentJobRunner.run_once", "complete_agent_job"): 1,
})
_ALLOWED_EXTERNAL_FEATURE_IMPORTS = frozenset({
    (
        _A7_PREFIX + "assignment_projection.py",
        "backend.features.brigade_lineage.readiness_report",
        "classify_contract_item",
    ),
    (
        _A7_PREFIX + "assignment_projection.py",
        "backend.features.estimate_row_transfer.audit",
        "classify_assignment_lineage_and_balance",
    ),
    (
        _A7_PREFIX + "combined_contract.py",
        "backend.features.project_budget_adjustments.plan",
        "BudgetAdjustmentPlanError",
    ),
    (
        _A7_PREFIX + "combined_contract.py",
        "backend.features.project_budget_adjustments.plan",
        "build_budget_adjustment_plan",
    ),
    (
        _A7_PREFIX + "combined_report.py",
        "backend.features.project_budget_adjustments.preview_service",
        "build_budget_adjustment_preview",
    ),
    (
        _A7_PREFIX + "contract.py",
        "backend.features.agent_change_dispatch.shadow",
        "build_estimate_activation_source_revision",
    ),
    (
        _A7_PREFIX + "contract.py",
        "features.agent_change_dispatch.shadow",
        "build_estimate_activation_source_revision",
    ),
    (
        _A7_PREFIX + "economics_projection.py",
        "backend.features.project_budget_adjustments.plan",
        "BudgetAdjustmentPlanError",
    ),
    (
        _A7_PREFIX + "economics_projection.py",
        "backend.features.project_budget_adjustments.plan",
        "build_budget_adjustment_plan",
    ),
    (
        _A7_PREFIX + "economics_projection.py",
        "backend.features.project_budget_adjustments.preview",
        "BudgetAdjustmentPreviewError",
    ),
    (
        _A7_PREFIX + "economics_projection.py",
        "backend.features.project_budget_adjustments.preview_service",
        "PUBLIC_PREVIEW_FIELDS",
    ),
    (
        _A7_PREFIX + "economics_projection.py",
        "backend.features.project_budget_adjustments.preview_service",
        "build_budget_adjustment_preview",
    ),
    (
        _HANDLER_PATH,
        "backend.features.agent_jobs.service",
        "AgentJobValidationError",
    ),
    (
        _HANDLER_PATH,
        "backend.features.agent_jobs.service",
        "serialize_safe_json_object",
    ),
    (
        _HANDOFF_PATH,
        "backend.features.agent_jobs.service",
        "enqueue_agent_job",
    ),
    (
        _HANDOFF_PATH,
        "features.agent_jobs.service",
        "enqueue_agent_job",
    ),
    (
        _A7_PREFIX + "material_projection.py",
        "backend.features.brigade_lineage.canonical",
        "parse_sections",
    ),
    (
        _A7_PREFIX + "material_projection.py",
        "backend.features.estimate_row_transfer.policy",
        "is_explicit_material_item",
    ),
    (
        _PRODUCER_PATH,
        "backend.features.agent_jobs.service",
        "enqueue_agent_job",
    ),
    (
        _PRODUCER_PATH,
        "features.agent_jobs.service",
        "enqueue_agent_job",
    ),
    (
        _A7_PREFIX + "readiness_report.py",
        "backend.features.agent_jobs.readiness_report",
        "build_report",
    ),
    (
        _A7_PREFIX + "supply_warehouse_audit.py",
        "backend.features.brigade_lineage.canonical",
        "parse_sections",
    ),
    (
        _A7_PREFIX + "supply_warehouse_projection.py",
        "backend.features.brigade_lineage.snapshot_service",
        "LineageResolutionError",
    ),
    (
        _A7_PREFIX + "supply_warehouse_projection.py",
        "backend.features.brigade_lineage.snapshot_service",
        "resolve_snapshot_item",
    ),
    (
        _A7_PREFIX + "supply_warehouse_projection.py",
        "backend.features.supply_estimate_refresh.service",
        "OPEN_SUPPLY_STATUSES",
    ),
})
_FORBIDDEN_IMPORT_FRAGMENTS = (
    "anthropic",
    "gemini",
    "messenger",
    "model_gateway",
    "notification",
    "openai",
    "telegram",
)
_DML_RE = re.compile(
    r"\b(insert\s+into|update|delete\s+from)\s+(?:public\.)?"
    r"([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _repository_sources(repo_root):
    root = Path(repo_root).resolve()
    paths = [
        path
        for path in sorted((root / "backend").rglob("*.py"))
        if not path.name.startswith("test_")
        and "__pycache__" not in path.parts
    ]
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in paths
    }


def _parse(path, source, violations):
    try:
        return ast.parse(textwrap.dedent(source or ""), filename=path)
    except (SyntaxError, ValueError):
        violations.append({
            "reasonCode": "source_parse_error",
            "file": path,
        })
        return None


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


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


def _find_definition(tree, symbol):
    return next(
        (node for name, node in _definitions(tree) if name == symbol),
        None,
    )


def _top_level_string_constants(tree):
    values = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        for target in targets:
            if isinstance(target, ast.Name):
                values[target.id] = value.value
    return values


def _integration_names(source):
    try:
        tree = ast.parse(source or "", filename="test_postgres_cutover.py")
    except (SyntaxError, ValueError):
        return set()
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _a7_dml(path, tree):
    statements = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        for match in _DML_RE.finditer(node.value):
            statements.append({
                "file": path,
                "line": node.lineno,
                "operation": match.group(1).lower().split()[0],
                "table": match.group(2).lower(),
            })
    return statements


def _forbidden_dependencies(path, tree):
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
            for module in modules:
                if module.startswith(("backend.features.", "features.")):
                    violations.append({
                        "reasonCode": "a7_external_import_not_allowlisted",
                        "file": path,
                        "line": node.lineno,
                    })
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
            module = node.module or ""
            if module.startswith(("backend.features.", "features.")):
                for alias in node.names:
                    if (path, module, alias.name) not in (
                        _ALLOWED_EXTERNAL_FEATURE_IMPORTS
                    ):
                        violations.append({
                            "reasonCode": "a7_external_import_not_allowlisted",
                            "file": path,
                            "line": node.lineno,
                        })
        else:
            modules = []
        for module in modules:
            normalized = module.lower()
            if any(part in normalized for part in _FORBIDDEN_IMPORT_FRAGMENTS):
                violations.append({
                    "reasonCode": "a7_forbidden_dependency",
                    "file": path,
                    "line": node.lineno,
                })
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            function = call.func if call is not None else decorator
            if (
                isinstance(function, ast.Attribute)
                and function.attr in {"get", "post", "put", "patch", "delete"}
                and isinstance(function.value, ast.Name)
                and function.value.id in {"app", "router"}
            ):
                violations.append({
                    "reasonCode": "a7_http_route_forbidden",
                    "file": path,
                    "symbol": node.name,
                    "line": node.lineno,
                })
    return violations


def _operational_calls(path, tree):
    calls = Counter()
    if path not in {_PRODUCER_PATH, _HANDOFF_PATH, _RUNNER_PATH}:
        return calls

    def owned_nodes(function):
        pending = list(function.body)
        while pending:
            node = pending.pop()
            if isinstance(node, (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            )):
                continue
            yield node
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                )):
                    continue
                pending.append(child)

    for symbol, function in _definitions(tree):
        for node in owned_nodes(function):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name in {"enqueue_job", "complete_agent_job"}:
                calls[(path, symbol, name)] += 1
    return calls


def _automatic_a7_routes(path, tree):
    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(
                decorator.func, ast.Attribute
            ):
                continue
            if decorator.func.attr not in {"post", "put", "patch", "delete"}:
                continue
            route = decorator.args[0] if decorator.args else None
            if not isinstance(route, ast.Constant) or not isinstance(
                route.value, str
            ):
                continue
            normalized = route.value.lower().replace("_", "-")
            if "estimate-revision-impact" in normalized:
                routes.append({
                    "reasonCode": "automatic_a7_apply_route",
                    "file": path,
                    "symbol": node.name,
                    "line": node.lineno,
                })
    return routes


def _handler_boundaries(tree):
    builder = _find_definition(tree, "build_estimate_revision_impact_handler")
    if builder is None:
        return False
    defaults = list(builder.args.defaults) + [
        value for value in builder.args.kw_defaults if value is not None
    ]
    combined_default = any(
        isinstance(value, ast.Name)
        and value.id == "run_combined_impact_audit"
        for value in defaults
    )
    calls = Counter(
        _call_name(node.func)
        for node in ast.walk(builder)
        if isinstance(node, ast.Call)
    )
    return (
        combined_default
        and calls["source_from_job_payload"] == 1
        and calls["run_report_dependency"] == 1
    )


def _registration_count(tree):
    function = _find_definition(tree, "build_default_handler_registry")
    if function is None:
        return 0
    return sum(
        1
        for node in ast.walk(function)
        if isinstance(node, ast.Constant)
        and node.value == "estimate.revision_impact"
    )


def _post_commit_handoffs(tree, violations):
    ready = 0
    for symbol in _MAIN_HANDOFF_FUNCTIONS:
        function = _find_definition(tree, symbol)
        if function is None:
            violations.append({
                "reasonCode": "activation_function_missing",
                "symbol": symbol,
            })
            continue
        commits = []
        handoffs = []
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            if name == "commit":
                commits.append(node.lineno)
            elif name == "handoff_estimate_revision_impact_transition":
                handoffs.append(node.lineno)
        if len(handoffs) != 1 or not any(
            line < handoffs[0] for line in commits
        ):
            violations.append({
                "reasonCode": "post_commit_handoff_invalid",
                "symbol": symbol,
            })
            continue
        ready += 1
    return ready


def audit_cutover_inventory(
    repo_root=None,
    *,
    source_files=None,
    integration_test_source=None,
    enforce_complete_inventory=None,
):
    """Return bounded import-free proof of the reviewed A7 execution surface."""

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[3]
    if enforce_complete_inventory is None:
        enforce_complete_inventory = source_files is None
    if source_files is None:
        source_files = _repository_sources(repo_root)
    if integration_test_source is None:
        test_path = (
            Path(repo_root).resolve()
            / _A7_PREFIX
            / "test_postgres_cutover.py"
        )
        integration_test_source = (
            test_path.read_text(encoding="utf-8") if test_path.exists() else ""
        )

    violations = []
    trees = {}
    a7_dml = []
    operational_calls = Counter()
    for raw_path, source in sorted(source_files.items()):
        path = Path(raw_path).as_posix()
        tree = _parse(path, source, violations)
        if tree is None:
            continue
        trees[path] = tree
        violations.extend(_automatic_a7_routes(path, tree))
        if path.startswith(_A7_PREFIX):
            a7_dml.extend(_a7_dml(path, tree))
            violations.extend(_forbidden_dependencies(path, tree))
        operational_calls.update(_operational_calls(path, tree))

    for statement in a7_dml:
        violations.append({
            "reasonCode": "a7_business_dml_forbidden",
            **statement,
        })

    if enforce_complete_inventory and operational_calls != _EXPECTED_OPERATIONAL_CALLS:
        violations.append({
            "reasonCode": "operational_mutation_inventory_mismatch",
            "expected": sum(_EXPECTED_OPERATIONAL_CALLS.values()),
            "actual": sum(operational_calls.values()),
        })

    handler_ready = _handler_boundaries(trees.get(_HANDLER_PATH)) if trees.get(
        _HANDLER_PATH
    ) is not None else False
    if enforce_complete_inventory and not handler_ready:
        violations.append({"reasonCode": "handler_boundary_mismatch"})

    handoff_tree = trees.get(_HANDOFF_PATH)
    constants = _top_level_string_constants(handoff_tree) if handoff_tree else {}
    controls_ready = constants.get("FEATURE_FLAG") == (
        "ESTIMATE_REVISION_IMPACT_APPLY"
    ) and constants.get("COMPANY_ALLOWLIST") == (
        "ESTIMATE_REVISION_IMPACT_COMPANY_IDS"
    )
    if enforce_complete_inventory and not controls_ready:
        violations.append({"reasonCode": "handoff_controls_mismatch"})

    registration_count = _registration_count(trees.get(_REGISTRY_PATH)) if trees.get(
        _REGISTRY_PATH
    ) is not None else 0
    if enforce_complete_inventory and registration_count != 1:
        violations.append({
            "reasonCode": "handler_registration_mismatch",
            "expected": 1,
            "actual": registration_count,
        })

    main_tree = trees.get(_MAIN_PATH)
    post_commit_handoffs = (
        _post_commit_handoffs(main_tree, violations) if main_tree else 0
    )

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

    ready = not violations
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "writerInventoryReady": ready,
        "runtimeInventoryReady": ready,
        "a7DmlStatements": len(a7_dml),
        "operationalMutationCalls": sum(operational_calls.values()),
        "expectedOperationalMutationCalls": sum(
            _EXPECTED_OPERATIONAL_CALLS.values()
        ),
        "handlerRegistrations": registration_count,
        "postCommitHandoffs": post_commit_handoffs,
        "requiredIntegrationChecks": len(_REQUIRED_INTEGRATION_CHECKS),
        "missingIntegrationChecks": missing_checks,
        "violationCount": len(violations),
        "violations": violations[:MAX_VIOLATIONS],
        "violationsTruncated": len(violations) > MAX_VIOLATIONS,
    }


__all__ = ["audit_cutover_inventory"]
