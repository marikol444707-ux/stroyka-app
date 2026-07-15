import unittest
from contextlib import redirect_stderr
from io import StringIO
from unittest.mock import Mock, patch

from backend.features.tenant_readiness.report import build_report, main, run_report


def entry(resource, state="stored", *, kind="table", access="verified"):
    return {
        "domain": "test",
        "resource": resource,
        "kind": kind,
        "companyState": state,
        "accessState": access,
    }


def company_fact(*, index=True, null_rows=0):
    return {
        "exists": True,
        "columns": {"company_id": {"nullable": True}},
        "indexes": ["CREATE INDEX idx_company ON sample(company_id)"] if index else [],
        "constraints": [],
        "totalRows": 3,
        "companyNullRows": null_rows,
        "ownerScopeNullRows": 0,
        "companyOwnerNullRows": 0,
        "invalidOwnerScopeRows": 0,
        "orphanCompanyRows": 0,
        "orphanProjectRows": 0,
        "mismatchedProjectRows": 0,
    }


class TenantReadinessReportTests(unittest.TestCase):
    def test_registry_states_and_pending_runtime_block_constraints(self):
        entries = [
            entry("missing_table", "missing", access=""),
            entry("legacy_table", "legacy_default", access=""),
            entry("uploads", "public_surface", kind="surface", access=""),
            entry("pending_table", access="stored_owner_runtime_local_release_pending"),
        ]

        report = build_report(entries, {"pending_table": company_fact()})

        self.assertFalse(report["readyForConstraints"])
        reasons = {item["resource"]: item["reason"] for item in report["registryBlockers"]}
        self.assertEqual(reasons["missing_table"], "owner_state_missing")
        self.assertEqual(reasons["legacy_table"], "owner_state_legacy_default")
        self.assertEqual(reasons["uploads"], "public_surface_not_private")
        self.assertEqual(reasons["pending_table"], "runtime_release_pending")

    def test_verified_stored_table_with_index_and_no_null_owner_is_candidate(self):
        report = build_report([entry("sample")], {"sample": company_fact()})

        self.assertTrue(report["readyForConstraints"])
        self.assertEqual(report["constraintCandidates"], ["sample"])
        self.assertEqual(report["schemaBlockers"], [])

    def test_missing_company_index_blocks_constraint_planning(self):
        report = build_report([entry("sample")], {"sample": company_fact(index=False)})

        self.assertFalse(report["readyForConstraints"])
        self.assertEqual(report["schemaBlockers"][0]["reason"], "company_index_missing")

    def test_company_null_rows_block_company_owned_table(self):
        report = build_report([entry("sample")], {"sample": company_fact(null_rows=2)})

        self.assertFalse(report["readyForConstraints"])
        self.assertEqual(report["schemaBlockers"][0]["count"], 2)
        self.assertEqual(report["schemaBlockers"][0]["reason"], "company_owner_missing")

    def test_scoped_table_allows_platform_rows_but_rejects_broken_company_owner(self):
        fact = company_fact()
        fact["columns"]["owner_scope"] = {"nullable": True}
        fact["companyNullRows"] = 2
        fact["companyOwnerNullRows"] = 0
        report = build_report([entry("api_errors")], {"api_errors": fact})
        self.assertTrue(report["readyForConstraints"])

        fact["companyOwnerNullRows"] = 1
        report = build_report([entry("api_errors")], {"api_errors": fact})
        self.assertFalse(report["readyForConstraints"])
        self.assertEqual(report["schemaBlockers"][0]["reason"], "company_scope_owner_missing")

    def test_orphan_company_and_project_relationships_block_constraints(self):
        fact = company_fact()
        fact["columns"]["project_id"] = {"nullable": True}
        fact["indexes"].append("CREATE INDEX idx_project ON sample(project_id)")
        fact["orphanCompanyRows"] = 1
        fact["orphanProjectRows"] = 2
        fact["mismatchedProjectRows"] = 3

        report = build_report([entry("sample")], {"sample": fact})

        self.assertFalse(report["readyForConstraints"])
        reasons = {item["reason"]: item["count"] for item in report["schemaBlockers"]}
        self.assertEqual(reasons["company_not_found"], 1)
        self.assertEqual(reasons["project_not_found"], 2)
        self.assertEqual(reasons["project_company_mismatch"], 3)

    def test_project_column_requires_project_index(self):
        fact = company_fact()
        fact["columns"]["project_id"] = {"nullable": True}

        report = build_report([entry("sample")], {"sample": fact})

        self.assertFalse(report["readyForConstraints"])
        self.assertEqual(report["schemaBlockers"][0]["reason"], "project_index_missing")

    def test_unknown_owner_scope_blocks_constraint_planning(self):
        fact = company_fact()
        fact["columns"]["owner_scope"] = {"nullable": True}
        fact["invalidOwnerScopeRows"] = 4

        report = build_report([entry("sample")], {"sample": fact})

        self.assertFalse(report["readyForConstraints"])
        self.assertEqual(report["schemaBlockers"][0]["reason"], "owner_scope_invalid")
        self.assertEqual(report["schemaBlockers"][0]["count"], 4)

    def test_run_report_forces_read_only_transaction_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur

        with patch(
            "backend.features.tenant_readiness.report.collect_table_facts",
            return_value={},
        ):
            report = run_report(conn, [])

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        self.assertTrue(report["rolledBack"])

    def test_cli_reports_connection_failure_without_unhandled_traceback(self):
        stderr = StringIO()

        with patch(
            "backend.features.tenant_readiness.report.psycopg2.connect",
            side_effect=RuntimeError("database unavailable"),
        ), redirect_stderr(stderr):
            exit_code = main()

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "FAIL: RuntimeError: database unavailable\n")


if __name__ == "__main__":
    unittest.main()
