import ast
import copy
import hashlib
import inspect
import unittest
from pathlib import Path
from unittest import mock

import psycopg2.extras

from backend.features.estimate_revision_impact.combined_contract import (
    build_combined_report,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
)
from backend.features.estimate_revision_impact import (
    test_supply_warehouse_audit as _supply_warehouse_audit_fixtures,
)
from backend.features.warehouse_recommendation_preview import content_preview
from backend.features.warehouse_recommendation_preview.content_preview import (
    WAREHOUSE_ANOMALY_CONTENT_VERSION,
    WarehouseAnomalyContentError,
    run_warehouse_anomaly_content_preview,
)
from backend.features.warehouse_recommendation_preview.content_contract import (
    _finalize_warehouse_anomaly_content,
    _prepare_warehouse_anomaly_content,
    _validate_current_warehouse_anomaly_report,
)
from backend.features.warehouse_recommendation_preview.test_content_contract import (
    _a92c_case,
    _a92c_replace_raw_reviews,
    current_a7_report,
)
from backend.features.warehouse_recommendation_preview.readiness import (
    build_warehouse_anomaly_readiness,
)


def _raise_stage(failures, stage):
    failure = failures.get(stage)
    if failure is not None:
        raise failure


class _LifecycleCursor:
    def __init__(
        self, events, *, failures=None, falsey=False, close_callback=None,
    ):
        self.events = events
        self.failures = failures or {}
        self.falsey = falsey
        self.close_callback = close_callback
        self.calls = []
        self.closed = False

    def __bool__(self):
        return not self.falsey

    def execute(self, sql, params=()):
        self.events.append("set_config")
        self.calls.append((" ".join(sql.split()), tuple(params)))
        _raise_stage(self.failures, "set_config")

    def close(self):
        self.events.append("cursor_close")
        self.closed = True
        if self.close_callback is not None:
            self.close_callback()
        _raise_stage(self.failures, "cursor_close")


class _LifecycleConnection:
    def __init__(
        self, events, cursor, *, failures=None, falsey=False,
        close_callback=None,
    ):
        self.events = events
        self.cursor_value = cursor
        self.failures = failures or {}
        self.falsey = falsey
        self.close_callback = close_callback
        self.session = None
        self.cursor_kwargs = None
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def __bool__(self):
        return not self.falsey

    def set_session(self, **kwargs):
        self.events.append("set_session")
        self.session = kwargs
        _raise_stage(self.failures, "set_session")

    def cursor(self, **kwargs):
        self.events.append("cursor")
        self.cursor_kwargs = kwargs
        _raise_stage(self.failures, "cursor")
        return self.cursor_value

    def rollback(self):
        self.events.append("rollback")
        self.rollbacks += 1
        _raise_stage(self.failures, "rollback")

    def commit(self):
        self.commits += 1
        raise AssertionError("A9.2 preview must never commit")

    def close(self):
        self.events.append("connection_close")
        self.closed = True
        if self.close_callback is not None:
            self.close_callback()
        _raise_stage(self.failures, "connection_close")


class _MissingMethodProxy:
    def __init__(self, target, missing):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_missing", missing)

    def __getattribute__(self, name):
        if name in {"_target", "_missing"}:
            return object.__getattribute__(self, name)
        if name == object.__getattribute__(self, "_missing"):
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_target"), name)


def _real_a7_case():
    current = current_a7_report("review_required")
    stored = build_combined_report(
        current["source"],
        assignment=None,
        material=None,
        supply_warehouse=current["supplyWarehouseImpact"],
        economics=None,
    )
    stored.update({"readOnlyTransaction": True, "rolledBack": True})
    readiness = build_warehouse_anomaly_readiness(stored)
    candidate = next(
        item for item in readiness["candidates"]
        if item["anomalyCode"] == "warehouse_invoice_project_mismatch"
    )
    selection = {
        name: candidate[name]
        for name in ("subjectKind", "subjectId", "anomalyCode")
    }
    result_sets = list(
        _supply_warehouse_audit_fixtures
        .SupplyWarehouseProjectionCollectorTests()
        .result_sets()
    )
    result_sets[9] = (
        _supply_warehouse_audit_fixtures._bounded_invoice_rows(
            _supply_warehouse_audit_fixtures._bounded_invoice_row(
                invoice_project="Other project",
            ),
        )
    )
    return stored, selection, tuple(result_sets)


class WarehouseAnomalyContentPreviewRunnerTests(unittest.TestCase):
    maxDiff = None

    def _run_with_normal_failures(self, stages):
        expected_prepared, stored, selection, current = _a92c_case()
        events = []
        cursor = _LifecycleCursor(events, failures=stages)
        connection = _LifecycleConnection(
            events, cursor, failures=stages,
        )

        def get_db():
            events.append("get_db")
            _raise_stage(stages, "get_db")
            return connection

        def collect(actual_cursor, source):
            events.append("collect")
            self.assertIs(actual_cursor, cursor)
            self.assertEqual(source, expected_prepared.source_contract)
            _raise_stage(stages, "collector")
            return current

        def validate(raw, source):
            events.append("validate")
            self.assertIs(raw, current)
            self.assertEqual(source, expected_prepared.source_contract)
            _raise_stage(stages, "raw_validator")
            return _validate_current_warehouse_anomaly_report(raw, source)

        def finalize(prepared, validated_current):
            events.append("finalize")
            self.assertTrue(cursor.closed)
            self.assertTrue(connection.closed)
            _raise_stage(stages, "finalizer")
            return _finalize_warehouse_anomaly_content(
                prepared, validated_current,
            )

        with mock.patch.object(
            content_preview,
            "collect_supply_warehouse_impact_audit",
            side_effect=collect,
        ) as collector, mock.patch.object(
            content_preview,
            "_validate_current_warehouse_anomaly_report",
            side_effect=validate,
        ) as validator, mock.patch.object(
            content_preview,
            "_finalize_warehouse_anomaly_content",
            side_effect=finalize,
        ) as finalizer:
            with self.assertRaises(WarehouseAnomalyContentError) as raised:
                run_warehouse_anomaly_content_preview(
                    get_db, stored, selection,
                )

        return {
            "error": raised.exception,
            "events": events,
            "connection": connection,
            "cursor": cursor,
            "collector": collector,
            "validator": validator,
            "finalizer": finalizer,
        }

    def _run_with_control_flow(self, stages):
        expected_prepared, stored, selection, current = _a92c_case()
        events = []
        cursor = _LifecycleCursor(events, failures=stages)
        connection = _LifecycleConnection(
            events, cursor, failures=stages,
        )

        def get_db():
            events.append("get_db")
            _raise_stage(stages, "get_db")
            return connection

        def collect(actual_cursor, source):
            events.append("collect")
            self.assertIs(actual_cursor, cursor)
            self.assertEqual(source, expected_prepared.source_contract)
            _raise_stage(stages, "collector")
            return current

        def validate(raw, source):
            events.append("validate")
            _raise_stage(stages, "raw_validator")
            return _validate_current_warehouse_anomaly_report(raw, source)

        def finalize(prepared, validated_current):
            events.append("finalize")
            _raise_stage(stages, "finalizer")
            return _finalize_warehouse_anomaly_content(
                prepared, validated_current,
            )

        captured = None
        with mock.patch.object(
            content_preview,
            "collect_supply_warehouse_impact_audit",
            side_effect=collect,
        ) as collector, mock.patch.object(
            content_preview,
            "_validate_current_warehouse_anomaly_report",
            side_effect=validate,
        ) as validator, mock.patch.object(
            content_preview,
            "_finalize_warehouse_anomaly_content",
            side_effect=finalize,
        ) as finalizer:
            try:
                run_warehouse_anomaly_content_preview(
                    get_db, stored, selection,
                )
            except BaseException as exc:
                captured = exc

        self.assertIsNotNone(captured)
        return {
            "error": captured,
            "events": events,
            "connection": connection,
            "cursor": cursor,
            "collector": collector,
            "validator": validator,
            "finalizer": finalizer,
        }

    def test_approved_public_runner_surface_exists(self):
        self.assertEqual(WAREHOUSE_ANOMALY_CONTENT_VERSION, 1)
        self.assertTrue(issubclass(WarehouseAnomalyContentError, ValueError))
        self.assertTrue(callable(run_warehouse_anomaly_content_preview))

    def test_happy_path_collects_once_and_finalizes_only_after_cleanup(self):
        expected_prepared, stored, selection, current = _a92c_case()
        stored_before = copy.deepcopy(stored)
        selection_before = copy.deepcopy(selection)
        current_before = copy.deepcopy(current)
        events = []
        cursor = _LifecycleCursor(events)
        connection = _LifecycleConnection(events, cursor)

        def get_db():
            events.append("get_db")
            return connection

        def collect(actual_cursor, source):
            events.append("collect")
            self.assertIs(actual_cursor, cursor)
            self.assertEqual(source, expected_prepared.source_contract)
            return current

        def finalize(prepared, validated_current):
            events.append("finalize")
            self.assertEqual(prepared, expected_prepared)
            self.assertEqual(validated_current, current_before)
            self.assertIsNot(validated_current, current)
            self.assertIsNot(validated_current["source"], current["source"])
            self.assertIsNot(
                validated_current["supplyWarehouseImpact"],
                current["supplyWarehouseImpact"],
            )
            self.assertEqual(connection.rollbacks, 1)
            self.assertTrue(cursor.closed)
            self.assertTrue(connection.closed)
            return _finalize_warehouse_anomaly_content(
                prepared, validated_current,
            )

        with mock.patch.object(
            content_preview,
            "collect_supply_warehouse_impact_audit",
            side_effect=collect,
            create=True,
        ) as collector, mock.patch.object(
            content_preview,
            "_finalize_warehouse_anomaly_content",
            side_effect=finalize,
            create=True,
        ) as finalizer:
            result = run_warehouse_anomaly_content_preview(
                get_db, stored, selection,
            )

        self.assertEqual(events, [
            "get_db",
            "set_session",
            "cursor",
            "set_config",
            "collect",
            "rollback",
            "cursor_close",
            "connection_close",
            "finalize",
        ])
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.cursor_kwargs, {
            "cursor_factory": psycopg2.extras.RealDictCursor,
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        collector.assert_called_once()
        finalizer.assert_called_once()

        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        self.assertTrue(sql.upper().startswith("SELECT "))
        self.assertEqual(
            sql.count("pg_catalog.set_config(%s, %s, true)"), 4,
        )
        self.assertEqual(params, (
            "statement_timeout", "60000",
            "lock_timeout", "5000",
            "idle_in_transaction_session_timeout", "60000",
            "search_path", "pg_catalog,public",
        ))
        self.assertNotIn("FOR UPDATE", sql.upper())
        for mutation in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE "):
            self.assertNotIn(mutation, sql.upper())

        self.assertEqual(result["state"], "preview_ready")
        self.assertIs(result["readOnlyTransaction"], True)
        self.assertIs(result["rolledBack"], True)
        self.assertEqual(stored, stored_before)
        self.assertEqual(selection, selection_before)
        self.assertEqual(current, current_before)

    def test_non_callable_get_db_fails_before_preparation(self):
        _prepared, stored, selection, _current = _a92c_case()
        with mock.patch.object(
            content_preview,
            "_prepare_warehouse_anomaly_content",
            wraps=_prepare_warehouse_anomaly_content,
            create=True,
        ) as prepare:
            with self.assertRaises(WarehouseAnomalyContentError) as raised:
                run_warehouse_anomaly_content_preview(
                    None, stored, selection,
                )

        self.assertEqual(
            raised.exception.code,
            "warehouse_anomaly_content_input_invalid",
        )
        self.assertEqual(str(raised.exception), raised.exception.code)
        self.assertEqual(raised.exception.args, (raised.exception.code,))
        prepare.assert_not_called()

    def test_each_normal_lifecycle_failure_has_one_fixed_non_leaking_code(self):
        cases = (
            (
                "get_db",
                "warehouse_anomaly_content_read_failed",
                ["get_db"],
            ),
            (
                "set_session",
                "warehouse_anomaly_content_read_failed",
                ["get_db", "set_session", "rollback", "connection_close"],
            ),
            (
                "cursor",
                "warehouse_anomaly_content_read_failed",
                [
                    "get_db", "set_session", "cursor", "rollback",
                    "connection_close",
                ],
            ),
            (
                "set_config",
                "warehouse_anomaly_content_read_failed",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "rollback", "cursor_close", "connection_close",
                ],
            ),
            (
                "collector",
                "warehouse_anomaly_content_read_failed",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "collect", "rollback", "cursor_close",
                    "connection_close",
                ],
            ),
            (
                "raw_validator",
                "warehouse_anomaly_content_current_report_invalid",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "collect", "validate", "rollback", "cursor_close",
                    "connection_close",
                ],
            ),
            (
                "rollback",
                "warehouse_anomaly_content_rollback_failed",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "collect", "validate", "rollback", "cursor_close",
                    "connection_close",
                ],
            ),
            (
                "cursor_close",
                "warehouse_anomaly_content_cleanup_failed",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "collect", "validate", "rollback", "cursor_close",
                    "connection_close",
                ],
            ),
            (
                "connection_close",
                "warehouse_anomaly_content_cleanup_failed",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "collect", "validate", "rollback", "cursor_close",
                    "connection_close",
                ],
            ),
            (
                "finalizer",
                "warehouse_anomaly_content_contract_invalid",
                [
                    "get_db", "set_session", "cursor", "set_config",
                    "collect", "validate", "rollback", "cursor_close",
                    "connection_close", "finalize",
                ],
            ),
        )

        for stage, code, expected_events in cases:
            with self.subTest(stage=stage):
                private = f"PRIVATE::{stage}"
                outcome = self._run_with_normal_failures({
                    stage: RuntimeError(private),
                })

                error = outcome["error"]
                self.assertEqual(error.code, code)
                self.assertEqual(str(error), code)
                self.assertEqual(error.args, (code,))
                self.assertNotIn(private, str(error))
                self.assertNotIn(private, repr(error))
                self.assertEqual(outcome["events"], expected_events)
                self.assertEqual(outcome["connection"].commits, 0)
                if stage == "get_db":
                    self.assertEqual(outcome["connection"].rollbacks, 0)
                    self.assertFalse(outcome["connection"].closed)
                else:
                    self.assertEqual(outcome["connection"].rollbacks, 1)
                    self.assertTrue(outcome["connection"].closed)
                if stage in {"get_db", "set_session", "cursor"}:
                    self.assertFalse(outcome["cursor"].closed)
                else:
                    self.assertTrue(outcome["cursor"].closed)
                outcome["finalizer"].assert_called_once() if (
                    stage == "finalizer"
                ) else outcome["finalizer"].assert_not_called()

        settings = self._run_with_normal_failures({
            "set_config": RuntimeError("PRIVATE::settings"),
        })
        settings["collector"].assert_not_called()
        settings["validator"].assert_not_called()
        settings["finalizer"].assert_not_called()

    def test_normal_failure_precedence_is_rollback_read_cleanup_current(self):
        collisions = (
            (
                "rollback_over_read_and_cleanup",
                {
                    "collector": RuntimeError("PRIVATE::read"),
                    "rollback": RuntimeError("PRIVATE::rollback"),
                    "cursor_close": RuntimeError("PRIVATE::cursor-close"),
                    "connection_close": RuntimeError("PRIVATE::connection-close"),
                },
                "warehouse_anomaly_content_rollback_failed",
            ),
            (
                "read_over_cleanup",
                {
                    "collector": RuntimeError("PRIVATE::read"),
                    "cursor_close": RuntimeError("PRIVATE::cursor-close"),
                    "connection_close": RuntimeError("PRIVATE::connection-close"),
                },
                "warehouse_anomaly_content_read_failed",
            ),
            (
                "cleanup_over_current_invalid",
                {
                    "raw_validator": RuntimeError("PRIVATE::validator"),
                    "cursor_close": RuntimeError("PRIVATE::cursor-close"),
                    "connection_close": RuntimeError("PRIVATE::connection-close"),
                },
                "warehouse_anomaly_content_cleanup_failed",
            ),
        )

        for name, failures, expected_code in collisions:
            with self.subTest(name=name):
                outcome = self._run_with_normal_failures(failures)
                self.assertEqual(outcome["error"].code, expected_code)
                self.assertEqual(str(outcome["error"]), expected_code)
                self.assertEqual(outcome["connection"].rollbacks, 1)
                self.assertTrue(outcome["cursor"].closed)
                self.assertTrue(outcome["connection"].closed)
                outcome["finalizer"].assert_not_called()
                for failure in failures.values():
                    self.assertNotIn(str(failure), str(outcome["error"]))

    def test_dependency_same_class_error_cannot_smuggle_a_public_code(self):
        injected = WarehouseAnomalyContentError(
            "PRIVATE::dependency-controlled-code"
        )
        outcome = self._run_with_normal_failures({"collector": injected})
        self.assertEqual(
            outcome["error"].code,
            "warehouse_anomaly_content_read_failed",
        )
        self.assertNotIn("PRIVATE", str(outcome["error"]))

        finalizer = self._run_with_normal_failures({"finalizer": injected})
        self.assertEqual(
            finalizer["error"].code,
            "warehouse_anomaly_content_contract_invalid",
        )
        self.assertNotIn("PRIVATE", str(finalizer["error"]))

    def test_invalid_finalizer_result_never_escapes_after_cleanup(self):
        prepared, stored, selection, current = _a92c_case()
        valid = _finalize_warehouse_anomaly_content(
            prepared, copy.deepcopy(current),
        )
        cases = {
            "none": None,
            "empty": {},
            "private_extra": {**valid, "private": "PRIVATE::result"},
            "false_transaction": {
                **valid,
                "readOnlyTransaction": False,
                "rolledBack": False,
            },
            "wrong_state": {**valid, "state": "blocked"},
            "wrong_blockers": {**valid, "blockers": ["PRIVATE::blocker"]},
            "wrong_hash": {**valid, "contentSha256": "0" * 64},
            "wrong_candidate": {
                **valid,
                "candidate": {**valid["candidate"], "subjectId": 999999},
            },
            "wrong_source": {
                **valid,
                "source": {**valid["source"], "companyId": 999999},
            },
        }
        for name, invalid in cases.items():
            with self.subTest(name=name):
                events = []
                cursor = _LifecycleCursor(events)
                connection = _LifecycleConnection(events, cursor)
                with mock.patch.object(
                    content_preview,
                    "collect_supply_warehouse_impact_audit",
                    return_value=current,
                ), mock.patch.object(
                    content_preview,
                    "_finalize_warehouse_anomaly_content",
                    return_value=invalid,
                ):
                    with self.assertRaises(
                        WarehouseAnomalyContentError
                    ) as raised:
                        run_warehouse_anomaly_content_preview(
                            lambda: connection, stored, selection,
                        )

                self.assertEqual(
                    raised.exception.code,
                    "warehouse_anomaly_content_contract_invalid",
                )
                self.assertNotIn("PRIVATE", str(raised.exception))
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def test_falsey_resources_and_close_time_raw_mutation_are_safe(self):
        prepared, stored, selection, current = _a92c_case()
        expected = _finalize_warehouse_anomaly_content(
            prepared, copy.deepcopy(current),
        )
        events = []

        def mutate_after_validation():
            current["source"]["reconciliationStatus"] = "PRIVATE MUTATION"
            current["supplyWarehouseImpact"]["needsReview"][0][
                "sourceId"
            ] = 999999

        cursor = _LifecycleCursor(
            events, falsey=True, close_callback=mutate_after_validation,
        )
        connection = _LifecycleConnection(
            events, cursor, falsey=True,
        )

        with mock.patch.object(
            content_preview,
            "collect_supply_warehouse_impact_audit",
            return_value=current,
        ) as collector:
            result = run_warehouse_anomaly_content_preview(
                lambda: connection, stored, selection,
            )

        self.assertFalse(cursor)
        self.assertFalse(connection)
        self.assertEqual(result, expected)
        self.assertEqual(result["state"], "preview_ready")
        self.assertNotIn("PRIVATE MUTATION", repr(result))
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        collector.assert_called_once()

    def test_business_precedence_runs_only_after_successful_cleanup(self):
        _prepared, stored, selection, exact = _a92c_case()

        source_drift = copy.deepcopy(exact)
        source_drift["source"]["reconciliationStatus"] = "На проверке"

        snapshot_blocked = copy.deepcopy(exact)
        _a92c_replace_raw_reviews(
            snapshot_blocked,
            "warehouse_invoice_items_limit_exceeded",
            902,
        )

        candidate_stale = copy.deepcopy(exact)
        projection = candidate_stale["supplyWarehouseImpact"]
        projection.update({
            "state": "complete",
            "complete": True,
            "reasonCounts": {},
            "needsReview": [],
            "needsReviewTruncated": False,
        })
        projection["summary"]["needsReview"] = 0
        candidate_stale["readyForSupplyWarehouseProjection"] = True

        relevant_drift = copy.deepcopy(exact)
        relevant_drift["supplyWarehouseImpact"]["openSupply"][0][
            "requestId"
        ] += 1000

        cases = (
            (
                "source_not_ready",
                current_a7_report("not_collected"),
                "blocked",
                "warehouse_anomaly_current_source_not_ready",
            ),
            (
                "source_drift",
                source_drift,
                "stale",
                "warehouse_anomaly_source_drift",
            ),
            (
                "snapshot_blocked",
                snapshot_blocked,
                "blocked",
                "warehouse_anomaly_current_snapshot_blocked",
            ),
            (
                "candidate_stale",
                candidate_stale,
                "stale",
                "warehouse_anomaly_candidate_stale",
            ),
            (
                "relevant_drift",
                relevant_drift,
                "stale",
                "warehouse_anomaly_relevant_evidence_drift",
            ),
            ("preview_ready", exact, "preview_ready", None),
        )
        for name, current, state, blocker in cases:
            with self.subTest(name=name):
                cursor = _LifecycleCursor([])
                connection = _LifecycleConnection([], cursor)
                with mock.patch.object(
                    content_preview,
                    "collect_supply_warehouse_impact_audit",
                    return_value=current,
                ):
                    result = run_warehouse_anomaly_content_preview(
                        lambda: connection, stored, selection,
                    )

                self.assertEqual(result["state"], state)
                self.assertEqual(
                    result["blockers"], [] if blocker is None else [blocker],
                )
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

        core_drift = copy.deepcopy(exact)
        core_drift["source"]["companyId"] += 1
        cursor = _LifecycleCursor([])
        connection = _LifecycleConnection([], cursor)
        with mock.patch.object(
            content_preview,
            "collect_supply_warehouse_impact_audit",
            return_value=core_drift,
        ), mock.patch.object(
            content_preview,
            "_finalize_warehouse_anomaly_content",
            wraps=_finalize_warehouse_anomaly_content,
        ) as finalizer:
            with self.assertRaises(WarehouseAnomalyContentError) as raised:
                run_warehouse_anomaly_content_preview(
                    lambda: connection, stored, selection,
                )
        self.assertEqual(
            raised.exception.code,
            "warehouse_anomaly_content_current_report_invalid",
        )
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        finalizer.assert_not_called()

    def test_each_control_flow_exception_keeps_exact_identity_at_every_phase(self):
        expected_events = {
            "get_db": ["get_db"],
            "set_session": [
                "get_db", "set_session", "rollback", "connection_close",
            ],
            "cursor": [
                "get_db", "set_session", "cursor", "rollback",
                "connection_close",
            ],
            "set_config": [
                "get_db", "set_session", "cursor", "set_config",
                "rollback", "cursor_close", "connection_close",
            ],
            "collector": [
                "get_db", "set_session", "cursor", "set_config",
                "collect", "rollback", "cursor_close", "connection_close",
            ],
            "raw_validator": [
                "get_db", "set_session", "cursor", "set_config",
                "collect", "validate", "rollback", "cursor_close",
                "connection_close",
            ],
            "rollback": [
                "get_db", "set_session", "cursor", "set_config",
                "collect", "validate", "rollback", "cursor_close",
                "connection_close",
            ],
            "cursor_close": [
                "get_db", "set_session", "cursor", "set_config",
                "collect", "validate", "rollback", "cursor_close",
                "connection_close",
            ],
            "connection_close": [
                "get_db", "set_session", "cursor", "set_config",
                "collect", "validate", "rollback", "cursor_close",
                "connection_close",
            ],
            "finalizer": [
                "get_db", "set_session", "cursor", "set_config",
                "collect", "validate", "rollback", "cursor_close",
                "connection_close", "finalize",
            ],
        }

        for exception_type in (KeyboardInterrupt, SystemExit, GeneratorExit):
            for stage, events in expected_events.items():
                with self.subTest(
                    exception=exception_type.__name__, stage=stage,
                ):
                    control = exception_type(
                        f"PRIVATE::{exception_type.__name__}::{stage}"
                    )
                    outcome = self._run_with_control_flow({stage: control})
                    self.assertIs(outcome["error"], control)
                    self.assertEqual(outcome["events"], events)
                    self.assertEqual(outcome["connection"].commits, 0)
                    if stage == "get_db":
                        self.assertEqual(outcome["connection"].rollbacks, 0)
                        self.assertFalse(outcome["connection"].closed)
                    else:
                        self.assertEqual(outcome["connection"].rollbacks, 1)
                        self.assertTrue(outcome["connection"].closed)
                    if stage in {"get_db", "set_session", "cursor"}:
                        self.assertFalse(outcome["cursor"].closed)
                    else:
                        self.assertTrue(outcome["cursor"].closed)
                    outcome["finalizer"].assert_called_once() if (
                        stage == "finalizer"
                    ) else outcome["finalizer"].assert_not_called()

    def test_first_control_flow_wins_every_multi_failure_collision(self):
        first_primary = KeyboardInterrupt("PRIVATE::first-primary")
        later_rollback = SystemExit("PRIVATE::later-rollback")
        later_cursor = GeneratorExit("PRIVATE::later-cursor")
        later_connection = KeyboardInterrupt("PRIVATE::later-connection")
        primary = self._run_with_control_flow({
            "collector": first_primary,
            "rollback": later_rollback,
            "cursor_close": later_cursor,
            "connection_close": later_connection,
        })
        self.assertIs(primary["error"], first_primary)
        self.assertTrue(primary["cursor"].closed)
        self.assertTrue(primary["connection"].closed)

        first_rollback = SystemExit("PRIVATE::first-rollback")
        rollback = self._run_with_control_flow({
            "collector": RuntimeError("PRIVATE::normal-read"),
            "rollback": first_rollback,
            "cursor_close": GeneratorExit("PRIVATE::later-cursor"),
            "connection_close": KeyboardInterrupt("PRIVATE::later-connection"),
        })
        self.assertIs(rollback["error"], first_rollback)

        first_cleanup = GeneratorExit("PRIVATE::first-cleanup")
        cleanup = self._run_with_control_flow({
            "collector": RuntimeError("PRIVATE::normal-read"),
            "cursor_close": first_cleanup,
            "connection_close": SystemExit("PRIVATE::later-connection"),
        })
        self.assertIs(cleanup["error"], first_cleanup)

        first_validator = KeyboardInterrupt("PRIVATE::first-validator")
        validator = self._run_with_control_flow({
            "raw_validator": first_validator,
            "rollback": GeneratorExit("PRIVATE::later-rollback"),
            "cursor_close": SystemExit("PRIVATE::later-cursor"),
        })
        self.assertIs(validator["error"], first_validator)

    def test_missing_and_non_callable_lifecycle_methods_fail_closed(self):
        cases = (
            ("connection", "set_session", "warehouse_anomaly_content_read_failed"),
            ("connection", "cursor", "warehouse_anomaly_content_read_failed"),
            ("cursor", "execute", "warehouse_anomaly_content_read_failed"),
            ("connection", "rollback", "warehouse_anomaly_content_rollback_failed"),
            ("cursor", "close", "warehouse_anomaly_content_cleanup_failed"),
            ("connection", "close", "warehouse_anomaly_content_cleanup_failed"),
        )

        for form in ("missing", "non_callable"):
            for resource, method, expected_code in cases:
                with self.subTest(form=form, resource=resource, method=method):
                    _prepared, stored, selection, current = _a92c_case()
                    events = []
                    cursor = _LifecycleCursor(events)
                    connection = _LifecycleConnection(events, cursor)
                    passed_connection = connection
                    if resource == "connection":
                        if form == "missing":
                            passed_connection = _MissingMethodProxy(
                                connection, method,
                            )
                        else:
                            setattr(connection, method, None)
                    elif form == "missing":
                        connection.cursor_value = _MissingMethodProxy(
                            cursor, method,
                        )
                    else:
                        setattr(cursor, method, None)

                    with mock.patch.object(
                        content_preview,
                        "collect_supply_warehouse_impact_audit",
                        return_value=current,
                    ), mock.patch.object(
                        content_preview,
                        "_finalize_warehouse_anomaly_content",
                        wraps=_finalize_warehouse_anomaly_content,
                    ) as finalizer:
                        with self.assertRaises(
                            WarehouseAnomalyContentError
                        ) as raised:
                            run_warehouse_anomaly_content_preview(
                                lambda: passed_connection, stored, selection,
                            )

                    self.assertEqual(raised.exception.code, expected_code)
                    self.assertEqual(str(raised.exception), expected_code)
                    self.assertEqual(connection.commits, 0)
                    finalizer.assert_not_called()

        dependencies = (
            (
                "collect_supply_warehouse_impact_audit",
                "warehouse_anomaly_content_read_failed",
            ),
            (
                "_validate_current_warehouse_anomaly_report",
                "warehouse_anomaly_content_current_report_invalid",
            ),
            (
                "_finalize_warehouse_anomaly_content",
                "warehouse_anomaly_content_contract_invalid",
            ),
        )
        for dependency, expected_code in dependencies:
            with self.subTest(non_callable_dependency=dependency):
                _prepared, stored, selection, current = _a92c_case()
                cursor = _LifecycleCursor([])
                connection = _LifecycleConnection([], cursor)
                patches = {
                    "collect_supply_warehouse_impact_audit": mock.DEFAULT,
                    "_validate_current_warehouse_anomaly_report": mock.DEFAULT,
                    "_finalize_warehouse_anomaly_content": mock.DEFAULT,
                }
                patches[dependency] = None
                with mock.patch.multiple(content_preview, **patches) as mocked:
                    if dependency != "collect_supply_warehouse_impact_audit":
                        mocked[
                            "collect_supply_warehouse_impact_audit"
                        ].return_value = current
                    if dependency != "_validate_current_warehouse_anomaly_report":
                        mocked[
                            "_validate_current_warehouse_anomaly_report"
                        ].side_effect = _validate_current_warehouse_anomaly_report
                    if dependency != "_finalize_warehouse_anomaly_content":
                        mocked[
                            "_finalize_warehouse_anomaly_content"
                        ].side_effect = _finalize_warehouse_anomaly_content
                    with self.assertRaises(
                        WarehouseAnomalyContentError
                    ) as raised:
                        run_warehouse_anomaly_content_preview(
                            lambda: connection, stored, selection,
                        )
                self.assertEqual(raised.exception.code, expected_code)
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def test_real_a7_collector_path_stays_within_exact_15_select_ceiling(self):
        stored, selection, result_sets = _real_a7_case()
        cursor = FakeCursor(result_sets)
        connection = FakeConnection(cursor)

        result = run_warehouse_anomaly_content_preview(
            lambda: connection, stored, selection,
        )

        self.assertEqual(result["state"], "preview_ready")
        self.assertEqual(len(cursor.calls), 15)
        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        for index, (sql, params) in enumerate(cursor.calls):
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            self.assertNotIn("FOR UPDATE", normalized)
            for mutation in ("INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE "):
                self.assertNotIn(mutation, normalized)
            self.assertIsInstance(params, tuple)
            if index:
                self.assertGreater(len(params), 0)
        self.assertEqual(
            cursor.calls[0][1],
            (
                "statement_timeout", "60000",
                "lock_timeout", "5000",
                "idle_in_transaction_session_timeout", "60000",
                "search_path", "pg_catalog,public",
            ),
        )

    def test_static_surface_imports_and_runtime_boundaries_are_closed(self):
        module_path = Path(content_preview.__file__).resolve()
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        imports.update(
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertEqual(imports, {
            "psycopg2.extras",
            "backend.features.estimate_revision_impact.supply_warehouse_audit",
            "backend.features.warehouse_recommendation_preview.content_contract",
        })
        self.assertFalse(any(
            isinstance(node, ast.ImportFrom) and node.level
            for node in ast.walk(tree)
        ))
        self.assertEqual(content_preview.__all__, [
            "WAREHOUSE_ANOMALY_CONTENT_VERSION",
            "WarehouseAnomalyContentError",
            "run_warehouse_anomaly_content_preview",
        ])
        self.assertEqual(
            str(inspect.signature(run_warehouse_anomaly_content_preview)),
            "(get_db, combined_report, selected)",
        )
        self.assertIs(
            content_preview.WarehouseAnomalyContentError,
            WarehouseAnomalyContentError,
        )
        self.assertEqual(content_preview.WAREHOUSE_ANOMALY_CONTENT_VERSION, 1)

        for forbidden in (
            "run_baseline_audit",
            "run_supply_warehouse_impact_audit",
            "collect_combined_impact_audit",
            "backend.db",
            "backend.main",
            "routes",
            "agent_jobs",
            "provider",
            "model",
            "notification",
            "outbox",
            "requests",
            "urllib",
            "socket",
            ".commit(",
            "FOR UPDATE",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "ALTER ",
            "CREATE ",
        ):
            self.assertNotIn(forbidden, source)
        execute_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
        ]
        self.assertEqual(len(execute_calls), 1)

        package_init = module_path.with_name("__init__.py")
        self.assertEqual(
            hashlib.sha256(package_init.read_bytes()).hexdigest(),
            "d30babfeb425141af2fbf645be82eef358b6dea7d213b6d6b23cef3e7c551fea",
        )
        root = module_path.parents[3]
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "package.json",
        ):
            self.assertNotIn(
                "warehouse_recommendation_preview.content_preview",
                (root / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
