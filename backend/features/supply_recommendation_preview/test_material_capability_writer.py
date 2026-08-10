import copy
import inspect
import json
import subprocess
import sys
import unittest
from unittest import mock

import psycopg2

from backend.features.supply_recommendation_preview import (
    material_capability_proof,
    material_capability_schema_probe,
    material_capability_writer,
)
from backend.features.supply_recommendation_preview.material_capability_schema_contract import (
    ADVISORY_LOCK_ID,
)
from backend.features.supply_recommendation_preview.test_rfq_content import (
    valid_report,
)


AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
CONFIRM_COMMAND = {
    "companyId": 4,
    "companySupplierLinkId": 61,
    "supplierId": 71,
    "confirmationSubjectSha256": "c" * 64,
}
REVOKE_COMMAND = {
    "companyId": 4,
    "confirmationAssertionId": 901,
}
SELECTED = {"requestId": 21, "requestItemIndex": 0}

RESULT_FIELDS = {
    "writeVersion", "ok", "eventKind", "state", "companyId",
    "companySupplierLinkId", "supplierId", "materialIdentitySha256",
    "confirmationSubjectSha256", "assertionId", "revokesAssertionId",
    "actorUserId", "actorMembershipId", "writesAttempted", "committed",
}

INPUT_INVALID = "supply_supplier_material_writer_input_invalid"
AUTHENTICATION_REQUIRED = (
    "supply_supplier_material_writer_authentication_required"
)
TENANT_MISMATCH = "supply_supplier_material_writer_tenant_mismatch"
SCHEMA_NOT_READY = "supply_supplier_material_writer_schema_not_ready"
SUBJECT_STALE = "supply_supplier_material_writer_subject_stale"
SUBJECT_TERMINAL = "supply_supplier_material_writer_subject_terminal"
EVIDENCE_INVALID = "supply_supplier_material_writer_evidence_invalid"
TARGET_INVALID = "supply_supplier_material_writer_target_invalid"
WRITE_CONFLICT = "supply_supplier_material_writer_write_conflict"
WRITE_FAILED = "supply_supplier_material_writer_write_failed"
COMMIT_UNKNOWN = "supply_supplier_material_writer_commit_outcome_unknown"
ROLLBACK_FAILED = "supply_supplier_material_writer_rollback_failed"
CLEANUP_FAILED = "supply_supplier_material_writer_cleanup_failed"


class AlwaysEqualText(str):
    def __eq__(self, _other):
        return True

    def __ne__(self, _other):
        return False


class TextSubclass(str):
    pass


class AlwaysEqualList(list):
    def __eq__(self, _other):
        return True

    def __ne__(self, _other):
        return False


def _actor_row(**overrides):
    row = {
        "actor_user_id": 41,
        "actor_membership_id": 51,
        "actor_company_id": 4,
    }
    row.update(overrides)
    return row


def _assertion_row(assertion_id=901, **overrides):
    row = {
        "id": assertion_id,
        "confirmation_version": 1,
        "event_kind": "confirmed",
        "company_id": 4,
        "company_supplier_link_id": 61,
        "supplier_id": 71,
        "material_identity_sha256": "b" * 64,
        "confirmation_subject_sha256": "c" * 64,
        "actor_membership_id": 501,
        "actor_user_id": 401,
        "actor_role": "директор",
        "source_kind": "director_manual",
        "revokes_assertion_id": None,
    }
    row.update(overrides)
    return row


def _revocation_row(assertion_id=902, **overrides):
    row = _assertion_row(
        assertion_id,
        event_kind="revoked",
        actor_membership_id=51,
        actor_user_id=41,
        revokes_assertion_id=901,
    )
    row.update(overrides)
    return row


def _proof_snapshot(proof_state="missing", **overrides):
    evidence = []
    if proof_state in {"confirmed", "revoked"}:
        evidence.append({
            "assertionId": 901,
            "eventKind": "confirmed",
            "actorMembershipId": 501,
            "actorUserId": 401,
            "actorRole": "директор",
            "sourceKind": "director_manual",
            "revokesAssertionId": None,
        })
    if proof_state == "revoked":
        evidence.append({
            "assertionId": 902,
            "eventKind": "revoked",
            "actorMembershipId": 502,
            "actorUserId": 402,
            "actorRole": "директор",
            "sourceKind": "director_manual",
            "revokesAssertionId": 901,
        })
    subject = {
        "companySupplierLinkId": 61,
        "supplierId": 71,
        "materialIdentitySha256": "b" * 64,
        "confirmationSubjectSha256": "c" * 64,
        "proofState": proof_state,
        "evidence": evidence,
    }
    source = {
        "companyId": 4,
        "requestId": 21,
        "requestItemIndex": 0,
        "requestItemSha256": "1" * 64,
        "rfqContentSha256": "2" * 64,
        "supplierEligibilitySha256": "3" * 64,
        "materialIdentitySha256": "b" * 64,
    }
    if proof_state == "confirmed":
        state, blockers = "proof_complete", []
    elif proof_state == "revoked":
        state = "confirmation_required"
        blockers = ["supply_supplier_material_confirmation_required"]
    else:
        state = "confirmation_required"
        blockers = ["supply_supplier_material_confirmation_required"]
    state = overrides.pop("state", state)
    blockers = overrides.pop("blockers", blockers)
    subjects = overrides.pop("proof_subjects", [subject])
    result = material_capability_proof._result(
        source=source,
        confirmation_sha256="d" * 64,
        confirmation_subject_count=len(subjects),
        state=state,
        blockers=blockers,
        proof_subjects=subjects,
    )
    result.update(overrides)
    return result


class ScriptedCursor:
    def __init__(
        self,
        *,
        auth_batches=None,
        target_rows=None,
        revocation_rows=None,
        insert_row=None,
        insert_error=None,
        events=None,
        close_error=None,
    ):
        self.auth_batches = list(auth_batches or [
            [_actor_row()],
            [_actor_row()],
        ])
        self.target_rows = list(target_rows or [])
        self.revocation_rows = list(revocation_rows or [])
        self.insert_row = insert_row
        self.insert_error = insert_error
        self.events = events if events is not None else []
        self.close_error = close_error
        self.calls = []
        self.current = []
        self.closed = False

    def execute(self, sql, params=()):
        compact = " ".join(str(sql).split())
        lowered = compact.lower()
        params = tuple(params or ())
        self.calls.append((compact, params))
        if lowered.startswith("set local"):
            self.events.append("config")
            self.current = []
        elif "from public.user_sessions" in lowered:
            self.events.append("auth")
            self.current = (
                self.auth_batches.pop(0) if self.auth_batches else []
            )
        elif "pg_advisory_xact_lock" in lowered:
            self.events.append("advisory_lock")
            self.current = [{}]
        elif lowered.startswith("lock table public.companies"):
            self.events.append("migration_gate_lock")
            self.current = []
        elif lowered.startswith(
            "lock table public.supplier_material_capability_assertions"
        ):
            self.events.append("table_lock")
            self.current = []
        elif lowered.startswith(
            "insert into public.supplier_material_capability_assertions"
        ):
            self.events.append("insert")
            if self.insert_error is not None:
                raise self.insert_error
            self.current = [] if self.insert_row is None else [
                copy.deepcopy(self.insert_row)
            ]
        elif (
            "from public.supplier_material_capability_assertions" in lowered
            and "revokes_assertion_id=%s" in lowered
        ):
            self.events.append("existing_revocation")
            self.current = copy.deepcopy(self.revocation_rows)
        elif (
            "from public.supplier_material_capability_assertions" in lowered
            and "id=%s" in lowered
        ):
            self.events.append("target")
            self.current = copy.deepcopy(self.target_rows)
        else:
            raise AssertionError("unexpected SQL in writer test: " + compact)

    def fetchall(self):
        return list(self.current)

    def fetchone(self):
        return self.current[0] if self.current else None

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class ScriptedConnection:
    def __init__(
        self,
        cursor,
        *,
        commit_error=None,
        rollback_error=None,
        close_error=None,
    ):
        self.cursor_value = cursor
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.close_error = close_error
        self.session = None
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session = dict(kwargs)

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def rollback(self):
        self.rollbacks += 1
        if self.rollback_error is not None:
            raise self.rollback_error

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def _connection_factory(connection, calls):
    def get_db():
        calls.append(connection)
        return connection
    return get_db


class MaterialCapabilityWriterTests(unittest.TestCase):
    def _assert_error(self, code, callback):
        with self.assertRaises(
            material_capability_writer.MaterialCapabilityWriterError
        ) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(str(raised.exception), code)
        self.assertNotIn("PRIVATE", str(raised.exception))

    def test_confirmation_rebuilds_missing_subject_and_commits_one_insert(self):
        events = []
        inserted = _assertion_row(
            actor_membership_id=51,
            actor_user_id=41,
        )
        cursor = ScriptedCursor(insert_row=inserted, events=events)
        connection = ScriptedConnection(cursor)
        db_calls = []
        seen = {}

        def collect_snapshot(cur, prepared):
            events.append("proof")
            seen["cursor"] = cur
            seen["prepared"] = prepared
            return _proof_snapshot("missing")

        with mock.patch.object(
            material_capability_writer,
            "_collect_proof",
            side_effect=collect_snapshot,
        ):
            result = (
                material_capability_writer
                .run_material_capability_confirmation_write(
                    _connection_factory(connection, db_calls),
                    valid_report(),
                    SELECTED,
                    AUTHENTICATION,
                    CONFIRM_COMMAND,
                )
            )

        self.assertEqual(set(result), RESULT_FIELDS)
        self.assertEqual(result, {
            "writeVersion": 1,
            "ok": True,
            "eventKind": "confirmed",
            "state": "confirmed",
            "companyId": 4,
            "companySupplierLinkId": 61,
            "supplierId": 71,
            "materialIdentitySha256": "b" * 64,
            "confirmationSubjectSha256": "c" * 64,
            "assertionId": 901,
            "revokesAssertionId": None,
            "actorUserId": 41,
            "actorMembershipId": 51,
            "writesAttempted": 1,
            "committed": True,
        })
        self.assertEqual(db_calls, [connection])
        self.assertIs(seen["cursor"], cursor)
        self.assertEqual(seen["prepared"]["source"]["companyId"], 4)
        self.assertEqual(connection.session, {
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        })
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)
        self.assertEqual(events, [
            "config", "config", "config", "config",
            "migration_gate_lock", "table_lock", "advisory_lock", "auth",
            "proof", "auth", "insert",
        ])

        self.assertEqual(cursor.calls[:4], [
            ("SET LOCAL statement_timeout='60s'", ()),
            ("SET LOCAL lock_timeout='5s'", ()),
            ("SET LOCAL idle_in_transaction_session_timeout='60s'", ()),
            ("SET LOCAL search_path=pg_catalog,public", ()),
        ])
        auth_calls = [
            call for call in cursor.calls
            if "FROM public.user_sessions" in call[0]
        ]
        self.assertEqual(len(auth_calls), 2)
        auth_sql, auth_params = auth_calls[0]
        for required in (
            "session.session_hash=%s",
            "session.revoked_at IS NULL",
            "session.expires_at>clock_timestamp()",
            "session.two_factor_passed IS TRUE",
            "actor_user.active IS TRUE",
            "actor_user.two_factor_enabled IS TRUE",
            "membership.role='\u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440'",
            "membership.active IS TRUE",
            "company.active IS TRUE",
            "membership.platform_account_id=company.platform_account_id",
            "LIMIT %s",
            "FOR SHARE OF session,actor_user,membership,company,"
            "platform_account",
        ):
            self.assertIn(required, auth_sql)
        self.assertNotIn("actor_user.role=", auth_sql)
        self.assertEqual(auth_params, ("a" * 64, 4, 2))
        self.assertEqual(auth_calls[1][1], auth_params)

        advisory = next(
            call for call in cursor.calls
            if "pg_advisory_xact_lock" in call[0]
        )
        self.assertEqual(advisory[1], (ADVISORY_LOCK_ID,))
        gate_lock = next(
            call for call in cursor.calls
            if call[0].lower().startswith("lock table public.companies")
        )
        self.assertEqual(
            gate_lock[0],
            "LOCK TABLE public.companies IN SHARE UPDATE EXCLUSIVE MODE",
        )
        table_lock = next(
            call for call in cursor.calls
            if call[0].lower().startswith(
                "lock table public.supplier_material_capability_assertions"
            )
        )
        self.assertEqual(
            table_lock[0],
            "LOCK TABLE public.supplier_material_capability_assertions "
            "IN SHARE ROW EXCLUSIVE MODE",
        )
        gate_lock_index = cursor.calls.index(gate_lock)
        table_lock_index = cursor.calls.index(table_lock)
        advisory_index = cursor.calls.index(advisory)
        first_auth_index = cursor.calls.index(auth_calls[0])
        self.assertLess(gate_lock_index, table_lock_index)
        self.assertLess(table_lock_index, advisory_index)
        self.assertLess(advisory_index, first_auth_index)
        insert_sql, insert_params = next(
            call for call in cursor.calls
            if call[0].lower().startswith("insert into")
        )
        self.assertIn(
            "(confirmation_version,event_kind,company_id,"
            "company_supplier_link_id,supplier_id,material_identity_sha256,"
            "confirmation_subject_sha256,actor_membership_id,actor_user_id,"
            "actor_role,source_kind,revokes_assertion_id)",
            insert_sql,
        )
        self.assertEqual(insert_params, (
            1, "confirmed", 4, 61, 71, "b" * 64, "c" * 64,
            51, 41, "директор", "director_manual", None,
        ))
        self.assertNotIn("a" * 64, json.dumps(result, ensure_ascii=False))
        self.assertNotIn("a" * 64, repr(insert_params))

    def test_confirmation_idempotency_and_fail_closed_subject_states(self):
        non_integer_company = _proof_snapshot("missing")
        non_integer_company["source"]["companyId"] = 4.0
        non_integer_company["proofSha256"] = (
            material_capability_proof.calculate_proof_sha256(
                non_integer_company
            )
        )
        contaminated_supplier_ids = _proof_snapshot("missing")
        contaminated_supplier_ids["supplierIds"] = AlwaysEqualList([999])
        contaminated_supplier_ids["proofSha256"] = (
            material_capability_proof.calculate_proof_sha256(
                contaminated_supplier_ids
            )
        )
        contaminated_subject_kind = _proof_snapshot("missing")
        contaminated_subject_kind["subjectKind"] = AlwaysEqualText(
            "poison_subject_kind"
        )
        contaminated_subject_kind["proofSha256"] = (
            material_capability_proof.calculate_proof_sha256(
                contaminated_subject_kind
            )
        )
        contaminated_state = _proof_snapshot("missing")
        contaminated_state["state"] = TextSubclass(
            "confirmation_required"
        )
        contaminated_state["proofSha256"] = (
            material_capability_proof.calculate_proof_sha256(
                contaminated_state
            )
        )
        contaminated_proof_hash = _proof_snapshot("missing")
        contaminated_proof_hash["proofSha256"] = AlwaysEqualText(
            "poison_proof_hash"
        )
        cases = (
            (
                _proof_snapshot("confirmed"),
                CONFIRM_COMMAND,
                None,
                "already_confirmed",
            ),
            (
                _proof_snapshot("revoked"),
                CONFIRM_COMMAND,
                SUBJECT_TERMINAL,
                None,
            ),
            (
                _proof_snapshot("missing"),
                dict(
                    CONFIRM_COMMAND,
                    confirmationSubjectSha256="f" * 64,
                ),
                SUBJECT_STALE,
                None,
            ),
            (
                _proof_snapshot(
                    "missing",
                    state="no_candidates",
                    blockers=["supply_supplier_no_active_company_links"],
                    proof_subjects=[],
                ),
                CONFIRM_COMMAND,
                SUBJECT_STALE,
                None,
            ),
            (
                _proof_snapshot(
                    "missing",
                    state="incomplete",
                    blockers=[
                        "supply_supplier_material_schema_not_ready"
                    ],
                    proof_subjects=[],
                ),
                CONFIRM_COMMAND,
                SCHEMA_NOT_READY,
                None,
            ),
            (
                _proof_snapshot(
                    "missing",
                    state="needs_review",
                    blockers=[
                        "supply_supplier_material_evidence_invalid"
                    ],
                    proof_subjects=[],
                ),
                CONFIRM_COMMAND,
                EVIDENCE_INVALID,
                None,
            ),
            (
                non_integer_company,
                CONFIRM_COMMAND,
                EVIDENCE_INVALID,
                None,
            ),
            (
                contaminated_supplier_ids,
                CONFIRM_COMMAND,
                EVIDENCE_INVALID,
                None,
            ),
            (
                contaminated_subject_kind,
                CONFIRM_COMMAND,
                EVIDENCE_INVALID,
                None,
            ),
            (
                contaminated_state,
                CONFIRM_COMMAND,
                EVIDENCE_INVALID,
                None,
            ),
            (
                contaminated_proof_hash,
                CONFIRM_COMMAND,
                EVIDENCE_INVALID,
                None,
            ),
        )
        for snapshot, command, error_code, expected_state in cases:
            with self.subTest(error=error_code, state=expected_state):
                cursor = ScriptedCursor()
                connection = ScriptedConnection(cursor)
                with mock.patch.object(
                    material_capability_writer,
                    "_collect_proof",
                    return_value=copy.deepcopy(snapshot),
                ):
                    callback = lambda: (
                        material_capability_writer
                        .run_material_capability_confirmation_write(
                            lambda: connection,
                            valid_report(),
                            SELECTED,
                            AUTHENTICATION,
                            command,
                        )
                    )
                    if error_code:
                        self._assert_error(error_code, callback)
                    else:
                        result = callback()
                        self.assertEqual(set(result), RESULT_FIELDS)
                        self.assertEqual(result["state"], expected_state)
                        self.assertEqual(result["eventKind"], "confirmed")
                        self.assertEqual(result["assertionId"], 901)
                        self.assertEqual(result["actorUserId"], 401)
                        self.assertEqual(result["actorMembershipId"], 501)
                        self.assertEqual(result["writesAttempted"], 0)
                        self.assertFalse(result["committed"])
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)
                self.assertFalse(any(
                    sql.lower().startswith("insert into")
                    for sql, _params in cursor.calls
                ))

    def test_inputs_and_live_cookie_director_authentication_are_strict(self):
        invalid_authentication = (
            {},
            {"authenticationKind": "bearer", "sessionHash": "a" * 64},
            {
                "authenticationKind": "cookie_session",
                "sessionHash": "A" * 64,
            },
            {
                "authenticationKind": "cookie_session",
                "sessionHash": "a" * 64,
                "twoFactorPassed": True,
            },
            {
                "authenticationKind": AlwaysEqualText("bearer"),
                "sessionHash": "a" * 64,
            },
        )
        for authentication in invalid_authentication:
            with self.subTest(authentication=authentication):
                calls = []
                self._assert_error(
                    INPUT_INVALID,
                    lambda: (
                        material_capability_writer
                        .run_material_capability_confirmation_write(
                            lambda: calls.append("db"),
                            valid_report(),
                            SELECTED,
                            authentication,
                            CONFIRM_COMMAND,
                        )
                    ),
                )
                self.assertEqual(calls, [])

        invalid_commands = (
            dict(CONFIRM_COMMAND, companyId=True),
            dict(CONFIRM_COMMAND, companySupplierLinkId=True),
            dict(CONFIRM_COMMAND, supplierId=0),
            dict(CONFIRM_COMMAND, confirmationSubjectSha256="x" * 64),
            dict(CONFIRM_COMMAND, actorUserId=41),
        )
        for command in invalid_commands:
            with self.subTest(command=command):
                calls = []
                self._assert_error(
                    INPUT_INVALID,
                    lambda: (
                        material_capability_writer
                        .run_material_capability_confirmation_write(
                            lambda: calls.append("db"),
                            valid_report(),
                            SELECTED,
                            AUTHENTICATION,
                            command,
                        )
                    ),
                )
                self.assertEqual(calls, [])

        calls = []
        self._assert_error(
            TENANT_MISMATCH,
            lambda: (
                material_capability_writer
                .run_material_capability_confirmation_write(
                    lambda: calls.append("db"),
                    valid_report(),
                    SELECTED,
                    AUTHENTICATION,
                    dict(CONFIRM_COMMAND, companyId=999),
                )
            ),
        )
        self.assertEqual(calls, [])

        for auth_rows in (
            [],
            [_actor_row(), _actor_row()],
            [_actor_row(actor_company_id=4.0)],
        ):
            with self.subTest(auth_rows=auth_rows):
                events = []
                cursor = ScriptedCursor(
                    auth_batches=[auth_rows],
                    events=events,
                )
                connection = ScriptedConnection(cursor)
                with mock.patch.object(
                    material_capability_writer,
                    "_collect_proof",
                ) as proof:
                    self._assert_error(
                        AUTHENTICATION_REQUIRED,
                        lambda: (
                            material_capability_writer
                            .run_material_capability_confirmation_write(
                                lambda: connection,
                                valid_report(),
                                SELECTED,
                                AUTHENTICATION,
                                CONFIRM_COMMAND,
                            )
                        ),
                    )
                    proof.assert_not_called()
                self.assertEqual(events, [
                    "config", "config", "config", "config",
                    "migration_gate_lock", "table_lock", "advisory_lock",
                    "auth",
                ])
                self.assertEqual(connection.rollbacks, 1)

        changed_actor = ScriptedCursor(auth_batches=[
            [_actor_row()],
            [_actor_row(actor_membership_id=999)],
        ])
        changed_connection = ScriptedConnection(changed_actor)
        with mock.patch.object(
            material_capability_writer,
            "_collect_proof",
            return_value=_proof_snapshot("missing"),
        ):
            self._assert_error(
                AUTHENTICATION_REQUIRED,
                lambda: (
                    material_capability_writer
                    .run_material_capability_confirmation_write(
                        lambda: changed_connection,
                        valid_report(),
                        SELECTED,
                        AUTHENTICATION,
                        CONFIRM_COMMAND,
                    )
                ),
            )
        self.assertFalse(any(
            sql.lower().startswith("insert into")
            for sql, _params in changed_actor.calls
        ))
        self.assertEqual(changed_connection.rollbacks, 1)

    def test_revocation_copies_historical_target_without_supplier_rebuild(self):
        events = []
        target = _assertion_row()
        inserted = _revocation_row()
        cursor = ScriptedCursor(
            target_rows=[target],
            revocation_rows=[],
            insert_row=inserted,
            events=events,
        )
        connection = ScriptedConnection(cursor)

        def schema_readiness(cur):
            self.assertIs(cur, cursor)
            events.append("schema")
            return {"contractVersion": 1, "complete": True, "blockers": []}

        with mock.patch.object(
            material_capability_schema_probe,
            "collect_material_capability_schema_readiness",
            side_effect=schema_readiness,
        ), mock.patch.object(
            material_capability_writer,
            "_collect_proof",
        ) as proof:
            result = (
                material_capability_writer
                .run_material_capability_revocation_write(
                    lambda: connection,
                    AUTHENTICATION,
                    REVOKE_COMMAND,
                )
            )
            proof.assert_not_called()

        self.assertEqual(set(result), RESULT_FIELDS)
        self.assertEqual(result["eventKind"], "revoked")
        self.assertEqual(result["state"], "revoked")
        self.assertEqual(result["assertionId"], 902)
        self.assertEqual(result["revokesAssertionId"], 901)
        self.assertEqual(result["materialIdentitySha256"], "b" * 64)
        self.assertEqual(result["confirmationSubjectSha256"], "c" * 64)
        self.assertEqual(result["actorUserId"], 41)
        self.assertEqual(result["actorMembershipId"], 51)
        self.assertEqual(result["writesAttempted"], 1)
        self.assertTrue(result["committed"])
        self.assertEqual(events, [
            "config", "config", "config", "config",
            "migration_gate_lock", "table_lock", "advisory_lock", "auth",
            "schema", "target", "existing_revocation", "auth", "insert",
        ])
        target_sql, target_params = next(
            call for call in cursor.calls
            if "FROM public.supplier_material_capability_assertions" in call[0]
            and "id=%s" in call[0]
            and "revokes_assertion_id=%s" not in call[0]
        )
        self.assertIn("company_id=%s", target_sql)
        self.assertIn("LIMIT %s", target_sql)
        self.assertIn("FOR SHARE", target_sql)
        self.assertEqual(target_params, (4, 901, 2))
        all_sql = " ".join(sql.lower() for sql, _params in cursor.calls)
        self.assertNotIn("company_supplier_links", all_sql)
        self.assertNotIn("from public.suppliers", all_sql)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)

    def test_revocation_is_idempotent_and_rejects_invalid_or_ambiguous_target(self):
        cases = (
            ([_assertion_row()], [_revocation_row()], True, None),
            ([], [], False, TARGET_INVALID),
            ([_assertion_row(), _assertion_row(903)], [], False,
             EVIDENCE_INVALID),
            ([_assertion_row(event_kind="revoked")], [], False,
             TARGET_INVALID),
            ([_assertion_row()], [_revocation_row(), _revocation_row(904)],
             False, EVIDENCE_INVALID),
        )
        for targets, revocations, idempotent, error_code in cases:
            with self.subTest(error=error_code, idempotent=idempotent):
                cursor = ScriptedCursor(
                    target_rows=targets,
                    revocation_rows=revocations,
                )
                connection = ScriptedConnection(cursor)
                with mock.patch.object(
                    material_capability_schema_probe,
                    "collect_material_capability_schema_readiness",
                    return_value={
                        "contractVersion": 1,
                        "complete": True,
                        "blockers": [],
                    },
                ):
                    callback = lambda: (
                        material_capability_writer
                        .run_material_capability_revocation_write(
                            lambda: connection,
                            AUTHENTICATION,
                            REVOKE_COMMAND,
                        )
                    )
                    if error_code:
                        self._assert_error(error_code, callback)
                    else:
                        result = callback()
                        self.assertEqual(result["state"], "already_revoked")
                        self.assertEqual(result["assertionId"], 902)
                        self.assertEqual(result["revokesAssertionId"], 901)
                        self.assertEqual(result["writesAttempted"], 0)
                        self.assertFalse(result["committed"])
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)
                self.assertFalse(any(
                    sql.lower().startswith("insert into")
                    for sql, _params in cursor.calls
                ))

        invalid_readiness_results = (
            {
                "contractVersion": 1,
                "complete": False,
                "blockers": ["material_capability_schema_not_ready"],
            },
            {"contractVersion": 1.0, "complete": True, "blockers": []},
            {
                "contractVersion": 1,
                "complete": True,
                "blockers": AlwaysEqualList(["schema_drift"]),
            },
        )
        for readiness in invalid_readiness_results:
            with self.subTest(readiness=readiness):
                cursor = ScriptedCursor(target_rows=[_assertion_row()])
                connection = ScriptedConnection(cursor)
                with mock.patch.object(
                    material_capability_schema_probe,
                    "collect_material_capability_schema_readiness",
                    return_value=readiness,
                ):
                    self._assert_error(
                        SCHEMA_NOT_READY,
                        lambda: (
                            material_capability_writer
                            .run_material_capability_revocation_write(
                                lambda: connection,
                                AUTHENTICATION,
                                REVOKE_COMMAND,
                            )
                        ),
                    )
                self.assertNotIn("target", cursor.events)
                self.assertEqual(connection.rollbacks, 1)

    def test_write_commit_rollback_and_cleanup_failures_are_fixed(self):
        def run_confirmation(connection, snapshot=None):
            with mock.patch.object(
                material_capability_writer,
                "_collect_proof",
                return_value=snapshot or _proof_snapshot("missing"),
            ):
                return (
                    material_capability_writer
                    .run_material_capability_confirmation_write(
                        lambda: connection,
                        valid_report(),
                        SELECTED,
                        AUTHENTICATION,
                        CONFIRM_COMMAND,
                    )
                )

        conflict_cursor = ScriptedCursor(
            insert_row=_assertion_row(
                actor_membership_id=51,
                actor_user_id=41,
            ),
            insert_error=psycopg2.IntegrityError(
                "PRIVATE_UNIQUE_DETAIL"
            ),
        )
        conflict = ScriptedConnection(conflict_cursor)
        self._assert_error(WRITE_CONFLICT, lambda: run_confirmation(conflict))
        self.assertEqual(conflict.commits, 0)
        self.assertEqual(conflict.rollbacks, 1)

        def poisoned_db():
            raise material_capability_writer.MaterialCapabilityWriterError(
                "PRIVATE_ATTACKER_CODE"
            )

        self._assert_error(
            WRITE_FAILED,
            lambda: (
                material_capability_writer
                .run_material_capability_confirmation_write(
                    poisoned_db,
                    valid_report(),
                    SELECTED,
                    AUTHENTICATION,
                    CONFIRM_COMMAND,
                )
            ),
        )
        for injected_lifecycle_code in (
            COMMIT_UNKNOWN,
            ROLLBACK_FAILED,
            CLEANUP_FAILED,
        ):
            with self.subTest(injected=injected_lifecycle_code):
                def poisoned_lifecycle_db(code=injected_lifecycle_code):
                    raise (
                        material_capability_writer
                        .MaterialCapabilityWriterError(code)
                    )

                self._assert_error(
                    WRITE_FAILED,
                    lambda: (
                        material_capability_writer
                        .run_material_capability_confirmation_write(
                            poisoned_lifecycle_db,
                            valid_report(),
                            SELECTED,
                            AUTHENTICATION,
                            CONFIRM_COMMAND,
                        )
                    ),
                )

        missing_return = ScriptedConnection(ScriptedCursor(insert_row=None))
        self._assert_error(
            WRITE_FAILED,
            lambda: run_confirmation(missing_return),
        )
        self.assertEqual(missing_return.commits, 0)
        self.assertEqual(missing_return.rollbacks, 1)

        commit_unknown = ScriptedConnection(
            ScriptedCursor(insert_row=_assertion_row(
                actor_membership_id=51,
                actor_user_id=41,
            )),
            commit_error=RuntimeError("PRIVATE_COMMIT_DETAIL"),
        )
        self._assert_error(
            COMMIT_UNKNOWN,
            lambda: run_confirmation(commit_unknown),
        )
        self.assertEqual(commit_unknown.commits, 1)

        rollback_failed = ScriptedConnection(
            ScriptedCursor(),
            rollback_error=RuntimeError("PRIVATE_ROLLBACK_DETAIL"),
        )
        self._assert_error(
            ROLLBACK_FAILED,
            lambda: run_confirmation(
                rollback_failed,
                _proof_snapshot("confirmed"),
            ),
        )
        self.assertEqual(rollback_failed.rollbacks, 1)

        cleanup_failed = ScriptedConnection(
            ScriptedCursor(close_error=RuntimeError(
                "PRIVATE_CLEANUP_DETAIL"
            )),
        )
        self._assert_error(
            CLEANUP_FAILED,
            lambda: run_confirmation(
                cleanup_failed,
                _proof_snapshot("confirmed"),
            ),
        )
        self.assertEqual(cleanup_failed.rollbacks, 1)
        self.assertTrue(cleanup_failed.closed)

    def test_public_contract_and_import_are_unregistered_and_model_free(self):
        confirmation_signature = inspect.signature(
            material_capability_writer
            .run_material_capability_confirmation_write
        )
        self.assertEqual(list(confirmation_signature.parameters), [
            "get_db", "combined_report", "selected", "authentication",
            "command",
        ])
        revocation_signature = inspect.signature(
            material_capability_writer
            .run_material_capability_revocation_write
        )
        self.assertEqual(list(revocation_signature.parameters), [
            "get_db", "authentication", "command",
        ])
        self.assertEqual(material_capability_writer.__all__, [
            "WRITE_VERSION",
            "MaterialCapabilityWriterError",
            "run_material_capability_confirmation_write",
            "run_material_capability_revocation_write",
        ])
        source = inspect.getsource(material_capability_writer).lower()
        self.assertNotIn("_collect_snapshot", source)
        self.assertIn(
            "collect_prepared_supplier_material_capability_proof",
            source,
        )
        for forbidden in (
            "backend.main", "yandex", "openai", "gemini", "llm",
            "requests.", "httpx", "smtp", "messenger_outbox",
            "supply_request_recipients", "supplier_catalog",
            "supplier_offers", "audit_log", "create_audit",
        ):
            self.assertNotIn(forbidden, source)
        for forbidden_sql in (
            "update public.", "delete from public.", "truncate ",
            "create table", "alter table", "drop table",
        ):
            self.assertNotIn(forbidden_sql, source)

        script = """
import atexit
import json
import sys
before = len(getattr(atexit, '_exithandlers', ()))
import backend.features.supply_recommendation_preview.material_capability_writer
print(json.dumps({
    'mainLoaded': 'backend.main' in sys.modules,
    'dbLoaded': 'backend.db' in sys.modules,
    'fastapiLoaded': 'fastapi' in sys.modules,
    'migrationLoaded': (
        'backend.features.supply_recommendation_preview.'
        'material_capability_schema' in sys.modules
    ),
    'routeModules': sorted(
        name for name in sys.modules
        if name.endswith('.routes') or name.endswith('.runtime_routes')
    ),
    'handlersAdded': len(getattr(atexit, '_exithandlers', ())) - before,
}))
"""
        completed = subprocess.run(
            [sys.executable, "-c", script],
            text=True,
            capture_output=True,
            check=True,
        )
        report = json.loads(completed.stdout)
        self.assertFalse(report["mainLoaded"])
        self.assertFalse(report["dbLoaded"])
        self.assertFalse(report["fastapiLoaded"])
        self.assertFalse(report["migrationLoaded"])
        self.assertEqual(report["routeModules"], [])
        self.assertEqual(report["handlersAdded"], 0)


if __name__ == "__main__":
    unittest.main()
