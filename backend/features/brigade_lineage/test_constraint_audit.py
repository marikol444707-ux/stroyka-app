import unittest

from backend.features.brigade_lineage.constraint_audit import (
    audit_brigade_lineage_constraints,
    build_constraint_audit,
)


def complete_facts():
    columns = [
        {
            "table_name": table,
            "column_name": column,
            "is_nullable": "NO" if (table, column) == (
                "brigade_contract_items",
                "source_type",
            ) else "YES",
            "column_default": None,
        }
        for table, column in (
            ("brigade_contract_items", "id"),
            ("brigade_contract_items", "contract_id"),
            ("brigade_contract_items", "source_type"),
            ("brigade_contract_items", "source_estimate_version_id"),
            ("brigade_contract_items", "source_section_index"),
            ("brigade_contract_items", "source_item_index"),
            ("brigade_contract_items", "source_item_key"),
            ("brigade_contracts", "id"),
            ("brigade_contracts", "company_id"),
            ("brigade_contracts", "project_id"),
            ("estimate_versions", "id"),
            ("estimate_versions", "estimate_id"),
            ("estimate_versions", "sections_json"),
            ("estimate_versions", "sections_sha256"),
            ("estimates", "id"),
            ("estimates", "company_id"),
            ("estimates", "project_id"),
        )
    ]
    constraints = [
        {
            "constraint_name": "fk_brigade_contract_items_contract_id",
            "table_name": "brigade_contract_items",
            "constraint_type": "f",
            "validated": True,
            "local_columns": ["contract_id"],
            "foreign_table": "brigade_contracts",
            "foreign_columns": ["id"],
            "delete_action": "r",
            "definition": "FOREIGN KEY (contract_id) REFERENCES brigade_contracts(id) ON DELETE RESTRICT",
        },
        {
            "constraint_name": "fk_brigade_contract_items_source_estimate_version_id",
            "table_name": "brigade_contract_items",
            "constraint_type": "f",
            "validated": True,
            "local_columns": ["source_estimate_version_id"],
            "foreign_table": "estimate_versions",
            "foreign_columns": ["id"],
            "delete_action": "r",
            "definition": "FOREIGN KEY (source_estimate_version_id) REFERENCES estimate_versions(id) ON DELETE RESTRICT",
        },
        {
            "constraint_name": "fk_estimate_versions_estimate_id",
            "table_name": "estimate_versions",
            "constraint_type": "f",
            "validated": True,
            "local_columns": ["estimate_id"],
            "foreign_table": "estimates",
            "foreign_columns": ["id"],
            "delete_action": "r",
            "definition": "FOREIGN KEY (estimate_id) REFERENCES estimates(id) ON DELETE RESTRICT",
        },
        {
            "constraint_name": "chk_brigade_contract_items_source_type",
            "table_name": "brigade_contract_items",
            "constraint_type": "c",
            "validated": True,
            "definition": "CHECK (source_type IN ('estimate','manual','pricelist','legacy'))",
        },
        {
            "constraint_name": "chk_brigade_contract_items_source_shape",
            "table_name": "brigade_contract_items",
            "constraint_type": "c",
            "validated": True,
            "definition": """CHECK (
                (source_type = 'estimate'
                 AND source_estimate_version_id IS NOT NULL
                 AND source_section_index >= 0
                 AND source_item_index >= 0
                 AND source_item_key IS NOT NULL
                 AND btrim(source_item_key) <> '')
                OR
                (source_type IN ('manual','pricelist','legacy')
                 AND source_estimate_version_id IS NULL
                 AND source_section_index IS NULL
                 AND source_item_index IS NULL
                 AND source_item_key IS NULL)
            )""",
        },
        {
            "constraint_name": "chk_estimate_versions_sections_sha256",
            "table_name": "estimate_versions",
            "constraint_type": "c",
            "validated": True,
            "definition": "CHECK (sections_sha256 IS NULL OR sections_sha256 ~ '^[0-9a-f]{64}$')",
        },
    ]
    indexes = [
        {
            "index_name": "uq_brigade_contract_items_estimate_source",
            "table_name": "brigade_contract_items",
            "is_unique": True,
            "is_valid": True,
            "is_ready": True,
            "columns": [
                "contract_id",
                "source_estimate_version_id",
                "source_section_index",
                "source_item_index",
                "source_item_key",
            ],
            "predicate": "source_type = 'estimate'",
        },
        {
            "index_name": "idx_brigade_contract_items_source_estimate_version",
            "table_name": "brigade_contract_items",
            "is_unique": False,
            "is_valid": True,
            "is_ready": True,
            "columns": ["source_estimate_version_id"],
            "predicate": "source_estimate_version_id IS NOT NULL",
        },
        {
            "index_name": "uq_estimate_versions_estimate_sections_sha256",
            "table_name": "estimate_versions",
            "is_unique": True,
            "is_valid": True,
            "is_ready": True,
            "columns": ["estimate_id", "sections_sha256"],
            "predicate": "sections_sha256 IS NOT NULL",
        },
    ]
    triggers = [
        {
            "trigger_name": "trg_brigade_contract_items_source_guard",
            "table_name": "brigade_contract_items",
            "enabled": "O",
            "is_row": True,
            "is_before": True,
            "fires_insert": True,
            "fires_update": True,
            "fires_delete": False,
            "function_schema": "public",
            "function_name": "brigade_contract_items_source_guard",
            "function_definition": """CREATE FUNCTION brigade_contract_items_source_guard()
                RETURNS trigger AS $$ BEGIN
                IF OLD.source_type IS DISTINCT FROM NEW.source_type
                   OR OLD.source_estimate_version_id IS DISTINCT FROM NEW.source_estimate_version_id
                   OR OLD.source_section_index IS DISTINCT FROM NEW.source_section_index
                   OR OLD.source_item_index IS DISTINCT FROM NEW.source_item_index
                   OR OLD.source_item_key IS DISTINCT FROM NEW.source_item_key
                THEN RAISE EXCEPTION 'immutable source'; END IF;
                PERFORM 1 FROM estimate_versions JOIN estimates ON estimates.id=estimate_versions.estimate_id
                JOIN brigade_contracts ON brigade_contracts.company_id=estimates.company_id
                  AND brigade_contracts.project_id=estimates.project_id;
                RETURN NEW; END $$ LANGUAGE plpgsql""",
        },
        {
            "trigger_name": "trg_estimate_versions_snapshot_immutable",
            "table_name": "estimate_versions",
            "enabled": "O",
            "is_row": True,
            "is_before": True,
            "fires_insert": False,
            "fires_update": True,
            "fires_delete": False,
            "function_schema": "public",
            "function_name": "estimate_versions_snapshot_immutable_guard",
            "function_definition": """CREATE FUNCTION estimate_versions_snapshot_immutable_guard()
                RETURNS trigger AS $$ BEGIN
                IF OLD.estimate_id IS DISTINCT FROM NEW.estimate_id
                   OR OLD.sections_json IS DISTINCT FROM NEW.sections_json
                   OR OLD.sections_sha256 IS DISTINCT FROM NEW.sections_sha256
                THEN RAISE EXCEPTION 'immutable snapshot'; END IF;
                RETURN NEW; END $$ LANGUAGE plpgsql""",
        },
    ]
    data = {
        "source_type_null": 0,
        "invalid_source_type": 0,
        "invalid_source_shape": 0,
        "orphan_contract": 0,
        "orphan_source_version": 0,
        "orphan_estimate_version": 0,
        "cross_owner_estimate_source": 0,
        "missing_snapshot_hash": 0,
        "invalid_snapshot_hash": 0,
        "duplicate_estimate_lineage": 0,
        "duplicate_snapshot_hash": 0,
    }
    return {
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "triggers": triggers,
        "data": data,
    }


class ConstraintAuditTests(unittest.TestCase):
    def test_complete_structural_facts_are_ready(self):
        report = build_constraint_audit(complete_facts())

        self.assertTrue(report["ok"])
        self.assertTrue(report["catalogReady"])
        self.assertTrue(report["dataReadyForConstraints"])
        self.assertTrue(report["constraintsReady"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["missingConstraints"], [])
        self.assertEqual(report["invalidConstraints"], [])
        self.assertEqual(report["invalidIndexes"], [])
        self.assertEqual(report["invalidTriggers"], [])

    def test_named_but_wrong_or_unvalidated_objects_fail_closed(self):
        facts = complete_facts()
        facts["constraints"][0]["delete_action"] = "c"
        facts["constraints"][3]["validated"] = False
        facts["indexes"][0]["columns"] = ["contract_id"]
        facts["triggers"][0]["enabled"] = "D"

        report = build_constraint_audit(facts)

        self.assertFalse(report["ok"])
        self.assertFalse(report["catalogReady"])
        self.assertFalse(report["constraintsReady"])
        self.assertEqual(report["invalidConstraints"], [
            "chk_brigade_contract_items_source_type",
            "fk_brigade_contract_items_contract_id",
        ])
        self.assertEqual(report["invalidIndexes"], [
            "uq_brigade_contract_items_estimate_source",
        ])
        self.assertEqual(report["invalidTriggers"], [
            "trg_brigade_contract_items_source_guard",
        ])

    def test_explicit_legacy_rows_do_not_fail_aggregate_preflight(self):
        facts = complete_facts()
        facts["data"]["explicit_legacy"] = 151

        report = build_constraint_audit(facts)

        self.assertTrue(report["dataReadyForConstraints"])
        self.assertNotIn("explicitLegacy", report["dataIssues"])

    def test_reversed_check_and_incomplete_guard_fail_closed(self):
        facts = complete_facts()
        facts["constraints"][3]["definition"] = (
            "CHECK (source_type NOT IN ('estimate','manual','pricelist','legacy'))"
        )
        facts["triggers"][0]["function_definition"] = facts["triggers"][0][
            "function_definition"
        ].replace("source_item_key", "unrelated_column")

        report = build_constraint_audit(facts)

        self.assertEqual(report["invalidConstraints"], [
            "chk_brigade_contract_items_source_type",
        ])
        self.assertEqual(report["invalidTriggers"], [
            "trg_brigade_contract_items_source_guard",
        ])

    def test_data_duplicates_and_unknown_counts_fail_closed_without_payloads(self):
        facts = complete_facts()
        facts["data"]["duplicate_snapshot_hash"] = 2
        facts["data"]["missing_snapshot_hash"] = None

        report = build_constraint_audit(facts)

        self.assertFalse(report["dataReadyForConstraints"])
        self.assertEqual(report["dataIssues"], [
            "duplicateSnapshotHash",
            "missingSnapshotHash",
        ])
        self.assertNotIn("sections_json", str(report))


class Cursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.responses.pop(0))

    def fetchone(self):
        rows = self.responses.pop(0)
        return rows[0] if rows else None


class ConstraintDatabaseAuditTests(unittest.TestCase):
    def test_database_audit_uses_only_parameterized_public_selects(self):
        facts = complete_facts()
        cursor = Cursor([
            facts["columns"],
            facts["constraints"],
            facts["indexes"],
            facts["triggers"],
            [facts["data"]],
        ])

        report = audit_brigade_lineage_constraints(cursor)

        self.assertTrue(report["constraintsReady"])
        self.assertEqual(len(cursor.calls), 5)
        for sql, params in cursor.calls:
            self.assertTrue(sql.startswith("SELECT"))
            self.assertIn("%s", sql)
            self.assertIn("public", params)
            self.assertNotIn("sections_json AS", sql)


if __name__ == "__main__":
    unittest.main()
