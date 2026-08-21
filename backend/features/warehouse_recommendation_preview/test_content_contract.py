import ast
import copy
import hashlib
import json
import unittest
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from backend.features.brigade_lineage import snapshot_service
from backend.features.estimate_revision_impact import baseline as a7_baseline
from backend.features.estimate_revision_impact import (
    supply_warehouse_audit as a7_supply_warehouse_audit,
)
from backend.features.estimate_revision_impact import (
    supply_warehouse_projection as a7_supply_warehouse_projection,
)
from backend.features.estimate_revision_impact.combined_contract import (
    build_combined_report,
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionSource,
)
from backend.features.estimate_revision_impact.supply_warehouse_audit import (
    SUPPLY_WAREHOUSE_REQUIRED_COLUMNS,
    collect_supply_warehouse_impact_audit,
)
from backend.features.estimate_revision_impact.test_baseline import FakeCursor
from backend.features.estimate_revision_impact import (
    test_supply_warehouse_audit as a7_supply_warehouse_fixtures,
)
from backend.features.warehouse_recommendation_preview.test_readiness import (
    CANDIDATE_CASES,
    candidate_review,
    refresh_envelope,
    rehash,
    review,
    stored_report,
    warehouse_report,
)
from backend.features.warehouse_recommendation_preview import content_contract
from backend.features.warehouse_recommendation_preview.content_contract import (
    WarehouseAnomalyContentError,
    _BASELINE_REASON_RULES,
    _BASELINE_REQUIRED_COLUMNS,
    _RAW_REQUIRED_COLUMNS,
    _RAW_REVIEW_RULES,
    _finalize_warehouse_anomaly_content,
    _prepare_warehouse_anomaly_content,
    _snapshot_stored_report,
    _validate_current_warehouse_anomaly_report,
    _validate_raw_supply_warehouse_projection,
    _validated_raw_review,
)


MAX_STORED_REPORT_CANONICAL_BYTES = 4 * 1024 * 1024
SOURCE_FIELDS = frozenset({
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
    "reconciliationId",
    "baseEstimateId",
    "reconciliationStatus",
})
CANDIDATE_FIELDS = frozenset({
    "subjectKind",
    "subjectId",
    "anomalyCode",
    "recommendationCode",
})


def _reason_rules(kind, id_policy, codes):
    return {code: (kind, id_policy) for code in codes}


EXPECTED_RAW_REVIEW_RULES = MappingProxyType({
    **_reason_rules("supplyWarehouse", "none", (
        "supply_warehouse_impact_schema_not_ready",
        "supply_warehouse_project_identity_invalid",
        "supply_warehouse_source_snapshot_invalid",
        "supply_request_scan_limit_exceeded",
        "supply_warehouse_scan_limit_exceeded",
    )),
    **_reason_rules("supply", "none", (
        "supply_request_identity_invalid",
        "supply_request_owner_mismatch",
    )),
    **_reason_rules("supply", "positive", (
        "supply_source_coordinate_not_found",
        "supply_source_snapshot_invalid",
        "supply_source_item_key_invalid",
        "supply_source_item_key_ambiguous",
        "supply_request_project_mismatch",
        "supply_request_package_mismatch",
        "supply_items_json_invalid",
        "supply_request_item_limit_exceeded",
        "supply_source_lineage_invalid",
        "supply_source_coordinate_invalid",
        "supply_source_lineage_drift",
        "supply_quantity_invalid",
        "supply_source_coordinate_duplicate",
        "supply_source_estimate_invalid",
        "supply_snapshot_content_invalid",
        "supply_source_item_key_noncanonical",
        "supply_source_item_key_missing",
        "supply_source_item_key_required",
        "supply_source_item_key_mismatch",
        "supply_delivery_allocation_ambiguous",
        "supply_allocation_lineage_drift",
        "supply_protected_exceeds_requested",
    )),
    **_reason_rules("delivery", "optional", (
        "supply_delivery_identity_invalid",
    )),
    **_reason_rules("delivery", "none", (
        "supply_delivery_owner_mismatch",
    )),
    **_reason_rules("delivery", "positive", (
        "supply_delivery_request_mismatch",
        "supply_delivery_scope_mismatch",
        "supply_received_quantity_invalid",
    )),
    **_reason_rules("allocation", "optional", (
        "supply_allocation_identity_invalid",
    )),
    **_reason_rules("allocation", "none", (
        "supply_allocation_owner_mismatch",
    )),
    **_reason_rules("allocation", "positive", (
        "supply_allocation_request_mismatch",
        "supply_allocation_lineage_invalid",
        "supply_allocation_quantity_invalid",
    )),
    **_reason_rules("supplier_invoice", "optional", (
        "supplier_invoice_identity_invalid",
    )),
    **_reason_rules("supplier_invoice", "none", (
        "supplier_invoice_owner_mismatch",
    )),
    **_reason_rules("supplier_invoice", "positive", (
        "supplier_invoice_request_mismatch",
    )),
    **_reason_rules("warehouseInvoice", "optional", (
        "warehouse_invoice_identity_invalid",
    )),
    **_reason_rules("warehouseInvoice", "none", (
        "warehouse_invoice_owner_mismatch",
    )),
    **_reason_rules("warehouseInvoice", "positive", (
        "warehouse_invoice_request_mismatch",
        "warehouse_invoice_project_mismatch",
        "warehouse_invoice_delivery_mismatch",
        "warehouse_invoice_supplier_invoice_mismatch",
        "warehouse_invoice_items_invalid",
        "warehouse_invoice_items_limit_exceeded",
    )),
    **_reason_rules("warehouse_receipt", "optional", (
        "warehouse_receipt_identity_invalid",
    )),
    **_reason_rules("warehouse_receipt", "none", (
        "warehouse_receipt_owner_mismatch",
    )),
    **_reason_rules("warehouse_receipt", "positive", (
        "warehouse_receipt_invoice_mismatch",
        "warehouse_receipt_line_invalid",
        "warehouse_receipt_package_mismatch",
    )),
    **_reason_rules("warehouse_receipt_lot", "optional", (
        "warehouse_receipt_lot_identity_invalid",
    )),
    **_reason_rules("warehouse_receipt_lot", "none", (
        "warehouse_receipt_lot_owner_mismatch",
    )),
    **_reason_rules("warehouse_receipt_lot", "positive", (
        "warehouse_receipt_lot_invoice_mismatch",
        "warehouse_receipt_lot_line_invalid",
        "warehouse_receipt_lot_project_mismatch",
    )),
    **_reason_rules("warehouse_movement", "optional", (
        "warehouse_movement_identity_invalid",
    )),
    **_reason_rules("warehouse_movement", "none", (
        "warehouse_movement_owner_mismatch",
    )),
    **_reason_rules("warehouse_movement", "positive", (
        "warehouse_movement_invoice_mismatch",
        "warehouse_movement_line_invalid",
        "warehouse_movement_package_mismatch",
    )),
    **_reason_rules("lotMovement", "optional", (
        "warehouse_lot_movement_identity_invalid",
    )),
    **_reason_rules("lotMovement", "none", (
        "warehouse_lot_movement_owner_mismatch",
    )),
    **_reason_rules("lotMovement", "positive", (
        "warehouse_lot_movement_parent_mismatch",
        "warehouse_lot_movement_source_mismatch",
    )),
    **_reason_rules("warehouseMovement", "positive", (
        "warehouse_movement_lot_missing",
        "warehouse_lot_movement_missing",
    )),
})


EXPECTED_BASELINE_REASON_RULES = MappingProxyType({
    "estimate_revision_impact_schema_not_ready": (
        False, False, 0, 0, 0, 0,
    ),
    "impact_source_not_found": (True, True, 0, 0, 0, 0),
    "impact_source_ambiguous": (True, True, 2, 2, 0, 0),
    "impact_source_owner_mismatch": (True, True, 1, 1, 0, 0),
    "impact_estimate_not_active": (True, True, 1, 1, 0, 0),
    "impact_estimate_template": (True, True, 1, 1, 0, 0),
    "impact_estimate_not_customer": (True, True, 1, 1, 0, 0),
    "impact_estimate_package_invalid": (True, True, 1, 1, 0, 0),
    "impact_estimate_snapshot_invalid": (True, True, 1, 1, 0, 0),
    "impact_estimate_snapshot_too_large": (True, True, 1, 1, 0, 0),
    "source_revision_mismatch": (True, True, 1, 1, 0, 0),
    "impact_reconciliation_scan_limit_exceeded": (
        True, False, 1, 1, 101, 101,
    ),
    "impact_reconciliation_not_found": (True, True, 1, 1, 0, 0),
    "impact_reconciliation_ambiguous": (True, True, 1, 1, 2, 100),
    "impact_reconciliation_id_invalid": (True, True, 1, 1, 1, 1),
    "impact_reconciliation_estimate_pair_invalid": (
        True, True, 1, 1, 1, 1,
    ),
    "impact_reconciliation_owner_mismatch": (
        True, True, 1, 1, 1, 1,
    ),
    "impact_reconciliation_not_customer": (
        True, True, 1, 1, 1, 1,
    ),
    "impact_reconciliation_package_mismatch": (
        True, True, 1, 1, 1, 1,
    ),
    "impact_reconciliation_next_not_active": (
        True, True, 1, 1, 1, 1,
    ),
    "impact_reconciliation_status_invalid": (
        True, True, 1, 1, 1, 1,
    ),
})


def selected(
    anomaly_code="warehouse_invoice_project_mismatch",
    *,
    subject_kind="warehouseInvoice",
    subject_id=31,
):
    return {
        "subjectKind": subject_kind,
        "subjectId": subject_id,
        "anomalyCode": anomaly_code,
    }


def selected_report(
    anomaly_code="warehouse_invoice_project_mismatch",
    *,
    subject_id=31,
):
    return warehouse_report(candidate_review(anomaly_code, subject_id))


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def expected_relevant_evidence_sha256(report):
    preimage = {
        "warehouseAnomalyRelevantEvidenceVersion": 1,
        "source": report["source"],
        "supply": report["domains"]["supply"],
        "warehouse": report["domains"]["warehouse"],
    }
    return hashlib.sha256(canonical_bytes(preimage)).hexdigest()


def report_with_exact_canonical_size(size):
    report = selected_report()
    missing = report["domains"]["assignments"]["missingColumns"]
    missing[:] = ["a.b"]
    rehash(report)
    base_size = len(canonical_bytes(report))
    if size < base_size:
        raise AssertionError("requested canonical size is too small")
    missing[:] = ["a" * (1 + size - base_size) + ".b"]
    rehash(report)
    if len(canonical_bytes(report)) != size:
        raise AssertionError("failed to construct exact canonical size")
    return report


def prepared_field_values(prepared):
    if not is_dataclass(prepared):
        raise AssertionError("prepared plan must be a private dataclass")
    return {
        field.name: getattr(prepared, field.name)
        for field in fields(prepared)
    }


def exact_mapping(values, expected_fields):
    matches = [
        value for value in values
        if isinstance(value, Mapping) and set(value) == set(expected_fields)
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one immutable mapping with fields {expected_fields}"
        )
    return matches[0]


def current_a7_report(outcome="complete"):
    """Return exact public A7 producer output for one systemic outcome."""

    fixture = (
        a7_supply_warehouse_fixtures
        .SupplyWarehouseProjectionCollectorTests()
    )
    result_sets = list(fixture.result_sets())
    if outcome == "review_required":
        result_sets[9] = a7_supply_warehouse_fixtures._bounded_invoice_rows(
            a7_supply_warehouse_fixtures._bounded_invoice_row(
                invoice_project="Other project",
            ),
        )
    elif outcome == "incomplete":
        result_sets = result_sets[:4]
        result_sets[3] = result_sets[3][:-1]
    elif outcome == "not_collected":
        result_sets = result_sets[:2]
        result_sets[1] = ()
    elif outcome == "baseline_incomplete":
        result_sets = result_sets[:1]
        result_sets[0] = result_sets[0][:-1]
    elif outcome != "complete":
        raise AssertionError(f"unknown current A7 outcome: {outcome}")
    return collect_supply_warehouse_impact_audit(
        FakeCursor(tuple(result_sets)),
        a7_supply_warehouse_fixtures.source(),
    )


def flattened_required_columns(required_columns):
    return frozenset(
        f"{table}.{column}"
        for table, columns in required_columns.items()
        for column in columns
    )


def _ast_call_name(call):
    return call.func.id if isinstance(call.func, ast.Name) else None


def _ast_keyword(call, name):
    return next(
        (keyword.value for keyword in call.keywords if keyword.arg == name),
        None,
    )


def _ast_parent_map(tree):
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _ast_enclosing(node, parents, node_type):
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, node_type):
            return current
    return None


def _ast_negates_name(value, name):
    return any(
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.Not)
        and isinstance(node.operand, ast.Name)
        and node.operand.id == name
        for node in ast.walk(value)
    )


def _ast_source_id_policy(node, source, expose, parents):
    if expose is not None:
        if not (
            isinstance(expose, ast.Constant)
            and type(expose.value) is bool
        ):
            raise AssertionError("producer expose-ID expression is dynamic")
        if expose.value is False:
            return "none"
    if isinstance(source, ast.Constant) and source.value is None:
        return "none"
    if not isinstance(source, ast.Name):
        raise AssertionError("unsupported producer source-ID expression")
    current = node
    while current in parents:
        child = current
        current = parents[current]
        if isinstance(current, ast.FunctionDef):
            break
        if (
            isinstance(current, ast.If)
            and child in current.body
            and _ast_negates_name(current.test, source.id)
        ):
            return "optional"
    return "positive"


def _ast_kind_values(value, function_name, helper_kinds):
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return {value.value}
    if isinstance(value, ast.Name) and value.id == "kind":
        kinds = helper_kinds.get(function_name, set())
        if kinds:
            return set(kinds)
    raise AssertionError("unsupported producer source-kind expression")


def _ast_reason_kind_pairs(value, kind_values):
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return {(value.value, kind) for kind in kind_values}
    if (
        isinstance(value, ast.BinOp)
        and isinstance(value.op, ast.Add)
        and isinstance(value.left, ast.Name)
        and value.left.id == "kind"
        and isinstance(value.right, ast.Constant)
        and isinstance(value.right.value, str)
    ):
        return {
            (kind + value.right.value, kind) for kind in kind_values
        }
    raise AssertionError("unsupported producer reason expression")


def _ast_branch_policy(assignment, source, parents):
    branch = _ast_enclosing(assignment, parents, ast.If)
    if branch is None:
        raise AssertionError("producer reason assignment is not conditional")
    expose_false = any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "expose"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and node.value.value is False
        for statement in branch.body
        for node in ast.walk(statement)
    )
    if expose_false:
        return "none"
    if isinstance(source, ast.Name) and _ast_negates_name(
        branch.test, source.id,
    ):
        return "optional"
    return "positive"


def _assert_closed_review_emissions(tree, allowed_functions):
    parents = _ast_parent_map(tree)

    def assert_allowed(node):
        function = _ast_enclosing(node, parents, ast.FunctionDef)
        if function is None or function.name not in allowed_functions:
            raise AssertionError("unreviewed reasonCode emission site")

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "reviews"
        ):
            exact_review_append = (
                node.func.attr == "append"
                and len(node.args) == 1
                and not node.keywords
                and isinstance(node.args[0], ast.Call)
                and _ast_call_name(node.args[0]) == "_review"
            )
            exact_request_review_extend = (
                node.func.attr == "extend"
                and len(node.args) == 1
                and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "request_reviews"
            )
            if exact_request_review_extend:
                function = _ast_enclosing(node, parents, ast.FunctionDef)
                provenance = [
                    assignment
                    for assignment in ast.walk(function)
                    if isinstance(assignment, ast.Assign)
                    and isinstance(assignment.value, ast.Call)
                    and _ast_call_name(assignment.value) == "_request_items"
                    and any(
                        isinstance(target, ast.Tuple)
                        and any(
                            isinstance(element, ast.Name)
                            and element.id == "request_reviews"
                            for element in target.elts
                        )
                        for target in assignment.targets
                    )
                ]
                exact_request_review_extend = len(provenance) == 1
            if not exact_review_append and not exact_request_review_extend:
                raise AssertionError("unreviewed reviews mutation site")
        if isinstance(node, ast.Constant) and node.value == "reasonCode":
            parent = parents.get(node)
            if (
                isinstance(parent, ast.Subscript)
                and parent.slice is node
                and isinstance(parent.ctx, ast.Load)
            ):
                continue
            if isinstance(parent, ast.Dict) and node in parent.keys:
                assert_allowed(parent)
                continue
            assert_allowed(node)
        elif isinstance(node, ast.Call) and any(
            keyword.arg == "reasonCode" for keyword in node.keywords
        ):
            assert_allowed(node)


def extracted_a7_raw_review_rules():
    projection_tree = ast.parse(
        Path(a7_supply_warehouse_projection.__file__).read_text(
            encoding="utf-8"
        )
    )
    audit_tree = ast.parse(
        Path(a7_supply_warehouse_audit.__file__).read_text(encoding="utf-8")
    )
    dependency_tree = ast.parse(
        Path(snapshot_service.__file__).read_text(encoding="utf-8")
    )
    _assert_closed_review_emissions(projection_tree, {"_review"})
    _assert_closed_review_emissions(audit_tree, {"_empty_projection"})
    parents = _ast_parent_map(projection_tree)
    functions = {
        node.name: node
        for node in projection_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    request_review_returns = [
        node for node in ast.walk(functions["_request_items"])
        if isinstance(node, ast.Return)
    ]
    if not request_review_returns:
        raise AssertionError("request review producer has no return")
    for return_node in request_review_returns:
        if not (
            isinstance(return_node.value, ast.Tuple)
            and len(return_node.value.elts) == 2
        ):
            raise AssertionError("request review return shape changed")
        review_value = return_node.value.elts[1]
        exact_review_list = (
            isinstance(review_value, ast.List)
            and all(
                isinstance(element, ast.Call)
                and _ast_call_name(element) == "_review"
                for element in review_value.elts
            )
        )
        exact_review_accumulator = (
            isinstance(review_value, ast.Name)
            and review_value.id == "reviews"
        )
        if not exact_review_list and not exact_review_accumulator:
            raise AssertionError("request review return provenance changed")

    helper_names = {"_valid_parent_rows", "_valid_invoice_line_rows"}
    helper_kinds = {name: set() for name in helper_names}
    helper_option_kinds = {
        ("_valid_invoice_line_rows", "package_field"): set(),
        ("_valid_invoice_line_rows", "project_field"): set(),
    }
    for call in (
        node for node in ast.walk(projection_tree)
        if isinstance(node, ast.Call)
        and _ast_call_name(node) in helper_names
    ):
        kind = _ast_keyword(call, "kind")
        if not (
            isinstance(kind, ast.Constant) and isinstance(kind.value, str)
        ):
            raise AssertionError("producer helper kind is not constant")
        helper_name = _ast_call_name(call)
        helper_kinds[helper_name].add(kind.value)
        for option in ("package_field", "project_field"):
            if (
                (helper_name, option) in helper_option_kinds
                and _ast_keyword(call, option) is not None
            ):
                helper_option_kinds[(helper_name, option)].add(kind.value)

    canonical_errors = set()
    for node in ast.walk(functions["_canonical_item_key"]):
        if (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Tuple)
            and len(node.value.elts) == 2
            and isinstance(node.value.elts[1], ast.Constant)
            and isinstance(node.value.elts[1].value, str)
        ):
            canonical_errors.add(node.value.elts[1].value)

    all_dependency_functions = {
        node.name: node
        for node in dependency_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    reachable_names = set()
    pending_names = ["resolve_snapshot_item"]
    while pending_names:
        function_name = pending_names.pop()
        if function_name in reachable_names:
            continue
        function = all_dependency_functions.get(function_name)
        if function is None:
            raise AssertionError("resolver dependency function is missing")
        reachable_names.add(function_name)
        for call in (
            node for node in ast.walk(function) if isinstance(node, ast.Call)
        ):
            called_name = _ast_call_name(call)
            if (
                called_name in all_dependency_functions
                and called_name not in reachable_names
            ):
                pending_names.append(called_name)
    dependency_functions = {
        name: all_dependency_functions[name] for name in reachable_names
    }
    if "_bounded_key" not in dependency_functions:
        raise AssertionError("bounded resolver dependency is unreachable")
    resolver_codes = set()
    for function_name, function in dependency_functions.items():
        for call in (
            node for node in ast.walk(function) if isinstance(node, ast.Call)
        ):
            call_name = _ast_call_name(call)
            if call_name == "LineageResolutionError":
                if not call.args:
                    raise AssertionError("resolver error has no code")
                code = call.args[0]
                if isinstance(code, ast.Name):
                    positional_names = [
                        argument.arg
                        for argument in (
                            getattr(function.args, "posonlyargs", [])
                            + function.args.args
                        )
                    ]
                    parameter_names = positional_names + [
                        argument.arg
                        for argument in function.args.kwonlyargs
                    ]
                    if code.id not in parameter_names:
                        raise AssertionError("resolver error code is dynamic")
                    parameter_index = (
                        positional_names.index(code.id)
                        if code.id in positional_names
                        else None
                    )
                    callsite_values = []
                    for caller in dependency_functions.values():
                        for candidate in (
                            node for node in ast.walk(caller)
                            if isinstance(node, ast.Call)
                            and _ast_call_name(node) == function_name
                        ):
                            supplied = _ast_keyword(candidate, code.id)
                            if (
                                supplied is None
                                and parameter_index is not None
                                and parameter_index < len(candidate.args)
                            ):
                                supplied = candidate.args[parameter_index]
                            callsite_values.append(supplied)
                    if not callsite_values or any(
                        not isinstance(value, ast.Constant)
                        or not isinstance(value.value, str)
                        for value in callsite_values
                    ):
                        raise AssertionError("resolver error code is dynamic")
                    resolver_codes.update(
                        value.value for value in callsite_values
                    )
                    continue
                if not (
                    isinstance(code, ast.Constant)
                    and isinstance(code.value, str)
                ):
                    raise AssertionError("resolver error code is dynamic")
                resolver_codes.add(code.value)

    extracted = {}
    native_reasons = set()
    resolver_reasons = set()

    def add(reason, kind, policy, *, dependency=False):
        shape = (kind, policy)
        existing = extracted.get(reason)
        if existing is not None and existing != shape:
            raise AssertionError(
                f"producer reason {reason!r} has conflicting shapes"
            )
        extracted[reason] = shape
        (resolver_reasons if dependency else native_reasons).add(reason)

    for call in (
        node for node in ast.walk(projection_tree)
        if isinstance(node, ast.Call) and _ast_call_name(node) == "_review"
    ):
        if len(call.args) < 3:
            raise AssertionError("producer review call is incomplete")
        function = _ast_enclosing(call, parents, ast.FunctionDef)
        if function is None:
            raise AssertionError("producer review call has no function")
        kinds = _ast_kind_values(
            call.args[0], function.name, helper_kinds,
        )
        reason = call.args[2]
        if isinstance(reason, ast.Name) and reason.id == "reason":
            source = call.args[1]
            for assignment in (
                node for node in ast.walk(function)
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "reason"
                    for target in node.targets
                )
                and not (
                    isinstance(node.value, ast.Constant)
                    and node.value.value is None
                )
            ):
                policy = _ast_branch_policy(assignment, source, parents)
                assignment_kinds = kinds
                if (
                    isinstance(assignment.value, ast.BinOp)
                    and isinstance(assignment.value.right, ast.Constant)
                ):
                    option_by_suffix = {
                        "_package_mismatch": "package_field",
                        "_project_mismatch": "project_field",
                    }
                    option = option_by_suffix.get(
                        assignment.value.right.value
                    )
                    if option is not None:
                        assignment_kinds = helper_option_kinds[
                            (function.name, option)
                        ]
                for reason_value, kind in _ast_reason_kind_pairs(
                    assignment.value, assignment_kinds,
                ):
                    add(reason_value, kind, policy)
            continue
        if isinstance(reason, ast.Name) and reason.id == "key_error":
            policy = _ast_source_id_policy(
                call, call.args[1], _ast_keyword(call, "expose_id"), parents,
            )
            for reason_value in canonical_errors:
                for kind in kinds:
                    add(reason_value, kind, policy)
            continue
        if (
            isinstance(reason, ast.BinOp)
            and isinstance(reason.op, ast.Add)
            and isinstance(reason.left, ast.Constant)
            and reason.left.value == "supply_"
            and isinstance(reason.right, ast.Attribute)
            and reason.right.attr == "code"
        ):
            policy = _ast_source_id_policy(
                call, call.args[1], _ast_keyword(call, "expose_id"), parents,
            )
            for code in resolver_codes:
                for kind in kinds:
                    add(
                        "supply_" + code,
                        kind,
                        policy,
                        dependency=True,
                    )
            continue
        policy = _ast_source_id_policy(
            call, call.args[1], _ast_keyword(call, "expose_id"), parents,
        )
        for reason_value, kind in _ast_reason_kind_pairs(reason, kinds):
            add(reason_value, kind, policy)

    for call in (
        node for node in ast.walk(audit_tree)
        if isinstance(node, ast.Call) and _ast_call_name(node) == "_empty_projection"
    ):
        reason = (
            call.args[1]
            if len(call.args) >= 2
            else _ast_keyword(call, "reason_code")
        )
        if reason is None:
            continue
        if not (
            isinstance(reason, ast.Constant) and isinstance(reason.value, str)
        ):
            raise AssertionError("systemic producer reason is dynamic")
        add(reason.value, "supplyWarehouse", "none")

    return extracted, native_reasons, resolver_reasons


def empty_complete_raw_projection():
    projection = copy.deepcopy(
        current_a7_report("not_collected")["supplyWarehouseImpact"]
    )
    projection.update({
        "state": "complete",
        "scanComplete": True,
        "complete": True,
    })
    return projection


def raw_review(reason_code, source_id_marker="default"):
    source_kind, id_policy = EXPECTED_RAW_REVIEW_RULES[reason_code]
    if source_id_marker == "default":
        source_id = None if id_policy == "none" else 1
    else:
        source_id = source_id_marker
    return {
        "sourceKind": source_kind,
        "sourceId": source_id,
        "reasonCode": reason_code,
    }


def raw_review_projection(reason_code, count):
    projection = empty_complete_raw_projection()
    projection.update({
        "state": "review_required",
        "complete": False,
        "needsReviewTruncated": count > 100,
    })
    projection["summary"]["needsReview"] = count
    projection["reasonCounts"] = {reason_code: count}
    projection["needsReview"] = [
        raw_review(reason_code)
        for _ in range(min(count, 100))
    ]
    return projection


def baseline_reason_report(reason_code):
    report = current_a7_report("not_collected")
    (
        schema_ready,
        scan_complete,
        estimate_min,
        _estimate_max,
        reconciliation_min,
        _reconciliation_max,
    ) = EXPECTED_BASELINE_REASON_RULES[reason_code]
    report.update({
        "schemaReady": schema_ready,
        "missingColumns": (
            ["projects.company_id"]
            if reason_code == "estimate_revision_impact_schema_not_ready"
            else []
        ),
        "scanComplete": scan_complete,
        "summary": {
            "estimateRows": estimate_min,
            "reconciliationRows": reconciliation_min,
        },
        "reasonCounts": {reason_code: 1},
    })
    report["issues"][0]["reasonCode"] = reason_code
    return report


class WarehouseAnomalyContentPreparationTests(unittest.TestCase):
    maxDiff = None

    def assert_content_error(self, code, report, selection):
        with self.assertRaises(WarehouseAnomalyContentError) as raised:
            _prepare_warehouse_anomaly_content(report, selection)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(str(raised.exception), code)
        self.assertNotIn("must-not-leak", str(raised.exception))

    def test_prepares_one_private_frozen_minimal_plan(self):
        report = selected_report()
        report["domains"]["assignments"]["missingColumns"] = [
            "must_not_leak.column"
        ]
        rehash(report)
        selection = selected()
        report_before = copy.deepcopy(report)
        selection_before = copy.deepcopy(selection)

        prepared = _prepare_warehouse_anomaly_content(report, selection)

        self.assertEqual(report, report_before)
        self.assertEqual(selection, selection_before)
        self.assertTrue(type(prepared).__name__.startswith("_"))
        self.assertTrue(is_dataclass(prepared))
        self.assertTrue(prepared.__dataclass_params__.frozen)
        self.assertFalse(hasattr(prepared, "__dict__"))
        values_by_name = prepared_field_values(prepared)
        values = list(values_by_name.values())
        with self.assertRaises(FrozenInstanceError):
            setattr(prepared, next(iter(values_by_name)), None)

        source_values = [
            value for value in values
            if isinstance(value, EstimateRevisionSource)
        ]
        self.assertEqual(source_values, [EstimateRevisionSource(
            schema_version=REPORT_VERSION,
            event_type=EVENT_TYPE,
            company_id=report_before["source"]["companyId"],
            project_id=report_before["source"]["projectId"],
            estimate_id=report_before["source"]["estimateId"],
            source_revision=report_before["source"]["sourceRevision"],
        )])

        stored_source = exact_mapping(values, SOURCE_FIELDS)
        candidate = exact_mapping(values, CANDIDATE_FIELDS)
        self.assertIsInstance(stored_source, MappingProxyType)
        self.assertIsInstance(candidate, MappingProxyType)
        self.assertEqual(dict(stored_source), report_before["source"])
        self.assertEqual(dict(candidate), {
            **selection_before,
            "recommendationCode": "review_warehouse_invoice_lineage",
        })
        with self.assertRaises(TypeError):
            stored_source["companyId"] = 999
        with self.assertRaises(TypeError):
            candidate["subjectId"] = 999

        self.assertIn(report_before["evidenceSha256"], values)
        self.assertIn(
            expected_relevant_evidence_sha256(report_before), values,
        )
        self.assertNotIn("must_not_leak.column", repr(prepared))
        lowered_names = " ".join(values_by_name).lower()
        for forbidden in (
            "report", "content", "finding", "title", "action",
            "trusted", "provenance", "authorized", "verified",
        ):
            self.assertNotIn(forbidden, lowered_names)

        report["source"]["companyId"] = 999
        selection["subjectId"] = 999
        self.assertEqual(dict(stored_source), report_before["source"])
        self.assertEqual(candidate["subjectId"], 31)

    def test_accepts_every_exact_a91_selection_shape(self):
        for index, (
            anomaly_code,
            _source_kind,
            subject_kind,
            recommendation_code,
        ) in enumerate(CANDIDATE_CASES, start=1):
            with self.subTest(anomaly_code=anomaly_code):
                report = selected_report(
                    anomaly_code, subject_id=100 + index,
                )
                selection = selected(
                    anomaly_code,
                    subject_kind=subject_kind,
                    subject_id=100 + index,
                )

                prepared = _prepare_warehouse_anomaly_content(
                    report, selection,
                )

                candidate = exact_mapping(
                    prepared_field_values(prepared).values(),
                    CANDIDATE_FIELDS,
                )
                self.assertEqual(dict(candidate), {
                    **selection,
                    "recommendationCode": recommendation_code,
                })

    def test_rejects_non_exact_or_incompatible_selection(self):
        report = selected_report()
        cases = {
            "not_mapping": [],
            "missing": {
                "subjectKind": "warehouseInvoice",
                "subjectId": 31,
            },
            "extra_recommendation": {
                **selected(),
                "recommendationCode": "review_warehouse_invoice_lineage",
            },
            "bool_id": selected(subject_id=True),
            "zero_id": selected(subject_id=0),
            "negative_id": selected(subject_id=-1),
            "string_id": selected(subject_id="31"),
            "unknown_kind": selected(subject_kind="futureWarehouseObject"),
            "unknown_code": selected(
                anomaly_code="warehouse_invoice_future_mismatch"
            ),
            "incompatible_kind": selected(subject_kind="warehouseHistory"),
        }
        for name, selection in cases.items():
            with self.subTest(name=name):
                report_before = copy.deepcopy(report)
                selection_before = copy.deepcopy(selection)

                self.assert_content_error(
                    "warehouse_anomaly_content_selection_invalid",
                    report,
                    selection,
                )

                self.assertEqual(report, report_before)
                self.assertEqual(selection, selection_before)

    def test_rejects_valid_but_absent_exact_candidate(self):
        report = selected_report(
            "warehouse_invoice_project_mismatch", subject_id=31,
        )
        selection = selected(
            "warehouse_invoice_request_mismatch", subject_id=31,
        )

        self.assert_content_error(
            "warehouse_anomaly_content_selection_invalid",
            report,
            selection,
        )

    def test_rejects_malformed_or_hash_mismatched_stored_report(self):
        extra = selected_report()
        extra["must-not-leak"] = "must-not-leak"

        hash_mismatch = selected_report()
        hash_mismatch["evidenceSha256"] = "0" * 64

        cases = {
            "not_mapping": [],
            "extra_field": extra,
            "hash_mismatch": hash_mismatch,
        }
        for name, report in cases.items():
            with self.subTest(name=name):
                report_before = copy.deepcopy(report)
                selection = selected()
                selection_before = copy.deepcopy(selection)

                self.assert_content_error(
                    "warehouse_anomaly_content_input_invalid",
                    report,
                    selection,
                )

                self.assertEqual(report, report_before)
                self.assertEqual(selection, selection_before)

    def test_rejects_blocked_stored_readiness_even_with_raw_candidate(self):
        report = selected_report()
        supply = report["domains"]["supply"]
        supply.update({
            "state": "review_required",
            "complete": False,
            "reasonCounts": {"supply_quantity_invalid": 1},
            "needsReview": [review(
                "supply_quantity_invalid", 21, "supply",
            )],
        })
        supply["summary"]["needsReview"] = 1
        refresh_envelope(report)
        before = copy.deepcopy(report)

        self.assert_content_error(
            "warehouse_anomaly_content_stored_readiness_blocked",
            report,
            selected(),
        )

        for invalid_selection in (
            selected(anomaly_code="warehouse_invoice_future_mismatch"),
            selected(subject_kind="warehouseHistory"),
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_selection_invalid",
                report,
                invalid_selection,
            )

        self.assertEqual(report, before)

    def test_rejects_clear_stored_readiness(self):
        self.assert_content_error(
            "warehouse_anomaly_content_stored_readiness_blocked",
            stored_report(),
            selected(),
        )

    def test_malformed_json_native_states_never_leak_dependency_errors(self):
        mutations = (
            ("source_status_list", ("source", "reconciliationStatus"), []),
            ("source_status_mapping", ("source", "reconciliationStatus"), {}),
            ("supply_state_list", ("domains", "supply", "state"), []),
            ("supply_state_mapping", ("domains", "supply", "state"), {}),
            ("warehouse_state_list", ("domains", "warehouse", "state"), []),
            ("warehouse_state_mapping", ("domains", "warehouse", "state"), {}),
        )
        for name, path, replacement in mutations:
            with self.subTest(name=name):
                report = selected_report()
                target = report
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = replacement
                rehash(report)
                self.assert_content_error(
                    "warehouse_anomaly_content_input_invalid",
                    report,
                    selected(),
                )

    def test_snapshot_detaches_and_preserves_shared_subtrees(self):
        shared = {"value": [1, 2, 3]}
        original = {"left": shared, "right": shared}

        snapshot = _snapshot_stored_report(original)

        self.assertIs(snapshot["left"], snapshot["right"])
        self.assertIsNot(snapshot["left"], shared)
        shared["value"].append(4)
        self.assertEqual(snapshot["left"]["value"], [1, 2, 3])

    def test_enforces_exact_inclusive_four_mib_canonical_bound(self):
        at_limit = report_with_exact_canonical_size(
            MAX_STORED_REPORT_CANONICAL_BYTES,
        )
        over_limit = report_with_exact_canonical_size(
            MAX_STORED_REPORT_CANONICAL_BYTES + 1,
        )
        self.assertEqual(
            len(canonical_bytes(at_limit)),
            MAX_STORED_REPORT_CANONICAL_BYTES,
        )
        self.assertEqual(
            len(canonical_bytes(over_limit)),
            MAX_STORED_REPORT_CANONICAL_BYTES + 1,
        )

        _prepare_warehouse_anomaly_content(at_limit, selected())
        self.assert_content_error(
            "warehouse_anomaly_content_input_invalid",
            over_limit,
            selected(),
        )

    def test_rejects_recursion_nan_and_non_json_values_with_fixed_code(self):
        recursive = selected_report()
        recursive["domains"]["assignments"]["recursive"] = recursive

        nan_report = selected_report()
        nan_report["domains"]["assignments"]["summary"][
            "assignmentRows"
        ] = float("nan")
        nan_report["evidenceSha256"] = calculate_evidence_sha256(nan_report)

        non_json = selected_report()
        non_json["domains"]["assignments"]["nonJson"] = {1}

        for name, report in (
            ("recursive", recursive),
            ("nan", nan_report),
            ("non_json", non_json),
        ):
            with self.subTest(name=name):
                self.assert_content_error(
                    "warehouse_anomaly_content_input_invalid",
                    report,
                    selected(),
                )

        del recursive["domains"]["assignments"]["recursive"]

    def test_rehashed_mapping_never_creates_a_provenance_claim(self):
        report = selected_report()
        report["source"]["reconciliationStatus"] = "На проверке"
        rehash(report)

        prepared = _prepare_warehouse_anomaly_content(report, selected())

        values_by_name = prepared_field_values(prepared)
        stored_source = exact_mapping(values_by_name.values(), SOURCE_FIELDS)
        self.assertEqual(
            stored_source["reconciliationStatus"], "На проверке",
        )
        names = " ".join(values_by_name).lower()
        for unsupported_claim in (
            "trusted", "provenance", "authorized", "verified", "tenant",
        ):
            self.assertNotIn(unsupported_claim, names)

    def test_pure_module_has_only_allowlisted_dependencies_and_no_runtime_io(self):
        module_path = Path(__file__).with_name("content_contract.py")
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                self.assertIsNotNone(node.module)
                imported.add(node.module)

        project_imports = {
            name for name in imported if name.startswith("backend.")
        }
        self.assertEqual(project_imports, {
            "backend.features.estimate_revision_impact.combined_contract",
            "backend.features.estimate_revision_impact.contract",
            "backend.features.warehouse_recommendation_preview.readiness",
        })
        non_project_roots = {
            name.split(".", 1)[0]
            for name in imported - project_imports
        }
        self.assertEqual(non_project_roots, {
            "collections", "dataclasses", "hashlib", "json", "math",
            "types",
        })
        for forbidden_text in (
            ".execute(", ".cursor(", ".commit(", ".rollback(",
            "psycopg2", "sqlalchemy", "httpx", "openai",
            "anthropic", "INSERT INTO", "UPDATE warehouse", "DELETE FROM",
            "FOR UPDATE", "create_task(", "get_db", ".write_text(",
            ".write_bytes(", "open(",
        ):
            self.assertNotIn(forbidden_text, source)


class WarehouseAnomalyCurrentProducerContractTests(unittest.TestCase):
    maxDiff = None

    def assert_current_report_invalid(self, report, source_contract=None):
        before = copy.deepcopy(report)
        with self.assertRaises(WarehouseAnomalyContentError) as raised:
            _validate_current_warehouse_anomaly_report(
                report,
                source_contract or a7_supply_warehouse_fixtures.source(),
            )
        self.assertEqual(
            raised.exception.code,
            "warehouse_anomaly_content_current_report_invalid",
        )
        self.assertEqual(str(raised.exception), raised.exception.code)
        self.assertEqual(report, before)

    def test_rejects_bool_as_one_in_current_source_and_baseline_issue_ids(self):
        source_revision = current_a7_report()["source"]["sourceRevision"]
        source_contract = EstimateRevisionSource(
            schema_version=REPORT_VERSION,
            event_type=EVENT_TYPE,
            company_id=1,
            project_id=1,
            estimate_id=1,
            source_revision=source_revision,
        )

        ready = current_a7_report()
        for field in ("companyId", "projectId", "estimateId"):
            ready["source"][field] = 1
        _validate_current_warehouse_anomaly_report(ready, source_contract)

        nonready = current_a7_report("not_collected")
        for field in ("companyId", "projectId", "estimateId"):
            nonready["source"][field] = 1
            nonready["issues"][0][field] = 1
        _validate_current_warehouse_anomaly_report(nonready, source_contract)

        cases = []
        for field in ("companyId", "projectId", "estimateId"):
            report = copy.deepcopy(ready)
            report["source"][field] = True
            cases.append((f"ready_source_{field}", report))

            report = copy.deepcopy(nonready)
            report["source"][field] = True
            cases.append((f"nonready_source_{field}", report))

            report = copy.deepcopy(nonready)
            report["issues"][0][field] = True
            cases.append((f"nonready_issue_{field}", report))

        for name, invalid in cases:
            with self.subTest(name=name):
                self.assert_current_report_invalid(invalid, source_contract)

    def test_accepts_positive_producer_ids_without_numeric_ceiling(self):
        large_id = 2 ** 63
        report = current_a7_report()
        source_contract = EstimateRevisionSource(
            schema_version=REPORT_VERSION,
            event_type=EVENT_TYPE,
            company_id=large_id,
            project_id=large_id + 1,
            estimate_id=large_id + 2,
            source_revision=report["source"]["sourceRevision"],
        )
        report["source"].update({
            "companyId": source_contract.company_id,
            "projectId": source_contract.project_id,
            "estimateId": source_contract.estimate_id,
            "reconciliationId": large_id + 3,
            "baseEstimateId": large_id + 4,
        })
        for item in report["supplyWarehouseImpact"]["openSupply"]:
            item["sourceEstimateId"] = large_id + 4
        _validate_current_warehouse_anomaly_report(report, source_contract)

        nonready = current_a7_report("not_collected")
        nonready_contract = EstimateRevisionSource(
            schema_version=REPORT_VERSION,
            event_type=EVENT_TYPE,
            company_id=large_id,
            project_id=large_id + 1,
            estimate_id=large_id + 2,
            source_revision=nonready["source"]["sourceRevision"],
        )
        for field, value in (
            ("companyId", nonready_contract.company_id),
            ("projectId", nonready_contract.project_id),
            ("estimateId", nonready_contract.estimate_id),
        ):
            nonready["source"][field] = value
            nonready["issues"][0][field] = value
        _validate_current_warehouse_anomaly_report(
            nonready, nonready_contract,
        )

        self.assertIs(
            _validated_raw_review(
                raw_review("supply_quantity_invalid", large_id)
            )["sourceId"],
            large_id,
        )
        projection = empty_complete_raw_projection()
        projection["summary"].update({
            "supplyRequestRows": 1,
            "supplyItems": 1,
            "openSupplyItems": 1,
            "deliveries": 1,
        })
        projection["openSupply"] = [{
            "requestId": large_id,
            "requestItemIndex": 0,
            "sourceEstimateId": large_id + 4,
            "sourceSectionIndex": large_id,
            "sourceItemIndex": large_id,
            "state": "open_balance",
        }]
        projection["protectedEvidence"]["deliveryIds"] = [large_id]
        _validate_raw_supply_warehouse_projection(
            projection,
            base_estimate_id=large_id + 4,
            allow_not_collected=False,
        )

    def test_freezes_all_71_current_review_shapes_and_producer_dependencies(self):
        self.assertIsInstance(_RAW_REVIEW_RULES, MappingProxyType)
        self.assertEqual(
            dict(_RAW_REVIEW_RULES), dict(EXPECTED_RAW_REVIEW_RULES),
        )
        self.assertEqual(len(_RAW_REVIEW_RULES), 71)

        actual_rules, native_reasons, resolver_reasons = (
            extracted_a7_raw_review_rules()
        )
        self.assertEqual(actual_rules, dict(EXPECTED_RAW_REVIEW_RULES))
        self.assertEqual(len(native_reasons), 65)
        self.assertEqual(
            resolver_reasons - native_reasons,
            {
                "supply_source_estimate_invalid",
                "supply_snapshot_content_invalid",
                "supply_source_item_key_noncanonical",
                "supply_source_item_key_missing",
                "supply_source_item_key_required",
                "supply_source_item_key_mismatch",
            },
        )
        self.assertEqual(
            native_reasons | resolver_reasons,
            set(EXPECTED_RAW_REVIEW_RULES),
        )

        for reason_code, (source_kind, id_policy) in (
            EXPECTED_RAW_REVIEW_RULES.items()
        ):
            with self.subTest(reason_code=reason_code, valid=True):
                valid = raw_review(reason_code)
                self.assertIs(_validated_raw_review(valid), valid)
                self.assertEqual(valid["sourceKind"], source_kind)
            if id_policy == "optional":
                with self.subTest(reason_code=reason_code, optional_none=True):
                    valid_none = raw_review(reason_code, None)
                    self.assertIs(
                        _validated_raw_review(valid_none), valid_none,
                    )
            invalid_ids = {
                "none": (1, True),
                "positive": (None, 0, -1, True),
                "optional": (0, -1, True),
            }[id_policy]
            for invalid_id in invalid_ids:
                with self.subTest(
                    reason_code=reason_code, invalid_id=invalid_id,
                ):
                    with self.assertRaises(ValueError):
                        _validated_raw_review(
                            raw_review(reason_code, invalid_id)
                        )
            wrong_kind = raw_review(reason_code)
            wrong_kind["sourceKind"] = source_kind + "Future"
            with self.subTest(reason_code=reason_code, wrong_kind=True):
                with self.assertRaises(ValueError):
                    _validated_raw_review(wrong_kind)

        aggregate_reasons = {
            reason_code: rule
            for reason_code, rule in EXPECTED_RAW_REVIEW_RULES.items()
            if rule[0] != "supplyWarehouse"
        }
        projection = empty_complete_raw_projection()
        projection.update({
            "state": "review_required",
            "complete": False,
            "reasonCounts": {
                reason_code: 1
                for reason_code in aggregate_reasons
            },
            "needsReview": [
                raw_review(reason_code)
                for reason_code in aggregate_reasons
            ],
        })
        projection["summary"]["needsReview"] = len(aggregate_reasons)
        _validate_raw_supply_warehouse_projection(
            projection,
            base_estimate_id=51,
            allow_not_collected=False,
        )

    def test_static_parity_helpers_fail_closed_on_new_emission_forms(self):
        dynamic_tree = ast.parse(
            "def producer(row_id, expose):\n"
            "    return _review(\"supply\", row_id, \"new_reason\", "
            "expose_id=expose)\n"
        )
        dynamic_parents = _ast_parent_map(dynamic_tree)
        dynamic_call = next(
            node for node in ast.walk(dynamic_tree)
            if isinstance(node, ast.Call) and _ast_call_name(node) == "_review"
        )
        with self.assertRaises(AssertionError):
            _ast_source_id_policy(
                dynamic_call,
                dynamic_call.args[1],
                _ast_keyword(dynamic_call, "expose_id"),
                dynamic_parents,
            )

        unreviewed_sources = (
            "def producer(review):\n"
            "    review.setdefault(\"reasonCode\", \"new_reason\")\n",
            "def producer(value):\n"
            "    return dict([(\"reasonCode\", value)])\n",
            "def producer(value):\n"
            "    return {\"reasonCode\": value}\n",
            "def producer(reviews, value):\n"
            "    key = \"reason\" + \"Code\"\n"
            "    reviews.append({key: value})\n",
        )
        for source in unreviewed_sources:
            with self.subTest(source=source.splitlines()[-1].strip()):
                with self.assertRaises(AssertionError):
                    _assert_closed_review_emissions(
                        ast.parse(source), {"_review"},
                    )

        _assert_closed_review_emissions(
            ast.parse(
                "def _review(value):\n"
                "    return {\"reasonCode\": value}\n"
                "def inspect(item):\n"
                "    return item[\"reasonCode\"]\n"
            ),
            {"_review"},
        )

    def test_freezes_all_baseline_reason_shapes_and_current_source_bounds(self):
        self.assertIsInstance(_BASELINE_REASON_RULES, MappingProxyType)
        self.assertEqual(
            dict(_BASELINE_REASON_RULES),
            dict(EXPECTED_BASELINE_REASON_RULES),
        )
        baseline_tree = ast.parse(
            Path(a7_baseline.__file__).read_text(encoding="utf-8")
        )
        producer_reasons = {
            node.value
            for node in ast.walk(baseline_tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith((
                "estimate_revision_impact_", "impact_",
                "source_revision_",
            ))
        }
        self.assertEqual(
            producer_reasons, set(EXPECTED_BASELINE_REASON_RULES),
        )

        for reason_code in EXPECTED_BASELINE_REASON_RULES:
            with self.subTest(reason_code=reason_code):
                report = baseline_reason_report(reason_code)
                before = copy.deepcopy(report)
                _validate_current_warehouse_anomaly_report(
                    report, a7_supply_warehouse_fixtures.source(),
                )
                self.assertEqual(report, before)

        for reason_code, estimate_rows, reconciliation_rows in (
            ("impact_reconciliation_ambiguous", 1, 100),
            ("impact_reconciliation_scan_limit_exceeded", 1, 101),
        ):
            with self.subTest(reason_code=reason_code, upper_bound=True):
                report = baseline_reason_report(reason_code)
                report["summary"] = {
                    "estimateRows": estimate_rows,
                    "reconciliationRows": reconciliation_rows,
                }
                _validate_current_warehouse_anomaly_report(
                    report, a7_supply_warehouse_fixtures.source(),
                )

    def test_freezes_17_and_59_column_allowlists_and_sentinel_shapes(self):
        expected_baseline_columns = flattened_required_columns(
            a7_baseline.REQUIRED_COLUMNS,
        )
        expected_raw_columns = flattened_required_columns(
            SUPPLY_WAREHOUSE_REQUIRED_COLUMNS,
        )
        self.assertEqual(len(expected_baseline_columns), 17)
        self.assertEqual(len(expected_raw_columns), 59)
        self.assertEqual(
            _BASELINE_REQUIRED_COLUMNS, expected_baseline_columns,
        )
        self.assertEqual(_RAW_REQUIRED_COLUMNS, expected_raw_columns)

        raw_column_shapes = (
            *([column] for column in sorted(expected_raw_columns)),
            sorted(expected_raw_columns),
            ["schema_scan_limit_exceeded"],
        )
        for missing_columns in raw_column_shapes:
            with self.subTest(raw_missing_columns=missing_columns[:2]):
                projection = a7_supply_warehouse_audit._empty_projection(
                    "incomplete",
                    "supply_warehouse_impact_schema_not_ready",
                    schema_ready=False,
                    missing_columns=missing_columns,
                )
                _validate_raw_supply_warehouse_projection(
                    projection,
                    base_estimate_id=51,
                    allow_not_collected=False,
                )

        baseline_column_shapes = (
            *([column] for column in sorted(expected_baseline_columns)),
            sorted(expected_baseline_columns),
            ["schema_scan_limit_exceeded"],
        )
        for missing_columns in baseline_column_shapes:
            with self.subTest(baseline_missing_columns=missing_columns[:2]):
                report = baseline_reason_report(
                    "estimate_revision_impact_schema_not_ready"
                )
                report["missingColumns"] = missing_columns
                _validate_current_warehouse_anomaly_report(
                    report, a7_supply_warehouse_fixtures.source(),
                )

        invalid_raw_columns = (
            ["warehouse_invoices.future_column"],
            ["projects.id", "projects.id"],
            list(reversed(sorted(expected_raw_columns)[:2])),
            [True],
        )
        for missing_columns in invalid_raw_columns:
            with self.subTest(invalid_raw_columns=missing_columns):
                projection = empty_complete_raw_projection()
                projection.update({
                    "state": "incomplete",
                    "schemaReady": False,
                    "missingColumns": missing_columns,
                    "complete": False,
                })
                with self.assertRaises(ValueError):
                    _validate_raw_supply_warehouse_projection(
                        projection,
                        base_estimate_id=51,
                        allow_not_collected=False,
                    )

    def test_review_count_list_histogram_and_truncation_boundaries(self):
        for count in (100, 101, 10800):
            with self.subTest(count=count):
                projection = raw_review_projection(
                    "supply_quantity_invalid", count,
                )
                before = copy.deepcopy(projection)
                _validate_raw_supply_warehouse_projection(
                    projection,
                    base_estimate_id=51,
                    allow_not_collected=False,
                )
                self.assertEqual(projection, before)
                self.assertEqual(
                    projection["needsReviewTruncated"], count > 100,
                )
                self.assertEqual(
                    len(projection["needsReview"]), min(count, 100),
                )

        over_limit = raw_review_projection(
            "supply_quantity_invalid", 10801,
        )
        with self.assertRaises(ValueError):
            _validate_raw_supply_warehouse_projection(
                over_limit,
                base_estimate_id=51,
                allow_not_collected=False,
            )

        cases = []
        projection = raw_review_projection("supply_quantity_invalid", 1)
        projection["reasonCounts"]["supply_quantity_invalid"] = True
        cases.append(("bool_reason_count", projection))

        projection = raw_review_projection("supply_quantity_invalid", 1)
        projection["summary"]["needsReview"] = True
        cases.append(("bool_summary_count", projection))

        projection = raw_review_projection("supply_quantity_invalid", 101)
        projection["needsReviewTruncated"] = False
        cases.append(("missing_truncation", projection))

        projection = raw_review_projection("supply_quantity_invalid", 101)
        projection["needsReview"][0]["reasonCode"] = (
            "supply_source_lineage_invalid"
        )
        cases.append(("visible_histogram_not_in_total", projection))

        projection = raw_review_projection("supply_quantity_invalid", 100)
        projection["needsReview"].pop()
        cases.append(("short_visible_list", projection))

        for name, invalid in cases:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    _validate_raw_supply_warehouse_projection(
                        invalid,
                        base_estimate_id=51,
                        allow_not_collected=False,
                    )

    def test_enforces_inclusive_raw_count_list_and_cross_field_bounds(self):
        count_list_pairs = {
            "deliveries": "deliveryIds",
            "allocations": "allocationIds",
            "supplierInvoices": "supplierInvoiceIds",
            "warehouseInvoices": "warehouseInvoiceIds",
            "warehouseHistoryRows": "warehouseHistoryIds",
            "receiptLots": "receiptLotIds",
            "warehouseMovements": "warehouseMovementIds",
            "lotMovements": "lotMovementIds",
        }

        def open_item(sequence, *, request_item_index=None):
            return {
                "requestId": 1 + sequence // 100,
                "requestItemIndex": (
                    sequence % 100
                    if request_item_index is None
                    else request_item_index
                ),
                "sourceEstimateId": 51,
                "sourceSectionIndex": sequence,
                "sourceItemIndex": 0,
                "state": "open_balance",
            }

        def open_projection(count):
            projection = empty_complete_raw_projection()
            projection["summary"].update({
                "supplyRequestRows": (count + 99) // 100,
                "supplyItems": count,
                "openSupplyItems": count,
            })
            projection["openSupply"] = [
                open_item(index) for index in range(min(count, 100))
            ]
            if count > 100:
                projection.update({
                    "state": "incomplete",
                    "complete": False,
                    "factsTruncated": True,
                })
            return projection

        valid_cases = []

        projection = empty_complete_raw_projection()
        projection["summary"]["supplyRequestRows"] = 100
        valid_cases.append(("request_rows_100", projection))

        projection = empty_complete_raw_projection()
        projection["summary"].update({
            "supplyRequestRows": 100,
            "supplyItems": 10000,
        })
        valid_cases.append(("supply_items_10000", projection))

        for count_name, list_name in count_list_pairs.items():
            projection = empty_complete_raw_projection()
            projection["summary"][count_name] = 100
            projection["protectedEvidence"][list_name] = list(
                range(1, 101)
            )
            valid_cases.append((f"{count_name}_100", projection))

        projection = open_projection(1)
        projection["openSupply"][0]["requestItemIndex"] = 99
        valid_cases.append(("request_item_index_99", projection))

        valid_cases.extend((
            ("open_items_100_not_truncated", open_projection(100)),
            ("open_items_101_truncated", open_projection(101)),
        ))

        projection = empty_complete_raw_projection()
        projection["summary"].update({
            "supplyRequestRows": 1,
            "supplyItems": 2,
            "openSupplyItems": 1,
            "protectedSupplyItems": 1,
        })
        projection["openSupply"] = [open_item(0)]
        valid_cases.append(("open_plus_protected_equals_items", projection))

        projection = empty_complete_raw_projection()
        projection["summary"].update({
            "supplyRequestRows": 100,
            "closedSupplyRequests": 100,
        })
        projection["protectedEvidence"][
            "closedSupplyRequestIds"
        ] = list(range(1, 101))
        valid_cases.append(("closed_equals_requests", projection))

        for name, valid in valid_cases:
            with self.subTest(name=name, expected="valid"):
                before = copy.deepcopy(valid)
                _validate_raw_supply_warehouse_projection(
                    valid,
                    base_estimate_id=51,
                    allow_not_collected=False,
                )
                self.assertEqual(valid, before)

        invalid_cases = []

        projection = empty_complete_raw_projection()
        projection["summary"]["supplyRequestRows"] = 101
        invalid_cases.append(("request_rows_101", projection))

        projection = empty_complete_raw_projection()
        projection["summary"].update({
            "supplyRequestRows": 100,
            "supplyItems": 10001,
        })
        invalid_cases.append(("supply_items_10001", projection))

        for count_name, list_name in count_list_pairs.items():
            projection = empty_complete_raw_projection()
            projection["summary"][count_name] = 101
            projection["protectedEvidence"][list_name] = list(
                range(1, 101)
            )
            projection.update({
                "state": "incomplete",
                "complete": False,
                "factsTruncated": True,
            })
            invalid_cases.append((f"{count_name}_101", projection))

        projection = open_projection(1)
        projection["openSupply"][0]["requestItemIndex"] = 100
        invalid_cases.append(("request_item_index_100", projection))

        projection = open_projection(1)
        projection["summary"]["supplyItems"] = 0
        invalid_cases.append(("open_exceeds_items", projection))

        projection = empty_complete_raw_projection()
        projection["summary"]["protectedSupplyItems"] = 1
        invalid_cases.append(("protected_exceeds_items", projection))

        projection = open_projection(1)
        projection["summary"]["protectedSupplyItems"] = 1
        invalid_cases.append(("open_plus_protected_exceeds_items", projection))

        projection = empty_complete_raw_projection()
        projection["summary"]["closedSupplyRequests"] = 1
        projection["protectedEvidence"][
            "closedSupplyRequestIds"
        ] = [1]
        invalid_cases.append(("closed_exceeds_requests", projection))

        for summary_field in tuple(
            empty_complete_raw_projection()["summary"]
        ):
            projection = empty_complete_raw_projection()
            projection["summary"][summary_field] = True
            invalid_cases.append((f"bool_{summary_field}", projection))

        for name, invalid in invalid_cases:
            with self.subTest(name=name, expected="invalid"):
                with self.assertRaises(ValueError):
                    _validate_raw_supply_warehouse_projection(
                        invalid,
                        base_estimate_id=51,
                        allow_not_collected=False,
                    )

    def test_accepts_exact_public_a7_producer_systemic_shapes_unchanged(self):
        for outcome in (
            "complete", "review_required", "incomplete", "not_collected",
            "baseline_incomplete",
        ):
            with self.subTest(outcome=outcome):
                report = current_a7_report(outcome)
                before = copy.deepcopy(report)

                _validate_current_warehouse_anomaly_report(
                    report, a7_supply_warehouse_fixtures.source(),
                )

                self.assertEqual(report, before)

        systemic_cases = (
            (
                "supply_warehouse_impact_schema_not_ready",
                "incomplete",
                False,
                ["projects.name"],
            ),
            (
                "supply_warehouse_project_identity_invalid",
                "review_required",
                True,
                [],
            ),
            (
                "supply_warehouse_scan_limit_exceeded",
                "incomplete",
                True,
                [],
            ),
            (
                "supply_warehouse_source_snapshot_invalid",
                "review_required",
                True,
                [],
            ),
            (
                "supply_request_scan_limit_exceeded",
                "incomplete",
                True,
                [],
            ),
        )
        for reason_code, state, schema_ready, missing_columns in (
            systemic_cases
        ):
            with self.subTest(systemic_reason=reason_code):
                report = current_a7_report()
                report["supplyWarehouseImpact"] = (
                    a7_supply_warehouse_audit._empty_projection(
                        state,
                        reason_code,
                        schema_ready=schema_ready,
                        missing_columns=missing_columns,
                    )
                )
                report["readyForSupplyWarehouseProjection"] = False
                before = copy.deepcopy(report)

                _validate_current_warehouse_anomaly_report(
                    report, a7_supply_warehouse_fixtures.source(),
                )

                self.assertEqual(report, before)

    def test_rejects_non_exact_wrapper_flags_and_requested_source_drift(self):
        cases = []

        report = current_a7_report()
        report["ignored"] = "normalizer-would-drop-this"
        cases.append(("extra_wrapper_field", report))

        report = current_a7_report()
        del report["issuesTruncated"]
        cases.append(("missing_wrapper_field", report))

        report = current_a7_report()
        report["writesAttempted"] = False
        cases.append(("bool_writes_attempted", report))

        report = current_a7_report()
        report["source"]["companyId"] = 5
        cases.append(("requested_source_drift", report))

        report = current_a7_report()
        report["readyForDomainScan"] = False
        cases.append(("source_ready_flag_contradiction", report))

        report = current_a7_report()
        report["readyForSupplyWarehouseProjection"] = False
        cases.append(("projection_ready_flag_contradiction", report))

        for name, invalid in cases:
            with self.subTest(name=name):
                self.assert_current_report_invalid(invalid)

    def test_rejects_outer_baseline_bounds_and_issue_coherence_mutations(self):
        cases = []

        report = current_a7_report("baseline_incomplete")
        report["missingColumns"] = [
            "warehouse_invoices.future_column",
        ]
        cases.append(("arbitrary_baseline_missing_column", report))

        report = current_a7_report("incomplete")
        report["supplyWarehouseImpact"]["missingColumns"] = [
            "warehouse_invoices.future_column",
        ]
        cases.append(("arbitrary_projection_missing_column", report))

        report = current_a7_report()
        report["summary"]["estimateRows"] = 3
        cases.append(("estimate_rows_over_bound", report))

        report = current_a7_report()
        report["summary"]["reconciliationRows"] = 102
        cases.append(("reconciliation_rows_over_bound", report))

        report = current_a7_report("not_collected")
        report["issueCount"] = 2
        cases.append(("issue_count_histogram_mismatch", report))

        report = current_a7_report("not_collected")
        report["issuesTruncated"] = True
        cases.append(("issue_truncation_mismatch", report))

        for name, invalid in cases:
            with self.subTest(name=name):
                self.assert_current_report_invalid(invalid)

    def test_rejects_raw_projection_mutations_before_normalization(self):
        cases = []

        report = current_a7_report()
        report["supplyWarehouseImpact"]["ignored"] = "drop-me"
        cases.append(("extra_projection_field", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"]["state"] = "review_required"
        cases.append(("state_complete_contradiction", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"]["summary"]["supplyItems"] = 101
        cases.append(("items_exceed_request_bound", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"]["openSupply"][0][
            "requestItemIndex"
        ] = 100
        cases.append(("request_item_index_over_bound", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"]["openSupply"][0][
            "sourceEstimateId"
        ] = 52
        cases.append(("wrong_base_estimate", report))

        report = current_a7_report()
        projection = report["supplyWarehouseImpact"]
        duplicate = dict(projection["openSupply"][0])
        duplicate["requestItemIndex"] = 1
        projection["openSupply"].append(duplicate)
        projection["summary"]["supplyItems"] = 2
        projection["summary"]["openSupplyItems"] = 2
        cases.append(("duplicate_source_coordinate", report))

        report = current_a7_report()
        projection = report["supplyWarehouseImpact"]
        projection["protectedEvidence"]["deliveryIds"] = [72, 71]
        projection["summary"]["deliveries"] = 2
        cases.append(("unsorted_protected_ids", report))

        report = current_a7_report("review_required")
        projection = report["supplyWarehouseImpact"]
        old_code = projection["needsReview"][0]["reasonCode"]
        projection["needsReview"][0]["reasonCode"] = "future_reason"
        projection["reasonCounts"].pop(old_code)
        projection["reasonCounts"]["future_reason"] = 1
        cases.append(("unknown_review_reason", report))

        for name, invalid in cases:
            with self.subTest(name=name):
                self.assert_current_report_invalid(invalid)

    def test_rejects_missing_raw_fields_id_and_state_relation_mutations(self):
        projection_fields = tuple(sorted(
            current_a7_report()["supplyWarehouseImpact"]
        ))
        for field in projection_fields:
            with self.subTest(missing_projection_field=field):
                report = current_a7_report()
                del report["supplyWarehouseImpact"][field]
                self.assert_current_report_invalid(report)

        id_cases = (
            ("duplicate_id", [1, 1], 2),
            ("zero_id", [0], 1),
            ("bool_id", [True], 1),
        )
        for name, ids, count in id_cases:
            with self.subTest(name=name):
                report = current_a7_report()
                projection = report["supplyWarehouseImpact"]
                projection["protectedEvidence"]["deliveryIds"] = ids
                projection["summary"]["deliveries"] = count
                self.assert_current_report_invalid(report)

        cases = []

        report = current_a7_report()
        projection = report["supplyWarehouseImpact"]
        projection.update({
            "state": "incomplete",
            "schemaReady": False,
            "complete": False,
        })
        cases.append(("schema_false_without_missing_columns", report))

        report = current_a7_report("incomplete")
        report["supplyWarehouseImpact"]["schemaReady"] = True
        cases.append(("schema_true_with_missing_columns", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"]["scanComplete"] = False
        cases.append(("complete_with_incomplete_scan", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"].update({
            "state": "incomplete",
            "complete": False,
        })
        cases.append(("incomplete_with_complete_facts", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"].update({
            "state": "incomplete",
            "complete": False,
            "factsTruncated": True,
        })
        cases.append(("truncated_without_over_limit_facts", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"] = (
            a7_supply_warehouse_audit._empty_projection("not_collected")
        )
        report["readyForSupplyWarehouseProjection"] = False
        cases.append(("source_ready_not_collected", report))

        for name, invalid in cases:
            with self.subTest(name=name):
                self.assert_current_report_invalid(invalid)

    def test_rejects_impossible_noncanonical_systemic_projection_shapes(self):
        cases = []

        report = current_a7_report()
        report["supplyWarehouseImpact"].update({
            "state": "incomplete",
            "scanComplete": False,
            "complete": False,
        })
        report["readyForSupplyWarehouseProjection"] = False
        cases.append(("scan_failure_retains_collected_facts", report))

        report = current_a7_report()
        report["supplyWarehouseImpact"].update({
            "state": "incomplete",
            "schemaReady": False,
            "missingColumns": ["projects.name"],
            "complete": False,
        })
        report["readyForSupplyWarehouseProjection"] = False
        cases.append(("schema_failure_retains_collected_facts", report))

        report = current_a7_report()
        projection = report["supplyWarehouseImpact"]
        projection.update({
            "state": "review_required",
            "complete": False,
            "reasonCounts": {
                "supply_warehouse_project_identity_invalid": 1,
            },
            "needsReview": [{
                "sourceKind": "supplyWarehouse",
                "sourceId": None,
                "reasonCode": (
                    "supply_warehouse_project_identity_invalid"
                ),
            }],
        })
        projection["summary"]["needsReview"] = 1
        report["readyForSupplyWarehouseProjection"] = False
        cases.append(("systemic_reason_mixed_with_collected_facts", report))

        report = current_a7_report()
        projection = a7_supply_warehouse_audit._empty_projection(
            "incomplete", "supply_warehouse_scan_limit_exceeded",
        )
        projection["summary"]["deliveries"] = 1
        projection["protectedEvidence"]["deliveryIds"] = [1]
        report["supplyWarehouseImpact"] = projection
        report["readyForSupplyWarehouseProjection"] = False
        cases.append(("scan_limit_systemic_contains_child_fact", report))

        for name, invalid in cases:
            with self.subTest(name=name):
                self.assert_current_report_invalid(invalid)


A92C_FIXED_FINDINGS = MappingProxyType({
    "warehouse_invoice_request_mismatch": (
        "Связь складской накладной с заявкой не совпадает с текущей "
        "точной цепочкой источника."
    ),
    "warehouse_invoice_project_mismatch": (
        "Проект складской накладной не совпадает с текущей точной "
        "цепочкой источника."
    ),
    "warehouse_invoice_delivery_mismatch": (
        "Связь складской накладной с поставкой не совпадает с текущей "
        "точной цепочкой источника."
    ),
    "warehouse_invoice_supplier_invoice_mismatch": (
        "Связь складской накладной с документом поставщика не совпадает "
        "с текущей точной цепочкой источника."
    ),
    "warehouse_invoice_items_invalid": (
        "Состав строк складской накладной не подтверждён текущим точным "
        "snapshot."
    ),
    "warehouse_receipt_invoice_mismatch": (
        "Приход склада не связан с ожидаемой накладной в текущем точном "
        "snapshot."
    ),
    "warehouse_receipt_line_invalid": (
        "Строка-источник складского прихода отсутствует или невалидна "
        "в текущем точном snapshot."
    ),
    "warehouse_receipt_package_mismatch": (
        "Пакет работ складского прихода не совпадает с текущей точной "
        "цепочкой источника."
    ),
    "warehouse_receipt_lot_invoice_mismatch": (
        "Партия прихода не связана с ожидаемой накладной в текущем "
        "точном snapshot."
    ),
    "warehouse_receipt_lot_line_invalid": (
        "Строка-источник партии прихода отсутствует или невалидна в "
        "текущем точном snapshot."
    ),
    "warehouse_receipt_lot_project_mismatch": (
        "Проект партии прихода не совпадает с текущей точной цепочкой "
        "источника."
    ),
    "warehouse_movement_invoice_mismatch": (
        "Движение склада не связано с ожидаемой накладной в текущем "
        "точном snapshot."
    ),
    "warehouse_movement_line_invalid": (
        "Строка-источник движения склада отсутствует или невалидна в "
        "текущем точном snapshot."
    ),
    "warehouse_movement_package_mismatch": (
        "Пакет работ движения склада не совпадает с текущей точной "
        "цепочкой источника."
    ),
    "warehouse_movement_lot_missing": (
        "Для движения склада не найдена ожидаемая связь с партией "
        "прихода."
    ),
    "warehouse_lot_movement_missing": (
        "Для связи партии не найдено ожидаемое складское движение."
    ),
    "warehouse_lot_movement_parent_mismatch": (
        "Родительская связь события партии не совпадает с текущим "
        "точным snapshot."
    ),
    "warehouse_lot_movement_source_mismatch": (
        "Источник события партии не совпадает с текущим точным snapshot."
    ),
})

A92C_FIXED_RECOMMENDATION_CONTENT = MappingProxyType({
    "review_warehouse_invoice_lineage": (
        "Проверить связь складской накладной",
        "Сверьте первичный документ и его точные связи. Не меняйте "
        "остаток автоматически.",
    ),
    "review_warehouse_invoice_items": (
        "Проверить состав складской накладной",
        "Сверьте строки первичного документа с источником. Не исправляйте "
        "количество автоматически.",
    ),
    "review_warehouse_receipt_lineage": (
        "Проверить связь складского прихода",
        "Сверьте приход с накладной, строкой и пакетом работ. Не создавайте "
        "корректирующее движение автоматически.",
    ),
    "review_receipt_lot_lineage": (
        "Проверить связь партии прихода",
        "Сверьте партию с накладной, строкой и проектом. Не меняйте "
        "доступное количество автоматически.",
    ),
    "review_warehouse_movement_lineage": (
        "Проверить источник движения склада",
        "Сверьте движение с накладной, строкой и пакетом работ. Не "
        "отменяйте и не повторяйте движение автоматически.",
    ),
    "review_warehouse_movement_traceability": (
        "Проверить трассируемость движения склада",
        "Сверьте движение и событие партии по первичным ID. Не "
        "восстанавливайте связь автоматически.",
    ),
    "review_lot_movement_lineage": (
        "Проверить событие партии",
        "Сверьте родительское движение и источник события партии. Не "
        "перепривязывайте событие автоматически.",
    ),
})

A92C_RESULT_FIELDS = frozenset({
    "warehouseAnomalyContentVersion",
    "ok",
    "dryRun",
    "writesAttempted",
    "previewOnly",
    "stockMovementAllowed",
    "inventoryAdjustmentAllowed",
    "applyAllowed",
    "state",
    "source",
    "candidate",
    "content",
    "blockers",
    "contentSha256",
    "readOnlyTransaction",
    "rolledBack",
})


def _a92c_replace_raw_reviews(current, anomaly_code, subject_id):
    source_kind, id_policy = EXPECTED_RAW_REVIEW_RULES[anomaly_code]
    if id_policy != "positive":
        raise AssertionError("A9.2 fixed finding must identify one subject")
    projection = current["supplyWarehouseImpact"]
    projection.update({
        "state": "review_required",
        "complete": False,
        "reasonCounts": {anomaly_code: 1},
        "needsReview": [{
            "sourceKind": source_kind,
            "sourceId": subject_id,
            "reasonCode": anomaly_code,
        }],
        "needsReviewTruncated": False,
    })
    projection["summary"]["needsReview"] = 1
    current["readyForSupplyWarehouseProjection"] = False


def _a92c_case(case_index=1):
    anomaly_code, _source_kind, subject_kind, recommendation_code = (
        CANDIDATE_CASES[case_index]
    )
    subject_id = 200 + case_index
    current = copy.deepcopy(current_a7_report("review_required"))
    _a92c_replace_raw_reviews(current, anomaly_code, subject_id)
    stored = build_combined_report(
        current["source"],
        assignment=None,
        material=None,
        supply_warehouse=current["supplyWarehouseImpact"],
        economics=None,
    )
    stored.update({"readOnlyTransaction": True, "rolledBack": True})
    selection = selected(
        anomaly_code,
        subject_kind=subject_kind,
        subject_id=subject_id,
    )
    prepared = _prepare_warehouse_anomaly_content(stored, selection)
    if prepared.candidate["recommendationCode"] != recommendation_code:
        raise AssertionError("test fixture recommendation mapping drifted")
    return prepared, stored, selection, current


def _a92c_content_sha256(result):
    preimage = {
        "warehouseAnomalyContentVersion": (
            result["warehouseAnomalyContentVersion"]
        ),
        "source": result["source"],
        "candidate": result["candidate"],
        "content": result["content"],
    }
    return hashlib.sha256(canonical_bytes(preimage)).hexdigest()


def _a92c_relevant_sha256(current):
    report = build_combined_report(
        current["source"],
        assignment=None,
        material=None,
        supply_warehouse=current["supplyWarehouseImpact"],
        economics=None,
    )
    return expected_relevant_evidence_sha256(report)


class WarehouseAnomalyContentFinalizationTests(unittest.TestCase):
    maxDiff = None

    def assert_content_error(self, code, prepared, current):
        before = copy.deepcopy(current)
        with self.assertRaises(WarehouseAnomalyContentError) as raised:
            _finalize_warehouse_anomaly_content(prepared, current)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(str(raised.exception), code)
        self.assertEqual(raised.exception.args, (code,))
        self.assertEqual(current, before)
        self.assertNotIn("must_not_leak", str(raised.exception))

    def assert_non_ready(self, result, prepared, state, blocker):
        self.assertEqual(set(result), A92C_RESULT_FIELDS)
        self.assertEqual(result["warehouseAnomalyContentVersion"], 1)
        self.assertIs(result["ok"], True)
        self.assertIs(result["dryRun"], True)
        self.assertEqual(type(result["writesAttempted"]), int)
        self.assertEqual(result["writesAttempted"], 0)
        self.assertIs(result["previewOnly"], True)
        self.assertIs(result["stockMovementAllowed"], False)
        self.assertIs(result["inventoryAdjustmentAllowed"], False)
        self.assertIs(result["applyAllowed"], False)
        self.assertEqual(result["state"], state)
        self.assertEqual(result["candidate"], dict(prepared.candidate))
        self.assertEqual(result["source"], {
            **dict(prepared.stored_source),
            "revalidatedRelevantEvidenceSha256": None,
        })
        self.assertEqual(result["blockers"], [blocker])
        self.assertIsNone(result["content"])
        self.assertIsNone(result["contentSha256"])
        self.assertIs(result["readOnlyTransaction"], True)
        self.assertIs(result["rolledBack"], True)

    def test_all_18_findings_and_seven_title_action_pairs_are_exact(self):
        self.assertEqual(
            set(A92C_FIXED_FINDINGS),
            {case[0] for case in CANDIDATE_CASES},
        )
        self.assertEqual(
            set(A92C_FIXED_RECOMMENDATION_CONTENT),
            {case[3] for case in CANDIDATE_CASES},
        )

        for case_index, case in enumerate(CANDIDATE_CASES):
            anomaly_code, _source_kind, _subject_kind, recommendation_code = (
                case
            )
            with self.subTest(anomaly_code=anomaly_code):
                prepared, stored, selection, current = _a92c_case(case_index)
                stored_before = copy.deepcopy(stored)
                selection_before = copy.deepcopy(selection)
                current_before = copy.deepcopy(current)

                result = _finalize_warehouse_anomaly_content(
                    prepared, current,
                )
                repeated = _finalize_warehouse_anomaly_content(
                    prepared, copy.deepcopy(current),
                )

                title, action = A92C_FIXED_RECOMMENDATION_CONTENT[
                    recommendation_code
                ]
                self.assertEqual(result, repeated)
                self.assertEqual(set(result), A92C_RESULT_FIELDS)
                self.assertEqual(result["warehouseAnomalyContentVersion"], 1)
                self.assertIs(result["ok"], True)
                self.assertIs(result["dryRun"], True)
                self.assertEqual(type(result["writesAttempted"]), int)
                self.assertEqual(result["writesAttempted"], 0)
                self.assertIs(result["previewOnly"], True)
                self.assertIs(result["stockMovementAllowed"], False)
                self.assertIs(result["inventoryAdjustmentAllowed"], False)
                self.assertIs(result["applyAllowed"], False)
                self.assertEqual(result["state"], "preview_ready")
                self.assertEqual(result["source"], {
                    **dict(prepared.stored_source),
                    "revalidatedRelevantEvidenceSha256": (
                        prepared.relevant_evidence_sha256
                    ),
                })
                self.assertEqual(result["candidate"], dict(prepared.candidate))
                self.assertEqual(result["content"], {
                    "title": title,
                    "finding": A92C_FIXED_FINDINGS[anomaly_code],
                    "nextSafeAction": action,
                })
                self.assertEqual(result["blockers"], [])
                self.assertRegex(result["contentSha256"], r"^[0-9a-f]{64}$")
                self.assertEqual(
                    result["contentSha256"], _a92c_content_sha256(result),
                )
                self.assertIs(result["readOnlyTransaction"], True)
                self.assertIs(result["rolledBack"], True)
                self.assertEqual(stored, stored_before)
                self.assertEqual(selection, selection_before)
                self.assertEqual(current, current_before)

    def test_unrelated_domain_drift_cannot_change_relevant_or_content_hash(self):
        prepared, stored, selection, current = _a92c_case()
        variant = copy.deepcopy(stored)
        variant["domains"]["assignments"]["missingColumns"] = [
            "private.must_not_leak"
        ]
        variant["domains"]["assignments"]["summary"][
            "assignmentRows"
        ] = 7
        variant["domains"]["materials"]["summary"][
            "targetMaterialRows"
        ] = 8
        variant["domains"]["economics"]["summary"][
            "nonActionablePlans"
        ] = 9
        refresh_envelope(variant)
        variant_before = copy.deepcopy(variant)

        variant_prepared = _prepare_warehouse_anomaly_content(
            variant, selection,
        )
        baseline = _finalize_warehouse_anomaly_content(prepared, current)
        drifted = _finalize_warehouse_anomaly_content(
            variant_prepared, current,
        )

        self.assertNotEqual(
            prepared.impact_evidence_sha256,
            variant_prepared.impact_evidence_sha256,
        )
        self.assertEqual(
            prepared.relevant_evidence_sha256,
            variant_prepared.relevant_evidence_sha256,
        )
        self.assertEqual(baseline, drifted)
        self.assertEqual(variant, variant_before)
        serialized = json.dumps(drifted, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "must_not_leak",
            "impactEvidenceSha256",
            "materialName",
            "projectName",
            "supplierName",
            "notes",
            "price",
            "rawReport",
            "SELECT ",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_business_state_precedence_is_exact_and_never_leaks_hash(self):
        prepared, _stored, _selection, exact = _a92c_case()

        source_not_ready = current_a7_report("not_collected")

        source_drift = copy.deepcopy(exact)
        source_drift["source"]["reconciliationStatus"] = "На проверке"
        _a92c_replace_raw_reviews(
            source_drift, "warehouse_invoice_items_limit_exceeded", 901,
        )

        snapshot_blocked = copy.deepcopy(exact)
        _a92c_replace_raw_reviews(
            snapshot_blocked,
            "warehouse_invoice_items_limit_exceeded",
            902,
        )
        other_snapshot_blocked = copy.deepcopy(exact)
        other_projection = other_snapshot_blocked["supplyWarehouseImpact"]
        other_projection.update({
            "state": "review_required",
            "complete": False,
            "reasonCounts": {"warehouse_invoice_owner_mismatch": 1},
            "needsReview": [{
                "sourceKind": "warehouseInvoice",
                "sourceId": None,
                "reasonCode": "warehouse_invoice_owner_mismatch",
            }],
            "needsReviewTruncated": False,
        })
        other_projection["summary"]["needsReview"] = 1
        other_snapshot_blocked[
            "readyForSupplyWarehouseProjection"
        ] = False

        clear = copy.deepcopy(exact)
        clear_projection = clear["supplyWarehouseImpact"]
        clear_projection.update({
            "state": "complete",
            "complete": True,
            "reasonCounts": {},
            "needsReview": [],
            "needsReviewTruncated": False,
        })
        clear_projection["summary"]["needsReview"] = 0
        clear["readyForSupplyWarehouseProjection"] = True

        changed_candidate = copy.deepcopy(exact)
        _a92c_replace_raw_reviews(
            changed_candidate,
            "warehouse_invoice_request_mismatch",
            prepared.candidate["subjectId"],
        )

        relevant_drift = copy.deepcopy(exact)
        relevant_drift["supplyWarehouseImpact"]["openSupply"][0][
            "requestId"
        ] += 1000
        other_relevant_drift = copy.deepcopy(exact)
        other_relevant_drift["supplyWarehouseImpact"][
            "protectedEvidence"
        ]["deliveryIds"] = [72]
        self.assertNotEqual(
            _a92c_relevant_sha256(relevant_drift),
            prepared.relevant_evidence_sha256,
        )
        self.assertNotEqual(
            _a92c_relevant_sha256(other_relevant_drift),
            prepared.relevant_evidence_sha256,
        )

        cases = (
            (
                "source_not_ready",
                source_not_ready,
                "blocked",
                "warehouse_anomaly_current_source_not_ready",
            ),
            (
                "source_drift_before_blocked",
                source_drift,
                "stale",
                "warehouse_anomaly_source_drift",
            ),
            (
                "snapshot_blocked_before_candidate_and_hash",
                snapshot_blocked,
                "blocked",
                "warehouse_anomaly_current_snapshot_blocked",
            ),
            (
                "other_snapshot_blocked",
                other_snapshot_blocked,
                "blocked",
                "warehouse_anomaly_current_snapshot_blocked",
            ),
            (
                "clear_before_hash",
                clear,
                "stale",
                "warehouse_anomaly_candidate_stale",
            ),
            (
                "changed_candidate_before_hash",
                changed_candidate,
                "stale",
                "warehouse_anomaly_candidate_stale",
            ),
            (
                "relevant_drift_after_exact_candidate",
                relevant_drift,
                "stale",
                "warehouse_anomaly_relevant_evidence_drift",
            ),
            (
                "other_relevant_drift",
                other_relevant_drift,
                "stale",
                "warehouse_anomaly_relevant_evidence_drift",
            ),
        )
        outcomes = {}
        for name, current, state, blocker in cases:
            with self.subTest(name=name):
                before = copy.deepcopy(current)
                result = _finalize_warehouse_anomaly_content(
                    prepared, current,
                )
                self.assert_non_ready(result, prepared, state, blocker)
                self.assertEqual(current, before)
                outcomes[name] = result
        self.assertEqual(outcomes["clear_before_hash"], outcomes[
            "changed_candidate_before_hash"
        ])
        self.assertEqual(
            outcomes["snapshot_blocked_before_candidate_and_hash"],
            outcomes["other_snapshot_blocked"],
        )
        self.assertEqual(
            outcomes["relevant_drift_after_exact_candidate"],
            outcomes["other_relevant_drift"],
        )

    def test_each_reconciliation_field_drift_uses_stored_source_only(self):
        prepared, _stored, _selection, exact = _a92c_case()
        cases = {
            "reconciliationId": 92,
            "baseEstimateId": 53,
            "reconciliationStatus": "На проверке",
        }
        outcomes = []
        for field, value in cases.items():
            with self.subTest(field=field):
                current = copy.deepcopy(exact)
                current["source"][field] = value
                if field == "baseEstimateId":
                    for item in current["supplyWarehouseImpact"][
                        "openSupply"
                    ]:
                        item["sourceEstimateId"] = value

                result = _finalize_warehouse_anomaly_content(
                    prepared, current,
                )

                self.assert_non_ready(
                    result,
                    prepared,
                    "stale",
                    "warehouse_anomaly_source_drift",
                )
                self.assertEqual(
                    result["source"][field], prepared.stored_source[field],
                )
                outcomes.append(result)
        self.assertEqual(outcomes, [outcomes[0]] * len(outcomes))

    def test_precedence_short_circuits_later_business_dependencies(self):
        prepared, _stored, _selection, exact = _a92c_case()
        source_not_ready = current_a7_report("not_collected")
        source_drift = copy.deepcopy(exact)
        source_drift["source"]["reconciliationStatus"] = "На проверке"

        for name, current, state, blocker in (
            (
                "source_not_ready",
                source_not_ready,
                "blocked",
                "warehouse_anomaly_current_source_not_ready",
            ),
            (
                "source_drift",
                source_drift,
                "stale",
                "warehouse_anomaly_source_drift",
            ),
        ):
            with self.subTest(name=name), mock.patch.object(
                content_contract,
                "build_combined_report",
                side_effect=AssertionError("combined builder must not run"),
            ), mock.patch.object(
                content_contract,
                "build_warehouse_anomaly_readiness",
                side_effect=AssertionError("readiness must not run"),
            ), mock.patch.object(
                content_contract,
                "_canonical_sha256",
                side_effect=AssertionError("hash must not run"),
            ):
                result = _finalize_warehouse_anomaly_content(
                    prepared, current,
                )
                self.assert_non_ready(result, prepared, state, blocker)

        blocked = copy.deepcopy(exact)
        _a92c_replace_raw_reviews(
            blocked, "warehouse_invoice_items_limit_exceeded", 903,
        )
        clear = copy.deepcopy(exact)
        projection = clear["supplyWarehouseImpact"]
        projection.update({
            "state": "complete",
            "complete": True,
            "reasonCounts": {},
            "needsReview": [],
            "needsReviewTruncated": False,
        })
        projection["summary"]["needsReview"] = 0
        clear["readyForSupplyWarehouseProjection"] = True
        for name, current, state, blocker in (
            (
                "readiness_blocked",
                blocked,
                "blocked",
                "warehouse_anomaly_current_snapshot_blocked",
            ),
            (
                "candidate_stale",
                clear,
                "stale",
                "warehouse_anomaly_candidate_stale",
            ),
        ):
            with self.subTest(name=name), mock.patch.object(
                content_contract,
                "_canonical_sha256",
                side_effect=AssertionError("relevant hash must not run"),
            ):
                result = _finalize_warehouse_anomaly_content(
                    prepared, current,
                )
                self.assert_non_ready(result, prepared, state, blocker)

    def test_source_ready_builder_receives_only_detached_current_evidence(self):
        prepared, _stored, _selection, current = _a92c_case()
        before = copy.deepcopy(current)
        with mock.patch.object(
            content_contract,
            "build_combined_report",
            wraps=build_combined_report,
        ) as builder, mock.patch.object(
            content_contract,
            "build_warehouse_anomaly_readiness",
            wraps=content_contract.build_warehouse_anomaly_readiness,
        ) as readiness:
            result = _finalize_warehouse_anomaly_content(prepared, current)

        self.assertEqual(result["state"], "preview_ready")
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(readiness.call_count, 1)
        call = builder.call_args
        arguments = list(call.args)
        keywords = dict(call.kwargs)
        source_arg = arguments.pop(0) if arguments else keywords.pop("source")
        self.assertEqual(arguments, [])
        self.assertEqual(source_arg, before["source"])
        self.assertIsNot(source_arg, current["source"])
        self.assertEqual(set(keywords), {
            "assignment", "material", "supply_warehouse", "economics",
        })
        self.assertIsNone(keywords["assignment"])
        self.assertIsNone(keywords["material"])
        self.assertIsNone(keywords["economics"])
        self.assertEqual(
            keywords["supply_warehouse"],
            before["supplyWarehouseImpact"],
        )
        self.assertIsNot(
            keywords["supply_warehouse"],
            current["supplyWarehouseImpact"],
        )
        self.assertEqual(current, before)

    def test_each_relevant_domain_change_with_same_candidate_is_stale(self):
        prepared, _stored, _selection, exact = _a92c_case()
        mutations = {}

        changed_open = copy.deepcopy(exact)
        changed_open["supplyWarehouseImpact"]["openSupply"][0][
            "requestId"
        ] += 1
        mutations["supply_open_fact"] = changed_open

        changed_supply_evidence = copy.deepcopy(exact)
        changed_supply_evidence["supplyWarehouseImpact"][
            "protectedEvidence"
        ]["deliveryIds"] = [72]
        mutations["supply_protected_evidence"] = changed_supply_evidence

        changed_warehouse_evidence = copy.deepcopy(exact)
        changed_warehouse_projection = changed_warehouse_evidence[
            "supplyWarehouseImpact"
        ]
        changed_warehouse_projection["summary"]["warehouseInvoices"] = 1
        changed_warehouse_projection["protectedEvidence"][
            "warehouseInvoiceIds"
        ] = [501]
        mutations["warehouse_protected_evidence"] = (
            changed_warehouse_evidence
        )

        added_candidate = copy.deepcopy(exact)
        added_projection = added_candidate["supplyWarehouseImpact"]
        added_projection["needsReview"].append({
            "sourceKind": "warehouseInvoice",
            "sourceId": 777,
            "reasonCode": "warehouse_invoice_request_mismatch",
        })
        added_projection["reasonCounts"] = {
            prepared.candidate["anomalyCode"]: 1,
            "warehouse_invoice_request_mismatch": 1,
        }
        added_projection["summary"]["needsReview"] = 2
        mutations["additional_candidate"] = added_candidate

        outcomes = []
        for name, current in mutations.items():
            with self.subTest(name=name):
                before = copy.deepcopy(current)
                self.assertNotEqual(
                    _a92c_relevant_sha256(current),
                    prepared.relevant_evidence_sha256,
                )
                result = _finalize_warehouse_anomaly_content(
                    prepared, current,
                )
                self.assert_non_ready(
                    result,
                    prepared,
                    "stale",
                    "warehouse_anomaly_relevant_evidence_drift",
                )
                self.assertEqual(current, before)
                outcomes.append(result)
        self.assertEqual(outcomes, [outcomes[0]] * len(outcomes))

    def test_dependency_contract_failures_are_fixed_and_control_flow_survives(self):
        prepared, _stored, _selection, current = _a92c_case()
        current_combined = build_combined_report(
            current["source"],
            assignment=None,
            material=None,
            supply_warehouse=current["supplyWarehouseImpact"],
            economics=None,
        )
        current_combined.update({
            "readOnlyTransaction": True,
            "rolledBack": True,
        })
        valid_readiness = content_contract.build_warehouse_anomaly_readiness(
            current_combined
        )

        readiness_cases = {}
        extra = copy.deepcopy(valid_readiness)
        extra["must_not_leak"] = "private dependency text"
        readiness_cases["extra"] = extra
        missing = copy.deepcopy(valid_readiness)
        missing.pop("blockers")
        readiness_cases["missing"] = missing
        source_hash_drift = copy.deepcopy(valid_readiness)
        source_hash_drift["source"]["impactEvidenceSha256"] = "0" * 64
        readiness_cases["source_hash_drift"] = source_hash_drift
        duplicate = copy.deepcopy(valid_readiness)
        duplicate["candidates"].append(copy.deepcopy(
            duplicate["candidates"][0]
        ))
        duplicate["candidateCount"] = len(duplicate["candidates"])
        readiness_cases["duplicate_candidate"] = duplicate
        oversized = copy.deepcopy(valid_readiness)
        oversized["candidates"] = []
        for subject_id in range(1, 102):
            candidate = copy.deepcopy(valid_readiness["candidates"][0])
            candidate["subjectId"] = subject_id
            oversized["candidates"].append(candidate)
        oversized["candidateCount"] = len(oversized["candidates"])
        readiness_cases["oversized_candidates"] = oversized
        unknown_blocker = copy.deepcopy(valid_readiness)
        unknown_blocker.update({
            "state": "blocked",
            "classificationComplete": False,
            "readyForRecommendationPreview": False,
            "candidateCount": 0,
            "candidates": [],
            "blockers": ["impossible_private_dependency_blocker"],
        })
        readiness_cases["unknown_blocker"] = unknown_blocker

        with mock.patch.object(
            content_contract, "build_combined_report", return_value=[]
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )
        with mock.patch.object(
            content_contract,
            "build_combined_report",
            side_effect=RuntimeError("must_not_leak builder"),
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )
        with mock.patch.object(
            content_contract,
            "build_combined_report",
            side_effect=WarehouseAnomalyContentError("must_not_leak"),
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )
        for name, dependency_result in readiness_cases.items():
            with self.subTest(name=name), mock.patch.object(
                content_contract,
                "build_warehouse_anomaly_readiness",
                return_value=dependency_result,
            ):
                self.assert_content_error(
                    "warehouse_anomaly_content_contract_invalid",
                    prepared,
                    current,
                )
        with mock.patch.object(
            content_contract,
            "build_warehouse_anomaly_readiness",
            side_effect=RuntimeError("must_not_leak readiness"),
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )
        with mock.patch.object(
            content_contract,
            "build_warehouse_anomaly_readiness",
            side_effect=WarehouseAnomalyContentError("must_not_leak"),
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )
        with mock.patch.object(
            content_contract,
            "_canonical_sha256",
            side_effect=ValueError("must_not_leak canonicalization"),
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )

        for exception in (
            MemoryError("must_not_leak memory"),
            KeyboardInterrupt("must_not_leak keyboard"),
            SystemExit("must_not_leak exit"),
            GeneratorExit("must_not_leak generator"),
        ):
            with self.subTest(exception=type(exception).__name__), (
                mock.patch.object(
                    content_contract,
                    "build_combined_report",
                    side_effect=exception,
                )
            ):
                with self.assertRaises(type(exception)) as raised:
                    _finalize_warehouse_anomaly_content(prepared, current)
                self.assertIs(raised.exception, exception)

    def test_rejects_bool_as_int_in_current_readiness_source(self):
        _prepared, _stored, selection, current = _a92c_case()
        current["source"]["reconciliationId"] = 1
        stored = build_combined_report(
            current["source"],
            assignment=None,
            material=None,
            supply_warehouse=current["supplyWarehouseImpact"],
            economics=None,
        )
        stored.update({"readOnlyTransaction": True, "rolledBack": True})
        prepared = _prepare_warehouse_anomaly_content(stored, selection)
        current_combined = build_combined_report(
            current["source"],
            assignment=None,
            material=None,
            supply_warehouse=current["supplyWarehouseImpact"],
            economics=None,
        )
        current_combined.update({
            "readOnlyTransaction": True,
            "rolledBack": True,
        })
        forged = content_contract.build_warehouse_anomaly_readiness(
            current_combined
        )
        forged["source"]["reconciliationId"] = True

        with mock.patch.object(
            content_contract,
            "build_warehouse_anomaly_readiness",
            return_value=forged,
        ):
            self.assert_content_error(
                "warehouse_anomaly_content_contract_invalid",
                prepared,
                current,
            )

    def test_result_is_deterministic_detached_and_inputs_are_immutable(self):
        prepared, stored, selection, current = _a92c_case()
        stored_before = copy.deepcopy(stored)
        selection_before = copy.deepcopy(selection)
        current_before = copy.deepcopy(current)

        result = _finalize_warehouse_anomaly_content(prepared, current)
        expected = copy.deepcopy(result)
        current["source"]["reconciliationStatus"] = "Отклонена"
        current["supplyWarehouseImpact"]["needsReview"][0][
            "sourceId"
        ] = 999999
        self.assertEqual(result, expected)

        result["content"]["title"] = "must_not_leak"
        repeated = _finalize_warehouse_anomaly_content(
            prepared, current_before,
        )
        self.assertEqual(repeated, expected)
        self.assertEqual(stored, stored_before)
        self.assertEqual(selection, selection_before)

    def test_invalid_current_or_forged_plan_has_no_partial_result(self):
        prepared, _stored, _selection, current = _a92c_case()
        invalid = copy.deepcopy(current)
        invalid["must_not_leak"] = "private current report"
        self.assert_content_error(
            "warehouse_anomaly_content_current_report_invalid",
            prepared,
            invalid,
        )

        self.assert_content_error(
            "warehouse_anomaly_content_contract_invalid",
            {},
            current,
        )

        class HostileStoredSource(Mapping):
            def __len__(self):
                return len(SOURCE_FIELDS)

            def __iter__(self):
                raise WarehouseAnomalyContentError("must_not_leak")

            def __getitem__(self, key):
                raise WarehouseAnomalyContentError("must_not_leak")

        forged = replace(
            prepared,
            stored_source=MappingProxyType(HostileStoredSource()),
        )
        self.assert_content_error(
            "warehouse_anomaly_content_contract_invalid",
            forged,
            current,
        )


if __name__ == "__main__":
    unittest.main()
