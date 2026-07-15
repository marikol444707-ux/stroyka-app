import unittest
from unittest.mock import Mock, patch

from backend.features.tenant_readiness.coverage_report import (
    build_coverage_report,
    collect_schema_tables,
    run_coverage_report,
)


def entry(resource, *, kind="table"):
    return {
        "resource": resource,
        "kind": kind,
        "companyState": "stored" if kind == "table" else "public_surface",
    }


class TenantRegistryCoverageTests(unittest.TestCase):
    def test_exact_registered_schema_is_ready_for_freeze(self):
        report = build_coverage_report(
            [entry("projects"), entry("uploads", kind="surface")],
            {"projects": {"id", "company_id", "name"}},
        )

        self.assertTrue(report["readyForRegistryFreeze"])
        self.assertEqual(report["summary"]["registeredTables"], 1)
        self.assertEqual(report["unregisteredTables"], [])
        self.assertEqual(report["registeredTablesMissing"], [])

    def test_unregistered_company_owned_table_is_critical(self):
        report = build_coverage_report(
            [entry("projects")],
            {
                "projects": {"id", "company_id"},
                "crm_leads": {"id", "company_id", "name"},
            },
        )

        self.assertFalse(report["readyForRegistryFreeze"])
        self.assertEqual(report["summary"]["unregisteredTables"], 1)
        self.assertEqual(report["unregisteredTables"][0], {
            "resource": "crm_leads",
            "risk": "critical",
            "ownershipSignals": ["company_id"],
        })

    def test_project_signal_and_unclassified_table_are_both_fail_closed(self):
        report = build_coverage_report(
            [],
            {
                "project_documents": {"id", "project_id"},
                "shared_lookup": {"id", "label"},
            },
        )

        by_resource = {item["resource"]: item for item in report["unregisteredTables"]}
        self.assertEqual(by_resource["project_documents"]["risk"], "high")
        self.assertEqual(by_resource["project_documents"]["ownershipSignals"], ["project_id"])
        self.assertEqual(by_resource["shared_lookup"]["risk"], "unclassified")
        self.assertEqual(by_resource["shared_lookup"]["ownershipSignals"], [])
        self.assertFalse(report["readyForRegistryFreeze"])

    def test_missing_registered_table_and_duplicate_registry_entry_block_freeze(self):
        report = build_coverage_report(
            [entry("projects"), entry("projects"), entry("missing_table")],
            {"projects": {"id", "company_id"}},
        )

        self.assertFalse(report["readyForRegistryFreeze"])
        self.assertEqual(report["duplicateRegistryTables"], ["projects"])
        self.assertEqual(report["registeredTablesMissing"], ["missing_table"])

    def test_run_report_is_read_only_and_rolls_back(self):
        conn = Mock()
        cur = Mock()
        conn.cursor.return_value = cur

        with patch(
            "backend.features.tenant_readiness.coverage_report.collect_schema_tables",
            return_value={"projects": {"id", "company_id"}},
        ):
            result = run_coverage_report(conn, [entry("projects")])

        conn.set_session.assert_called_once_with(readonly=True, autocommit=False)
        conn.rollback.assert_called_once_with()
        cur.close.assert_called_once_with()
        self.assertTrue(result["rolledBack"])
        self.assertEqual(result["writesAttempted"], 0)

    def test_schema_collector_reads_metadata_without_business_rows(self):
        cur = Mock()
        cur.fetchall.return_value = [
            {"table_name": "projects", "column_name": "id"},
            {"table_name": "projects", "column_name": "company_id"},
            {"table_name": "crm_leads", "column_name": "project_id"},
        ]

        tables = collect_schema_tables(cur)

        self.assertEqual(tables, {
            "projects": {"id", "company_id"},
            "crm_leads": {"project_id"},
        })
        sql = " ".join(str(cur.execute.call_args.args[0]).split())
        self.assertIn("information_schema.columns", sql)
        self.assertIn("information_schema.tables", sql)
        self.assertNotIn("COUNT(", sql.upper())


if __name__ == "__main__":
    unittest.main()
