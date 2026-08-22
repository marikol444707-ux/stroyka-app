import unittest
from unittest import mock

from backend.features.accounting_exception_checks import ownership_remediation_runner
from backend.features.accounting_exception_checks.ownership_remediation import (
    build_accounting_ownership_remediation_request,
)


class _Cursor:
    def __init__(self):
        self.calls = []
        self.closed = False
        self.rowcount = 1
        self.fetchone_value = {"id": 900}

    def execute(self, sql, params=()):
        self.calls.append((" ".join(str(sql).split()), tuple(params or ())))

    def fetchone(self):
        return self.fetchone_value

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_value = _Cursor()
        self.sessions = []
        self.commits = 0
        self.rollbacks = 0

    def set_session(self, **kwargs):
        self.sessions.append(dict(kwargs))

    def cursor(self, **_kwargs):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _InspectionCursor:
    def __init__(self):
        self.calls = []
        self.rows = []

    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, tuple(params or ())))
        if "FROM public.users" in normalized:
            self.rows = [{"id": 31}]
        elif "FROM public.companies" in normalized:
            self.rows = [{"id": 4}]
        elif "FROM public.projects" in normalized:
            self.rows = [{"id": 19}]
        elif (
            "FROM public.accountable_payments" in normalized
            and "given_to_id" in normalized
        ):
            self.rows = [{
                "id": 200,
                "company_id": None,
                "project_id": None,
                "company_scope_verified": False,
                "given_to_id": 100,
            }]
        elif "FROM public.staff" in normalized:
            self.rows = [{"id": 100}]
        else:
            raise AssertionError("unexpected SQL: " + normalized)

    def fetchall(self):
        return list(self.rows)


def _request():
    return build_accounting_ownership_remediation_request(
        source="accountable_payments",
        record_id=200,
        company_id=4,
        project_id=19,
        operator_user_id=31,
    )


def _evidence(status="ready", fingerprint="a" * 64):
    return {
        **_request(),
        "state": status,
        "evidenceSha256": fingerprint,
    }


class AccountingOwnershipRemediationRunnerTests(unittest.TestCase):
    def test_apply_inspection_uses_only_exact_row_locks(self):
        cursor = _InspectionCursor()
        with mock.patch.object(
            ownership_remediation_runner,
            "_schema_contract_is_exact",
            return_value=True,
        ):
            result = ownership_remediation_runner._inspect_request(
                cursor, _request(), lock=True
            )

        self.assertEqual(result["state"], "ready")
        sql = [query for query, _ in cursor.calls]
        self.assertTrue(any(
            "FROM public.accountable_payments" in query
            and query.endswith("FOR UPDATE")
            for query in sql
        ))
        self.assertEqual(
            sum(query.endswith("FOR KEY SHARE") for query in sql), 4
        )
        self.assertFalse(any(query.startswith("LOCK TABLE") for query in sql))

    def test_evidence_fingerprint_binds_the_fixed_parent_link(self):
        request = _request()
        target = {
            "company_id": None,
            "project_id": None,
            "company_scope_verified": False,
            "given_to_id": 100,
        }
        original = ownership_remediation_runner._evidence_sha256(
            request, target, "ready"
        )
        changed = ownership_remediation_runner._evidence_sha256(
            request, {**target, "given_to_id": 101}, "ready"
        )

        self.assertRegex(original, r"^[0-9a-f]{64}$")
        self.assertNotEqual(original, changed)

    def test_default_is_read_only_and_returns_only_detached_evidence(self):
        connection = _Connection()
        evidence = _evidence()
        with mock.patch.object(ownership_remediation_runner, "_inspect_request", return_value=evidence):
            report = ownership_remediation_runner.run_accounting_ownership_remediation(
                connection, _request()
            )

        self.assertEqual(report, {**evidence, "rolledBack": True})
        self.assertEqual(connection.sessions, [{"readonly": True, "autocommit": False}])
        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertFalse(any(sql.startswith(("UPDATE ", "INSERT ")) for sql, _ in connection.cursor_value.calls))

    def test_apply_guard_rejects_missing_or_invalid_fingerprint_before_database(self):
        connection = _Connection()
        with self.assertRaisesRegex(ValueError, "accounting_remediation_apply_guard_invalid"):
            ownership_remediation_runner.run_accounting_ownership_remediation(
                connection, _request(), apply=True, expected_evidence_sha256="bad"
            )
        self.assertEqual(connection.sessions, [])
        self.assertEqual(connection.cursor_value.calls, [])

    def test_malformed_request_fails_with_fixed_error_before_database(self):
        connection = _Connection()
        malformed = {**_request(), "source": ["accountable_payments"]}

        with self.assertRaisesRegex(
            ValueError, "accounting_remediation_input_invalid"
        ):
            ownership_remediation_runner.run_accounting_ownership_remediation(
                connection, malformed
            )

        self.assertEqual(connection.sessions, [])
        self.assertEqual(connection.cursor_value.calls, [])

    def test_apply_revalidates_updates_one_row_writes_audit_and_commits(self):
        connection = _Connection()
        before = _evidence("ready")
        after = _evidence("already_verified", "b" * 64)
        with mock.patch.object(
            ownership_remediation_runner, "_inspect_request", side_effect=[before, after]
        ):
            report = ownership_remediation_runner.run_accounting_ownership_remediation(
                connection,
                _request(),
                apply=True,
                expected_evidence_sha256=before["evidenceSha256"],
            )

        self.assertTrue(report["complete"])
        self.assertEqual(report["writesAttempted"], 1)
        self.assertEqual(report["auditWritesAttempted"], 1)
        self.assertEqual(report["auditEventId"], 900)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        sql = [query for query, _ in connection.cursor_value.calls]
        self.assertEqual(sum(query.startswith("LOCK TABLE public.") for query in sql), 0)
        self.assertEqual(sum(query.startswith("UPDATE public.") for query in sql), 1)
        self.assertEqual(sum(query.startswith("INSERT INTO public.audit_log") for query in sql), 1)

    def test_apply_rejects_drift_or_blocked_evidence_before_writes(self):
        for evidence, expected, message in (
            (_evidence("ready", "b" * 64), "a" * 64, "accounting_remediation_evidence_changed"),
            (_evidence("blocked"), "a" * 64, "accounting_remediation_owner_invalid"),
        ):
            connection = _Connection()
            with self.subTest(message=message):
                with mock.patch.object(ownership_remediation_runner, "_inspect_request", return_value=evidence):
                    with self.assertRaisesRegex(RuntimeError, message):
                        ownership_remediation_runner.run_accounting_ownership_remediation(
                            connection,
                            _request(),
                            apply=True,
                            expected_evidence_sha256=expected,
                        )
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)
                self.assertFalse(any(sql.startswith(("UPDATE ", "INSERT ")) for sql, _ in connection.cursor_value.calls))

    def test_audit_or_postcheck_failure_rolls_back_the_owner_update(self):
        before = _evidence("ready")
        for audit_effect, inspections, message in (
            (RuntimeError("audit failed"), [before], "audit failed"),
            (None, [before, _evidence("ready", "b" * 64)], "accounting_remediation_postcheck_failed"),
        ):
            connection = _Connection()
            with self.subTest(message=message):
                with mock.patch.object(ownership_remediation_runner, "_inspect_request", side_effect=inspections), mock.patch.object(
                    ownership_remediation_runner,
                    "_insert_audit_event",
                    side_effect=audit_effect,
                    return_value=900,
                ):
                    with self.assertRaisesRegex(RuntimeError, message):
                        ownership_remediation_runner.run_accounting_ownership_remediation(
                            connection,
                            _request(),
                            apply=True,
                            expected_evidence_sha256=before["evidenceSha256"],
                        )
                self.assertEqual(connection.commits, 0)
                self.assertEqual(connection.rollbacks, 1)


if __name__ == "__main__":
    unittest.main()
