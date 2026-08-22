import unittest
from datetime import datetime, timezone
from unittest import mock

from psycopg2.extras import RealDictRow

from backend.features.human_approved_actions import action_kernel as kernel
from backend.features.human_approved_actions.contract import (
    build_human_action_event,
    build_review_acknowledgement_proposal,
)


AUTHENTICATION = {
    "authenticationKind": "cookie_session",
    "sessionHash": "a" * 64,
}
BODY = {
    "projectId": 17,
    "jobId": 29,
    "selected": {
        "subjectKind": "warehouseInvoice",
        "subjectId": 61,
        "anomalyCode": "warehouse_invoice_project_mismatch",
    },
}
ACTOR_ROW = {
    "actor_user_id": 41,
    "actor_membership_id": 71,
    "actor_company_id": 4,
    "project_exists": True,
}
NOW = datetime(2026, 8, 22, 9, 10, 11, 123456, tzinfo=timezone.utc)


def ready_preview(**changes):
    value = {
        "warehouseAnomalyContentVersion": 1,
        "state": "preview_ready",
        "source": {"companyId": 4, "projectId": 17},
        "candidate": dict(BODY["selected"]),
        "contentSha256": "b" * 64,
    }
    value.update(changes)
    return value


class ScriptedCursor:
    def __init__(self, steps, *, close_error=None):
        self.steps = list(steps)
        self.calls = []
        self.rows = []
        self.closed = False
        self.close_error = close_error

    def execute(self, query, params=None):
        compact = " ".join(str(query).split())
        self.calls.append((compact, params))
        if not self.steps:
            raise AssertionError("unexpected SQL: " + compact)
        marker, rows = self.steps.pop(0)
        if marker not in compact:
            raise AssertionError(f"expected {marker!r}, got {compact!r}")
        if isinstance(rows, BaseException):
            raise rows
        self.rows = rows

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class FakeConnection:
    def __init__(
        self,
        steps,
        *,
        commit_error=None,
        rollback_error=None,
        cursor_close_error=None,
        close_error=None,
    ):
        self.cursor_value = ScriptedCursor(
            steps, close_error=cursor_close_error,
        )
        self.sessions = []
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.commit_error = commit_error
        self.rollback_error = rollback_error
        self.close_error = close_error

    def set_session(self, **kwargs):
        self.sessions.append(dict(kwargs))

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
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error


def proposal_steps(actor=ACTOR_ROW):
    return [
        ("pg_catalog.set_config", []),
        ("FROM public.user_sessions session", [actor] if actor else []),
        ("pg_advisory_xact_lock", []),
        ("FROM public.human_action_proposals proposal", []),
        ("SELECT clock_timestamp() AS occurred_at", [{"occurred_at": NOW}]),
        ("INSERT INTO public.human_action_proposals", [{"id": 501}]),
        ("INSERT INTO public.human_action_events", [{"id": 601}]),
    ]


def stored_proposal():
    return build_review_acknowledgement_proposal(
        {
            "companyId": 4,
            "projectId": 17,
            "jobId": 29,
            **BODY["selected"],
            "contentVersion": 1,
            "contentSha256": "b" * 64,
        },
        {"userId": 41, "membershipId": 71, "companyId": 4},
        created_at=NOW,
    )


def proposal_row():
    item = stored_proposal()
    return {
        "id": 501,
        "contract_version": item.contract_version,
        "action_kind": item.action_kind,
        "effect_kind": "audit_only",
        "company_id": item.company_id,
        "project_id": item.project_id,
        "source_job_id": item.source_job_id,
        "subject_kind": item.subject_kind,
        "subject_id": item.subject_id,
        "anomaly_code": item.anomaly_code,
        "source_content_version": item.source_content_version,
        "source_content_sha256": item.source_content_sha256,
        "proposer_user_id": item.proposer_user_id,
        "proposer_membership_id": item.proposer_membership_id,
        "created_at": NOW,
        "expires_at": datetime(
            2026, 8, 22, 9, 25, 11, 123456, tzinfo=timezone.utc,
        ),
        "idempotency_key": item.idempotency_key,
        "proposal_sha256": item.proposal_sha256,
    }


def event_row(event_kind, occurred_at):
    event = build_human_action_event(
        stored_proposal(),
        proposal_id=501,
        event_kind=event_kind,
        actor={"userId": 41, "membershipId": 71, "companyId": 4},
        occurred_at=occurred_at,
    )
    return {
        "id": {"proposed": 601, "approved": 602, "applied": 603}[event_kind],
        "contract_version": event.contract_version,
        "event_kind": event.event_kind,
        "proposal_id": event.proposal_id,
        "proposal_sha256": event.proposal_sha256,
        "action_kind": event.action_kind,
        "company_id": event.company_id,
        "project_id": event.project_id,
        "subject_kind": event.subject_kind,
        "subject_id": event.subject_id,
        "proposer_user_id": event.proposer_user_id,
        "proposer_membership_id": event.proposer_membership_id,
        "actor_user_id": event.actor_user_id,
        "actor_membership_id": event.actor_membership_id,
        "proposal_created_at": NOW,
        "proposal_expires_at": datetime(
            2026, 8, 22, 9, 25, 11, 123456, tzinfo=timezone.utc,
        ),
        "occurred_at": occurred_at,
        "event_sha256": event.event_sha256,
    }


def decision_payload(decision="approve"):
    return {
        "proposalId": 501,
        "proposalSha256": stored_proposal().proposal_sha256,
        "decision": decision,
    }


class HumanActionProposalKernelTests(unittest.TestCase):
    def assert_fixed(self, code, operation):
        with self.assertRaises(kernel.HumanActionKernelError) as raised:
            operation()
        self.assertEqual(raised.exception.args, (code,))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertNotIn("PRIVATE", repr(raised.exception))

    def test_creates_exact_proposal_and_proposed_event_atomically(self):
        connection = FakeConnection(proposal_steps())
        get_db = mock.Mock(return_value=connection)
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ) as rebuild:
            receipt = kernel.create_review_acknowledgement_proposal(
                get_db,
                AUTHENTICATION,
                company_mode="company",
                company_id="4",
                body=BODY,
            )

        self.assertEqual(receipt, {
            "humanActionReceiptVersion": 1,
            "state": "proposed",
            "actionKind": "warehouse_anomaly_review_acknowledged",
            "proposalId": 501,
            "proposalSha256": receipt["proposalSha256"],
            "companyId": 4,
            "projectId": 17,
            "sourceJobId": 29,
            "subjectKind": "warehouseInvoice",
            "subjectId": 61,
            "actorUserId": 41,
            "actorMembershipId": 71,
            "expiresAt": "2026-08-22T09:25:11.123456Z",
            "writesAttempted": 2,
            "committed": True,
            "idempotent": False,
        })
        self.assertRegex(receipt["proposalSha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(connection.sessions, [{
            "readonly": False,
            "autocommit": False,
            "isolation_level": "SERIALIZABLE",
        }])
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.closes, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertEqual(connection.cursor_value.steps, [])
        rebuild.assert_called_once()
        claims = rebuild.call_args.args[1]
        self.assertEqual(claims.job_id, 29)
        inserts = [
            call for call in connection.cursor_value.calls
            if call[0].startswith("INSERT INTO")
        ]
        self.assertEqual(len(inserts), 2)
        self.assertIn(29, inserts[0][1])
        self.assertNotIn("PRIVATE", repr(receipt))

    def test_accepts_and_detaches_the_real_dict_cursor_row_type(self):
        connection = FakeConnection(proposal_steps(
            actor=RealDictRow(ACTOR_ROW),
        ))
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ):
            receipt = kernel.create_review_acknowledgement_proposal(
                lambda: connection,
                AUTHENTICATION,
                company_mode="company",
                company_id="4",
                body=BODY,
            )

        self.assertEqual(receipt["state"], "proposed")
        self.assertEqual(receipt["actorUserId"], 41)
        self.assertEqual(receipt["actorMembershipId"], 71)
        self.assertEqual(connection.commits, 1)

    def test_repeated_current_proposal_is_idempotent_without_new_event(self):
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [ACTOR_ROW]),
            ("pg_advisory_xact_lock", []),
            ("FROM public.human_action_proposals proposal", [proposal_row()]),
            ("FROM public.human_action_events", [event_row("proposed", NOW)]),
        ])
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ):
            receipt = kernel.create_review_acknowledgement_proposal(
                lambda: connection,
                AUTHENTICATION,
                company_mode="company",
                company_id="4",
                body=BODY,
            )
        self.assertEqual(receipt["proposalId"], 501)
        self.assertEqual(receipt["proposalSha256"], stored_proposal().proposal_sha256)
        self.assertTrue(receipt["idempotent"])
        self.assertEqual(receipt["writesAttempted"], 0)
        self.assertTrue(receipt["committed"])
        self.assertEqual(connection.commits, 1)
        self.assertFalse(any(
            sql.startswith("INSERT INTO")
            for sql, _params in connection.cursor_value.calls
        ))


class HumanActionDecisionKernelTests(unittest.TestCase):
    def assert_fixed(self, code, operation):
        with self.assertRaises(kernel.HumanActionKernelError) as raised:
            operation()
        self.assertEqual(raised.exception.args, (code,))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertNotIn("PRIVATE", repr(raised.exception))

    def test_approve_revalidates_exact_preview_and_atomically_applies_audit_only(self):
        decision_time = datetime(
            2026, 8, 22, 9, 11, 11, 123456, tzinfo=timezone.utc,
        )
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [ACTOR_ROW]),
            ("FROM public.human_action_proposals proposal", [proposal_row()]),
            ("FROM public.human_action_events", [event_row("proposed", NOW)]),
            ("SELECT clock_timestamp() AS occurred_at", [{"occurred_at": decision_time}]),
            ("INSERT INTO public.human_action_events", [{"id": 602}]),
            ("INSERT INTO public.human_action_events", [{"id": 603}]),
            ("INSERT INTO public.audit_log", [{"id": 701}]),
        ])
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ) as rebuild:
            receipt = kernel.decide_review_acknowledgement(
                lambda: connection,
                AUTHENTICATION,
                decision_payload(),
                company_mode="company",
                company_id="4",
            )

        self.assertEqual(receipt, {
            "humanActionReceiptVersion": 1,
            "state": "applied",
            "actionKind": "warehouse_anomaly_review_acknowledged",
            "proposalId": 501,
            "proposalSha256": stored_proposal().proposal_sha256,
            "companyId": 4,
            "projectId": 17,
            "sourceJobId": 29,
            "subjectKind": "warehouseInvoice",
            "subjectId": 61,
            "actorUserId": 41,
            "actorMembershipId": 71,
            "eventId": 603,
            "auditEventId": 701,
            "writesAttempted": 3,
            "committed": True,
            "idempotent": False,
        })
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.closes, 1)
        rebuild.assert_called_once()
        self.assertEqual(rebuild.call_args.args[1].job_id, 29)
        sql = [query for query, _params in connection.cursor_value.calls]
        self.assertEqual(sum(item.startswith("INSERT INTO") for item in sql), 3)
        self.assertFalse(any(
            item.startswith(("UPDATE ", "DELETE ", "ALTER ", "TRUNCATE "))
            for item in sql
        ))

    def test_reject_writes_one_terminal_event_without_rebuilding_or_audit(self):
        decision_time = datetime(
            2026, 8, 22, 9, 11, 11, 123456, tzinfo=timezone.utc,
        )
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [ACTOR_ROW]),
            ("FROM public.human_action_proposals proposal", [proposal_row()]),
            ("FROM public.human_action_events", [event_row("proposed", NOW)]),
            ("SELECT clock_timestamp() AS occurred_at", [{"occurred_at": decision_time}]),
            ("INSERT INTO public.human_action_events", [{"id": 602}]),
        ])
        with mock.patch.object(
            kernel,
            "_rebuild_current_preview",
            side_effect=AssertionError("reject must not rebuild"),
        ):
            receipt = kernel.decide_review_acknowledgement(
                lambda: connection,
                AUTHENTICATION,
                decision_payload("reject"),
                company_mode="company",
                company_id="4",
            )
        self.assertEqual(receipt["state"], "rejected")
        self.assertEqual(receipt["writesAttempted"], 1)
        self.assertEqual(receipt["eventId"], 602)
        self.assertIsNone(receipt["auditEventId"])
        self.assertEqual(connection.commits, 1)

    def test_repeated_approve_returns_existing_receipt_without_second_write(self):
        decision_time = datetime(
            2026, 8, 22, 9, 11, 11, 123456, tzinfo=timezone.utc,
        )
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [ACTOR_ROW]),
            ("FROM public.human_action_proposals proposal", [proposal_row()]),
            ("FROM public.human_action_events", [
                event_row("proposed", NOW),
                event_row("approved", decision_time),
                event_row("applied", decision_time),
            ]),
            ("FROM public.audit_log", [{"id": 701}]),
        ])
        with mock.patch.object(
            kernel,
            "_rebuild_current_preview",
            side_effect=AssertionError("idempotent replay must not rebuild"),
        ):
            receipt = kernel.decide_review_acknowledgement(
                lambda: connection,
                AUTHENTICATION,
                decision_payload(),
                company_mode="company",
                company_id="4",
            )
        self.assertEqual(receipt["state"], "applied")
        self.assertTrue(receipt["idempotent"])
        self.assertEqual(receipt["writesAttempted"], 0)
        self.assertTrue(receipt["committed"])
        self.assertEqual(receipt["eventId"], 603)
        self.assertEqual(receipt["auditEventId"], 701)
        self.assertEqual(connection.commits, 1)
        self.assertFalse(any(
            sql.startswith("INSERT INTO")
            for sql, _params in connection.cursor_value.calls
        ))

    def test_expiry_or_preview_drift_rolls_back_without_audit(self):
        after_expiry = datetime(
            2026, 8, 22, 9, 25, 11, 123456, tzinfo=timezone.utc,
        )
        cases = (
            (
                "expired",
                [
                    ("pg_catalog.set_config", []),
                    ("FROM public.user_sessions session", [ACTOR_ROW]),
                    ("FROM public.human_action_proposals proposal", [proposal_row()]),
                    ("FROM public.human_action_events", [event_row("proposed", NOW)]),
                    ("SELECT clock_timestamp() AS occurred_at", [{"occurred_at": after_expiry}]),
                ],
                ready_preview(),
                "human_action_kernel_proposal_expired",
            ),
            (
                "drift",
                [
                    ("pg_catalog.set_config", []),
                    ("FROM public.user_sessions session", [ACTOR_ROW]),
                    ("FROM public.human_action_proposals proposal", [proposal_row()]),
                    ("FROM public.human_action_events", [event_row("proposed", NOW)]),
                    ("SELECT clock_timestamp() AS occurred_at", [{"occurred_at": NOW}]),
                ],
                ready_preview(contentSha256="c" * 64),
                "human_action_kernel_source_stale",
            ),
        )
        for name, steps, preview, code in cases:
            connection = FakeConnection(steps)
            with self.subTest(name=name), mock.patch.object(
                kernel, "_rebuild_current_preview", return_value=preview,
            ):
                self.assert_fixed(
                    code,
                    lambda: kernel.decide_review_acknowledgement(
                        lambda: connection,
                        AUTHENTICATION,
                        decision_payload(),
                        company_mode="company",
                        company_id="4",
                    ),
                )
            self.assertEqual(connection.commits, 0)
            self.assertEqual(connection.rollbacks, 1)
            self.assertFalse(any(
                sql.startswith("INSERT INTO")
                for sql, _params in connection.cursor_value.calls
            ))

    def test_audit_failure_rolls_back_both_events_and_never_reports_success(self):
        decision_time = datetime(
            2026, 8, 22, 9, 11, 11, 123456, tzinfo=timezone.utc,
        )
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [ACTOR_ROW]),
            ("FROM public.human_action_proposals proposal", [proposal_row()]),
            ("FROM public.human_action_events", [event_row("proposed", NOW)]),
            ("SELECT clock_timestamp() AS occurred_at", [{"occurred_at": decision_time}]),
            ("INSERT INTO public.human_action_events", [{"id": 602}]),
            ("INSERT INTO public.human_action_events", [{"id": 603}]),
            ("INSERT INTO public.audit_log", RuntimeError("PRIVATE AUDIT")),
        ])
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ):
            self.assert_fixed(
                "human_action_kernel_write_failed",
                lambda: kernel.decide_review_acknowledgement(
                    lambda: connection,
                    AUTHENTICATION,
                    decision_payload(),
                    company_mode="company",
                    company_id="4",
                ),
            )
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.closes, 1)
        self.assertTrue(connection.cursor_value.closed)

    def test_invalid_decision_or_authentication_fails_before_connection(self):
        get_db = mock.Mock(side_effect=AssertionError("must not connect"))
        for authentication, decision in (
            ({**AUTHENTICATION, "extra": "PRIVATE"}, decision_payload()),
            (AUTHENTICATION, {**decision_payload(), "decision": "apply"}),
        ):
            with self.subTest(authentication=authentication, decision=decision):
                self.assert_fixed(
                    "human_action_kernel_input_invalid",
                    lambda authentication=authentication, decision=decision: (
                        kernel.decide_review_acknowledgement(
                            get_db,
                            authentication,
                            decision,
                            company_mode="company",
                            company_id="4",
                        )
                    ),
                )
        get_db.assert_not_called()

    def test_selected_company_is_checked_before_foreign_proposal_details(self):
        foreign_actor = {
            **ACTOR_ROW,
            "actor_company_id": 5,
        }
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [foreign_actor]),
            ("FROM public.human_action_proposals proposal", []),
        ])

        self.assert_fixed(
            "human_action_kernel_proposal_not_found",
            lambda: kernel.decide_review_acknowledgement(
                lambda: connection,
                AUTHENTICATION,
                decision_payload(),
                company_mode="company",
                company_id="5",
            ),
        )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        proposal_sql, proposal_params = connection.cursor_value.calls[2]
        self.assertIn("proposal.company_id=%s", proposal_sql)
        self.assertEqual(proposal_params[-2], 5)
        self.assertFalse(any(
            "FROM public.human_action_events" in sql
            for sql, _params in connection.cursor_value.calls
        ))


class HumanActionHistoryKernelTests(unittest.TestCase):
    def assert_fixed(self, code, operation):
        with self.assertRaises(kernel.HumanActionKernelError) as raised:
            operation()
        self.assertEqual(raised.exception.args, (code,))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)

    def test_history_is_company_project_bounded_newest_first_and_read_only(self):
        occurred_at = datetime(
            2026, 8, 22, 9, 11, 11, 123456, tzinfo=timezone.utc,
        )
        event = event_row("applied", occurred_at)
        stored = {
            "event_id": event["id"],
            "contract_version": event["contract_version"],
            "event_kind": event["event_kind"],
            "proposal_id": event["proposal_id"],
            "proposal_sha256": event["proposal_sha256"],
            "action_kind": event["action_kind"],
            "company_id": event["company_id"],
            "project_id": event["project_id"],
            "source_job_id": 29,
            "subject_kind": event["subject_kind"],
            "subject_id": event["subject_id"],
            "proposer_user_id": event["proposer_user_id"],
            "proposer_membership_id": event["proposer_membership_id"],
            "actor_user_id": event["actor_user_id"],
            "actor_membership_id": event["actor_membership_id"],
            "proposal_created_at": event["proposal_created_at"],
            "proposal_expires_at": event["proposal_expires_at"],
            "occurred_at": occurred_at,
            "event_sha256": event["event_sha256"],
        }
        connection = FakeConnection([
            ("pg_catalog.set_config", []),
            ("FROM public.user_sessions session", [ACTOR_ROW]),
            ("FROM public.human_action_events event", [stored]),
        ])

        result = kernel.list_review_acknowledgement_history(
            lambda: connection,
            AUTHENTICATION,
            company_mode="company",
            company_id="4",
            project_id=17,
            before_event_id=700,
            limit=25,
        )

        self.assertEqual(result, {
            "humanActionHistoryVersion": 1,
            "companyId": 4,
            "projectId": 17,
            "items": [{
                "eventId": 603,
                "eventKind": "applied",
                "proposalId": 501,
                "proposalSha256": stored_proposal().proposal_sha256,
                "actionKind": "warehouse_anomaly_review_acknowledged",
                "sourceJobId": 29,
                "subjectKind": "warehouseInvoice",
                "subjectId": 61,
                "actorUserId": 41,
                "actorMembershipId": 71,
                "occurredAt": "2026-08-22T09:11:11.123456Z",
                "eventSha256": event["event_sha256"],
            }],
            "nextBeforeId": None,
        })
        self.assertEqual(connection.sessions, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        authentication_sql, authentication_params = (
            connection.cursor_value.calls[1]
        )
        self.assertNotIn("FOR SHARE", authentication_sql)
        self.assertEqual(authentication_params, (17, "a" * 64, 4, 2))
        history_sql, history_params = connection.cursor_value.calls[2]
        self.assertIn("event.company_id=%s", history_sql)
        self.assertIn("event.project_id=%s", history_sql)
        self.assertIn("event.id<%s", history_sql)
        self.assertIn("ORDER BY event.id DESC", history_sql)
        self.assertEqual(history_params, (4, 17, 700, 26))

    def test_invalid_history_scope_fails_before_connection(self):
        get_db = mock.Mock(side_effect=AssertionError("must not connect"))
        for changes in (
            {"company_mode": "all"},
            {"company_id": "04"},
            {"project_id": 0},
            {"before_event_id": 0},
            {"limit": 101},
        ):
            values = {
                "company_mode": "company",
                "company_id": "4",
                "project_id": 17,
                "before_event_id": None,
                "limit": 50,
                **changes,
            }
            with self.subTest(changes=changes):
                self.assert_fixed(
                    "human_action_kernel_input_invalid",
                    lambda values=values: (
                        kernel.list_review_acknowledgement_history(
                            get_db,
                            AUTHENTICATION,
                            **values,
                        )
                    ),
                )
        get_db.assert_not_called()


class HumanActionKernelLifecycleFailureTests(unittest.TestCase):
    def assert_fixed(self, code, operation):
        with self.assertRaises(kernel.HumanActionKernelError) as raised:
            operation()
        self.assertEqual(raised.exception.args, (code,))
        self.assertIsNone(raised.exception.__cause__)
        self.assertIsNone(raised.exception.__context__)
        self.assertNotIn("PRIVATE", repr(raised.exception))

    def test_invalid_input_fails_before_connection(self):
        get_db = mock.Mock(side_effect=AssertionError("must not connect"))
        self.assert_fixed(
            "human_action_kernel_input_invalid",
            lambda: kernel.create_review_acknowledgement_proposal(
                get_db,
                AUTHENTICATION,
                company_mode="company",
                company_id="4",
                body={**BODY, "extra": "PRIVATE"},
            ),
        )
        get_db.assert_not_called()

    def test_authentication_or_current_preview_failure_rolls_back_everything(self):
        cases = (
            (
                "authentication",
                FakeConnection(proposal_steps(actor=None)[:2]),
                ready_preview(),
                "human_action_kernel_authentication_required",
            ),
            (
                "stale",
                FakeConnection(proposal_steps()[:2]),
                ready_preview(state="stale", contentSha256=None),
                "human_action_kernel_source_stale",
            ),
        )
        for name, connection, preview, code in cases:
            with self.subTest(name=name), mock.patch.object(
                kernel, "_rebuild_current_preview", return_value=preview,
            ):
                self.assert_fixed(
                    code,
                    lambda: kernel.create_review_acknowledgement_proposal(
                        lambda: connection,
                        AUTHENTICATION,
                        company_mode="company",
                        company_id="4",
                        body=BODY,
                    ),
                )
            self.assertEqual(connection.commits, 0)
            self.assertEqual(connection.rollbacks, 1)
            self.assertEqual(connection.closes, 1)
            self.assertTrue(connection.cursor_value.closed)
            self.assertFalse(any(
                sql.startswith("INSERT INTO")
                for sql, _params in connection.cursor_value.calls
            ))

    def test_commit_failure_is_uncertain_and_does_not_guess(self):
        connection = FakeConnection(
            proposal_steps(), commit_error=RuntimeError("PRIVATE COMMIT"),
        )
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ):
            self.assert_fixed(
                "human_action_kernel_commit_outcome_unknown",
                lambda: kernel.create_review_acknowledgement_proposal(
                    lambda: connection,
                    AUTHENTICATION,
                    company_mode="company",
                    company_id="4",
                    body=BODY,
                ),
            )
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.closes, 1)

    def test_successful_commit_with_cleanup_failure_has_one_fixed_outcome(self):
        connection = FakeConnection(
            proposal_steps(),
            cursor_close_error=RuntimeError("PRIVATE CURSOR CLOSE"),
        )
        with mock.patch.object(
            kernel, "_rebuild_current_preview", return_value=ready_preview(),
        ):
            self.assert_fixed(
                "human_action_kernel_cleanup_failed",
                lambda: kernel.create_review_acknowledgement_proposal(
                    lambda: connection,
                    AUTHENTICATION,
                    company_mode="company",
                    company_id="4",
                    body=BODY,
                ),
            )
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertEqual(connection.closes, 1)

    def test_control_identity_and_rollback_failure_precedence_are_preserved(self):
        control = KeyboardInterrupt("PRIVATE CONTROL")
        connection = FakeConnection(proposal_steps()[:2])
        with mock.patch.object(
            kernel, "_rebuild_current_preview", side_effect=control,
        ):
            caught = None
            try:
                kernel.create_review_acknowledgement_proposal(
                    lambda: connection,
                    AUTHENTICATION,
                    company_mode="company",
                    company_id="4",
                    body=BODY,
                )
            except KeyboardInterrupt as error:
                caught = error
        self.assertIs(caught, control)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_value.closed)
        self.assertEqual(connection.closes, 1)

        rollback_connection = FakeConnection(
            proposal_steps()[:2],
            rollback_error=RuntimeError("PRIVATE ROLLBACK"),
        )
        with mock.patch.object(
            kernel,
            "_rebuild_current_preview",
            side_effect=RuntimeError("PRIVATE READ"),
        ):
            self.assert_fixed(
                "human_action_kernel_rollback_failed",
                lambda: kernel.create_review_acknowledgement_proposal(
                    lambda: rollback_connection,
                    AUTHENTICATION,
                    company_mode="company",
                    company_id="4",
                    body=BODY,
                ),
            )
        self.assertEqual(rollback_connection.rollbacks, 1)
        self.assertTrue(rollback_connection.cursor_value.closed)
        self.assertEqual(rollback_connection.closes, 1)


if __name__ == "__main__":
    unittest.main()
