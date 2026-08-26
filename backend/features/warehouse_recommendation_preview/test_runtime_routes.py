import asyncio
import ast
import copy
import hashlib
import inspect
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.features.warehouse_recommendation_preview.runtime_routes as runtime_routes
from backend.auth import CookieSessionAuthenticationError
from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
    source_from_job_payload,
)
from backend.features.warehouse_recommendation_preview import content_contract
from backend.features.warehouse_recommendation_preview import runtime_access
from backend.features.warehouse_recommendation_preview import runtime_budget
from backend.features.warehouse_recommendation_preview import runtime_contract
from backend.features.warehouse_recommendation_preview import runtime_preview
from backend.features.warehouse_recommendation_preview.test_content_preview import (
    _real_a7_case,
)
from backend.features.warehouse_recommendation_preview.test_runtime_access import (
    _artifact_row,
)
from backend.features.warehouse_recommendation_preview.test_runtime_preview import (
    _Clock,
    _Connection,
    _RawCursor,
)


REGISTER = runtime_routes.register_warehouse_anomaly_preview_routes
PATH = "/warehouse-anomaly-previews"
AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
BODY = {
    "projectId": 9,
    "jobId": 123,
    "selected": {
        "subjectKind": "warehouseInvoice",
        "subjectId": 456,
        "anomalyCode": "warehouse_invoice_project_mismatch",
    },
}
CANDIDATE = {
    **BODY["selected"],
    "recommendationCode": "review_warehouse_invoice_lineage",
}
PUBLIC_RESULT = {
    "warehouseAnomalyRuntimeVersion": 1,
    "ok": True,
    "dryRun": True,
    "writesAttempted": 0,
    "previewOnly": True,
    "stockMovementAllowed": False,
    "inventoryAdjustmentAllowed": False,
    "applyAllowed": False,
    "state": "preview_ready",
    "candidate": CANDIDATE,
    "content": content_contract._fixed_content(CANDIDATE),
    "blockers": [],
    "readOnlyTransaction": True,
    "rolledBack": True,
}
DB_CONFIG = {
    "dbname": "db",
    "user": "user",
    "password": "password",
    "host": "/private/socket",
    "port": "55432",
}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAIN_PATH = PROJECT_ROOT / "backend" / "main.py"
NGINX_PATH = PROJECT_ROOT / "ops-nginx-stroyka-public-api.conf"
FEATURE_ENV = "WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED"
ALLOWLIST_ENV = "WAREHOUSE_ANOMALY_PREVIEW_COMPANY_IDS"
REGISTER_NAME = "register_warehouse_anomaly_preview_routes"


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path, **kwargs):
        def decorate(func):
            self.routes[("POST", path)] = (func, dict(kwargs))
            return func

        return decorate


class DependencyMap(dict):
    def __init__(self, values):
        super().__init__(values)
        self.read_keys = []

    def __getitem__(self, key):
        self.read_keys.append(key)
        return super().__getitem__(key)


class PoisonCodeError(RuntimeError):
    @property
    def code(self):
        raise RuntimeError("PRIVATE CODE PROPERTY")


class RouteHarness:
    def __init__(
        self,
        *,
        result=None,
        authentication_error=None,
        authentication_result=None,
        reject_authorization=False,
        runtime_error=None,
        allowed_company_ids=frozenset({4}),
        telemetry=None,
    ):
        self.authentication_calls = []
        self.runtime_calls = []
        self.result = dict(PUBLIC_RESULT if result is None else result)
        self.authentication_error = authentication_error
        self.authentication_result = (
            dict(AUTHENTICATION)
            if authentication_result is None
            else authentication_result
        )
        self.reject_authorization = reject_authorization
        self.runtime_error = runtime_error
        self.app = FastAPI()
        dependencies = {
            "enabled": True,
            "allowed_company_ids": allowed_company_ids,
            "db_config": DB_CONFIG,
            "build_cookie_session_authentication": self.authenticate,
            "parse_warehouse_anomaly_runtime_claims": (
                runtime_contract._parse_warehouse_anomaly_runtime_claims
            ),
            "run_warehouse_anomaly_runtime_preview": self.run_preview,
        }
        if telemetry is not None:
            dependencies["telemetry"] = telemetry
        REGISTER(self.app, dependencies)
        self.client = TestClient(self.app)

    def authenticate(
        self,
        request,
        authorization=None,
        csrf_token=None,
        *,
        require_csrf=True,
    ):
        self.authentication_calls.append((
            request.method,
            request.url.path,
            authorization,
            csrf_token,
            require_csrf,
        ))
        if self.authentication_error is not None:
            raise self.authentication_error
        if self.reject_authorization and authorization is not None:
            raise CookieSessionAuthenticationError(
                "cookie_session_authentication_required"
            )
        return self.authentication_result

    def run_preview(self, *args, **kwargs):
        self.runtime_calls.append((args, kwargs))
        if self.runtime_error is not None:
            raise self.runtime_error
        return dict(self.result)

    @staticmethod
    def headers(**overrides):
        headers = {
            "Cookie": "stroyka_session=" + "s" * 64,
            "X-CSRF-Token": "csrf-value",
            "X-Company-Id": "4",
            "X-Company-Mode": "company",
        }
        headers.update(overrides)
        return headers


class WarehouseAnomalyRuntimeRouteRegistrationTests(unittest.TestCase):
    def test_disabled_registration_reads_no_runtime_dependency(self):
        app = FakeApp()
        deps = DependencyMap({"enabled": False})

        self.assertIsNone(REGISTER(app, deps))

        self.assertEqual(app.routes, {})
        self.assertEqual(deps.read_keys, [])

    def test_invalid_allowlist_registers_nothing_before_dependencies(self):
        invalid_values = (
            None,
            set(),
            frozenset(),
            frozenset({True}),
            frozenset({0}),
            frozenset({9223372036854775808}),
            frozenset(range(1, 102)),
        )
        for allowed_company_ids in invalid_values:
            with self.subTest(allowed_company_ids=allowed_company_ids):
                app = FakeApp()
                deps = DependencyMap({
                    "enabled": True,
                    "allowed_company_ids": allowed_company_ids,
                })

                self.assertIsNone(REGISTER(app, deps))

                self.assertEqual(app.routes, {})
                self.assertEqual(deps.read_keys, [])

    def test_valid_configuration_registers_one_exact_post_route(self):
        app = FakeApp()
        no_call = lambda *_args, **_kwargs: None

        self.assertIsNone(REGISTER(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4, 17}),
            "db_config": {
                "dbname": "db",
                "user": "user",
                "password": "password",
                "host": "/private/socket",
                "port": "55432",
            },
            "build_cookie_session_authentication": no_call,
            "parse_warehouse_anomaly_runtime_claims": no_call,
            "run_warehouse_anomaly_runtime_preview": no_call,
        }))

        self.assertEqual(set(app.routes), {("POST", PATH)})

    def test_a94c_registration_keeps_package_private_and_route_write_free(self):
        project_root = Path(__file__).resolve().parents[3]
        main_path = project_root / "backend" / "main.py"
        package_path = Path(__file__).with_name("__init__.py")
        runtime_path = Path(runtime_routes.__file__)
        main_bytes = main_path.read_bytes()
        package_bytes = package_path.read_bytes()
        runtime_source = runtime_path.read_text(encoding="utf-8")

        self.assertEqual(
            hashlib.sha256(main_bytes).hexdigest(),
            "a51d3be8e1d6dc2e391c7b39cc604a12800804ad23ba1bd3e283134b4badc475",
        )
        self.assertEqual(
            hashlib.sha256(package_bytes).hexdigest(),
            "d30babfeb425141af2fbf645be82eef358b6dea7d213b6d6b23cef3e7c551fea",
        )
        self.assertIn(
            b"warehouse_recommendation_preview.runtime_routes", main_bytes,
        )
        self.assertIn(
            b"register_warehouse_anomaly_preview_routes", main_bytes,
        )
        self.assertNotIn(b"runtime_routes", package_bytes)
        self.assertEqual(runtime_routes.__all__, [])
        for forbidden in (
            "get_current_user",
            "get_db",
            ".execute(",
            ".commit(",
            "insert_audit",
            "log_api_error",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, runtime_source)


class WarehouseAnomalyRuntimeMainAndNginxContractTests(unittest.TestCase):
    @staticmethod
    def _main_tree():
        source = MAIN_PATH.read_text(encoding="utf-8")
        return source, ast.parse(source, filename=str(MAIN_PATH))

    @staticmethod
    def _function(tree, name):
        matches = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ]
        if len(matches) != 1:
            raise AssertionError(f"expected one {name} function")
        return matches[0]

    def test_main_allowlist_parser_is_exact_and_fail_closed(self):
        _source, tree = self._main_tree()
        parser_node = copy.deepcopy(self._function(
            tree, "_parse_warehouse_anomaly_preview_company_ids",
        ))
        module = ast.Module(body=[parser_node], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {}
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        parse = namespace[parser_node.name]

        self.assertEqual(parse("4"), frozenset({4}))
        self.assertEqual(parse("4,17"), frozenset({4, 17}))
        self.assertEqual(
            parse("9223372036854775807"),
            frozenset({9223372036854775807}),
        )
        invalid = (
            None, "", "1,1", "01", " 1", "1 ", "1,,2", "+1",
            "１", "9223372036854775808",
            ",".join(str(value) for value in range(1, 102)),
        )
        for value in invalid:
            with self.subTest(value=repr(value)[:100]):
                self.assertIsNone(parse(value))

    def test_main_runtime_import_and_registration_are_inside_both_gates(self):
        source, tree = self._main_tree()
        statements = []
        for statement in tree.body:
            contains_runtime = any(
                (
                    isinstance(node, ast.ImportFrom)
                    and (node.module or "").endswith(
                        "warehouse_recommendation_preview.runtime_routes"
                    )
                )
                or (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == REGISTER_NAME
                )
                for node in ast.walk(statement)
            )
            if contains_runtime:
                statements.append(statement)
        self.assertEqual(len(statements), 1)
        outer = statements[0]
        self.assertIsInstance(outer, ast.If)
        self.assertEqual(
            ast.unparse(outer.test),
            "os.getenv('WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED') == 'true'",
        )
        nested = [node for node in outer.body if isinstance(node, ast.If)]
        self.assertEqual(len(nested), 1)
        self.assertEqual(
            ast.unparse(nested[0].test),
            "warehouse_anomaly_preview_company_ids is not None",
        )
        rendered_nested = ast.unparse(nested[0])
        for required in (
            "warehouse_recommendation_preview.runtime_routes",
            "warehouse_recommendation_preview.runtime_contract",
            "warehouse_recommendation_preview.runtime_preview",
            "register_warehouse_anomaly_preview_routes",
            "parse_warehouse_anomaly_runtime_claims",
            "run_warehouse_anomaly_runtime_preview",
            "DB_CONFIG",
        ):
            self.assertIn(required, rendered_nested)
        register_calls = [
            node for node in ast.walk(nested[0])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == REGISTER_NAME
        ]
        self.assertEqual(len(register_calls), 1)
        dependency_dict = register_calls[0].args[1]
        self.assertIsInstance(dependency_dict, ast.Dict)
        dependencies = {
            key.value: value
            for key, value in zip(
                dependency_dict.keys, dependency_dict.values,
            )
        }
        self.assertEqual(set(dependencies), {
            "enabled", "allowed_company_ids", "db_config",
            "build_cookie_session_authentication",
            "parse_warehouse_anomaly_runtime_claims",
            "run_warehouse_anomaly_runtime_preview",
        })
        self.assertIs(dependencies["enabled"].value, True)
        expected_names = {
            "allowed_company_ids": "warehouse_anomaly_preview_company_ids",
            "db_config": "warehouse_anomaly_db_config",
            "build_cookie_session_authentication": (
                "build_cookie_session_authentication"
            ),
            "parse_warehouse_anomaly_runtime_claims": (
                "parse_warehouse_anomaly_runtime_claims"
            ),
            "run_warehouse_anomaly_runtime_preview": (
                "run_warehouse_anomaly_runtime_preview"
            ),
        }
        for key, name in expected_names.items():
            self.assertIsInstance(dependencies[key], ast.Name)
            self.assertEqual(dependencies[key].id, name)
        self.assertNotIn(
            "WAREHOUSE_ANOMALY_PREVIEW_COMPANY_IDS",
            rendered_nested,
        )

    def test_extracted_main_wiring_registers_only_exact_enabled_allowlist(self):
        _source, tree = self._main_tree()
        parser_node = copy.deepcopy(self._function(
            tree, "_parse_warehouse_anomaly_preview_company_ids",
        ))
        wiring = [
            copy.deepcopy(statement)
            for statement in tree.body
            if isinstance(statement, ast.If)
            and ast.unparse(statement.test) == (
                "os.getenv('WAREHOUSE_ANOMALY_PREVIEW_HTTP_ENABLED') "
                "== 'true'"
            )
        ]
        self.assertEqual(len(wiring), 1)
        module = ast.Module(
            body=[parser_node, wiring[0]], type_ignores=[],
        )
        ast.fix_missing_locations(module)
        compiled = compile(module, str(MAIN_PATH), "exec")
        cases = (
            (None, None, False),
            ("1", "4", False),
            ("TRUE", "4", False),
            ("true ", "4", False),
            ("true", None, False),
            ("true", "", False),
            ("true", "4,4", False),
            ("true", "04", False),
            ("true", "4,17", True),
        )
        for enabled, allowlist, expected_route in cases:
            with self.subTest(enabled=enabled, allowlist=allowlist):
                app = FakeApp()
                namespace = {
                    "os": os,
                    "app": app,
                    "build_cookie_session_authentication": object(),
                }
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(FEATURE_ENV, None)
                    os.environ.pop(ALLOWLIST_ENV, None)
                    if enabled is not None:
                        os.environ[FEATURE_ENV] = enabled
                    if allowlist is not None:
                        os.environ[ALLOWLIST_ENV] = allowlist
                    exec(compiled, namespace)
                self.assertEqual(
                    set(app.routes),
                    {("POST", PATH)} if expected_route else set(),
                )

    def test_api_error_middleware_skips_only_the_exact_preview_path(self):
        _source, tree = self._main_tree()
        helper = copy.deepcopy(self._function(
            tree, "_api_error_logging_enabled_for_path",
        ))
        middleware = copy.deepcopy(self._function(
            tree, "api_error_logging_middleware",
        ))
        middleware.decorator_list = []
        events = []

        def log_error(request, error=None, status_code=500):
            events.append((request.url.path, error, status_code))

        namespace = {
            "Request": object,
            "Response": lambda status_code: type(
                "Response", (), {"status_code": status_code},
            )(),
            "_log_api_error": log_error,
        }
        module = ast.Module(body=[helper, middleware], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(MAIN_PATH), "exec"), namespace)
        run = namespace["api_error_logging_middleware"]

        class Request:
            def __init__(self, path):
                self.url = type("URL", (), {"path": path})()

        async def response_503(_request):
            return type("Response", (), {"status_code": 503})()

        async def failure(_request):
            raise RuntimeError("PRIVATE")

        exact = Request(PATH)
        neighbor = Request(PATH + "/")
        self.assertEqual(
            asyncio.run(run(exact, response_503)).status_code, 503,
        )
        self.assertEqual(events, [])
        self.assertEqual(
            asyncio.run(run(neighbor, response_503)).status_code, 503,
        )
        self.assertEqual(events, [(PATH + "/", None, 503)])
        with self.assertRaisesRegex(RuntimeError, "PRIVATE"):
            asyncio.run(run(exact, failure))
        self.assertEqual(len(events), 1)
        with self.assertRaisesRegex(RuntimeError, "PRIVATE"):
            asyncio.run(run(neighbor, failure))
        self.assertEqual(events[-1][0], PATH + "/")
        self.assertEqual(events[-1][2], 500)

    def test_local_nginx_contract_has_exact_capacity_and_json_errors(self):
        source = NGINX_PATH.read_text(encoding="utf-8")
        exact_fragments = (
            "limit_req_zone $binary_remote_addr "
            "zone=warehouse_anomaly_preview_limit:10m rate=6r/m;",
            "limit_conn_zone $server_name "
            "zone=warehouse_anomaly_preview_conn:10m;",
            "location = /warehouse-anomaly-previews {",
            "limit_req zone=warehouse_anomaly_preview_limit burst=1 nodelay;",
            "limit_conn warehouse_anomaly_preview_conn 1;",
            "limit_req_status 429;",
            "limit_conn_status 429;",
            "client_max_body_size 4k;",
            "proxy_connect_timeout 6s;",
            "proxy_send_timeout 10s;",
            "proxy_read_timeout 45s;",
            "error_page 413 = @warehouse_anomaly_preview_413;",
            "error_page 429 = @warehouse_anomaly_preview_429;",
            "location @warehouse_anomaly_preview_413 {",
            "location @warehouse_anomaly_preview_429 {",
            "return 413 '{\"detail\":\"warehouse_anomaly_preview_request_too_large\"}';",
            "return 429 '{\"detail\":\"warehouse_anomaly_preview_busy\"}';",
            "add_header Retry-After 10 always;",
            "add_header Cache-Control \"no-store, max-age=0\" always;",
            "add_header Pragma \"no-cache\" always;",
            "add_header Vary \"Cookie, X-Company-Id, X-Company-Mode\" always;",
        )
        for fragment in exact_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, source)
        self.assertEqual(
            source.count("location = /warehouse-anomaly-previews {"), 1,
        )
        self.assertEqual(
            source.count("zone=warehouse_anomaly_preview_limit:10m"), 1,
        )
        self.assertEqual(
            source.count("zone=warehouse_anomaly_preview_conn:10m"), 1,
        )
        self.assertEqual(source.count(
            'add_header Cache-Control "no-store, max-age=0" always;'
        ), 2)
        self.assertEqual(source.count(
            'add_header Pragma "no-cache" always;'
        ), 2)
        self.assertEqual(source.count(
            'add_header Vary "Cookie, X-Company-Id, X-Company-Mode" always;'
        ), 2)
        self.assertEqual(source.count("add_header Retry-After 10 always;"), 1)
        for private in (
            "$cookie_", "$http_x_csrf", "$http_x_company",
            "projectId", "jobId", "subjectId", "anomalyCode",
        ):
            self.assertNotIn(private, source)


class WarehouseAnomalyRuntimeRouteContractTests(unittest.TestCase):
    def assert_fixed_error(self, response, status, detail):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json(), {"detail": detail})
        self.assertEqual(
            response.headers.get("cache-control"), "no-store, max-age=0",
        )
        self.assertEqual(response.headers.get("pragma"), "no-cache")
        self.assertEqual(
            response.headers.get("vary"),
            "Cookie, X-Company-Id, X-Company-Mode",
        )
        self.assertNotIn("etag", response.headers)

    def test_real_runner_keeps_exact_transaction_inventory_and_aggregate_metrics(self):
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
        result_sets = [
            [dict(runtime_budget._EXPECTED_SETTINGS_ROW)],
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

        def run_preview(*args, **kwargs):
            return runtime_preview.run_warehouse_anomaly_runtime_preview(
                *args,
                **kwargs,
                clock=_Clock(),
                connect=connect,
            )

        class TelemetryClock:
            def __init__(self):
                self.values = iter((100.0, 100.5))

            def __call__(self):
                return next(self.values)

        telemetry = runtime_routes._WarehouseAnomalyPreviewTelemetry(
            TelemetryClock(),
        )
        app = FastAPI()
        REGISTER(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({source["companyId"]}),
            "db_config": DB_CONFIG,
            "build_cookie_session_authentication": (
                lambda *_args, **_kwargs: dict(AUTHENTICATION)
            ),
            "parse_warehouse_anomaly_runtime_claims": (
                runtime_contract._parse_warehouse_anomaly_runtime_claims
            ),
            "run_warehouse_anomaly_runtime_preview": run_preview,
            "telemetry": telemetry,
        })
        body = {
            "projectId": source["projectId"],
            "jobId": artifact["job_id"],
            "selected": dict(selection),
        }

        response = TestClient(app).post(
            PATH,
            headers={
                **RouteHarness.headers(),
                "X-Company-Id": str(source["companyId"]),
            },
            json=body,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), runtime_routes._PUBLIC_FIELDS)
        self.assertEqual(response.json()["candidate"], {
            **selection,
            "recommendationCode": (
                content_contract._ANOMALY_RECOMMENDATION_RULES[
                    selection["anomalyCode"]
                ]
            ),
        })
        rendered_response = response.text
        for private_field in (
            "combinedReport", "sourceRevision", "sessionHash",
            "idempotencyKey", "correlationId", "payloadJson", "resultJson",
        ):
            self.assertNotIn(private_field, rendered_response)
        self.assertEqual(len(connect_calls), 1)
        self.assertEqual(connect_calls[0]["connect_timeout"], 5)
        self.assertEqual(
            connect_calls[0]["options"], runtime_budget._STARTUP_OPTIONS,
        )
        self.assertEqual(connection.close_calls, 1)
        self.assertFalse(hasattr(connection, "commit"))
        self.assertEqual(raw_cursor.close_calls, 1)
        self.assertEqual(connection.cursor_calls, [{
            "cursor_factory": runtime_budget.psycopg2.extras.RealDictCursor,
        }])
        self.assertEqual(raw_cursor.fetchall_calls, 17)
        self.assertEqual(len(raw_cursor.execute_calls), 19)
        self.assertEqual(
            raw_cursor.execute_calls[-1],
            (runtime_budget._ROLLBACK_SQL, ()),
        )
        guarded = raw_cursor.execute_calls[:-1]
        self.assertEqual(len(guarded), 18)
        for sql, _params in guarded[1:]:
            upper = sql.upper()
            for forbidden in (
                "INSERT ", "UPDATE ", "DELETE ", "ALTER ", "CREATE ",
                "DROP ", "FOR UPDATE", "ADVISORY", "COMMIT",
            ):
                self.assertNotIn(forbidden, upper)
        self.assertEqual(raw_cursor.result_sets, [])
        self.assertEqual(telemetry.snapshot(), {
            "inFlight": 0,
            "outcomes": {
                "ok": 1,
                "busy": 0,
                "deadline": 0,
                "unavailable": 0,
            },
            "durations": {
                "le1s": 1,
                "le5s": 0,
                "le15s": 0,
                "le35s": 0,
                "gt35s": 0,
            },
        })

    def test_held_runtime_slot_returns_busy_without_a_second_connection(self):
        class TelemetryClock:
            def __init__(self):
                self.values = iter((200.0, 201.5))

            def __call__(self):
                return next(self.values)

        telemetry = runtime_routes._WarehouseAnomalyPreviewTelemetry(
            TelemetryClock(),
        )
        connect_calls = []

        def connect(**kwargs):
            connect_calls.append(dict(kwargs))
            raise AssertionError("busy request opened another connection")

        def run_preview(*args, **kwargs):
            return runtime_preview.run_warehouse_anomaly_runtime_preview(
                *args,
                **kwargs,
                clock=_Clock(),
                connect=connect,
            )

        app = FastAPI()
        REGISTER(app, {
            "enabled": True,
            "allowed_company_ids": frozenset({4}),
            "db_config": DB_CONFIG,
            "build_cookie_session_authentication": (
                lambda *_args, **_kwargs: dict(AUTHENTICATION)
            ),
            "parse_warehouse_anomaly_runtime_claims": (
                runtime_contract._parse_warehouse_anomaly_runtime_claims
            ),
            "run_warehouse_anomaly_runtime_preview": run_preview,
            "telemetry": telemetry,
        })
        holder = runtime_budget.acquire_warehouse_anomaly_runtime_slot(
            _Clock(), wait_seconds=0,
        )
        try:
            response = TestClient(app).post(
                PATH, headers=RouteHarness.headers(), json=BODY,
            )
        finally:
            holder.release()

        self.assert_fixed_error(
            response, 429, "warehouse_anomaly_preview_busy",
        )
        self.assertEqual(response.headers.get("retry-after"), "10")
        self.assertEqual(connect_calls, [])
        self.assertEqual(telemetry.snapshot(), {
            "inFlight": 0,
            "outcomes": {
                "ok": 0,
                "busy": 1,
                "deadline": 0,
                "unavailable": 0,
            },
            "durations": {
                "le1s": 0,
                "le5s": 1,
                "le15s": 0,
                "le35s": 0,
                "gt35s": 0,
            },
        })

    def test_telemetry_has_only_fixed_aggregate_outcomes_and_buckets(self):
        class TelemetryClock:
            def __init__(self):
                self.values = iter((
                    0.0, 0.1, 0.5, 3.1,
                    10.0, 20.0,
                    30.0, 60.0,
                    70.0, 106.0,
                ))

            def __call__(self):
                return next(self.values)

        telemetry = runtime_routes._WarehouseAnomalyPreviewTelemetry(
            TelemetryClock(),
        )
        starts = [telemetry.begin(), telemetry.begin()]
        self.assertEqual(telemetry.snapshot()["inFlight"], 1)
        telemetry.finish(starts[0], "ok")
        self.assertEqual(telemetry.snapshot()["inFlight"], 1)
        telemetry.finish(starts[1], "busy")
        for outcome in ("deadline", "unavailable", "PRIVATE"):
            telemetry.finish(telemetry.begin(), outcome)

        snapshot = telemetry.snapshot()
        self.assertEqual(snapshot, {
            "inFlight": 0,
            "outcomes": {
                "ok": 1,
                "busy": 1,
                "deadline": 1,
                "unavailable": 2,
            },
            "durations": {
                "le1s": 1,
                "le5s": 1,
                "le15s": 1,
                "le35s": 1,
                "gt35s": 1,
            },
        })
        rendered = json.dumps(snapshot, sort_keys=True)
        for private in (
            "session", "actor", "company", "project", "job",
            "candidate", "anomaly", "source", "hash", "PRIVATE",
        ):
            self.assertNotIn(private, rendered)
        telemetry_source = "\n".join(
            inspect.getsource(method)
            for method in (
                runtime_routes._WarehouseAnomalyPreviewTelemetry.begin,
                runtime_routes._WarehouseAnomalyPreviewTelemetry.finish,
                runtime_routes._WarehouseAnomalyPreviewTelemetry.snapshot,
            )
        ).lower()
        for forbidden_label in (
            "session", "actor", "company", "project", "job",
            "candidate", "anomaly", "source", "hash", "dependency",
        ):
            self.assertNotIn(forbidden_label, telemetry_source)

    def test_fixed_runtime_failures_feed_only_fixed_telemetry_outcomes(self):
        cases = (
            (
                runtime_budget._WarehouseAnomalyRuntimeError(
                    runtime_budget._DEADLINE_EXCEEDED,
                ),
                "deadline",
            ),
            (RuntimeError("PRIVATE_DSN SELECT 123"), "unavailable"),
        )
        for error, expected_outcome in cases:
            with self.subTest(expected_outcome=expected_outcome):
                class TelemetryClock:
                    def __init__(self):
                        self.values = iter((300.0, 300.25))

                    def __call__(self):
                        return next(self.values)

                telemetry = runtime_routes._WarehouseAnomalyPreviewTelemetry(
                    TelemetryClock(),
                )
                harness = RouteHarness(
                    runtime_error=error,
                    telemetry=telemetry,
                )

                response = harness.client.post(
                    PATH, headers=harness.headers(), json=BODY,
                )

                self.assert_fixed_error(
                    response, 503, "warehouse_anomaly_preview_unavailable",
                )
                self.assertNotIn("PRIVATE", response.text)
                self.assertNotIn("SELECT", response.text)
                snapshot = telemetry.snapshot()
                self.assertEqual(snapshot["inFlight"], 0)
                self.assertEqual(snapshot["outcomes"][expected_outcome], 1)
                self.assertEqual(sum(snapshot["outcomes"].values()), 1)
                self.assertEqual(sum(snapshot["durations"].values()), 1)

    def test_media_type_and_company_headers_fail_before_authentication(self):
        cases = (
            ({}, 415, "warehouse_anomaly_preview_media_type_invalid"),
            (
                {"Content-Type": "text/plain"},
                415,
                "warehouse_anomaly_preview_media_type_invalid",
            ),
            (
                {"Content-Type": "application/json", "X-Company-Mode": "all"},
                422,
                "warehouse_anomaly_preview_request_invalid",
            ),
            (
                {"Content-Type": "application/json", "X-Company-Id": "04"},
                422,
                "warehouse_anomaly_preview_request_invalid",
            ),
        )
        for overrides, status, detail in cases:
            with self.subTest(overrides=overrides):
                harness = RouteHarness()
                headers = harness.headers(**overrides)
                if "Content-Type" not in overrides:
                    headers.pop("Content-Type", None)
                response = harness.client.post(
                    PATH, headers=headers, content=b"{}",
                )

                self.assert_fixed_error(response, status, detail)
                self.assertEqual(harness.authentication_calls, [])
                self.assertEqual(harness.runtime_calls, [])

    def test_cookie_and_csrf_errors_are_fixed_and_precede_body(self):
        cases = (
            (
                "cookie_session_authentication_required",
                401,
                "warehouse_anomaly_preview_authentication_required",
            ),
            (
                "cookie_session_csrf_invalid",
                403,
                "warehouse_anomaly_preview_request_forbidden",
            ),
        )
        for private_code, status, public_code in cases:
            with self.subTest(private_code=private_code):
                harness = RouteHarness(authentication_error=(
                    CookieSessionAuthenticationError(private_code)
                ))
                headers = harness.headers()
                headers["Content-Type"] = "application/json"
                response = harness.client.post(
                    PATH,
                    headers=headers,
                    content=b"PRIVATE BODY MUST NOT BE PARSED",
                )

                self.assert_fixed_error(response, status, public_code)
                self.assertEqual(len(harness.authentication_calls), 1)
                self.assertEqual(harness.runtime_calls, [])

    def test_any_authorization_header_is_opaque_401(self):
        for authorization in ("", "Bearer PRIVATE"):
            with self.subTest(authorization=authorization):
                harness = RouteHarness(reject_authorization=True)
                response = harness.client.post(
                    PATH,
                    headers=harness.headers(Authorization=authorization),
                    json=BODY,
                )

                self.assert_fixed_error(
                    response,
                    401,
                    "warehouse_anomaly_preview_authentication_required",
                )
                self.assertEqual(harness.runtime_calls, [])

    def test_malformed_authentication_dependency_result_is_unavailable(self):
        harness = RouteHarness(authentication_result={
            "authenticationKind": "cookie_session",
            "sessionHash": "PRIVATE",
        })
        headers = harness.headers()
        headers["Content-Type"] = "application/json"

        response = harness.client.post(
            PATH,
            headers=headers,
            content=b"PRIVATE BODY MUST NOT BE PARSED",
        )

        self.assert_fixed_error(
            response, 503, "warehouse_anomaly_preview_unavailable",
        )
        self.assertEqual(response.headers.get("retry-after"), "30")
        self.assertNotIn("PRIVATE", response.text)
        self.assertEqual(harness.runtime_calls, [])

    def test_nonallowlisted_company_is_opaque_not_found_before_body(self):
        harness = RouteHarness(allowed_company_ids=frozenset({17}))
        headers = harness.headers()
        headers["Content-Type"] = "application/json"

        response = harness.client.post(
            PATH,
            headers=headers,
            content=b"PRIVATE BODY MUST NOT BE PARSED",
        )

        self.assert_fixed_error(
            response, 404, "warehouse_anomaly_preview_not_found",
        )
        self.assertEqual(len(harness.authentication_calls), 1)
        self.assertEqual(harness.runtime_calls, [])

    def test_body_stream_stops_immediately_after_the_hard_cap(self):
        class StreamRequest:
            def __init__(self):
                self.consumed = 0

            async def stream(self):
                for chunk in (b"a" * 3000, b"b" * 1097):
                    self.consumed += 1
                    yield chunk
                raise AssertionError("oversized parser consumed another chunk")

        request = StreamRequest()
        with self.assertRaises(OverflowError):
            asyncio.run(runtime_routes._json_body(request))
        self.assertEqual(request.consumed, 2)

    def test_invalid_json_and_selector_shapes_never_call_runner(self):
        raw_bodies = (
            b'{"projectId":9,"projectId":10,"jobId":123,"selected":{}}',
            b"\xff",
            b"not-json",
            ("[" * 1200 + "0" + "]" * 1200).encode("utf-8"),
            json.dumps({**BODY, "extra": True}).encode("utf-8"),
            json.dumps({
                **BODY,
                "selected": {**BODY["selected"], "subjectId": True},
            }).encode("utf-8"),
        )
        for raw_body in raw_bodies:
            with self.subTest(prefix=raw_body[:30]):
                harness = RouteHarness()
                headers = harness.headers()
                headers["Content-Type"] = "application/json"
                response = harness.client.post(
                    PATH, headers=headers, content=raw_body,
                )

                self.assert_fixed_error(
                    response, 422, "warehouse_anomaly_preview_request_invalid",
                )
                self.assertEqual(harness.runtime_calls, [])

    def test_oversized_json_returns_413_before_runner(self):
        harness = RouteHarness()
        headers = harness.headers()
        headers["Content-Type"] = "application/json"

        response = harness.client.post(
            PATH,
            headers=headers,
            content=b"{" + b" " * 4095 + b"}",
        )

        self.assert_fixed_error(
            response, 413, "warehouse_anomaly_preview_request_too_large",
        )
        self.assertEqual(harness.runtime_calls, [])

    def test_exact_4096_byte_json_boundary_is_accepted(self):
        harness = RouteHarness()
        raw = json.dumps(BODY, separators=(",", ":")).encode("utf-8")
        raw += b" " * (4096 - len(raw))
        headers = harness.headers()
        headers["Content-Type"] = "application/json"

        response = harness.client.post(
            PATH, headers=headers, content=raw,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), PUBLIC_RESULT)
        self.assertEqual(len(harness.runtime_calls), 1)

    def test_runtime_errors_map_to_the_fixed_public_table(self):
        cases = (
            (
                runtime_contract._WarehouseAnomalyRuntimeContractError(
                    runtime_contract._INPUT_INVALID,
                ),
                422,
                "warehouse_anomaly_preview_request_invalid",
                None,
            ),
            (
                runtime_contract._WarehouseAnomalyRuntimeContractError(
                    runtime_contract._AUTHENTICATION_REQUIRED,
                ),
                401,
                "warehouse_anomaly_preview_authentication_required",
                None,
            ),
            (
                runtime_contract._WarehouseAnomalyRuntimeContractError(
                    runtime_contract._RESOURCE_NOT_FOUND,
                ),
                404,
                "warehouse_anomaly_preview_not_found",
                None,
            ),
            (
                runtime_contract._WarehouseAnomalyRuntimeContractError(
                    runtime_access._ARTIFACT_INVALID,
                ),
                409,
                "warehouse_anomaly_preview_conflict",
                None,
            ),
            (
                runtime_budget._WarehouseAnomalyRuntimeError(
                    runtime_budget._BUSY,
                ),
                429,
                "warehouse_anomaly_preview_busy",
                "10",
            ),
            (
                runtime_budget._WarehouseAnomalyRuntimeError(
                    runtime_budget._DEADLINE_EXCEEDED,
                ),
                503,
                "warehouse_anomaly_preview_unavailable",
                "30",
            ),
            *(
                (
                    runtime_budget._WarehouseAnomalyRuntimeError(code),
                    503,
                    "warehouse_anomaly_preview_unavailable",
                    "30",
                )
                for code in (
                    runtime_budget._READ_FAILED,
                    runtime_budget._ROLLBACK_FAILED,
                    runtime_budget._CLEANUP_FAILED,
                    runtime_budget._CONTRACT_INVALID,
                )
            ),
            (
                RuntimeError("PRIVATE_DSN SELECT secret"),
                503,
                "warehouse_anomaly_preview_unavailable",
                "30",
            ),
            (
                PoisonCodeError("PRIVATE DEPENDENCY"),
                503,
                "warehouse_anomaly_preview_unavailable",
                "30",
            ),
        )
        for error, status, detail, retry_after in cases:
            with self.subTest(error=error.args):
                harness = RouteHarness(runtime_error=error)
                response = harness.client.post(
                    PATH, headers=harness.headers(), json=BODY,
                )

                self.assert_fixed_error(response, status, detail)
                self.assertEqual(
                    response.headers.get("retry-after"), retry_after,
                )
                self.assertNotIn("PRIVATE", response.text)
                self.assertNotIn("SELECT", response.text)
                self.assertEqual(len(harness.runtime_calls), 1)

    def test_blocked_and_stale_are_successful_exact_public_results(self):
        cases = (
            ("blocked", "warehouse_anomaly_preview_blocked"),
            ("stale", "warehouse_anomaly_preview_stale"),
        )
        for state, blocker in cases:
            with self.subTest(state=state):
                result = {
                    **PUBLIC_RESULT,
                    "state": state,
                    "content": None,
                    "blockers": [blocker],
                }
                harness = RouteHarness(result=result)
                response = harness.client.post(
                    PATH, headers=harness.headers(), json=BODY,
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), result)

    def test_invalid_runner_projection_is_opaque_unavailable(self):
        invalid_results = (
            {**PUBLIC_RESULT, "privateReport": "PRIVATE"},
            {**PUBLIC_RESULT, "content": {"private": "PRIVATE"}},
            {**PUBLIC_RESULT, "writesAttempted": 1},
            {
                **PUBLIC_RESULT,
                "candidate": {**CANDIDATE, "subjectId": 457},
                "content": content_contract._fixed_content({
                    **CANDIDATE, "subjectId": 457,
                }),
            },
            {
                **PUBLIC_RESULT,
                "state": "blocked",
                "blockers": ["PRIVATE"],
            },
        )
        for result in invalid_results:
            with self.subTest(keys=tuple(result)):
                harness = RouteHarness(result=result)
                response = harness.client.post(
                    PATH, headers=harness.headers(), json=BODY,
                )

                self.assert_fixed_error(
                    response,
                    503,
                    "warehouse_anomaly_preview_unavailable",
                )
                self.assertEqual(response.headers.get("retry-after"), "30")
                self.assertNotIn("PRIVATE", response.text)

    def test_valid_request_calls_runner_once_and_returns_no_store_projection(self):
        harness = RouteHarness()

        response = harness.client.post(
            PATH,
            headers=harness.headers(),
            json=BODY,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), PUBLIC_RESULT)
        self.assertEqual(harness.authentication_calls, [
            ("POST", PATH, None, "csrf-value", True),
        ])
        self.assertEqual(len(harness.runtime_calls), 1)
        args, kwargs = harness.runtime_calls[0]
        self.assertEqual(args, (DB_CONFIG, AUTHENTICATION))
        self.assertEqual(kwargs, {
            "company_mode": "company",
            "company_id": "4",
            "body": BODY,
        })
        self.assertIsNot(args[0], DB_CONFIG)
        self.assertEqual(
            response.headers.get("cache-control"), "no-store, max-age=0",
        )
        self.assertEqual(response.headers.get("pragma"), "no-cache")
        self.assertEqual(
            response.headers.get("vary"),
            "Cookie, X-Company-Id, X-Company-Mode",
        )
        self.assertNotIn("etag", response.headers)


if __name__ == "__main__":
    unittest.main()
