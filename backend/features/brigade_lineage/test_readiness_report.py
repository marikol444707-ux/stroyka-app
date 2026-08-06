import json
import unittest
from unittest.mock import patch

from backend.features.brigade_lineage import readiness_report as report_module
from backend.features.brigade_lineage.readiness_report import (
    LINEAGE_COLUMNS,
    SNAPSHOT_COLUMNS,
    build_report_from_rows,
    classify_contract_item,
    load_contract_item_rows,
    load_schema,
    load_snapshot_rows,
    run_readiness_report,
    sections_sha256,
)


def complete_schema():
    return {
        "brigade_contract_items": {
            "id",
            "contract_id",
            "estimate_item_key",
            *LINEAGE_COLUMNS,
        },
        "brigade_contracts": {"id", "company_id", "project_id"},
        "projects": {"id", "company_id"},
        "estimates": {"id", "company_id", "project_id"},
        "estimate_versions": {
            "id",
            "estimate_id",
            "sections_json",
            *SNAPSHOT_COLUMNS,
        },
    }


def legacy_row(**overrides):
    row = {
        "contract_item_id": 41,
        "legacy_item_key": "17:0:0",
        "contract_exists": True,
        "contract_company_id": 3,
        "contract_project_id": 8,
        "project_exists": True,
        "project_company_id": 3,
    }
    row.update(overrides)
    return row


def estimate_row(**overrides):
    sections = [{
        "name": "Раздел",
        "items": [{"name": "Работа", "estimateItemKey": "source-row-1"}],
    }]
    digest = sections_sha256(sections)
    row = {
        **legacy_row(legacy_item_key="source-row-1"),
        "source_type": "estimate",
        "source_estimate_version_id": 71,
        "source_section_index": 0,
        "source_item_index": 0,
        "source_item_key": "source-row-1",
        "estimate_exists": True,
        "estimate_company_id": 3,
        "estimate_project_id": 8,
        "snapshot_exists": True,
        "snapshot_version_id": 71,
        "snapshot_estimate_id": 17,
        "snapshot_sections_sha256": digest,
        "snapshot_sections_json": json.dumps(sections, ensure_ascii=False),
    }
    row.update(overrides)
    return row


def assignment_source_row(contract_item_id):
    row = estimate_row(contract_item_id=contract_item_id)
    for field in (
        "estimate_exists",
        "estimate_company_id",
        "estimate_project_id",
        "snapshot_exists",
        "snapshot_version_id",
        "snapshot_estimate_id",
        "snapshot_sections_sha256",
        "snapshot_sections_json",
    ):
        row.pop(field)
    return row


def snapshot_row(**overrides):
    sections = [{
        "name": "Раздел",
        "items": [{"name": "Работа", "estimateItemKey": "source-row-1"}],
    }]
    row = {
        "snapshot_exists": True,
        "snapshot_version_id": 71,
        "snapshot_estimate_id": 17,
        "snapshot_sections_sha256": sections_sha256(sections),
        "snapshot_sections_json": json.dumps(sections, ensure_ascii=False),
        "estimate_exists": True,
        "estimate_company_id": 3,
        "estimate_project_id": 8,
    }
    row.update(overrides)
    return row


class BrigadeLineageClassificationTests(unittest.TestCase):
    def test_legacy_item_key_is_never_treated_as_proven_lineage(self):
        result = classify_contract_item(
            legacy_row(),
            lineage_schema_ready=False,
            snapshot_schema_ready=False,
        )

        self.assertEqual(result, {
            "contractItemId": 41,
            "status": "legacy",
            "reason": "legacy_source_unproven",
            "sourceType": "legacy",
            "hasLegacyItemKey": True,
        })

    def test_manual_source_rejects_any_estimate_coordinate(self):
        result = classify_contract_item(
            legacy_row(source_type="manual", source_estimate_version_id=71),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "manual_source_has_estimate_coordinates")

    def test_manual_source_requires_null_not_blank_estimate_coordinates(self):
        result = classify_contract_item(
            legacy_row(
                legacy_item_key="",
                source_type="manual",
                source_estimate_version_id=None,
                source_section_index=None,
                source_item_index=None,
                source_item_key="",
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "manual_source_has_estimate_coordinates")

    def test_manual_source_rejects_legacy_estimate_item_key(self):
        result = classify_contract_item(
            legacy_row(source_type="manual"),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "manual_source_has_legacy_item_key")

    def test_explicit_legacy_source_remains_review_only(self):
        result = classify_contract_item(
            legacy_row(
                source_type="legacy",
                source_estimate_version_id=None,
                source_section_index=None,
                source_item_index=None,
                source_item_key=None,
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "legacy")
        self.assertEqual(result["reason"], "explicit_legacy_source")

    def test_missing_source_type_with_partial_coordinate_is_invalid(self):
        result = classify_contract_item(
            legacy_row(source_estimate_version_id=71),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "source_type_missing_with_coordinates")

    def test_missing_source_type_is_invalid_after_lineage_schema_exists(self):
        result = classify_contract_item(
            legacy_row(legacy_item_key=""),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "source_type_missing")

    def test_pricelist_source_is_distinct_and_has_no_estimate_coordinates(self):
        result = classify_contract_item(
            legacy_row(
                legacy_item_key="",
                source_type="pricelist",
                source_estimate_version_id=None,
                source_section_index=None,
                source_item_index=None,
                source_item_key=None,
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "declared_pricelist")
        self.assertEqual(result["reason"], "explicit_pricelist_source")

    def test_noncanonical_source_type_is_invalid(self):
        result = classify_contract_item(
            legacy_row(
                legacy_item_key="",
                source_type=" Estimate ",
                source_estimate_version_id=71,
                source_section_index=0,
                source_item_index=0,
                source_item_key="source-row-1",
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "source_type_not_canonical")

    def test_contract_project_must_belong_to_contract_company(self):
        result = classify_contract_item(
            legacy_row(project_company_id=4),
            lineage_schema_ready=False,
            snapshot_schema_ready=False,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "contract_project_owner_mismatch")

    def test_complete_estimate_source_is_verified_against_owner_row_and_hash(self):
        result = classify_contract_item(
            estimate_row(),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "verified_estimate")
        self.assertEqual(result["reason"], "exact_snapshot_row_verified")

    def test_cross_company_estimate_source_is_invalid(self):
        result = classify_contract_item(
            estimate_row(estimate_company_id=4),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "estimate_owner_mismatch")

    def test_snapshot_content_must_match_saved_hash(self):
        changed_sections = [{
            "name": "Раздел",
            "items": [{"name": "Другая работа", "estimateItemKey": "source-row-1"}],
        }]
        result = classify_contract_item(
            estimate_row(snapshot_sections_json=json.dumps(changed_sections, ensure_ascii=False)),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "snapshot_hash_mismatch")

    def test_snapshot_hash_must_be_canonical_lowercase_without_whitespace(self):
        row = estimate_row()
        result = classify_contract_item(
            estimate_row(snapshot_sections_sha256=row["snapshot_sections_sha256"].upper()),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "snapshot_hash_not_canonical")

    def test_compatibility_item_key_must_match_authoritative_source_key(self):
        result = classify_contract_item(
            estimate_row(legacy_item_key="different-key"),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "compatibility_item_key_mismatch")

    def test_source_item_key_must_not_be_normalized_during_verification(self):
        result = classify_contract_item(
            estimate_row(
                legacy_item_key=" source-row-1 ",
                source_item_key=" source-row-1 ",
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "source_item_key_not_canonical")

    def test_conflicting_explicit_snapshot_keys_are_ambiguous(self):
        sections = [{
            "name": "Раздел",
            "items": [{
                "name": "Работа",
                "estimateItemKey": "source-row-1",
                "estimate_item_key": "different-source-row",
            }],
        }]
        result = classify_contract_item(
            estimate_row(
                snapshot_sections_json=json.dumps(sections, ensure_ascii=False),
                snapshot_sections_sha256=sections_sha256(sections),
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "snapshot_row_key_ambiguous")

    def test_arbitrary_code_field_is_not_accepted_as_row_identity(self):
        sections = [{"name": "Раздел", "items": [{"name": "Работа", "code": "C-1"}]}]
        digest = sections_sha256(sections)
        result = classify_contract_item(
            estimate_row(
                legacy_item_key="C-1",
                source_item_key="C-1",
                snapshot_sections_json=json.dumps(sections, ensure_ascii=False),
                snapshot_sections_sha256=digest,
            ),
            lineage_schema_ready=True,
            snapshot_schema_ready=True,
        )

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "snapshot_row_key_mismatch")


class BrigadeLineageReportTests(unittest.TestCase):
    def test_pre_migration_report_is_consistent_read_only_and_content_free(self):
        schema = complete_schema()
        schema["brigade_contract_items"] -= set(LINEAGE_COLUMNS)
        schema["estimate_versions"] -= set(SNAPSHOT_COLUMNS)
        report = build_report_from_rows(
            schema,
            [
                legacy_row(),
                legacy_row(contract_item_id=42, legacy_item_key=""),
            ],
        )

        self.assertTrue(report["ok"])
        self.assertTrue(report["dryRun"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["reportVersion"], 1)
        self.assertEqual(report["schemaState"], "pre_migration")
        self.assertTrue(report["baseSchemaPresent"])
        self.assertFalse(report["lineageDataReady"])
        self.assertFalse(report["constraintAuditIncluded"])
        self.assertFalse(report["writerAuditIncluded"])
        self.assertTrue(report["reportConsistent"])
        self.assertEqual(report["summary"], {
            "totalRows": 2,
            "byState": {
                "verifiedEstimate": 0,
                "declaredManual": 0,
                "declaredPricelist": 0,
                "legacy": 2,
                "invalid": 0,
            },
            "bySourceType": {
                "estimate": 0,
                "manual": 0,
                "pricelist": 0,
                "legacy": 2,
                "unclassified": 0,
            },
            "legacyWithItemKey": 1,
            "legacyWithoutItemKey": 1,
        })
        self.assertEqual(report["reasonCounts"], {"legacy_source_unproven": 2})
        self.assertEqual(
            report["schema"]["brigadeContractItems"]["missingLineageColumns"],
            list(LINEAGE_COLUMNS),
        )
        self.assertNotIn("Работа", json.dumps(report, ensure_ascii=False))

    def test_lineage_data_ready_requires_zero_legacy_or_invalid_rows(self):
        report = build_report_from_rows(
            complete_schema(),
            [
                estimate_row(),
                legacy_row(
                    contract_item_id=43,
                    legacy_item_key="",
                    source_type="manual",
                    source_estimate_version_id=None,
                    source_section_index=None,
                    source_item_index=None,
                    source_item_key=None,
                ),
            ],
        )

        self.assertTrue(report["lineageDataReady"])
        self.assertEqual(report["summary"]["byState"]["verifiedEstimate"], 1)
        self.assertEqual(report["summary"]["byState"]["declaredManual"], 1)
        self.assertEqual(report["summary"]["byState"]["declaredPricelist"], 0)
        self.assertEqual(report["needsReview"], [])

    def test_reused_snapshot_is_hashed_once_for_all_assignment_rows(self):
        rows = [assignment_source_row(41), assignment_source_row(42)]
        with patch.object(
            report_module,
            "sections_sha256",
            wraps=sections_sha256,
        ) as digest:
            report = build_report_from_rows(
                complete_schema(),
                rows,
                snapshot_rows=[snapshot_row()],
            )

        self.assertEqual(digest.call_count, 1)
        self.assertEqual(report["summary"]["byState"]["verifiedEstimate"], 2)
        self.assertEqual(report["summary"]["byState"]["invalid"], 0)

    def test_excessively_nested_snapshot_is_invalid_instead_of_aborting_audit(self):
        rows = [assignment_source_row(41), assignment_source_row(42)]
        with patch.object(
            report_module,
            "sections_sha256",
            side_effect=RecursionError,
        ) as digest:
            report = build_report_from_rows(
                complete_schema(),
                rows,
                snapshot_rows=[
                    snapshot_row(snapshot_sections_sha256="0" * 64),
                ],
            )

        self.assertEqual(digest.call_count, 1)
        self.assertEqual(report["summary"]["byState"]["invalid"], 2)
        self.assertEqual(report["reasonCounts"], {"snapshot_content_invalid": 2})


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), tuple(params)))

    def fetchall(self):
        return list(self.responses.pop(0))

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.session_calls = []
        self.rollback_calls = 0
        self.closed = False

    def set_session(self, **kwargs):
        self.session_calls.append(kwargs)

    def cursor(self, **_kwargs):
        return self._cursor

    def rollback(self):
        self.rollback_calls += 1

    def close(self):
        self.closed = True


class BrigadeLineageDatabaseReportTests(unittest.TestCase):
    def test_schema_loader_reads_only_allowlisted_tables(self):
        cursor = FakeCursor([[
            {"table_name": "brigade_contract_items", "column_name": "id"},
            {"table_name": "brigade_contracts", "column_name": "id"},
        ]])

        schema = load_schema(cursor)

        self.assertEqual(schema, {
            "brigade_contract_items": {"id"},
            "brigade_contracts": {"id"},
        })
        self.assertEqual(len(cursor.calls), 1)
        self.assertTrue(cursor.calls[0][0].startswith("SELECT"))
        self.assertIn("information_schema.columns", cursor.calls[0][0])

    def test_pre_migration_row_query_never_mentions_missing_lineage_columns(self):
        schema = complete_schema()
        schema["brigade_contract_items"] -= set(LINEAGE_COLUMNS)
        schema["estimate_versions"] -= set(SNAPSHOT_COLUMNS)
        cursor = FakeCursor([[legacy_row()]])

        rows = load_contract_item_rows(cursor, schema)

        self.assertEqual(rows, [legacy_row()])
        sql = cursor.calls[0][0]
        self.assertTrue(sql.startswith("SELECT"))
        self.assertNotIn("bci.source_", sql)
        self.assertNotIn("ev.sections_sha256", sql)
        self.assertNotIn("description", sql)

    def test_complete_schema_item_query_does_not_repeat_snapshot_documents(self):
        cursor = FakeCursor([[assignment_source_row(41)]])

        rows = load_contract_item_rows(cursor, complete_schema())

        self.assertEqual(rows, [assignment_source_row(41)])
        sql = cursor.calls[0][0]
        self.assertIn("bci.source_estimate_version_id", sql)
        self.assertNotIn("estimate_versions", sql)
        self.assertNotIn("sections_json", sql)

    def test_snapshot_query_loads_each_requested_version_once(self):
        cursor = FakeCursor([[snapshot_row()]])

        rows = load_snapshot_rows(cursor, complete_schema(), [72, 71, 71, None])

        self.assertEqual(rows, [snapshot_row()])
        sql, params = cursor.calls[0]
        self.assertIn("FROM estimate_versions ev", sql)
        self.assertIn("ev.id=ANY(%s)", sql)
        self.assertEqual(params, ([71, 72],))

    def test_runner_is_read_only_rolls_back_and_closes_connection(self):
        cursor = FakeCursor([])
        connection = FakeConnection(cursor)
        with patch.object(
            report_module,
            "load_schema",
            return_value=complete_schema(),
        ), patch.object(
            report_module,
            "load_contract_item_rows",
            return_value=[estimate_row()],
        ), patch.object(
            report_module,
            "load_snapshot_rows",
            return_value=[snapshot_row()],
        ):
            report = run_readiness_report(lambda: connection)

        self.assertEqual(connection.session_calls, [{
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        }])
        self.assertEqual(connection.rollback_calls, 1)
        self.assertTrue(cursor.closed)
        self.assertTrue(connection.closed)
        self.assertTrue(report["rolledBack"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertTrue(report["lineageDataReady"])


if __name__ == "__main__":
    unittest.main()
