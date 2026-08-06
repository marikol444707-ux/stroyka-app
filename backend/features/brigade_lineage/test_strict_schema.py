import unittest

from backend.features.brigade_lineage.strict_schema import (
    _DDL_BY_PLAN_KEY,
    build_strict_migration_report,
)
from backend.features.brigade_lineage.constraint_audit import (
    build_constraint_audit,
)
from backend.features.brigade_lineage.test_constraint_audit import complete_facts


CONSTRAINT_NAMES = [
    "chk_brigade_contract_items_source_shape",
    "chk_brigade_contract_items_source_type",
    "chk_estimate_versions_sections_sha256",
    "fk_brigade_contract_items_contract_id",
    "fk_brigade_contract_items_source_estimate_version_id",
    "fk_estimate_versions_estimate_id",
]
INDEX_NAMES = [
    "idx_brigade_contract_items_source_estimate_version",
    "uq_brigade_contract_items_estimate_source",
    "uq_estimate_versions_estimate_sections_sha256",
]
TRIGGER_NAMES = [
    "trg_brigade_contract_items_source_guard",
    "trg_estimate_versions_snapshot_immutable",
]


def constraint_report(*, complete=False):
    return {
        "ok": complete,
        "dryRun": True,
        "writesAttempted": 0,
        "catalogReady": complete,
        "dataReadyForConstraints": True,
        "constraintsReady": complete,
        "missingColumns": [],
        "invalidColumns": [] if complete else [
            "brigade_contract_items.source_type.noDefault",
            "brigade_contract_items.source_type.notNull",
        ],
        "missingConstraints": [] if complete else list(CONSTRAINT_NAMES),
        "invalidConstraints": [],
        "missingIndexes": [] if complete else list(INDEX_NAMES),
        "invalidIndexes": [],
        "missingTriggers": [] if complete else list(TRIGGER_NAMES),
        "invalidTriggers": [],
        "data": {
            "sourceTypeNull": 0,
            "invalidSourceType": 0,
            "invalidSourceShape": 0,
            "orphanContract": 0,
            "orphanSourceVersion": 0,
            "orphanEstimateVersion": 0,
            "crossOwnerEstimateSource": 0,
            "missingSnapshotHash": 0,
            "invalidSnapshotHash": 0,
            "duplicateEstimateLineage": 0,
            "duplicateSnapshotHash": 0,
            "explicitLegacy": 151,
        },
        "dataIssues": [],
    }


def writer_report(*, ready=True):
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "insertStatements": 3,
        "updateStatements": 3,
        "violations": [] if ready else [{"code": "writer_changed"}],
    }


def delete_report(*, ready=True):
    return {
        "ok": ready,
        "dryRun": True,
        "writesAttempted": 0,
        "deleteRestrictionsReady": ready,
        "violations": [] if ready else ["exactEstimateVersionBlockerMissing"],
    }


def lineage_report(*, invalid=0, total=151):
    return {
        "schemaState": "complete",
        "baseSchemaPresent": True,
        "reportConsistent": True,
        "summary": {
            "totalRows": total,
            "byState": {
                "verifiedEstimate": 0,
                "declaredManual": 0,
                "declaredPricelist": 0,
                "legacy": total - invalid,
                "invalid": invalid,
            },
            "bySourceType": {
                "estimate": 0,
                "manual": 0,
                "pricelist": 0,
                "legacy": total,
                "unclassified": 0,
            },
        },
    }


def reports(*, complete=False, invalid=0):
    return (
        constraint_report(complete=complete),
        writer_report(),
        delete_report(),
        lineage_report(invalid=invalid),
    )


class StrictLineageMigrationPlanTests(unittest.TestCase):
    def test_current_production_shape_plans_exact_bounded_changes(self):
        report = build_strict_migration_report(*reports())

        self.assertTrue(report["ok"])
        self.assertTrue(report["readyForApply"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["changeCount"], 13)
        self.assertEqual(report["summary"], {
            "columnChanges": 2,
            "constraints": 6,
            "indexes": 3,
            "triggers": 2,
            "blockers": 0,
            "explicitLegacy": 151,
        })
        self.assertEqual(
            [item["name"] for item in report["plannedChanges"] if item["kind"] == "constraint"],
            CONSTRAINT_NAMES,
        )
        self.assertEqual(len(report["planSha256"]), 64)
        self.assertNotIn("CREATE FUNCTION", str(report["plannedChanges"]))

    def test_invalid_catalog_object_or_data_issue_blocks_apply(self):
        constraints, writers, deletion, lineage = reports()
        constraints["missingConstraints"].remove(CONSTRAINT_NAMES[0])
        constraints["invalidConstraints"] = [CONSTRAINT_NAMES[0]]
        constraints["dataReadyForConstraints"] = False
        constraints["dataIssues"] = ["orphanContract"]
        constraints["data"]["orphanContract"] = 1

        report = build_strict_migration_report(
            constraints, writers, deletion, lineage
        )

        self.assertFalse(report["ok"])
        self.assertFalse(report["readyForApply"])
        self.assertIn("invalidConstraint:" + CONSTRAINT_NAMES[0], report["blockers"])
        self.assertIn("data:orphanContract", report["blockers"])

    def test_writer_and_delete_policy_are_hard_apply_gates(self):
        report = build_strict_migration_report(
            constraint_report(),
            writer_report(ready=False),
            delete_report(ready=False),
            lineage_report(),
        )

        self.assertFalse(report["readyForApply"])
        self.assertIn("writersNotReady", report["blockers"])
        self.assertIn("deleteRestrictionsNotReady", report["blockers"])

    def test_plan_hash_changes_when_bounded_production_counts_drift(self):
        before = build_strict_migration_report(*reports())
        constraints, writers, deletion, lineage = reports()
        constraints["data"]["explicitLegacy"] = 152

        after = build_strict_migration_report(
            constraints, writers, deletion, lineage
        )

        self.assertNotEqual(before["planSha256"], after["planSha256"])

    def test_rollback_plan_is_reverse_order_and_contains_no_data_rewrite(self):
        report = build_strict_migration_report(*reports())
        rollback = " ".join(report["rollbackSql"])

        self.assertTrue(report["rollbackSql"][0].startswith("DROP TRIGGER"))
        self.assertIn("DROP INDEX", rollback)
        self.assertIn("DROP CONSTRAINT", rollback)
        self.assertIn("ALTER COLUMN source_type DROP NOT NULL", rollback)
        self.assertTrue(report["rollbackSql"][-1].endswith("SET DEFAULT 'legacy';"))
        self.assertNotIn("UPDATE ", rollback)

    def test_invalid_canonical_lineage_blocks_apply_even_when_aggregates_are_green(self):
        report = build_strict_migration_report(*reports(invalid=1))

        self.assertFalse(report["ok"])
        self.assertFalse(report["readyForApply"])
        self.assertIn("lineageRowsInvalid", report["blockers"])

    def test_generated_constraint_and_trigger_definitions_match_readiness_contract(self):
        facts = complete_facts()
        for item in facts["constraints"]:
            key = "constraint:" + item["constraint_name"]
            item["definition"] = _DDL_BY_PLAN_KEY[key][0]
        for item in facts["triggers"]:
            key = "trigger:" + item["trigger_name"]
            item["function_definition"] = _DDL_BY_PLAN_KEY[key][0]

        report = build_constraint_audit(facts)

        self.assertTrue(report["constraintsReady"])
        self.assertEqual(report["invalidConstraints"], [])
        self.assertEqual(report["invalidTriggers"], [])


if __name__ == "__main__":
    unittest.main()
