import ast
import inspect
import json
import unittest
from pathlib import Path

import backend.features.estimate_revision_impact as estimate_revision_impact
import backend.features.estimate_revision_impact.baseline as baseline
import backend.features.estimate_revision_impact.resource_limits as resource_limits
import backend.features.estimate_revision_impact.test_baseline as baseline_fixtures
from backend.features.estimate_revision_impact.contract import (
    MAX_CANONICAL_SOURCE_BYTES,
)
from backend.features.estimate_revision_impact.resource_limits import (
    MAX_COLLECTOR_VARIABLE_BYTES,
    MAX_JSON_QUERY_BYTES,
    MAX_NUMERIC_FIELD_BYTES,
    MAX_TEXT_FIELD_BYTES,
    MAX_TEXT_QUERY_AGGREGATE_BYTES,
    _VariableByteBudget,
    _VariableByteLimitError,
)


class _IntSubclass(int):
    pass


_TARGET_TEXT_FIELDS = (
    "version",
    "status",
    "smeta_type",
    "work_package",
)
_RECONCILIATION_TEXT_FIELDS = (
    "reconciliation_status",
    "reconciliation_smeta_type",
    "reconciliation_work_package",
    "base_smeta_type",
    "base_work_package",
    "next_status",
    "next_smeta_type",
    "next_work_package",
)


def _utf8_bytes(value):
    return len(value.encode("utf-8")) if isinstance(value, str) else 0


def _target_row(**overrides):
    row = baseline_fixtures.estimate_row(**overrides)
    json_bytes = _utf8_bytes(row.get("sections_json"))
    text_sizes = {
        field: _utf8_bytes(row.get(field))
        for field in _TARGET_TEXT_FIELDS
    }
    text_bytes = sum(text_sizes.values())
    row.update({
        "sections_bytes": json_bytes,
        "field_sections_json_bytes": json_bytes,
        "query_json_bytes": json_bytes,
        "query_text_bytes": text_bytes,
        "query_variable_bytes": json_bytes + text_bytes,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    })
    row.update({
        "field_" + field + "_bytes": size
        for field, size in text_sizes.items()
    })
    return row


def _reconciliation_row(**overrides):
    row = baseline_fixtures.reconciliation_row(**overrides)
    text_sizes = {
        field: _utf8_bytes(row.get(field))
        for field in _RECONCILIATION_TEXT_FIELDS
    }
    text_bytes = sum(text_sizes.values())
    row.update({
        "query_json_bytes": 0,
        "query_text_bytes": text_bytes,
        "query_variable_bytes": text_bytes,
        "cardinality_limit_exceeded": False,
        "payload_limit_exceeded": False,
    })
    row.update({
        "field_" + field + "_bytes": size
        for field, size in text_sizes.items()
    })
    return row


def _target_overflow(field):
    row = _target_row()
    for name in _TARGET_TEXT_FIELDS + ("sections_json",):
        row[name] = None
    size = (
        MAX_CANONICAL_SOURCE_BYTES + 1
        if field == "sections_json"
        else MAX_TEXT_FIELD_BYTES + 1
    )
    row["field_" + field + "_bytes"] = size
    row["sections_bytes"] = row["field_sections_json_bytes"]
    row["query_json_bytes"] = row["field_sections_json_bytes"]
    row["query_text_bytes"] = sum(
        row["field_" + name + "_bytes"]
        for name in _TARGET_TEXT_FIELDS
    )
    row["query_variable_bytes"] = (
        row["query_json_bytes"] + row["query_text_bytes"]
    )
    row["payload_limit_exceeded"] = True
    return row


def _reconciliation_overflow(field):
    row = _reconciliation_row()
    for name in _RECONCILIATION_TEXT_FIELDS:
        row[name] = None
    size = MAX_TEXT_FIELD_BYTES + 1
    row["field_" + field + "_bytes"] = size
    row["query_text_bytes"] = sum(
        row["field_" + name + "_bytes"]
        for name in _RECONCILIATION_TEXT_FIELDS
    )
    row["query_variable_bytes"] = (
        row["query_json_bytes"] + row["query_text_bytes"]
    )
    row["payload_limit_exceeded"] = True
    return row


def _reconciliation_cardinality_row(reconciliation_id):
    row = _reconciliation_row(reconciliation_id=reconciliation_id)
    for name in _RECONCILIATION_TEXT_FIELDS:
        row[name] = None
    row["cardinality_limit_exceeded"] = True
    return row


def _ready_result_sets():
    return (
        baseline_fixtures.REQUIRED_SCHEMA_ROWS,
        (_target_row(),),
        (_reconciliation_row(),),
    )


def _assert_query_wide_case(test, sql, aliases):
    normalized = " ".join(sql.upper().split())
    test.assertTrue(normalized.startswith("SELECT "))
    test.assertIn("WITH LIMITED AS MATERIALIZED", normalized)
    test.assertIn("SIZED AS MATERIALIZED", normalized)
    test.assertIn("GATED AS MATERIALIZED", normalized)
    test.assertIn("OCTET_LENGTH(CONVERT_TO(", normalized)
    test.assertIn("'UTF8'", normalized)
    test.assertTrue("MAX(" in normalized or "BOOL_AND(" in normalized)
    test.assertIn("PAYLOAD_ALLOWED", normalized)
    test.assertIn("CARDINALITY_LIMIT_EXCEEDED", normalized)
    test.assertIn("PAYLOAD_LIMIT_EXCEEDED", normalized)
    test.assertIn("QUERY_JSON_BYTES", normalized)
    test.assertIn("QUERY_TEXT_BYTES", normalized)
    test.assertIn("QUERY_VARIABLE_BYTES", normalized)
    for alias in aliases:
        exact_gate = (
            "CASE WHEN DECIDED.PAYLOAD_ALLOWED THEN DECIDED.EMITTED_"
            + alias.upper()
            + " ELSE NULL END AS "
            + alias.upper()
        )
        test.assertEqual(
            normalized.count(exact_gate),
            1,
            alias + " must use its own exact query-wide CASE",
        )


class VariableByteBudgetTests(unittest.TestCase):
    def test_limits_are_exact(self):
        self.assertEqual(MAX_JSON_QUERY_BYTES, 4_194_304)
        self.assertEqual(MAX_TEXT_FIELD_BYTES, 1_024)
        self.assertEqual(MAX_TEXT_QUERY_AGGREGATE_BYTES, 1_048_576)
        self.assertEqual(MAX_NUMERIC_FIELD_BYTES, 64)
        self.assertEqual(MAX_COLLECTOR_VARIABLE_BYTES, 17_825_792)

    def test_consumes_exact_17_mib_and_rejects_plus_one_atomically(self):
        budget = _VariableByteBudget()

        self.assertEqual(budget.remaining_bytes, MAX_COLLECTOR_VARIABLE_BYTES)
        self.assertIsNone(budget.consume(MAX_COLLECTOR_VARIABLE_BYTES))
        self.assertEqual(budget.remaining_bytes, 0)

        with self.assertRaisesRegex(
            _VariableByteLimitError,
            r"^variable byte limit exceeded$",
        ):
            budget.consume(1)

        self.assertEqual(budget.remaining_bytes, 0)

    def test_zero_and_incremental_consumption_are_deterministic(self):
        budget = _VariableByteBudget()

        self.assertIsNone(budget.consume(0))
        self.assertEqual(
            budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES,
        )
        self.assertIsNone(budget.consume(2))
        self.assertEqual(
            budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES - 2,
        )
        self.assertIsNone(budget.consume(MAX_COLLECTOR_VARIABLE_BYTES - 2))
        self.assertEqual(budget.remaining_bytes, 0)

    def test_budget_constructor_cannot_override_the_approved_ceiling(self):
        self.assertEqual(str(inspect.signature(_VariableByteBudget)), "()")
        with self.assertRaises(TypeError):
            _VariableByteBudget(MAX_COLLECTOR_VARIABLE_BYTES)
        with self.assertRaises(TypeError):
            _VariableByteBudget(limit_bytes=MAX_COLLECTOR_VARIABLE_BYTES)

    def test_text_aggregate_limit_is_inclusive_in_the_pure_gate(self):
        field_specs = []
        exact = {
            "query_json_bytes": 0,
            "query_text_bytes": MAX_TEXT_QUERY_AGGREGATE_BYTES,
            "query_variable_bytes": MAX_TEXT_QUERY_AGGREGATE_BYTES,
            "cardinality_limit_exceeded": False,
            "payload_limit_exceeded": False,
        }
        block = "a" * MAX_TEXT_FIELD_BYTES
        for index in range(
            MAX_TEXT_QUERY_AGGREGATE_BYTES // MAX_TEXT_FIELD_BYTES
        ):
            value_key = "value_" + str(index)
            byte_key = "field_value_" + str(index) + "_bytes"
            exact[value_key] = block
            exact[byte_key] = MAX_TEXT_FIELD_BYTES
            field_specs.append((
                value_key,
                byte_key,
                "text",
                MAX_TEXT_FIELD_BYTES,
                False,
            ))
        exact_budget = _VariableByteBudget()

        state, _rows, _overflow = resource_limits._accept_bounded_rows(
            [exact],
            exact_budget,
            scan_limit=1,
            field_specs=tuple(field_specs),
        )

        self.assertEqual(state, resource_limits._BOUNDED_ACCEPTED)
        self.assertEqual(
            exact_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES - MAX_TEXT_QUERY_AGGREGATE_BYTES,
        )

        overflow = dict(exact)
        overflow_key = "value_overflow"
        overflow_byte_key = "field_value_overflow_bytes"
        overflow[overflow_key] = None
        overflow[overflow_byte_key] = 1
        for value_key, _byte_key, *_rest in field_specs:
            overflow[value_key] = None
        overflow["query_text_bytes"] += 1
        overflow["query_variable_bytes"] += 1
        overflow["payload_limit_exceeded"] = True
        overflow_specs = tuple(field_specs) + ((
            overflow_key,
            overflow_byte_key,
            "text",
            MAX_TEXT_FIELD_BYTES,
            False,
        ),)
        overflow_budget = _VariableByteBudget()

        state, _rows, _overflow = resource_limits._accept_bounded_rows(
            [overflow],
            overflow_budget,
            scan_limit=1,
            field_specs=overflow_specs,
        )

        self.assertEqual(state, resource_limits._BOUNDED_OVERFLOW)
        self.assertEqual(
            overflow_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES,
        )

    def test_invalid_counts_do_not_mutate_state_or_leak_values(self):
        budget = _VariableByteBudget()
        invalid_values = (
            True,
            False,
            -1,
            1.0,
            "must-not-leak",
            None,
            _IntSubclass(1),
        )

        for value in invalid_values:
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(_VariableByteLimitError) as caught:
                    budget.consume(value)
                self.assertEqual(
                    caught.exception.args,
                    ("variable byte count is invalid",),
                )
                self.assertNotIn("must-not-leak", str(caught.exception))
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES,
                )

    def test_module_is_private_and_has_no_runtime_dependencies(self):
        module_path = Path(__file__).with_name("resource_limits.py")
        tree = ast.parse(module_path.read_text(encoding="utf-8"))

        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }

        self.assertEqual(imports, [])
        self.assertFalse(
            calls.intersection({"open", "print", "exec", "eval", "compile"})
        )
        self.assertEqual(resource_limits.__all__, [])
        for name in (
            "MAX_JSON_QUERY_BYTES",
            "MAX_TEXT_FIELD_BYTES",
            "MAX_TEXT_QUERY_AGGREGATE_BYTES",
            "MAX_NUMERIC_FIELD_BYTES",
            "MAX_COLLECTOR_VARIABLE_BYTES",
            "_VariableByteBudget",
            "_VariableByteLimitError",
        ):
            self.assertFalse(hasattr(estimate_revision_impact, name))


class BaselineVariablePayloadGateTests(unittest.TestCase):
    maxDiff = None

    def test_public_surface_and_success_report_stay_exact_and_strip_metadata(self):
        self.assertEqual(
            str(inspect.signature(baseline.collect_baseline_audit)),
            "(cur, source, *, max_reconciliation_rows=100, max_issues=100)",
        )
        self.assertEqual(baseline.__all__, [
            "DEFAULT_MAX_ISSUES",
            "MAX_RECONCILIATION_ROWS",
            "REQUIRED_COLUMNS",
            "collect_baseline_audit",
            "run_baseline_audit",
        ])
        cursor = baseline_fixtures.FakeCursor(_ready_result_sets())

        report = baseline.collect_baseline_audit(
            cursor,
            baseline_fixtures.source(),
        )

        self.assertTrue(report["readyForDomainScan"])
        serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "field_version_bytes",
            "field_sections_json_bytes",
            "query_json_bytes",
            "query_text_bytes",
            "query_variable_bytes",
            "cardinality_limit_exceeded",
            "payload_limit_exceeded",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_target_and_reconciliation_sql_use_one_ordered_query_wide_gate(self):
        cursor = baseline_fixtures.FakeCursor(_ready_result_sets())

        report = baseline.collect_baseline_audit(
            cursor,
            baseline_fixtures.source(),
        )

        self.assertTrue(report["readyForDomainScan"])
        self.assertEqual(len(cursor.calls), 3)
        target_sql, target_params = cursor.calls[1]
        reconciliation_sql, reconciliation_params = cursor.calls[2]
        _assert_query_wide_case(
            self,
            target_sql,
            _TARGET_TEXT_FIELDS + ("sections_json",),
        )
        _assert_query_wide_case(
            self,
            reconciliation_sql,
            _RECONCILIATION_TEXT_FIELDS,
        )
        target_upper = target_sql.upper()
        reconciliation_upper = reconciliation_sql.upper()
        self.assertEqual(target_upper.count("PUBLIC.ESTIMATES"), 1)
        self.assertEqual(
            reconciliation_upper.count("PUBLIC.ESTIMATE_RECONCILIATIONS"),
            1,
        )
        self.assertEqual(reconciliation_upper.count("PUBLIC.ESTIMATES"), 2)
        self.assertRegex(target_upper, r"ORDER BY [A-Z0-9_.]*ID LIMIT %S")
        self.assertRegex(
            reconciliation_upper,
            r"ORDER BY [A-Z0-9_.]*ID DESC LIMIT %S",
        )
        self.assertLess(
            target_upper.index("LIMIT %S"),
            target_upper.index("COUNT(*) OVER ()"),
        )
        self.assertLess(
            reconciliation_upper.index("LIMIT %S"),
            reconciliation_upper.index("COUNT(*) OVER ()"),
        )
        for expression in (
            "COALESCE(E.STATUS,'\u0427\u0415\u0420\u041d\u041e\u0412\u0418\u041a') AS EMITTED_STATUS",
            "COALESCE(E.SMETA_TYPE,'\u0417\u0410\u041a\u0410\u0417\u0427\u0418\u041a') AS EMITTED_SMETA_TYPE",
            "COALESCE(E.IS_TEMPLATE,FALSE) AS IS_TEMPLATE",
        ):
            self.assertIn(expression, target_upper)
        for expression in (
            "COALESCE(R.SMETA_TYPE,'\u0417\u0410\u041a\u0410\u0417\u0427\u0418\u041a') AS "
            "EMITTED_RECONCILIATION_SMETA_TYPE",
            "COALESCE(B.SMETA_TYPE,'\u0417\u0410\u041a\u0410\u0417\u0427\u0418\u041a') AS "
            "EMITTED_BASE_SMETA_TYPE",
            "COALESCE(N.STATUS,'\u0427\u0415\u0420\u041d\u041e\u0412\u0418\u041a') AS EMITTED_NEXT_STATUS",
            "COALESCE(N.SMETA_TYPE,'\u0417\u0410\u041a\u0410\u0417\u0427\u0418\u041a') AS "
            "EMITTED_NEXT_SMETA_TYPE",
            "COALESCE(N.IS_TEMPLATE,FALSE) AS NEXT_IS_TEMPLATE",
        ):
            self.assertIn(expression, reconciliation_upper)
        self.assertIn(MAX_TEXT_FIELD_BYTES, target_params)
        self.assertIn(MAX_TEXT_QUERY_AGGREGATE_BYTES, target_params)
        self.assertIn(MAX_CANONICAL_SOURCE_BYTES, target_params)
        self.assertIn(MAX_COLLECTOR_VARIABLE_BYTES, target_params)
        self.assertIn(MAX_TEXT_FIELD_BYTES, reconciliation_params)
        self.assertIn(MAX_TEXT_QUERY_AGGREGATE_BYTES, reconciliation_params)
        self.assertIn(
            MAX_COLLECTOR_VARIABLE_BYTES
            - _target_row()["query_variable_bytes"],
            reconciliation_params,
        )

    def test_private_core_consumes_exact_metadata_from_one_shared_budget(self):
        cursor = baseline_fixtures.FakeCursor(_ready_result_sets())
        budget = _VariableByteBudget()
        private_core = getattr(baseline, "_collect_baseline_audit")

        report = private_core(
            cursor,
            baseline_fixtures.source(),
            budget,
        )

        expected_consumed = (
            _target_row()["query_variable_bytes"]
            + _reconciliation_row()["query_variable_bytes"]
        )
        self.assertTrue(report["readyForDomainScan"])
        self.assertEqual(
            budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES - expected_consumed,
        )

    def test_target_rejects_invalid_utf8_metadata_before_reconciliation(self):
        invalid_rows = []
        field_mismatch = _target_row()
        field_mismatch["field_status_bytes"] += 1
        invalid_rows.append(field_mismatch)
        aggregate_mismatch = _target_row()
        aggregate_mismatch["query_text_bytes"] += 1
        invalid_rows.append(aggregate_mismatch)
        alias_mismatch = _target_row()
        alias_mismatch["sections_bytes"] += 1
        invalid_rows.append(alias_mismatch)
        invalid_type = _target_row()
        invalid_type["query_variable_bytes"] = True
        invalid_rows.append(invalid_type)

        for row in invalid_rows:
            with self.subTest(row=row):
                cursor = baseline_fixtures.FakeCursor((
                    baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                    (row,),
                ))

                report = baseline.collect_baseline_audit(
                    cursor,
                    baseline_fixtures.source(),
                )

                self.assertEqual(report["reasonCounts"], {
                    "impact_estimate_snapshot_invalid": 1,
                })
                self.assertEqual(len(cursor.calls), 2)

    def test_target_cardinality_nulls_payload_and_does_not_debit_budget(self):
        rows = [_target_row(), _target_row()]
        query_json_bytes = sum(row["field_sections_json_bytes"] for row in rows)
        query_text_bytes = sum(
            row["field_" + field + "_bytes"]
            for row in rows
            for field in _TARGET_TEXT_FIELDS
        )
        for row in rows:
            for field in _TARGET_TEXT_FIELDS + ("sections_json",):
                row[field] = None
            row.update({
                "query_json_bytes": query_json_bytes,
                "query_text_bytes": query_text_bytes,
                "query_variable_bytes": query_json_bytes + query_text_bytes,
                "cardinality_limit_exceeded": True,
                "payload_limit_exceeded": False,
            })
        budget = _VariableByteBudget()
        cursor = baseline_fixtures.FakeCursor((
            baseline_fixtures.REQUIRED_SCHEMA_ROWS,
            tuple(rows),
        ))

        report = baseline._collect_baseline_audit(
            cursor,
            baseline_fixtures.source(),
            budget,
        )

        self.assertEqual(report["reasonCounts"], {
            "impact_source_ambiguous": 1,
        })
        self.assertEqual(report["summary"]["estimateRows"], 2)
        self.assertEqual(budget.remaining_bytes, MAX_COLLECTOR_VARIABLE_BYTES)
        self.assertEqual(len(cursor.calls), 2)

    def test_target_rejects_false_flags_and_raw_payload_leaks(self):
        false_flag = _target_overflow("status")
        false_flag["payload_limit_exceeded"] = False
        leaked_raw = _target_overflow("status")
        leaked_raw["version"] = "must-not-leak"

        for kind, row in (("flag", false_flag), ("raw", leaked_raw)):
            with self.subTest(kind=kind):
                cursor = baseline_fixtures.FakeCursor((
                    baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                    (row,),
                ))

                report = baseline.collect_baseline_audit(
                    cursor,
                    baseline_fixtures.source(),
                )

                self.assertEqual(report["reasonCounts"], {
                    "impact_estimate_snapshot_invalid": 1,
                })
                self.assertNotIn(
                    "must-not-leak",
                    json.dumps(report, ensure_ascii=False),
                )
                self.assertEqual(len(cursor.calls), 2)

    def test_each_target_field_overflow_uses_existing_snapshot_reason(self):
        for field in _TARGET_TEXT_FIELDS + ("sections_json",):
            with self.subTest(field=field):
                budget = _VariableByteBudget()
                cursor = baseline_fixtures.FakeCursor((
                    baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                    (_target_overflow(field),),
                ))

                report = baseline._collect_baseline_audit(
                    cursor,
                    baseline_fixtures.source(),
                    budget,
                )

                self.assertEqual(report["reasonCounts"], {
                    "impact_estimate_snapshot_too_large": 1,
                })
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES,
                )
                self.assertEqual(len(cursor.calls), 2)

    def test_each_target_field_accepts_its_inclusive_utf8_boundary(self):
        exact_text = "\u044f" * (MAX_TEXT_FIELD_BYTES // 2)
        exact_json = '"' + (
            "a" * (MAX_CANONICAL_SOURCE_BYTES - 2)
        ) + '"'
        cases = {
            "version": (exact_text, "impact_estimate_snapshot_invalid"),
            "sections_json": (
                exact_json,
                "impact_estimate_snapshot_invalid",
            ),
            "status": (exact_text, "impact_estimate_not_active"),
            "smeta_type": (exact_text, "impact_estimate_not_customer"),
            "work_package": (
                exact_text,
                "impact_estimate_package_invalid",
            ),
        }
        for field, (value, reason) in cases.items():
            with self.subTest(field=field):
                row = _target_row(**{field: value})
                cap = (
                    MAX_CANONICAL_SOURCE_BYTES
                    if field == "sections_json"
                    else MAX_TEXT_FIELD_BYTES
                )
                self.assertEqual(row["field_" + field + "_bytes"], cap)
                budget = _VariableByteBudget()
                cursor = baseline_fixtures.FakeCursor((
                    baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                    (row,),
                ))

                report = baseline._collect_baseline_audit(
                    cursor,
                    baseline_fixtures.source(),
                    budget,
                )

                self.assertEqual(report["reasonCounts"], {reason: 1})
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES
                    - row["query_variable_bytes"],
                )
                self.assertEqual(len(cursor.calls), 2)

    def test_reconciliation_field_overflow_keeps_existing_specific_reasons(self):
        reasons = {
            "reconciliation_status": "impact_reconciliation_status_invalid",
            "reconciliation_smeta_type": "impact_reconciliation_not_customer",
            "reconciliation_work_package": (
                "impact_reconciliation_package_mismatch"
            ),
            "base_smeta_type": "impact_reconciliation_not_customer",
            "base_work_package": "impact_reconciliation_package_mismatch",
            "next_status": "impact_reconciliation_next_not_active",
            "next_smeta_type": "impact_reconciliation_not_customer",
            "next_work_package": "impact_reconciliation_package_mismatch",
        }
        for field, reason in reasons.items():
            with self.subTest(field=field):
                budget = _VariableByteBudget()
                cursor = baseline_fixtures.FakeCursor((
                    baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                    (_target_row(),),
                    (_reconciliation_overflow(field),),
                ))

                report = baseline._collect_baseline_audit(
                    cursor,
                    baseline_fixtures.source(),
                    budget,
                )

                self.assertEqual(report["reasonCounts"], {reason: 1})
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES
                    - _target_row()["query_variable_bytes"],
                )
                self.assertEqual(len(cursor.calls), 3)

    def test_each_reconciliation_field_accepts_its_inclusive_utf8_boundary(self):
        exact_text = "\u044f" * (MAX_TEXT_FIELD_BYTES // 2)
        reasons = {
            "reconciliation_status": "impact_reconciliation_status_invalid",
            "reconciliation_smeta_type": "impact_reconciliation_not_customer",
            "reconciliation_work_package": (
                "impact_reconciliation_package_mismatch"
            ),
            "base_smeta_type": "impact_reconciliation_not_customer",
            "base_work_package": "impact_reconciliation_package_mismatch",
            "next_status": "impact_reconciliation_next_not_active",
            "next_smeta_type": "impact_reconciliation_not_customer",
            "next_work_package": "impact_reconciliation_package_mismatch",
        }
        target = _target_row()
        for field, reason in reasons.items():
            with self.subTest(field=field):
                reconciliation = _reconciliation_row(**{field: exact_text})
                self.assertEqual(
                    reconciliation["field_" + field + "_bytes"],
                    MAX_TEXT_FIELD_BYTES,
                )
                budget = _VariableByteBudget()
                cursor = baseline_fixtures.FakeCursor((
                    baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                    (target,),
                    (reconciliation,),
                ))

                report = baseline._collect_baseline_audit(
                    cursor,
                    baseline_fixtures.source(),
                    budget,
                )

                self.assertEqual(report["reasonCounts"], {reason: 1})
                self.assertEqual(
                    budget.remaining_bytes,
                    MAX_COLLECTOR_VARIABLE_BYTES
                    - target["query_variable_bytes"]
                    - reconciliation["query_variable_bytes"],
                )
                self.assertEqual(len(cursor.calls), 3)

    def test_reconciliation_overflow_mapping_precedes_hidden_semantics(self):
        reconciliation = _reconciliation_overflow("reconciliation_status")
        reconciliation["next_is_template"] = True
        budget = _VariableByteBudget()
        target = _target_row()

        report = baseline._collect_baseline_audit(
            baseline_fixtures.FakeCursor((
                baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                (target,),
                (reconciliation,),
            )),
            baseline_fixtures.source(),
            budget,
        )

        self.assertEqual(report["reasonCounts"], {
            "impact_reconciliation_status_invalid": 1,
        })
        self.assertEqual(
            budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES - target["query_variable_bytes"],
        )

    def test_null_and_coalesced_values_have_exact_emitted_utf8_sizes(self):
        target = _target_row(
            status=None,
            smeta_type=None,
            work_package=None,
        )
        self.assertEqual(target["status"], "\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a")
        self.assertEqual(target["smeta_type"], "\u0417\u0430\u043a\u0430\u0437\u0447\u0438\u043a")
        self.assertEqual(
            target["field_status_bytes"],
            len("\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a".encode("utf-8")),
        )
        self.assertEqual(
            target["field_smeta_type_bytes"],
            len("\u0417\u0430\u043a\u0430\u0437\u0447\u0438\u043a".encode("utf-8")),
        )
        self.assertEqual(target["field_work_package_bytes"], 0)

        target_budget = _VariableByteBudget()
        target_report = baseline._collect_baseline_audit(
            baseline_fixtures.FakeCursor((
                baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                (target,),
            )),
            baseline_fixtures.source(),
            target_budget,
        )
        self.assertEqual(target_report["reasonCounts"], {
            "impact_estimate_not_active": 1,
        })
        self.assertEqual(
            target_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES - target["query_variable_bytes"],
        )

        reconciliation = _reconciliation_row(
            reconciliation_status=None,
            reconciliation_smeta_type=None,
            reconciliation_work_package=None,
            base_smeta_type=None,
            base_work_package=None,
            next_status=None,
            next_smeta_type=None,
            next_work_package=None,
        )
        for field in (
            "reconciliation_smeta_type",
            "base_smeta_type",
            "next_smeta_type",
        ):
            self.assertEqual(reconciliation[field], "\u0417\u0430\u043a\u0430\u0437\u0447\u0438\u043a")
            self.assertEqual(
                reconciliation["field_" + field + "_bytes"],
                len("\u0417\u0430\u043a\u0430\u0437\u0447\u0438\u043a".encode("utf-8")),
            )
        self.assertEqual(reconciliation["next_status"], "\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a")
        self.assertEqual(
            reconciliation["field_next_status_bytes"],
            len("\u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a".encode("utf-8")),
        )
        for field in (
            "reconciliation_status",
            "reconciliation_work_package",
            "base_work_package",
            "next_work_package",
        ):
            self.assertEqual(reconciliation["field_" + field + "_bytes"], 0)

        reconciliation_budget = _VariableByteBudget()
        ready_target = _target_row()
        reconciliation_report = baseline._collect_baseline_audit(
            baseline_fixtures.FakeCursor((
                baseline_fixtures.REQUIRED_SCHEMA_ROWS,
                (ready_target,),
                (reconciliation,),
            )),
            baseline_fixtures.source(),
            reconciliation_budget,
        )
        self.assertEqual(reconciliation_report["reasonCounts"], {
            "impact_reconciliation_package_mismatch": 1,
        })
        self.assertEqual(
            reconciliation_budget.remaining_bytes,
            MAX_COLLECTOR_VARIABLE_BYTES
            - ready_target["query_variable_bytes"]
            - reconciliation["query_variable_bytes"],
        )

    def test_reconciliation_cardinality_precedes_payload_validation(self):
        first, second = baseline_fixtures.reconciliation_rows(
            _reconciliation_cardinality_row(91),
            _reconciliation_cardinality_row(92),
            scan_limit=1,
        )
        self.assertEqual(
            first["query_variable_bytes"],
            second["query_variable_bytes"],
        )
        self.assertFalse(first["payload_limit_exceeded"])
        self.assertFalse(second["payload_limit_exceeded"])
        cursor = baseline_fixtures.FakeCursor((
            baseline_fixtures.REQUIRED_SCHEMA_ROWS,
            (_target_row(),),
            (first, second),
        ))

        report = baseline.collect_baseline_audit(
            cursor,
            baseline_fixtures.source(),
            max_reconciliation_rows=1,
        )

        self.assertFalse(report["scanComplete"])
        self.assertEqual(report["reasonCounts"], {
            "impact_reconciliation_scan_limit_exceeded": 1,
        })
        self.assertEqual(len(cursor.calls), 3)

    def test_cumulative_budget_overflow_is_atomic_and_stops_reconciliation(self):
        target = _target_row()
        required_bytes = target["query_variable_bytes"]
        for field in _TARGET_TEXT_FIELDS + ("sections_json",):
            target[field] = None
        target["payload_limit_exceeded"] = True
        budget = _VariableByteBudget()
        budget.consume(
            MAX_COLLECTOR_VARIABLE_BYTES - required_bytes + 1,
        )
        remaining_before = budget.remaining_bytes
        cursor = baseline_fixtures.FakeCursor((
            baseline_fixtures.REQUIRED_SCHEMA_ROWS,
            (target,),
        ))

        report = baseline._collect_baseline_audit(
            cursor,
            baseline_fixtures.source(),
            budget,
        )

        self.assertEqual(report["reasonCounts"], {
            "impact_estimate_snapshot_too_large": 1,
        })
        self.assertEqual(budget.remaining_bytes, remaining_before)
        self.assertEqual(len(cursor.calls), 2)
        self.assertIn(remaining_before, cursor.calls[1][1])

    def test_multibyte_field_boundary_uses_utf8_bytes(self):
        exact = _target_row(work_package="я" * 512)
        self.assertEqual(exact["field_work_package_bytes"], 1_024)
        exact_cursor = baseline_fixtures.FakeCursor((
            baseline_fixtures.REQUIRED_SCHEMA_ROWS,
            (exact,),
        ))

        exact_report = baseline.collect_baseline_audit(
            exact_cursor,
            baseline_fixtures.source(),
        )

        self.assertEqual(exact_report["reasonCounts"], {
            "impact_estimate_package_invalid": 1,
        })

        overflow = _target_overflow("work_package")
        overflow["field_work_package_bytes"] = 1_025
        overflow["query_text_bytes"] = sum(
            overflow["field_" + field + "_bytes"]
            for field in _TARGET_TEXT_FIELDS
        )
        overflow["query_variable_bytes"] = (
            overflow["query_json_bytes"] + overflow["query_text_bytes"]
        )
        overflow_cursor = baseline_fixtures.FakeCursor((
            baseline_fixtures.REQUIRED_SCHEMA_ROWS,
            (overflow,),
        ))

        overflow_report = baseline.collect_baseline_audit(
            overflow_cursor,
            baseline_fixtures.source(),
        )

        self.assertEqual(overflow_report["reasonCounts"], {
            "impact_estimate_snapshot_too_large": 1,
        })


if __name__ == "__main__":
    unittest.main()
