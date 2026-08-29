import ast
import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest import mock

from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
    source_from_job_payload,
)
from backend.features.warehouse_recommendation_preview import content_contract
from backend.features.warehouse_recommendation_preview import runtime_budget
from backend.features.warehouse_recommendation_preview import runtime_contract
from backend.features.warehouse_recommendation_preview import runtime_preview
from backend.features.warehouse_recommendation_preview.test_content_preview import (
    _real_a7_case,
)
from backend.features.warehouse_recommendation_preview.test_runtime_access import (
    _artifact_row,
)


_run_runtime_preview = (
    runtime_preview.run_warehouse_anomaly_runtime_preview
)
_SESSION_HASH = "a" * 64
_DB_CONFIG = {
    "dbname": "stroyka",
    "user": "stroyka",
    "password": "",
    "host": "/private/tmp/a93",
    "port": "55432",
}
_AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": _SESSION_HASH,
}
_BODY = {
    "projectId": 9,
    "jobId": 123,
    "selected": {
        "subjectKind": "warehouseInvoice",
        "subjectId": 456,
        "anomalyCode": "warehouse_invoice_project_mismatch",
    },
}


class _Lease:
    def __init__(self, events, *, guards=(), release_error=None):
        self.events = events
        self.guards = list(guards)
        self.release_error = release_error
        self.release_calls = 0

    def guard(self):
        self.events.append("outer_guard")
        if self.guards:
            error = self.guards.pop(0)
            if error is not None:
                raise error

    def release(self):
        self.events.append("release")
        self.release_calls += 1
        if self.release_error is not None:
            raise self.release_error


class _Clock:
    def __init__(self):
        self.value = 1.0
        self.calls = 0

    def __call__(self):
        self.calls += 1
        self.value += 0.001
        return self.value


class _RawCursor:
    def __init__(self, result_sets):
        self.result_sets = list(result_sets)
        self.pending = None
        self.execute_calls = []
        self.fetchall_calls = 0
        self.close_calls = 0

    def __bool__(self):
        return True

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.execute_calls.append((normalized, tuple(params)))
        if normalized in {
            runtime_budget._BEGIN_SQL,
            runtime_budget._ROLLBACK_SQL,
        }:
            self.pending = None
            return None
        if not self.result_sets:
            raise AssertionError("unexpected nineteenth SELECT")
        self.pending = self.result_sets.pop(0)

    def fetchall(self):
        self.fetchall_calls += 1
        if self.pending is None:
            raise AssertionError("fetchall without a SELECT result")
        result = self.pending
        self.pending = None
        return result

    def close(self):
        self.close_calls += 1


class _Connection:
    def __init__(self, raw_cursor):
        self.raw_cursor = raw_cursor
        self.autocommit = False
        self.cursor_calls = []
        self.close_calls = 0

    def __bool__(self):
        return True

    def cursor(self, **kwargs):
        self.cursor_calls.append(kwargs)
        return self.raw_cursor

    def close(self):
        self.close_calls += 1


class WarehouseAnomalyRuntimePreviewCompositionTests(unittest.TestCase):
    def _claims(self):
        return runtime_contract._parse_warehouse_anomaly_runtime_claims(
            _AUTHENTICATION,
            company_mode="company",
            company_id="4",
            body=_BODY,
        )

    def _assert_fixed(self, code, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(getattr(error, "code", None), code)
        self.assertEqual(error.args, (code,))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_private_runner_has_one_exact_unregistered_boundary(self):
        parameters = inspect.signature(_run_runtime_preview).parameters
        self.assertEqual(list(parameters), [
            "db_config",
            "authentication",
            "company_mode",
            "company_id",
            "body",
            "clock",
            "connect",
        ])
        for name in ("db_config", "authentication"):
            self.assertEqual(
                parameters[name].kind,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        for name in (
            "company_mode", "company_id", "body", "clock", "connect",
        ):
            self.assertEqual(
                parameters[name].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )
        for name in ("company_mode", "company_id", "body"):
            self.assertIs(
                parameters[name].default,
                inspect.Parameter.empty,
            )
        self.assertEqual(runtime_preview.__all__, [])

    def test_invalid_claims_fail_before_capacity_or_database_access(self):
        acquire = mock.Mock(
            side_effect=AssertionError("invalid input acquired capacity"),
        )
        open_connection = mock.Mock(
            side_effect=AssertionError("invalid input contacted database"),
        )
        with mock.patch.object(
            runtime_preview._runtime_budget,
            "acquire_warehouse_anomaly_runtime_slot",
            acquire,
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "open_warehouse_anomaly_read_connection",
            open_connection,
        ):
            with self.assertRaises(ValueError) as raised:
                _run_runtime_preview(
                    _DB_CONFIG,
                    {**_AUTHENTICATION, "sessionHash": "PRIVATE-INVALID"},
                    company_mode="company",
                    company_id="4",
                    body=_BODY,
                )

        self.assertEqual(
            getattr(raised.exception, "code", None),
            "warehouse_anomaly_runtime_input_invalid",
        )
        self.assertEqual(
            raised.exception.args,
            ("warehouse_anomaly_runtime_input_invalid",),
        )
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertNotIn("PRIVATE-INVALID", repr(raised.exception))
        acquire.assert_not_called()
        open_connection.assert_not_called()

    def test_happy_path_uses_one_snapshot_then_finalizes_and_releases(self):
        events = []
        claims = self._claims()
        lease = _Lease(events)
        connection = object()
        cursor = object()
        stored_report = {"stored": True}
        selected = dict(_BODY["selected"])
        artifact = {
            "combinedReport": stored_report,
            "selected": selected,
        }
        prepared = object()
        current = {"current": True}
        internal = {"internal": True}
        public = {"warehouseAnomalyRuntimeVersion": 1}

        def parse(*args, **kwargs):
            events.append("parse")
            return claims

        def acquire(clock):
            events.append("acquire")
            self.assertIs(clock, runtime_preview.time.monotonic)
            return lease

        def open_connection(db_config, actual_lease, *, connect):
            events.append("open")
            self.assertIs(db_config, _DB_CONFIG)
            self.assertIs(actual_lease, lease)
            self.assertIs(connect, runtime_preview.psycopg2.connect)
            return connection

        def authorize(actual_cursor, actual_claims):
            events.append("authorize")
            self.assertIs(actual_cursor, cursor)
            self.assertIs(actual_claims, claims)
            return claims

        def resolve(actual_cursor, actual_claims):
            events.append("artifact")
            self.assertIs(actual_cursor, cursor)
            self.assertIs(actual_claims, claims)
            return artifact

        def prepare(actual_report, actual_selected):
            events.append("prepare")
            self.assertIs(actual_report, stored_report)
            self.assertIs(actual_selected, selected)
            return prepared

        def collect(actual_cursor, actual_prepared):
            events.append("collect")
            self.assertIs(actual_cursor, cursor)
            self.assertIs(actual_prepared, prepared)
            return current

        def transaction(actual_connection, actual_lease, read):
            events.append("transaction")
            self.assertIs(actual_connection, connection)
            self.assertIs(actual_lease, lease)
            snapshot = read(cursor)
            events.append("transaction_cleanup")
            return snapshot

        def finalize(actual_prepared, actual_current):
            events.append("finalize")
            self.assertIn("transaction_cleanup", events)
            self.assertIs(actual_prepared, prepared)
            self.assertIs(actual_current, current)
            return internal

        def validate(actual_internal, actual_prepared):
            events.append("validate")
            self.assertIs(actual_internal, internal)
            self.assertIs(actual_prepared, prepared)
            return internal

        def project(actual_internal):
            events.append("project")
            self.assertIs(actual_internal, internal)
            return public

        patches = (
            mock.patch.object(
                runtime_preview._runtime_contract,
                "_parse_warehouse_anomaly_runtime_claims",
                side_effect=parse,
            ),
            mock.patch.object(
                runtime_preview._runtime_budget,
                "acquire_warehouse_anomaly_runtime_slot",
                side_effect=acquire,
            ),
            mock.patch.object(
                runtime_preview._runtime_budget,
                "open_warehouse_anomaly_read_connection",
                side_effect=open_connection,
            ),
            mock.patch.object(
                runtime_preview._runtime_budget,
                "run_warehouse_anomaly_read_transaction",
                side_effect=transaction,
            ),
            mock.patch.object(
                runtime_preview._runtime_access,
                "_authorize_warehouse_anomaly_runtime_access",
                side_effect=authorize,
            ),
            mock.patch.object(
                runtime_preview._runtime_access,
                "_resolve_warehouse_anomaly_runtime_artifact",
                side_effect=resolve,
            ),
            mock.patch.object(runtime_preview, "_prepare", side_effect=prepare),
            mock.patch.object(runtime_preview, "_collect", side_effect=collect),
            mock.patch.object(runtime_preview, "_finalize", side_effect=finalize),
            mock.patch.object(runtime_preview, "_validate", side_effect=validate),
            mock.patch.object(runtime_preview, "_project", side_effect=project),
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], \
                patches[5], patches[6], patches[7], patches[8], patches[9], \
                patches[10]:
            result = _run_runtime_preview(
                _DB_CONFIG,
                _AUTHENTICATION,
                company_mode="company",
                company_id="4",
                body=_BODY,
            )

        self.assertIs(result, public)
        self.assertEqual(events, [
            "parse",
            "acquire",
            "open",
            "transaction",
            "authorize",
            "artifact",
            "prepare",
            "collect",
            "outer_guard",
            "transaction_cleanup",
            "outer_guard",
            "finalize",
            "validate",
            "project",
            "outer_guard",
            "release",
        ])
        self.assertEqual(lease.release_calls, 1)

    def test_auth_artifact_and_preparation_business_outcomes_wait_for_cleanup(self):
        cases = (
            (
                "auth",
                "warehouse_anomaly_runtime_authentication_required",
                "warehouse_anomaly_runtime_authentication_required",
            ),
            (
                "artifact",
                "warehouse_anomaly_runtime_resource_not_found",
                "warehouse_anomaly_runtime_resource_not_found",
            ),
            (
                "artifact",
                "warehouse_anomaly_runtime_artifact_invalid",
                "warehouse_anomaly_runtime_artifact_invalid",
            ),
            (
                "prepare",
                "warehouse_anomaly_content_selection_invalid",
                "warehouse_anomaly_runtime_resource_not_found",
            ),
            (
                "prepare",
                "warehouse_anomaly_content_stored_readiness_blocked",
                "warehouse_anomaly_runtime_resource_not_found",
            ),
            (
                "prepare",
                "warehouse_anomaly_content_contract_invalid",
                "warehouse_anomaly_runtime_artifact_invalid",
            ),
        )
        for stage, source_code, expected_code in cases:
            events = []
            lease = _Lease(events)
            claims = self._claims()
            cursor = object()
            finalizer = mock.Mock(
                side_effect=AssertionError("business outcome finalized"),
            )
            project = mock.Mock(
                side_effect=AssertionError("business outcome projected"),
            )

            def fail_stage(name):
                if name != stage:
                    return None
                if name == "prepare":
                    raise content_contract.WarehouseAnomalyContentError(
                        source_code,
                    )
                runtime_contract._fail(source_code)

            def authorize(_cursor, _claims):
                events.append("authorize")
                fail_stage("auth")

            def resolve(_cursor, _claims):
                events.append("artifact")
                fail_stage("artifact")
                return {
                    "combinedReport": {},
                    "selected": {},
                }

            def prepare(_report, _selected):
                events.append("prepare")
                fail_stage("prepare")
                return object()

            def transaction(_connection, _lease, read):
                events.append("transaction")
                snapshot = read(cursor)
                events.append("transaction_cleanup")
                return snapshot

            with self.subTest(stage=stage, source_code=source_code):
                with mock.patch.object(
                    runtime_preview._runtime_contract,
                    "_parse_warehouse_anomaly_runtime_claims",
                    return_value=claims,
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "acquire_warehouse_anomaly_runtime_slot",
                    return_value=lease,
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "open_warehouse_anomaly_read_connection",
                    return_value=object(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "run_warehouse_anomaly_read_transaction",
                    side_effect=transaction,
                ), mock.patch.object(
                    runtime_preview._runtime_access,
                    "_authorize_warehouse_anomaly_runtime_access",
                    side_effect=authorize,
                ), mock.patch.object(
                    runtime_preview._runtime_access,
                    "_resolve_warehouse_anomaly_runtime_artifact",
                    side_effect=resolve,
                ), mock.patch.object(
                    runtime_preview, "_prepare", side_effect=prepare,
                ), mock.patch.object(
                    runtime_preview, "_finalize", finalizer,
                ), mock.patch.object(
                    runtime_preview, "_project", project,
                ):
                    self._assert_fixed(
                        expected_code,
                        lambda: _run_runtime_preview(
                            _DB_CONFIG,
                            _AUTHENTICATION,
                            company_mode="company",
                            company_id="4",
                            body=_BODY,
                        ),
                    )

                self.assertIn("transaction_cleanup", events)
                self.assertEqual(events[-2:], ["outer_guard", "release"])
                self.assertEqual(lease.release_calls, 1)
                finalizer.assert_not_called()
                project.assert_not_called()

    def test_contract_failure_inside_snapshot_is_primary_and_nonleaking(self):
        events = []
        lease = _Lease(events)
        claims = self._claims()
        secret = "PRIVATE-METADATA-DETAIL"

        def transaction(_connection, _lease, read):
            try:
                return read(object())
            finally:
                events.append("transaction_cleanup")

        with mock.patch.object(
            runtime_preview._runtime_contract,
            "_parse_warehouse_anomaly_runtime_claims",
            return_value=claims,
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "acquire_warehouse_anomaly_runtime_slot",
            return_value=lease,
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "open_warehouse_anomaly_read_connection",
            return_value=object(),
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "run_warehouse_anomaly_read_transaction",
            side_effect=transaction,
        ), mock.patch.object(
            runtime_preview._runtime_access,
            "_authorize_warehouse_anomaly_runtime_access",
            side_effect=lambda *_: runtime_contract._fail(
                "warehouse_anomaly_runtime_contract_invalid",
            ),
        ):
            self._assert_fixed(
                "warehouse_anomaly_runtime_contract_invalid",
                lambda: _run_runtime_preview(
                    _DB_CONFIG,
                    _AUTHENTICATION,
                    company_mode="company",
                    company_id="4",
                    body=_BODY,
                ),
                secrets=(secret,),
            )

        self.assertEqual(events, ["transaction_cleanup", "release"])
        self.assertEqual(lease.release_calls, 1)

    def test_primary_transaction_errors_skip_finalization_and_keep_codes(self):
        codes = (
            "warehouse_anomaly_runtime_read_failed",
            "warehouse_anomaly_runtime_rollback_failed",
            "warehouse_anomaly_runtime_cleanup_failed",
            "warehouse_anomaly_runtime_deadline_exceeded",
        )
        for code in codes:
            events = []
            lease = _Lease(events)
            finalizer = mock.Mock(
                side_effect=AssertionError("failed transaction finalized"),
            )
            error = runtime_budget._WarehouseAnomalyRuntimeError(code)
            with self.subTest(code=code):
                with mock.patch.object(
                    runtime_preview._runtime_contract,
                    "_parse_warehouse_anomaly_runtime_claims",
                    return_value=self._claims(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "acquire_warehouse_anomaly_runtime_slot",
                    return_value=lease,
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "open_warehouse_anomaly_read_connection",
                    return_value=object(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "run_warehouse_anomaly_read_transaction",
                    side_effect=error,
                ), mock.patch.object(
                    runtime_preview, "_finalize", finalizer,
                ):
                    self._assert_fixed(
                        code,
                        lambda: _run_runtime_preview(
                            _DB_CONFIG,
                            _AUTHENTICATION,
                            company_mode="company",
                            company_id="4",
                            body=_BODY,
                        ),
                    )
                self.assertEqual(lease.release_calls, 1)
                finalizer.assert_not_called()

    def test_outer_deadline_finalizer_release_and_control_precedence(self):
        deadline = runtime_budget._WarehouseAnomalyRuntimeError(
            "warehouse_anomaly_runtime_deadline_exceeded",
        )
        cleanup = RuntimeError("PRIVATE-RELEASE-DETAIL")
        cases = (
            (
                "post_cleanup_deadline_then_release_failure",
                (deadline,),
                None,
                cleanup,
                "warehouse_anomaly_runtime_cleanup_failed",
            ),
            (
                "finalizer_failure_before_release_failure",
                (),
                RuntimeError("PRIVATE-FINALIZER-DETAIL"),
                cleanup,
                "warehouse_anomaly_runtime_contract_invalid",
            ),
        )
        for name, guards, finalizer_error, release_error, expected in cases:
            lease = _Lease(
                [], guards=guards, release_error=release_error,
            )
            snapshot = runtime_preview._RuntimeSnapshot(
                object(), object(), None,
            )
            with self.subTest(name=name):
                with mock.patch.object(
                    runtime_preview._runtime_contract,
                    "_parse_warehouse_anomaly_runtime_claims",
                    return_value=self._claims(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "acquire_warehouse_anomaly_runtime_slot",
                    return_value=lease,
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "open_warehouse_anomaly_read_connection",
                    return_value=object(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "run_warehouse_anomaly_read_transaction",
                    return_value=snapshot,
                ), mock.patch.object(
                    runtime_preview,
                    "_finalize",
                    side_effect=finalizer_error,
                ):
                    self._assert_fixed(
                        expected,
                        lambda: _run_runtime_preview(
                            _DB_CONFIG,
                            _AUTHENTICATION,
                            company_mode="company",
                            company_id="4",
                            body=_BODY,
                        ),
                        secrets=(
                            "PRIVATE-RELEASE-DETAIL",
                            "PRIVATE-FINALIZER-DETAIL",
                        ),
                    )
                self.assertEqual(lease.release_calls, 1)

        controls = (KeyboardInterrupt(), SystemExit(), GeneratorExit())
        for control in controls:
            lease = _Lease([], release_error=RuntimeError("PRIVATE-RELEASE"))
            snapshot = runtime_preview._RuntimeSnapshot(
                object(), object(), None,
            )
            with self.subTest(control=type(control).__name__):
                with mock.patch.object(
                    runtime_preview._runtime_contract,
                    "_parse_warehouse_anomaly_runtime_claims",
                    return_value=self._claims(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "acquire_warehouse_anomaly_runtime_slot",
                    return_value=lease,
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "open_warehouse_anomaly_read_connection",
                    return_value=object(),
                ), mock.patch.object(
                    runtime_preview._runtime_budget,
                    "run_warehouse_anomaly_read_transaction",
                    return_value=snapshot,
                ), mock.patch.object(
                    runtime_preview, "_finalize", side_effect=control,
                ):
                    captured = None
                    try:
                        _run_runtime_preview(
                            _DB_CONFIG,
                            _AUTHENTICATION,
                            company_mode="company",
                            company_id="4",
                            body=_BODY,
                        )
                    except BaseException as error:
                        captured = error
                self.assertIs(captured, control)
                self.assertEqual(lease.release_calls, 1)

    def test_current_validation_deadline_is_detected_before_cleanup(self):
        events = []
        deadline = runtime_budget._WarehouseAnomalyRuntimeError(
            "warehouse_anomaly_runtime_deadline_exceeded",
        )
        lease = _Lease(events, guards=(deadline,))
        claims = self._claims()

        def transaction(_connection, _lease, read):
            try:
                return read(object())
            finally:
                events.append("transaction_cleanup")

        with mock.patch.object(
            runtime_preview._runtime_contract,
            "_parse_warehouse_anomaly_runtime_claims",
            return_value=claims,
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "acquire_warehouse_anomaly_runtime_slot",
            return_value=lease,
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "open_warehouse_anomaly_read_connection",
            return_value=object(),
        ), mock.patch.object(
            runtime_preview._runtime_budget,
            "run_warehouse_anomaly_read_transaction",
            side_effect=transaction,
        ), mock.patch.object(
            runtime_preview._runtime_access,
            "_authorize_warehouse_anomaly_runtime_access",
            return_value=claims,
        ), mock.patch.object(
            runtime_preview._runtime_access,
            "_resolve_warehouse_anomaly_runtime_artifact",
            return_value={"combinedReport": {}, "selected": {}},
        ), mock.patch.object(
            runtime_preview, "_prepare", return_value=object(),
        ), mock.patch.object(
            runtime_preview, "_collect", return_value=object(),
        ), mock.patch.object(
            runtime_preview,
            "_finalize",
            side_effect=AssertionError("expired current data finalized"),
        ):
            self._assert_fixed(
                "warehouse_anomaly_runtime_deadline_exceeded",
                lambda: _run_runtime_preview(
                    _DB_CONFIG,
                    _AUTHENTICATION,
                    company_mode="company",
                    company_id="4",
                    body=_BODY,
                ),
            )

        self.assertEqual(events, [
            "outer_guard",
            "transaction_cleanup",
            "release",
        ])

    def test_real_private_composition_uses_one_cursor_and_exact_18_statements(self):
        stored, selection, a7_result_sets = _real_a7_case()
        source = stored["source"]
        payload = {
            "schemaVersion": 1,
            "eventType": "estimate.version_activated",
            "companyId": source["companyId"],
            "projectId": source["projectId"],
            "estimateId": source["estimateId"],
            "sourceRevision": source["sourceRevision"],
        }
        plan = build_estimate_revision_impact_job_plan(
            source_from_job_payload(payload),
        )
        artifact = _artifact_row(
            company_id=source["companyId"],
            project_id=source["projectId"],
            project_scope_id=source["projectId"],
            idempotency_key=plan.idempotency_key,
            correlation_id=plan.correlation_id,
            payload_json=payload,
            result_json=json.loads(json.dumps(stored, ensure_ascii=False)),
            payload_bytes=len(json.dumps(payload).encode("utf-8")),
            result_bytes=len(
                json.dumps(stored, ensure_ascii=False).encode("utf-8")
            ),
        )
        settings = dict(runtime_budget._EXPECTED_SETTINGS_ROW)
        result_sets = [
            [settings],
            [{"actor_count": 1, "project_exists": True}],
            [artifact],
            *(
                [dict(row) for row in rows]
                for rows in a7_result_sets
            ),
        ]
        raw_cursor = _RawCursor(result_sets)
        connection = _Connection(raw_cursor)
        connect_calls = []

        def connect(**kwargs):
            connect_calls.append(dict(kwargs))
            return connection

        body = {
            "projectId": source["projectId"],
            "jobId": artifact["job_id"],
            "selected": dict(selection),
        }
        result = _run_runtime_preview(
            _DB_CONFIG,
            _AUTHENTICATION,
            company_mode="company",
            company_id=str(source["companyId"]),
            body=body,
            clock=_Clock(),
            connect=connect,
        )

        self.assertEqual(result["warehouseAnomalyRuntimeVersion"], 1)
        self.assertEqual(result["state"], "preview_ready")
        self.assertEqual(result["candidate"], {
            **selection,
            "recommendationCode": (
                content_contract._ANOMALY_RECOMMENDATION_RULES[
                    selection["anomalyCode"]
                ]
            ),
        })
        self.assertIs(result["readOnlyTransaction"], True)
        self.assertIs(result["rolledBack"], True)
        self.assertEqual(connection.close_calls, 1)
        self.assertEqual(raw_cursor.close_calls, 1)
        self.assertEqual(connection.cursor_calls, [{
            "cursor_factory": runtime_budget.psycopg2.extras.RealDictCursor,
        }])
        self.assertEqual(len(connect_calls), 1)
        self.assertEqual(connect_calls[0]["connect_timeout"], 5)
        self.assertEqual(
            connect_calls[0]["options"], runtime_budget._STARTUP_OPTIONS,
        )
        self.assertEqual(raw_cursor.fetchall_calls, 17)
        self.assertEqual(len(raw_cursor.execute_calls), 19)
        guarded = raw_cursor.execute_calls[:-1]
        self.assertEqual(len(guarded), 18)
        self.assertEqual(guarded[0], (runtime_budget._BEGIN_SQL, ()))
        self.assertEqual(guarded[1], (
            " ".join(runtime_budget._SETTINGS_SQL.split()),
            runtime_budget._SETTINGS_PARAMS,
        ))
        self.assertIn("FROM public.user_sessions session", guarded[2][0])
        self.assertIn("FROM public.agent_jobs job", guarded[3][0])
        self.assertEqual(
            raw_cursor.execute_calls[-1],
            (runtime_budget._ROLLBACK_SQL, ()),
        )
        for sql, _params in guarded[1:]:
            upper = sql.upper()
            for forbidden in (
                "INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE ",
                "DROP ", "FOR UPDATE", "ADVISORY", "COMMIT",
            ):
                self.assertNotIn(forbidden, upper)
        self.assertEqual(raw_cursor.result_sets, [])

        next_lease = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
            _Clock(), wait_seconds=0,
        )
        next_lease.release()

    def test_static_import_and_closed_call_graph_inventory_is_exact(self):
        source_path = Path(runtime_preview.__file__).resolve()
        source = source_path.read_text(encoding="utf-8")
        imports = []
        tree = compile(source, str(source_path), "exec", ast.PyCF_ONLY_AST)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        self.assertEqual(imports, [
            "time",
            "typing",
            "psycopg2",
            "backend.features.warehouse_recommendation_preview",
            "backend.features.warehouse_recommendation_preview",
            "backend.features.warehouse_recommendation_preview",
            "backend.features.warehouse_recommendation_preview.content_contract",
            "backend.features.warehouse_recommendation_preview.content_preview",
        ])
        callback_source = inspect.getsource(
            runtime_preview._read_runtime_snapshot,
        )
        expected_order = (
            "_authorize_warehouse_anomaly_runtime_access",
            "_resolve_warehouse_anomaly_runtime_artifact",
            "_prepare(",
            "_collect(",
            "lease.guard(",
        )
        offsets = [callback_source.index(value) for value in expected_order]
        self.assertEqual(offsets, sorted(offsets))
        for forbidden in (
            "run_warehouse_anomaly_content_preview",
            "run_supply_warehouse_impact_audit",
            "run_combined_impact_audit",
            "collect_combined_impact_audit",
            "backend.db",
            "get_db",
            "DB_CONFIG",
            ".execute(",
            ".fetchall(",
            ".cursor(",
            ".rollback(",
            ".commit(",
            ".close(",
            "Thread",
            "Executor",
            "requests",
            "httpx",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(runtime_preview.__all__, [])

        package_root = source_path.parent
        root = package_root.parents[2]
        expected_hashes = {
            package_root / "__init__.py": (
                "d30babfeb425141af2fbf645be82eef358b6dea7d213b6d6b23cef3e7c551fea"
            ),
            package_root / "content_preview.py": (
                "6bf1b385b833bd2f02b16e066fbb41a7ea6aa9566cb4ce4c6eeff8d5dea9da64"
            ),
            root / "backend/db.py": (
                "7e53bc3f1bed6481c9579dc241768b948fc22b37ec5d0809505022e62e2d750f"
            ),
            root / "backend/main.py": (
                "a6a7c8dd433384a31fafcc1cf1e84d8e11a5719b81865c1e0c3c964800160b99"
            ),
        }
        self.assertEqual({
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in expected_hashes
        }, expected_hashes)
        self.assertIn(
            "runtime_preview",
            (root / "backend/main.py").read_text(encoding="utf-8"),
        )
        self.assertNotIn(
            "runtime_preview",
            (
                root / "backend/features/agent_jobs/handler_registry.py"
            ).read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
