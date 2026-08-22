import inspect
import unittest

from backend.features.accounting_exception_checks import ownership_remediation


class AccountingOwnershipRemediationRequestTests(unittest.TestCase):
    def test_builds_deterministic_allowlisted_exact_id_request(self):
        first = ownership_remediation.build_accounting_ownership_remediation_request(
            source="accountable_payments",
            record_id=200,
            company_id=4,
            project_id=19,
            operator_user_id=31,
        )
        second = ownership_remediation.build_accounting_ownership_remediation_request(
            source="accountable_payments",
            record_id=200,
            company_id=4,
            project_id=19,
            operator_user_id=31,
        )

        self.assertEqual(first, second)
        self.assertEqual(first, {
            "version": "accounting-ownership-remediation-v1",
            "dryRun": True,
            "applyAllowed": False,
            "writesAttempted": 0,
            "auditWritesAttempted": 0,
            "source": "accountable_payments",
            "recordId": 200,
            "companyId": 4,
            "projectId": 19,
            "operatorUserId": 31,
            "requestSha256": first["requestSha256"],
        })
        self.assertRegex(first["requestSha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("name", repr(first).lower())
        self.assertNotIn("description", repr(first).lower())

    def test_company_only_sources_forbid_project_and_project_sources_require_it(self):
        for source in ("staff", "salary_payments"):
            value = ownership_remediation.build_accounting_ownership_remediation_request(
                source=source,
                record_id=1,
                company_id=4,
                project_id=None,
                operator_user_id=31,
            )
            self.assertIsNone(value["projectId"])

        for source in (
            "accountable_payments",
            "accountable_expenses",
            "expense_reports",
            "own_expenses",
            "expenses",
        ):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "accounting_remediation_input_invalid"):
                    ownership_remediation.build_accounting_ownership_remediation_request(
                        source=source,
                        record_id=1,
                        company_id=4,
                        project_id=None,
                        operator_user_id=31,
                    )

        with self.assertRaisesRegex(ValueError, "accounting_remediation_input_invalid"):
            ownership_remediation.build_accounting_ownership_remediation_request(
                source="staff",
                record_id=1,
                company_id=4,
                project_id=19,
                operator_user_id=31,
            )

    def test_rejects_unknown_sources_bool_strings_zero_and_subclasses(self):
        class IntSubclass(int):
            pass

        cases = (
            {"source": "unknown"},
            {"source": ["accountable_payments"]},
            {"record_id": True},
            {"record_id": "1"},
            {"record_id": 0},
            {"company_id": IntSubclass(4)},
            {"project_id": -1},
            {"operator_user_id": False},
        )
        base = {
            "source": "accountable_payments",
            "record_id": 1,
            "company_id": 4,
            "project_id": 19,
            "operator_user_id": 31,
        }
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaisesRegex(ValueError, "accounting_remediation_input_invalid"):
                    ownership_remediation.build_accounting_ownership_remediation_request(
                        **{**base, **override}
                    )

    def test_contract_has_no_database_registration_cli_or_automatic_apply(self):
        source = inspect.getsource(ownership_remediation)
        for forbidden in (
            "psycopg2",
            "get_db",
            "backend.main",
            "register_",
            "argparse",
            "if __name__",
            "INSERT ",
            "UPDATE ",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
