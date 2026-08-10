import ast
import copy
import inspect
import json
import re
import unittest
from unittest import mock

import psycopg2.extras

from backend.features.supply_recommendation_preview import (
    material_capability_proof,
    material_capability_runtime,
    material_capability_source_resolver,
)


RUN_PROOF_READ = material_capability_runtime.run_material_capability_proof_read
RUN_RUNTIME_READ = (
    material_capability_runtime.run_material_capability_runtime_read
)

AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
ACTOR = {
    "actor_user_id": 41,
    "actor_membership_id": 51,
    "actor_company_id": 4,
}

INPUT_INVALID = "supply_supplier_material_runtime_input_invalid"
AUTHENTICATION_REQUIRED = (
    "supply_supplier_material_runtime_authentication_required"
)
READ_FAILED = "supply_supplier_material_runtime_read_failed"
ROLLBACK_FAILED = "supply_supplier_material_runtime_rollback_failed"
CLEANUP_FAILED = "supply_supplier_material_runtime_cleanup_failed"

PROOF_FIELDS = {
    "proofVersion", "ok", "dryRun", "writesAttempted", "state",
    "source", "subjectKind", "confirmationSha256",
    "confirmationSubjectCount", "proofSubjectCount", "provenSubjectCount",
    "proofSubjects", "materialEligibilityProven", "rankingApplied",
    "supplierIds", "selectionAllowed", "sendAllowed", "blockers",
    "proofSha256", "readOnlyTransaction", "rolledBack",
}


def _proof_snapshot():
    source = {
        "companyId": 4,
        "requestId": 21,
        "requestItemIndex": 0,
        "requestItemSha256": "1" * 64,
        "rfqContentSha256": "2" * 64,
        "supplierEligibilitySha256": "3" * 64,
        "materialIdentitySha256": "4" * 64,
    }
    subject = {
        "companySupplierLinkId": 61,
        "supplierId": 71,
        "materialIdentitySha256": "4" * 64,
        "confirmationSubjectSha256": "5" * 64,
        "proofState": "missing",
        "evidence": [],
    }
    return material_capability_proof._result(
        source=source,
        confirmation_sha256="6" * 64,
        confirmation_subject_count=1,
        state="confirmation_required",
        blockers=["supply_supplier_material_confirmation_required"],
        proof_subjects=[subject],
        transaction_complete=False,
    )


class ScriptedCursor:
    def __init__(self, auth_rows=None, events=None, close_error=None):
        self.auth_rows = [ACTOR] if auth_rows is None else auth_rows
        self.events = events if events is not None else []
        self.close_error = close_error
        self.calls = []
        self.current = None
        self.closed = False

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        parameters = tuple(params or ())
        self.calls.append((normalized, parameters))
        if normalized.upper().startswith("SET LOCAL "):
            self.events.append("config")
            self.current = None
            return
        if "FROM public.user_sessions" in normalized:
            self.events.append("authentication")
            self.current = self.auth_rows
            return
        raise AssertionError("runtime executed an unexpected query: " + normalized)

    def fetchall(self):
        self.events.append("authentication_rows")
        return copy.deepcopy(self.current or [])

    def fetchone(self):
        raise AssertionError("runtime must retain the LIMIT 2 auth sentinel")

    def close(self):
        self.events.append("cursor_close")
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class ScriptedConnection:
    def __init__(
        self,
        cursor,
        events=None,
        rollback_error=None,
        close_error=None,
    ):
        self.cursor_value = cursor
        self.events = events if events is not None else cursor.events
        self.rollback_error = rollback_error
        self.close_error = close_error
        self.sessions = []
        self.cursor_kwargs = []
        self.rollbacks = 0
        self.commits = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.events.append("set_session")
        self.sessions.append(dict(kwargs))

    def cursor(self, **kwargs):
        self.events.append("cursor")
        self.cursor_kwargs.append(dict(kwargs))
        return self.cursor_value

    def commit(self):
        self.commits += 1
        raise AssertionError("proof reads must never commit")

    def rollback(self):
        self.events.append("rollback")
        self.rollbacks += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self):
        self.events.append("connection_close")
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _fixed_runtime_error(test_case, expected_code, callback):
    with test_case.assertRaises(ValueError) as raised:
        callback()
    error = raised.exception
    test_case.assertEqual(type(error).__name__, "MaterialCapabilityRuntimeError")
    test_case.assertEqual(getattr(error, "code", None), expected_code)
    test_case.assertEqual(str(error), expected_code)
    test_case.assertEqual(error.args, (expected_code,))
    test_case.assertNotIn("PRIVATE", repr(error) + repr(vars(error)))
    return error


class MaterialCapabilityRuntimeTests(unittest.TestCase):
    def _run_with_dependencies(
        self,
        connection,
        *,
        resolve_side_effect=None,
        prepare_side_effect=None,
        collect_side_effect=None,
        include_private_bundle=False,
    ):
        get_db = mock.Mock(return_value=connection)
        resolved = {
            "combinedReport": {"privateReport": "must-not-leak"},
            "selected": {"requestId": 21, "requestItemIndex": 0},
        }
        prepared = {"privatePrepared": "must-not-leak"}
        proof = _proof_snapshot()
        resolver_effect = (
            resolve_side_effect
            if resolve_side_effect is not None
            else lambda cur, **selectors: copy.deepcopy(resolved)
        )
        prepare_effect = (
            prepare_side_effect
            if prepare_side_effect is not None
            else lambda report, selected: copy.deepcopy(prepared)
        )
        collector_effect = (
            collect_side_effect
            if collect_side_effect is not None
            else lambda cur, value: copy.deepcopy(proof)
        )
        with mock.patch.object(
            material_capability_runtime.material_capability_source_resolver,
            "resolve_material_capability_source",
            side_effect=resolver_effect,
        ) as resolve_source, mock.patch.object(
            material_capability_runtime.rfq_content,
            "prepare_supply_rfq_content",
            side_effect=prepare_effect,
        ) as prepare, mock.patch.object(
            material_capability_runtime.material_capability_proof,
            "collect_prepared_supplier_material_capability_proof",
            side_effect=collector_effect,
        ) as collect:
            if include_private_bundle:
                result = RUN_RUNTIME_READ(
                    get_db,
                    AUTHENTICATION,
                    {
                        "companyId": 4,
                        "requestId": 21,
                        "requestItemIndex": 0,
                    },
                )
            else:
                result = RUN_PROOF_READ(
                    get_db,
                    AUTHENTICATION,
                    company_id=4,
                    request_id=21,
                    request_item_index=0,
                )
        return {
            "result": result,
            "get_db": get_db,
            "resolve": resolve_source,
            "prepare": prepare,
            "collect": collect,
            "resolved": resolved,
            "prepared": prepared,
            "proof": proof,
        }

    def test_public_contract_is_narrow_and_imports_no_write_or_model_surface(self):
        signature = inspect.signature(RUN_PROOF_READ)
        self.assertEqual(list(signature.parameters), [
            "get_db", "authentication", "company_id", "request_id",
            "request_item_index",
        ])
        for name in ("company_id", "request_id", "request_item_index"):
            self.assertEqual(
                signature.parameters[name].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )
        self.assertEqual(material_capability_runtime.__all__, [
            "MaterialCapabilityRuntimeError",
            "run_material_capability_proof_read",
            "run_material_capability_runtime_read",
        ])

        source = inspect.getsource(material_capability_runtime)
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name.lower() for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append((node.module or "").lower())
                imported.extend(alias.name.lower() for alias in node.names)
        joined_imports = " ".join(imported)
        for forbidden in (
            "backend.main", "material_capability_writer", "yandex", "openai",
            "gemini", "llm", "requests", "httpx", "smtp", "messenger",
            "outbox", "supplier_offers", "supplier_catalog",
        ):
            self.assertNotIn(forbidden, joined_imports)

        sql_fragments = [
            node.value.strip().upper()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and re.match(
                r"^(SELECT|SET|INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b",
                node.value.strip().upper(),
            )
        ]
        sql_text = " ".join(sql_fragments)
        self.assertIsNone(re.search(
            r"\b(INSERT|UPDATE|DELETE|ALTER|CREATE|DROP|TRUNCATE)\b",
            sql_text,
        ))
        for forbidden in (
            "LOCK TABLE", "PG_ADVISORY", "FOR UPDATE", "FOR SHARE",
        ):
            self.assertNotIn(forbidden, sql_text)
        self.assertFalse(any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            for node in ast.walk(tree)
        ))

    def test_one_readonly_snapshot_authenticates_resolves_and_collects_once(self):
        events = []
        cursor = ScriptedCursor(events=events)
        connection = ScriptedConnection(cursor, events=events)

        def resolve_source(cur, **selectors):
            self.assertIs(cur, cursor)
            self.assertEqual(selectors, {
                "company_id": 4,
                "request_id": 21,
                "request_item_index": 0,
            })
            events.append("resolve")
            return {
                "combinedReport": {"privateReport": "must-not-leak"},
                "selected": {"requestId": 21, "requestItemIndex": 0},
            }

        def prepare(report, selected):
            self.assertEqual(report, {"privateReport": "must-not-leak"})
            self.assertEqual(selected, {
                "requestId": 21, "requestItemIndex": 0,
            })
            events.append("prepare")
            return {"privatePrepared": "must-not-leak"}

        collected = _proof_snapshot()
        original_hash = collected["proofSha256"]

        def collect(cur, prepared):
            self.assertIs(cur, cursor)
            self.assertEqual(prepared, {"privatePrepared": "must-not-leak"})
            events.append("collect")
            return copy.deepcopy(collected)

        run = self._run_with_dependencies(
            connection,
            resolve_side_effect=resolve_source,
            prepare_side_effect=prepare,
            collect_side_effect=collect,
        )
        result = run["result"]

        run["get_db"].assert_called_once_with()
        run["resolve"].assert_called_once()
        run["prepare"].assert_called_once()
        run["collect"].assert_called_once()
        self.assertEqual(connection.sessions, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.cursor_kwargs, [{
            "cursor_factory": psycopg2.extras.RealDictCursor,
        }])
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

        compact_config = [
            "".join(sql.lower().split()) for sql, _params in cursor.calls[:4]
        ]
        self.assertEqual(compact_config, [
            "setlocalstatement_timeout='60s'",
            "setlocallock_timeout='5s'",
            "setlocalidle_in_transaction_session_timeout='60s'",
            "setlocalsearch_path=pg_catalog,public",
        ])
        self.assertTrue(all(params == () for _sql, params in cursor.calls[:4]))
        self.assertEqual(len(cursor.calls), 5)

        auth_sql, auth_params = cursor.calls[4]
        lowered = auth_sql.lower()
        for predicate in (
            "from public.user_sessions",
            "join public.users",
            "join public.user_company_roles",
            "join public.companies",
            "join public.platform_accounts",
            "session.session_hash=%s",
            "membership.company_id=%s",
            "session.revoked_at is null",
            "session.expires_at>clock_timestamp()",
            "session.two_factor_passed is true",
            "actor_user.active is true",
            "actor_user.two_factor_enabled is true",
            "membership.role='директор'",
            "membership.active is true",
            "company.active is true",
            "membership.platform_account_id=company.platform_account_id",
            "platform_account.active is true",
            "platform_account.status='active'",
            "order by membership.id",
            "limit %s",
        ):
            self.assertIn(predicate, lowered)
        for forbidden in ("for share", "for update", "lock table"):
            self.assertNotIn(forbidden, lowered)
        self.assertEqual(auth_params, ("a" * 64, 4, 2))

        self.assertEqual(events, [
            "set_session", "cursor",
            "config", "config", "config", "config",
            "authentication", "authentication_rows",
            "resolve", "prepare", "collect",
            "rollback", "cursor_close", "connection_close",
        ])
        self.assertEqual(set(result), PROOF_FIELDS)
        self.assertTrue(result["readOnlyTransaction"])
        self.assertTrue(result["rolledBack"])
        self.assertNotEqual(result["proofSha256"], original_hash)
        self.assertEqual(
            result["proofSha256"],
            material_capability_proof.calculate_proof_sha256(result),
        )
        serialized = json.dumps(result, ensure_ascii=False)
        for private in (
            "must-not-leak", AUTHENTICATION["sessionHash"],
            "combinedReport", "selected",
        ):
            self.assertNotIn(private, serialized)

    def test_private_runtime_bundle_reuses_the_same_single_snapshot(self):
        events = []
        cursor = ScriptedCursor(events=events)
        connection = ScriptedConnection(cursor, events=events)

        run = self._run_with_dependencies(
            connection,
            include_private_bundle=True,
        )

        self.assertEqual(set(run["result"]), {
            "proof", "combinedReport", "selected",
        })
        self.assertEqual(run["result"]["combinedReport"], run["resolved"][
            "combinedReport"
        ])
        self.assertEqual(run["result"]["selected"], run["resolved"][
            "selected"
        ])
        self.assertTrue(run["result"]["proof"]["readOnlyTransaction"])
        self.assertTrue(run["result"]["proof"]["rolledBack"])
        run["get_db"].assert_called_once_with()
        self.assertEqual(connection.rollbacks, 1)

    def test_strict_inputs_fail_before_opening_a_connection(self):
        invalid_cases = (
            (None, AUTHENTICATION, 4, 21, 0),
            ("not-callable", AUTHENTICATION, 4, 21, 0),
            (lambda: None, {}, 4, 21, 0),
            (lambda: None, {
                "authenticationKind": "bearer", "sessionHash": "a" * 64,
            }, 4, 21, 0),
            (lambda: None, {
                "authenticationKind": "cookie_session",
                "sessionHash": "A" * 64,
            }, 4, 21, 0),
            (lambda: None, {
                "authenticationKind": "cookie_session",
                "sessionHash": "a" * 64,
                "twoFactorPassed": True,
            }, 4, 21, 0),
            (lambda: None, AUTHENTICATION, True, 21, 0),
            (lambda: None, AUTHENTICATION, 0, 21, 0),
            (lambda: None, AUTHENTICATION, 4, False, 0),
            (lambda: None, AUTHENTICATION, 4, 0, 0),
            (lambda: None, AUTHENTICATION, 4, 21, True),
            (lambda: None, AUTHENTICATION, 4, 21, -1),
        )
        for get_db, authentication, company_id, request_id, index in invalid_cases:
            with self.subTest(
                authentication=authentication,
                company_id=company_id,
                request_id=request_id,
                index=index,
            ):
                _fixed_runtime_error(
                    self,
                    INPUT_INVALID,
                    lambda: RUN_PROOF_READ(
                        get_db,
                        authentication,
                        company_id=company_id,
                        request_id=request_id,
                        request_item_index=index,
                    ),
                )

    def test_live_authentication_is_exact_and_fails_before_source_resolution(self):
        invalid_auth_rows = (
            [],
            [ACTOR, ACTOR],
            [dict(ACTOR, actor_company_id=5)],
            [dict(ACTOR, actor_company_id=4.0)],
            [dict(ACTOR, private_detail="must-not-be-accepted")],
        )
        for rows in invalid_auth_rows:
            with self.subTest(rows=rows):
                events = []
                cursor = ScriptedCursor(auth_rows=rows, events=events)
                connection = ScriptedConnection(cursor, events=events)
                with mock.patch.object(
                    material_capability_runtime
                    .material_capability_source_resolver,
                    "resolve_material_capability_source",
                ) as resolver:
                    _fixed_runtime_error(
                        self,
                        AUTHENTICATION_REQUIRED,
                        lambda: RUN_PROOF_READ(
                            lambda: connection,
                            AUTHENTICATION,
                            company_id=4,
                            request_id=21,
                            request_item_index=0,
                        ),
                    )
                resolver.assert_not_called()
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)

    def test_only_allowlisted_resolver_and_proof_errors_keep_their_provenance(self):
        source_error = (
            material_capability_source_resolver
            .MaterialCapabilitySourceResolverError(
                "supply_supplier_material_source_not_found"
            )
        )
        proof_error = material_capability_proof.SupplierMaterialCapabilityProofError(
            "supply_supplier_material_schema_not_ready"
        )
        cases = (
            ("resolver", source_error),
            ("proof", proof_error),
        )
        for stage, expected in cases:
            with self.subTest(stage=stage):
                cursor = ScriptedCursor()
                connection = ScriptedConnection(cursor)

                def fail(*_args, **_kwargs):
                    raise expected

                kwargs = (
                    {"resolve_side_effect": fail}
                    if stage == "resolver"
                    else {"collect_side_effect": fail}
                )
                with self.assertRaises(type(expected)) as raised:
                    self._run_with_dependencies(connection, **kwargs)
                self.assertEqual(raised.exception.code, expected.code)
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(connection.closed)

    def test_unknown_or_forged_dependency_errors_become_fixed_read_failure(self):
        errors = (
            RuntimeError("PRIVATE_DATABASE_DETAIL"),
            material_capability_proof.SupplierMaterialCapabilityProofError(
                "PRIVATE_FORGED_PROOF_CODE"
            ),
        )
        for failure in errors:
            with self.subTest(failure=repr(failure)):
                cursor = ScriptedCursor()
                connection = ScriptedConnection(cursor)

                def fail(*_args, **_kwargs):
                    raise failure

                _fixed_runtime_error(
                    self,
                    READ_FAILED,
                    lambda: self._run_with_dependencies(
                        connection,
                        resolve_side_effect=fail,
                    ),
                )
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(connection.closed)

        def fail_to_open():
            raise RuntimeError("PRIVATE_CONNECTION_DETAIL")

        _fixed_runtime_error(
            self,
            READ_FAILED,
            lambda: RUN_PROOF_READ(
                fail_to_open,
                AUTHENTICATION,
                company_id=4,
                request_id=21,
                request_item_index=0,
            ),
        )

    def test_rollback_failure_has_one_fixed_error_and_still_cleans_up(self):
        cursor = ScriptedCursor()
        connection = ScriptedConnection(
            cursor,
            rollback_error=RuntimeError("PRIVATE_ROLLBACK_DETAIL"),
        )

        _fixed_runtime_error(
            self,
            ROLLBACK_FAILED,
            lambda: self._run_with_dependencies(connection),
        )

        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)

    def test_cursor_or_connection_cleanup_failure_has_one_fixed_error(self):
        cases = (
            (
                ScriptedCursor(
                    close_error=RuntimeError("PRIVATE_CURSOR_CLOSE_DETAIL")
                ),
                None,
            ),
            (ScriptedCursor(), RuntimeError("PRIVATE_CONNECTION_CLOSE_DETAIL")),
        )
        for cursor, connection_close_error in cases:
            with self.subTest(connection_close_error=connection_close_error):
                connection = ScriptedConnection(
                    cursor,
                    close_error=connection_close_error,
                )
                _fixed_runtime_error(
                    self,
                    CLEANUP_FAILED,
                    lambda: self._run_with_dependencies(connection),
                )
                self.assertEqual(connection.rollbacks, 1)
                self.assertTrue(cursor.closed)
                self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
