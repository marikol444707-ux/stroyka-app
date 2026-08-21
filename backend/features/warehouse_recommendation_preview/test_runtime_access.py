import ast
import inspect
import json
from pathlib import Path
import unittest
from unittest import mock

from backend.features.estimate_revision_impact.combined_contract import (
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.job_contract import (
    build_estimate_revision_impact_job_plan,
    source_from_job_payload,
)
from backend.features.estimate_revision_impact.test_combined_report import (
    combined,
)
from backend.features.warehouse_recommendation_preview import runtime_access
from backend.features.warehouse_recommendation_preview import runtime_contract


_authorize_live_access = (
    runtime_access._authorize_warehouse_anomaly_runtime_access
)
_read_artifact = runtime_access._read_warehouse_anomaly_runtime_artifact
_resolve_artifact = runtime_access._resolve_warehouse_anomaly_runtime_artifact

_SESSION_HASH = "a" * 64


def _claims(*, project_id=9, job_id=123):
    return runtime_contract._parse_warehouse_anomaly_runtime_claims(
        {
            "authenticationKind": "cookie_session",
            "sessionHash": _SESSION_HASH,
        },
        company_mode="company",
        company_id="4",
        body={
            "projectId": project_id,
            "jobId": job_id,
            "selected": {
                "subjectKind": "warehouseInvoice",
                "subjectId": 456,
                "anomalyCode": "warehouse_invoice_project_mismatch",
            },
        },
    )


class _Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        self.fetches = 0

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        self.fetches += 1
        return self.rows


_ARTIFACT_FIXED_FIELDS = {
    "job_id": 123,
    "owner_scope": "company",
    "company_id": 4,
    "project_id": 9,
    "project_scope_id": 9,
    "requested_by_user_id": None,
    "requested_by_role": "system",
    "job_type": "estimate.revision_impact",
    "idempotency_key": "revision-impact:" + "b" * 32,
    "correlation_id": "revision-impact:" + "b" * 32,
    "status": "succeeded",
    "priority": 4,
    "attempts": 1,
    "max_attempts": 3,
    "started_at_present": True,
    "completed_at_present": True,
    "last_error_empty": True,
    "locked_at_null": True,
    "locked_by_null": True,
    "lease_token_null": True,
    "lease_expires_at_null": True,
    "heartbeat_at_null": True,
}


def _artifact_row(**overrides):
    row = {
        **_ARTIFACT_FIXED_FIELDS,
        "payload_json": {"schemaVersion": 1},
        "result_json": {"combinedReportVersion": 1},
        "payload_bytes": 20,
        "result_bytes": 28,
        "row_count": 1,
        "payload_limit_exceeded": False,
        "result_limit_exceeded": False,
    }
    row.update(overrides)
    return row


def _payload():
    return {
        "schemaVersion": 1,
        "eventType": "estimate.version_activated",
        "companyId": 4,
        "projectId": 9,
        "estimateId": 52,
        "sourceRevision": "sha256:" + "a" * 64,
    }


def _result():
    report = {
        **combined(),
        "readOnlyTransaction": True,
        "rolledBack": True,
    }
    report["source"] = {
        **report["source"],
        "companyId": 4,
        "projectId": 9,
        "estimateId": 52,
        "sourceRevision": "sha256:" + "a" * 64,
    }
    report["evidenceSha256"] = calculate_evidence_sha256(report)
    return report


def _resolved_artifact_row(**overrides):
    payload = _payload()
    plan = build_estimate_revision_impact_job_plan(
        source_from_job_payload(payload),
    )
    result = _result()
    row = _artifact_row(
        idempotency_key=plan.idempotency_key,
        correlation_id=plan.correlation_id,
        payload_json=payload,
        result_json=result,
        payload_bytes=len(json.dumps(payload).encode("utf-8")),
        result_bytes=len(json.dumps(result, ensure_ascii=False).encode("utf-8")),
    )
    row.update(overrides)
    return row


class WarehouseAnomalyRuntimeLiveAuthorizationTests(unittest.TestCase):
    def _assert_fixed_error(self, code, callback):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(
            type(error).__name__, "_WarehouseAnomalyRuntimeContractError",
        )
        self.assertEqual(getattr(error, "code", None), code)
        self.assertEqual(error.args, (code,))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        self.assertNotIn(_SESSION_HASH, rendered)
        self.assertNotIn("директор", rendered)

    def test_private_seam_has_one_exact_caller_cursor_signature(self):
        parameters = inspect.signature(_authorize_live_access).parameters
        self.assertEqual(list(parameters), ["cur", "claims"])
        self.assertEqual(runtime_access.__all__, [])

    def test_one_small_parameterized_query_authorizes_and_returns_same_claims(self):
        claims = _claims()
        cursor = _Cursor([{
            "actor_count": 1,
            "project_exists": True,
        }])

        result = _authorize_live_access(cursor, claims)

        self.assertIs(result, claims)
        self.assertEqual(cursor.fetches, 1)
        self.assertEqual(len(cursor.calls), 1)
        sql, params = cursor.calls[0]
        normalized = " ".join(sql.split())
        upper = normalized.upper()
        self.assertIn("ACTOR AS MATERIALIZED", upper)
        self.assertIn("ACTOR_COUNT AS MATERIALIZED", upper)
        self.assertIn("ORDER BY MEMBERSHIP.ID LIMIT %S", upper)
        self.assertIn("COUNT(*)::BIGINT AS ACTOR_COUNT", upper)
        self.assertIn(
            "CASE WHEN ACTOR_COUNT.ACTOR_COUNT=1 THEN EXISTS",
            upper,
        )
        self.assertIn(
            "PROJECT.ID=%S AND PROJECT.COMPANY_ID=%S", upper,
        )
        self.assertEqual(
            params,
            (_SESSION_HASH, 4, 2, 9, 4),
        )

    def test_actor_cte_pins_the_exact_cookie_2fa_director_tenant_policy(self):
        cursor = _Cursor([{
            "actor_count": 1,
            "project_exists": True,
        }])

        _authorize_live_access(cursor, _claims())

        sql = " ".join(cursor.calls[0][0].split()).upper()
        required = (
            "FROM PUBLIC.USER_SESSIONS SESSION",
            "JOIN PUBLIC.USERS ACTOR_USER",
            "JOIN PUBLIC.USER_COMPANY_ROLES MEMBERSHIP",
            "JOIN PUBLIC.COMPANIES COMPANY",
            "JOIN PUBLIC.PLATFORM_ACCOUNTS PLATFORM_ACCOUNT",
            "SESSION.SESSION_HASH=%S",
            "MEMBERSHIP.COMPANY_ID=%S",
            "SESSION.REVOKED_AT IS NULL",
            "SESSION.EXPIRES_AT>CLOCK_TIMESTAMP()",
            "SESSION.TWO_FACTOR_PASSED IS TRUE",
            "ACTOR_USER.ACTIVE IS TRUE",
            "ACTOR_USER.TWO_FACTOR_ENABLED IS TRUE",
            "MEMBERSHIP.ROLE='ДИРЕКТОР'",
            "MEMBERSHIP.ACTIVE IS TRUE",
            "COMPANY.ACTIVE IS TRUE",
            "MEMBERSHIP.PLATFORM_ACCOUNT_ID=COMPANY.PLATFORM_ACCOUNT_ID",
            "PLATFORM_ACCOUNT.ID=COMPANY.PLATFORM_ACCOUNT_ID",
            "PLATFORM_ACCOUNT.ACTIVE IS TRUE",
            "PLATFORM_ACCOUNT.STATUS='ACTIVE'",
        )
        for fragment in required:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, sql)
        for forbidden in (
            "ACTOR_USER.ROLE",
            "USERS.ROLE",
            "ASSIGNED_PROJECTS",
            "PROJECT.NAME",
            "ALL_COMPANIES",
            "LAST_SEEN_AT",
            "UPDATE ",
            "INSERT ",
            "DELETE ",
            "FOR UPDATE",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, sql)

    def test_project_lookup_is_not_an_actor_inner_join_or_auth_oracle(self):
        claims = _claims()
        for actor_count in (0, 2):
            for project_exists in (False, True):
                cursor = _Cursor([{
                    "actor_count": actor_count,
                    "project_exists": project_exists,
                }])
                with self.subTest(
                    actor_count=actor_count,
                    project_exists=project_exists,
                ):
                    self._assert_fixed_error(
                        "warehouse_anomaly_runtime_authentication_required",
                        lambda cursor=cursor: _authorize_live_access(
                            cursor, claims,
                        ),
                    )
                self.assertEqual(len(cursor.calls), 1)

        cursor = _Cursor([{
            "actor_count": 1,
            "project_exists": False,
        }])
        self._assert_fixed_error(
            "warehouse_anomaly_runtime_resource_not_found",
            lambda: _authorize_live_access(cursor, claims),
        )
        sql = cursor.calls[0][0].upper()
        actor_sql = sql.split("ACTOR_COUNT AS MATERIALIZED", 1)[0]
        self.assertNotIn("PUBLIC.PROJECTS", actor_sql)

    def test_malformed_or_ambiguous_query_shape_is_contract_invalid(self):
        invalid_rows = (
            None,
            (),
            [],
            [
                {"actor_count": 1, "project_exists": True},
                {"actor_count": 1, "project_exists": True},
            ],
            [{}],
            [{"actor_count": 1}],
            [{"actor_count": 1, "project_exists": True, "actor_id": 7}],
            [{"actor_count": True, "project_exists": True}],
            [{"actor_count": 1, "project_exists": 1}],
        )
        for rows in invalid_rows:
            cursor = _Cursor(rows)
            with self.subTest(rows=repr(rows)):
                self._assert_fixed_error(
                    "warehouse_anomaly_runtime_contract_invalid",
                    lambda cursor=cursor: _authorize_live_access(
                        cursor, _claims(),
                    ),
                )
            self.assertEqual(len(cursor.calls), 1)
            self.assertEqual(cursor.fetches, 1)

    def test_invalid_claims_do_not_touch_the_cursor(self):
        cursor = _Cursor([{
            "actor_count": 1,
            "project_exists": True,
        }])
        self._assert_fixed_error(
            "warehouse_anomaly_runtime_contract_invalid",
            lambda: _authorize_live_access(cursor, object()),
        )
        self.assertEqual(cursor.calls, [])
        self.assertEqual(cursor.fetches, 0)


class WarehouseAnomalyRuntimeArtifactTransportTests(unittest.TestCase):
    def _assert_exact_artifact_sql_inventories(self, sql):
        normalized = " ".join(sql.split())
        limited_projection = normalized.split(
            "WITH limited AS MATERIALIZED ( SELECT ", 1,
        )[1].split(" FROM public.agent_jobs job", 1)[0]
        self.assertEqual(limited_projection, (
            "job.id AS job_id, job.owner_scope, job.company_id, "
            "job.project_id, job.project_scope_id, "
            "job.requested_by_user_id, job.requested_by_role, "
            "job.job_type, job.idempotency_key, job.correlation_id, "
            "job.status, job.priority, job.attempts, job.max_attempts, "
            "job.started_at IS NOT NULL AS started_at_present, "
            "job.completed_at IS NOT NULL AS completed_at_present, "
            "job.last_error='' AS last_error_empty, "
            "job.locked_at IS NULL AS locked_at_null, "
            "job.locked_by IS NULL AS locked_by_null, "
            "job.lease_token IS NULL AS lease_token_null, "
            "job.lease_expires_at IS NULL AS lease_expires_at_null, "
            "job.heartbeat_at IS NULL AS heartbeat_at_null, "
            "job.payload_json AS emitted_payload_json, "
            "job.result_json AS emitted_result_json"
        ))
        outer_projection = normalized.rsplit("SELECT ", 1)[1]
        self.assertEqual(outer_projection, (
            "gated.job_id, gated.owner_scope, gated.company_id, "
            "gated.project_id, gated.project_scope_id, "
            "gated.requested_by_user_id, gated.requested_by_role, "
            "gated.job_type, gated.idempotency_key, "
            "gated.correlation_id, gated.status, gated.priority, "
            "gated.attempts, gated.max_attempts, "
            "gated.started_at_present, gated.completed_at_present, "
            "gated.last_error_empty, gated.locked_at_null, "
            "gated.locked_by_null, gated.lease_token_null, "
            "gated.lease_expires_at_null, gated.heartbeat_at_null, "
            "CASE WHEN gated.payload_allowed THEN "
            "gated.emitted_payload_json ELSE NULL END AS payload_json, "
            "CASE WHEN gated.payload_allowed THEN "
            "gated.emitted_result_json ELSE NULL END AS result_json, "
            "gated.payload_bytes, gated.result_bytes, gated.row_count, "
            "gated.payload_limit_exceeded, gated.result_limit_exceeded "
            "FROM gated ORDER BY gated.job_id"
        ))

    def _assert_fixed_error(self, code, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(
            type(error).__name__, "_WarehouseAnomalyRuntimeContractError",
        )
        self.assertEqual(getattr(error, "code", None), code)
        self.assertEqual(error.args, (code,))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_private_artifact_reader_has_one_exact_caller_cursor_signature(self):
        parameters = inspect.signature(_read_artifact).parameters
        self.assertEqual(list(parameters), ["cur", "claims"])

    def test_one_opaque_query_has_ordered_limit_before_query_wide_utf8_gate(self):
        cursor = _Cursor([_artifact_row()])

        row = _read_artifact(cursor, _claims())

        self.assertEqual(row["job_id"], 123)
        self.assertEqual(len(cursor.calls), 1)
        self.assertEqual(cursor.fetches, 1)
        sql, params = cursor.calls[0]
        normalized = " ".join(sql.split())
        upper = normalized.upper()
        self.assertIn("LIMITED AS MATERIALIZED", upper)
        self.assertIn("SIZED AS MATERIALIZED", upper)
        self.assertIn("DECIDED AS MATERIALIZED", upper)
        self.assertIn("CLASSIFIED AS MATERIALIZED", upper)
        self.assertIn("GATED AS MATERIALIZED", upper)
        self.assertLess(
            upper.index("ORDER BY JOB.ID LIMIT %S"),
            upper.index("COUNT(*) OVER ()::BIGINT AS ROW_COUNT"),
        )
        for alias in ("PAYLOAD", "RESULT"):
            with self.subTest(alias=alias):
                self.assertIn(
                    "OCTET_LENGTH(CONVERT_TO(EMITTED_"
                    + alias
                    + "_JSON::TEXT,'UTF8'))",
                    upper,
                )
                self.assertIn(
                    "CASE WHEN GATED.PAYLOAD_ALLOWED THEN "
                    "GATED.EMITTED_" + alias + "_JSON ELSE NULL END AS "
                    + alias + "_JSON",
                    upper,
                )
        self.assertIn(
            "ROW_COUNT=1 AND PAYLOAD_LIMIT_EXCEEDED IS FALSE "
            "AND RESULT_LIMIT_EXCEEDED IS FALSE AS PAYLOAD_ALLOWED",
            upper,
        )
        self.assertEqual(params, (123, 4, 9, 2, 131072, 131072))
        self._assert_exact_artifact_sql_inventories(sql)

    def test_exact_sql_inventories_reject_raw_or_disguised_text_leaks(self):
        sql = runtime_access._ARTIFACT_SQL
        mutations = (
            sql.replace(
                "job.id AS job_id,",
                "job.last_error AS job_id,",
                1,
            ),
            sql.replace(
                "job.result_json AS emitted_result_json",
                "job.result_json AS emitted_result_json, "
                "job.last_error AS secret_text",
                1,
            ),
            sql.replace(
                "       gated.result_limit_exceeded\n  FROM gated",
                "       gated.result_limit_exceeded,\n"
                "       gated.emitted_result_json AS raw_result_json\n"
                "  FROM gated",
                1,
            ),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated != sql):
                self.assertNotEqual(mutated, sql)
                with self.assertRaises(AssertionError):
                    self._assert_exact_artifact_sql_inventories(mutated)

    def test_lookup_predicates_are_exact_and_lifecycle_stays_out_of_where(self):
        cursor = _Cursor([_artifact_row()])

        _read_artifact(cursor, _claims())

        sql = " ".join(cursor.calls[0][0].split()).upper()
        limited = sql.split("), SIZED AS MATERIALIZED", 1)[0]
        for required in (
            "FROM PUBLIC.AGENT_JOBS JOB",
            "JOB.ID=%S",
            "JOB.COMPANY_ID=%S",
            "JOB.PROJECT_ID=%S",
            "JOB.OWNER_SCOPE='COMPANY'",
            "JOB.JOB_TYPE='ESTIMATE.REVISION_IMPACT'",
            "JOB.STATUS='SUCCEEDED'",
            "JOB.REQUESTED_BY_USER_ID IS NULL",
            "JOB.REQUESTED_BY_ROLE='SYSTEM'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, limited)
        where = limited.split(" WHERE ", 1)[1]
        for forbidden in (
            "PROJECT_SCOPE_ID",
            "PRIORITY",
            "ATTEMPTS",
            "MAX_ATTEMPTS",
            "STARTED_AT IS NOT NULL",
            "COMPLETED_AT IS NOT NULL",
            "LAST_ERROR",
            "LOCKED_AT",
            "LOCKED_BY",
            "LEASE_TOKEN",
            "LEASE_EXPIRES_AT",
            "HEARTBEAT_AT",
            "IDEMPOTENCY_KEY",
            "CORRELATION_ID",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, where)

    def test_missing_or_ambiguous_opaque_lookup_is_one_not_found_outcome(self):
        for rows in ([], [
            _artifact_row(
                payload_json=None,
                result_json=None,
                row_count=2,
            ),
            _artifact_row(
                payload_json=None,
                result_json=None,
                row_count=2,
            ),
        ]):
            cursor = _Cursor(rows)
            with self.subTest(rows=len(rows)):
                self._assert_fixed_error(
                    "warehouse_anomaly_runtime_resource_not_found",
                    lambda cursor=cursor: _read_artifact(cursor, _claims()),
                )
            self.assertEqual(len(cursor.calls), 1)

    def test_ambiguous_mixed_overflow_withholds_every_json_before_not_found(self):
        rows = [
            _artifact_row(
                payload_json=None,
                result_json=None,
                payload_bytes=20,
                row_count=2,
                payload_limit_exceeded=True,
            ),
            _artifact_row(
                payload_json=None,
                result_json=None,
                payload_bytes=131073,
                row_count=2,
                payload_limit_exceeded=True,
            ),
        ]
        cursor = _Cursor(rows)

        self._assert_fixed_error(
            "warehouse_anomaly_runtime_resource_not_found",
            lambda: _read_artifact(cursor, _claims()),
            secrets=("PRIVATE-MIXED-ROW",),
        )
        self.assertTrue(all(row["payload_json"] is None for row in rows))
        self.assertTrue(all(row["result_json"] is None for row in rows))

    def test_size_overflow_requires_query_wide_nulling_and_is_artifact_invalid(self):
        marker = "PRIVATE-OVERSIZED-JOB-MARKER"
        for field in ("payload", "result"):
            values = {
                "payload_json": None,
                "result_json": None,
                "payload_bytes": 20,
                "result_bytes": 28,
                "payload_limit_exceeded": False,
                "result_limit_exceeded": False,
            }
            values[field + "_bytes"] = 131073
            values[field + "_limit_exceeded"] = True
            cursor = _Cursor([_artifact_row(**values)])
            with self.subTest(field=field):
                self._assert_fixed_error(
                    "warehouse_anomaly_runtime_artifact_invalid",
                    lambda cursor=cursor: _read_artifact(
                        cursor, _claims(),
                    ),
                    secrets=(marker,),
                )

        accepted = _read_artifact(
            _Cursor([_artifact_row(payload_bytes=131072)]),
            _claims(),
        )
        self.assertEqual(accepted["payload_bytes"], 131072)

    def test_exact_row_rechecks_all_lookup_and_terminal_invariants(self):
        invalid = {
            "job_id": 124,
            "owner_scope": "platform",
            "company_id": 5,
            "project_id": 10,
            "project_scope_id": 0,
            "requested_by_user_id": 7,
            "requested_by_role": "директор",
            "job_type": "other",
            "status": "failed",
            "priority": 5,
            "attempts": 0,
            "max_attempts": 4,
            "started_at_present": False,
            "completed_at_present": False,
            "last_error_empty": False,
            "locked_at_null": False,
            "locked_by_null": False,
            "lease_token_null": False,
            "lease_expires_at_null": False,
            "heartbeat_at_null": False,
        }
        for key, value in invalid.items():
            cursor = _Cursor([_artifact_row(**{key: value})])
            with self.subTest(key=key):
                self._assert_fixed_error(
                    "warehouse_anomaly_runtime_artifact_invalid",
                    lambda cursor=cursor: _read_artifact(
                        cursor, _claims(),
                    ),
                )

    def test_malformed_transport_metadata_is_contract_invalid(self):
        invalid = (
            None,
            (),
            [_artifact_row(extra=True)],
            [_artifact_row(payload_bytes=True)],
            [_artifact_row(result_bytes=-1)],
            [_artifact_row(row_count=2)],
            [_artifact_row(payload_limit_exceeded=1)],
            [_artifact_row(payload_bytes=131073)],
            [_artifact_row(payload_limit_exceeded=True)],
            [_artifact_row(payload_json=None)],
        )
        for rows in invalid:
            cursor = _Cursor(rows)
            with self.subTest(rows=repr(rows)[:160]):
                self._assert_fixed_error(
                    "warehouse_anomaly_runtime_contract_invalid",
                    lambda cursor=cursor: _read_artifact(
                        cursor, _claims(),
                    ),
                )

        cursor = _Cursor([_artifact_row()])
        self._assert_fixed_error(
            "warehouse_anomaly_runtime_contract_invalid",
            lambda: _read_artifact(cursor, object()),
        )
        self.assertEqual(cursor.calls, [])
        self.assertEqual(cursor.fetches, 0)


class WarehouseAnomalyRuntimeArtifactProvenanceTests(unittest.TestCase):
    def _assert_artifact_invalid(self, callback, secrets=()):
        with self.assertRaises(ValueError) as raised:
            callback()
        error = raised.exception
        self.assertEqual(
            type(error).__name__, "_WarehouseAnomalyRuntimeContractError",
        )
        self.assertEqual(
            getattr(error, "code", None),
            "warehouse_anomaly_runtime_artifact_invalid",
        )
        self.assertEqual(
            error.args, ("warehouse_anomaly_runtime_artifact_invalid",),
        )
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        rendered = " ".join((str(error), repr(error), repr(vars(error))))
        for secret in secrets:
            self.assertNotIn(secret, rendered)

    def test_resolver_returns_only_detached_report_and_exact_selection(self):
        stored = _resolved_artifact_row()
        cursor = _Cursor([stored])

        artifact = _resolve_artifact(cursor, _claims())

        self.assertEqual(set(artifact), {"combinedReport", "selected"})
        self.assertEqual(artifact["combinedReport"], stored["result_json"])
        self.assertIsNot(artifact["combinedReport"], stored["result_json"])
        self.assertEqual(artifact["selected"], {
            "subjectKind": "warehouseInvoice",
            "subjectId": 456,
            "anomalyCode": "warehouse_invoice_project_mismatch",
        })
        self.assertIs(type(artifact), dict)
        self.assertIs(type(artifact["combinedReport"]), dict)
        self.assertIs(type(artifact["selected"]), dict)
        self.assertEqual(len(cursor.calls), 1)

        artifact["combinedReport"]["source"]["projectId"] = 999
        artifact["selected"]["subjectId"] = 999
        self.assertEqual(stored["result_json"]["source"]["projectId"], 9)
        self.assertEqual(_claims().selection.subject_id, 456)

    def test_full_rebuilt_job_plan_must_match_every_stored_plan_field(self):
        invalid = {
            "idempotency_key": "revision-impact:" + "0" * 32,
            "correlation_id": "revision-impact:" + "0" * 32,
        }
        for key, value in invalid.items():
            cursor = _Cursor([_resolved_artifact_row(**{key: value})])
            with self.subTest(key=key):
                self._assert_artifact_invalid(
                    lambda cursor=cursor: _resolve_artifact(
                        cursor, _claims(),
                    ),
                )

    def test_payload_source_scope_and_exact_fields_are_rebuilt_server_side(self):
        invalid_payloads = (
            {},
            {**_payload(), "extra": True},
            {**_payload(), "companyId": 5},
            {**_payload(), "projectId": 10},
            {**_payload(), "estimateId": True},
            {**_payload(), "sourceRevision": "sha256:" + "z" * 64},
            {**_payload(), "authorizationToken": "PRIVATE-TOKEN"},
        )
        for payload in invalid_payloads:
            cursor = _Cursor([_resolved_artifact_row(
                payload_json=payload,
                payload_bytes=len(json.dumps(payload).encode("utf-8")),
            )])
            with self.subTest(payload=repr(payload)[:120]):
                self._assert_artifact_invalid(
                    lambda cursor=cursor: _resolve_artifact(
                        cursor, _claims(),
                    ),
                    secrets=("PRIVATE-TOKEN",),
                )

    def test_result_must_match_exact_source_hash_and_safe_combined_contract(self):
        invalid_results = (
            {},
            {**_result(), "extra": True},
            {**_result(), "rolledBack": False},
            {**_result(), "evidenceSha256": "0" * 64},
            {
                **_result(),
                "source": {**_result()["source"], "projectId": 10},
            },
        )
        for result in invalid_results:
            cursor = _Cursor([_resolved_artifact_row(
                result_json=result,
                result_bytes=len(
                    json.dumps(result, ensure_ascii=False).encode("utf-8")
                ),
            )])
            with self.subTest(result=repr(result)[:120]):
                self._assert_artifact_invalid(
                    lambda cursor=cursor: _resolve_artifact(
                        cursor, _claims(),
                    ),
                )

    def test_canonical_64k_limit_is_rechecked_below_the_128k_transport_gate(self):
        private_marker = "PRIVATE-CANONICAL-OVERFLOW-"
        payload = {**_payload(), "padding": private_marker + "x" * 70000}
        cursor = _Cursor([_resolved_artifact_row(
            payload_json=payload,
            payload_bytes=len(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")
            ),
        )])

        self._assert_artifact_invalid(
            lambda: _resolve_artifact(cursor, _claims()),
            secrets=(private_marker,),
        )

    def test_provenance_dependency_errors_are_fixed_but_controls_keep_identity(self):
        secret = "PRIVATE-DEPENDENCY-DETAIL"
        cursor = _Cursor([_resolved_artifact_row()])
        with mock.patch.object(
            runtime_access,
            "source_from_job_payload",
            side_effect=RuntimeError(secret),
        ):
            self._assert_artifact_invalid(
                lambda: _resolve_artifact(cursor, _claims()),
                secrets=(secret,),
            )

        for control_type in (KeyboardInterrupt, SystemExit, GeneratorExit):
            control = control_type()
            cursor = _Cursor([_resolved_artifact_row()])
            with self.subTest(control=control_type.__name__):
                with mock.patch.object(
                    runtime_access,
                    "source_from_job_payload",
                    side_effect=control,
                ):
                    with self.assertRaises(control_type) as raised:
                        _resolve_artifact(cursor, _claims())
                self.assertIs(raised.exception, control)

    def test_private_import_surface_and_zero_production_callsites_are_frozen(self):
        source = Path(runtime_access.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module)
        self.assertEqual(imported, [
            "json",
            "backend.features.agent_jobs.service",
            "backend.features.estimate_revision_impact.handler",
            "backend.features.estimate_revision_impact.job_contract",
            "backend.features.warehouse_recommendation_preview",
        ])
        for forbidden in (
            "backend.db",
            "get_db",
            "query_service",
            "psycopg2",
            "connect(",
            "cursor(",
            "commit(",
            "rollback(",
            "set_session(",
        ):
            self.assertNotIn(forbidden, source)

        package_root = Path(runtime_access.__file__).resolve().parent
        backend_root = package_root.parents[1]
        callsites = []
        for path in backend_root.rglob("*.py"):
            if path == Path(runtime_access.__file__).resolve():
                continue
            if path.name.startswith("test_"):
                continue
            parsed = ast.parse(path.read_text(encoding="utf-8"))
            if any(
                (
                    isinstance(node, ast.Import)
                    and any(
                        alias.name.endswith(
                            "warehouse_recommendation_preview.runtime_access"
                        )
                        for alias in node.names
                    )
                )
                or (
                    isinstance(node, ast.ImportFrom)
                    and (
                        (node.module or "").endswith(
                            "warehouse_recommendation_preview.runtime_access"
                        )
                        or (
                            (node.module or "").endswith(
                                "warehouse_recommendation_preview"
                            )
                            and any(
                                alias.name == "runtime_access"
                                for alias in node.names
                            )
                        )
                    )
                )
                for node in ast.walk(parsed)
            ):
                callsites.append(str(path.relative_to(backend_root)))
        self.assertEqual(callsites, [
            "features/warehouse_recommendation_preview/runtime_preview.py",
        ])




if __name__ == "__main__":
    unittest.main()
