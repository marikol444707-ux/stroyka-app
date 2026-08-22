import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from backend.features.accounting_exception_checks import (
    ownership_remediation_command,
)


class _Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class AccountingOwnershipRemediationCommandTests(unittest.TestCase):
    def _base_args(self):
        return [
            "--source", "accountable_payments",
            "--record-id", "200",
            "--company-id", "4",
            "--project-id", "19",
            "--operator-user-id", "31",
        ]

    def test_default_command_is_dry_run_and_closes_connection(self):
        connection = _Connection()
        report = {
            "dryRun": True,
            "requestSha256": "a" * 64,
            "evidenceSha256": "b" * 64,
            "state": "ready",
        }
        output = io.StringIO()
        with mock.patch.object(
            ownership_remediation_command,
            "_open_connection",
            return_value=connection,
        ) as opener, mock.patch.object(
            ownership_remediation_command,
            "run_accounting_ownership_remediation",
            return_value=report,
        ) as runner, redirect_stdout(output):
            exit_code = ownership_remediation_command.main(self._base_args())

        self.assertEqual(exit_code, 0)
        opener.assert_called_once_with()
        self.assertTrue(connection.closed)
        runner.assert_called_once()
        _connection, request = runner.call_args.args
        self.assertIs(_connection, connection)
        self.assertEqual(request["recordId"], 200)
        self.assertEqual(request["companyId"], 4)
        self.assertEqual(request["projectId"], 19)
        self.assertEqual(runner.call_args.kwargs, {
            "apply": False,
            "expected_evidence_sha256": None,
        })
        self.assertEqual(json.loads(output.getvalue()), report)

    def test_apply_requires_all_three_guards_before_database(self):
        incomplete = (
            ["--apply"],
            ["--apply", "--confirm", ownership_remediation_command.APPLY_CONFIRMATION],
            [
                "--apply", "--confirm",
                ownership_remediation_command.APPLY_CONFIRMATION,
                "--expected-request-sha256", "a" * 64,
            ],
        )
        for extra in incomplete:
            with self.subTest(extra=extra), mock.patch.object(
                ownership_remediation_command, "_open_connection"
            ) as opener, self.assertRaises(SystemExit):
                ownership_remediation_command.main(self._base_args() + extra)
            opener.assert_not_called()

    def test_apply_rejects_request_drift_before_database(self):
        args = self._base_args() + [
            "--apply",
            "--confirm", ownership_remediation_command.APPLY_CONFIRMATION,
            "--expected-request-sha256", "a" * 64,
            "--expected-evidence-sha256", "b" * 64,
        ]
        with mock.patch.object(
            ownership_remediation_command, "_open_connection"
        ) as opener, self.assertRaises(SystemExit):
            ownership_remediation_command.main(args)
        opener.assert_not_called()

    def test_apply_passes_only_exact_guarded_request_and_closes(self):
        connection = _Connection()
        request = ownership_remediation_command.build_accounting_ownership_remediation_request(
            source="accountable_payments",
            record_id=200,
            company_id=4,
            project_id=19,
            operator_user_id=31,
        )
        args = self._base_args() + [
            "--apply",
            "--confirm", ownership_remediation_command.APPLY_CONFIRMATION,
            "--expected-request-sha256", request["requestSha256"],
            "--expected-evidence-sha256", "b" * 64,
        ]
        with mock.patch.object(
            ownership_remediation_command,
            "_open_connection",
            return_value=connection,
        ), mock.patch.object(
            ownership_remediation_command,
            "run_accounting_ownership_remediation",
            return_value={"complete": True},
        ) as runner, redirect_stdout(io.StringIO()):
            self.assertEqual(ownership_remediation_command.main(args), 0)

        self.assertTrue(connection.closed)
        runner.assert_called_once_with(
            connection,
            request,
            apply=True,
            expected_evidence_sha256="b" * 64,
        )

    def test_runner_failure_still_closes_connection(self):
        connection = _Connection()
        with mock.patch.object(
            ownership_remediation_command,
            "_open_connection",
            return_value=connection,
        ), mock.patch.object(
            ownership_remediation_command,
            "run_accounting_ownership_remediation",
            side_effect=RuntimeError("accounting_remediation_owner_invalid"),
        ), self.assertRaisesRegex(
            RuntimeError, "accounting_remediation_owner_invalid"
        ):
            ownership_remediation_command.main(self._base_args())

        self.assertTrue(connection.closed)

    def test_dry_run_forbids_apply_guards_and_invalid_ids_before_database(self):
        cases = (
            self._base_args() + ["--expected-evidence-sha256", "b" * 64],
            [
                "--source", "accountable_payments",
                "--record-id", "0",
                "--company-id", "4",
                "--project-id", "19",
                "--operator-user-id", "31",
            ],
        )
        for args in cases:
            with self.subTest(args=args), mock.patch.object(
                ownership_remediation_command, "_open_connection"
            ) as opener, self.assertRaises(SystemExit):
                ownership_remediation_command.main(args)
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
