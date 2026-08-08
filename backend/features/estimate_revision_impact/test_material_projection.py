import json
import unittest

from backend.features.estimate_revision_impact.material_projection import (
    MATERIAL_REQUIRED_COLUMNS,
    MAX_ALIAS_ROWS,
    MAX_MATERIAL_ROWS,
    build_material_projection,
    collect_material_impact_audit,
    run_material_impact_audit,
)
from backend.features.estimate_revision_impact.test_baseline import (
    FakeConnection,
    FakeCursor,
    REQUIRED_SCHEMA_ROWS,
    estimate_row,
    reconciliation_row,
)
from backend.features.estimate_revision_impact.contract import (
    build_estimate_revision_source,
)


def context(**overrides):
    value = {
        "companyId": 4,
        "projectId": 17,
        "projectNameOwnerCount": 1,
        "baseEstimateId": 51,
        "targetEstimateId": 52,
        "workPackage": "Основная",
    }
    value.update(overrides)
    return value


def material(name, *, key=None, quantity="10", unit="кг", **extra):
    row = {
        "itemType": "material",
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "price": 999,
        "commercialNote": "must never be public",
    }
    if key is not None:
        row["estimateItemKey"] = key
    row.update(extra)
    return row


def sections(*items):
    return [{"name": "private section", "items": list(items)}]


def source():
    return build_estimate_revision_source(
        company_id=4,
        project_id=17,
        estimate_id=52,
        version="v2.0",
        sections=[{"name": "Работы", "items": []}],
    )


MATERIAL_REQUIRED_SCHEMA_ROWS = tuple(
    {"table_name": table, "column_name": column}
    for table, columns in MATERIAL_REQUIRED_COLUMNS.items()
    for column in columns
)


class MaterialProjectionContractTests(unittest.TestCase):
    def test_stable_key_reports_only_exact_changed_coordinates(self):
        projection = build_material_projection(
            context(),
            sections(material("Old private name", key="stable-1", quantity="10")),
            sections(material("New private name", key="stable-1", quantity="12")),
            [],
        )

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["state"], "complete")
        self.assertEqual(projection["summary"], {
            "baseMaterialRows": 1,
            "targetMaterialRows": 1,
            "pairedRows": 1,
            "changedPairs": 1,
            "baseOnlyRows": 0,
            "targetOnlyRows": 0,
            "needsReview": 0,
        })
        self.assertEqual(projection["changedPairs"], [{
            "base": {
                "estimateId": 51,
                "sectionIndex": 0,
                "itemIndex": 0,
            },
            "target": {
                "estimateId": 52,
                "sectionIndex": 0,
                "itemIndex": 0,
            },
            "matchKind": "stable_item_key",
            "aliasIds": [],
            "changeKinds": ["identity_changed", "quantity_changed"],
        }])
        serialized = json.dumps(projection, ensure_ascii=False)
        for forbidden in (
            "Old private name", "New private name", "private section",
            "must never be public", "stable-1", "999", '"quantity"', '"unit"',
        ):
            self.assertNotIn(forbidden, serialized)

    def test_confirmed_alias_pairs_one_to_one_without_name_matching(self):
        projection = build_material_projection(
            context(),
            sections(material("Alias private", quantity="7")),
            sections(material("Canonical private", quantity="7")),
            [{
                "id": 31,
                "project_name": "Same-name project kept internal",
                "alias_name": "Alias private",
                "canonical_name": "Canonical private",
                "canonical_unit": "кг",
                "active": True,
            }],
        )

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["summary"]["pairedRows"], 1)
        self.assertEqual(projection["summary"]["changedPairs"], 1)
        self.assertEqual(projection["changedPairs"][0]["matchKind"], "confirmed_alias")
        self.assertEqual(projection["changedPairs"][0]["aliasIds"], [31])
        self.assertEqual(
            projection["changedPairs"][0]["changeKinds"],
            ["alias_identity_changed"],
        )

    def test_unpaired_rows_are_exact_add_remove_facts(self):
        projection = build_material_projection(
            context(),
            sections(material("Removed", key="old")),
            sections(material("Added", key="new")),
            [],
        )

        self.assertTrue(projection["complete"])
        self.assertEqual(projection["baseOnlyRows"], [{
            "estimateId": 51,
            "sectionIndex": 0,
            "itemIndex": 0,
        }])
        self.assertEqual(projection["targetOnlyRows"], [{
            "estimateId": 52,
            "sectionIndex": 0,
            "itemIndex": 0,
        }])

    def test_ambiguous_alias_unit_norm_and_duplicate_key_require_review(self):
        aliases = [
            {
                "id": 31,
                "alias_name": "Alias",
                "canonical_name": "Canonical A",
                "canonical_unit": "кг",
                "active": True,
            },
            {
                "id": 32,
                "alias_name": "Alias",
                "canonical_name": "Canonical B",
                "canonical_unit": "кг",
                "active": True,
            },
        ]
        projection = build_material_projection(
            context(),
            sections(
                material("Alias"),
                material("Missing unit", key="unit", unit=""),
                material("Norm", key="norm", materialPlanIssue="private reason"),
                material("Duplicate 1", key="dup"),
                material("Duplicate 2", key="dup"),
            ),
            sections(),
            aliases,
        )

        self.assertFalse(projection["complete"])
        self.assertEqual(projection["state"], "review_required")
        self.assertEqual(projection["reasonCounts"], {
            "material_alias_ambiguous": 1,
            "material_item_key_duplicate": 2,
            "material_norm_ambiguous": 1,
            "material_unit_invalid": 1,
        })
        self.assertNotIn("private reason", json.dumps(projection))

    def test_same_project_name_in_two_companies_blocks_alias_use(self):
        projection = build_material_projection(
            context(projectNameOwnerCount=2),
            sections(material("Alias")),
            sections(material("Canonical")),
            [{
                "id": 31,
                "alias_name": "Alias",
                "canonical_name": "Canonical",
                "canonical_unit": "кг",
                "active": True,
            }],
        )

        self.assertFalse(projection["complete"])
        self.assertEqual(projection["reasonCounts"], {
            "material_alias_owner_ambiguous": 1,
        })
        self.assertEqual(projection["changedPairs"], [])

    def test_duplicate_key_is_scoped_to_one_revision(self):
        projection = build_material_projection(
            context(),
            sections(
                material("Base one", key="dup"),
                material("Base two", key="dup"),
            ),
            sections(material("Target", key="dup")),
            [],
        )

        self.assertEqual(projection["reasonCounts"], {
            "material_item_key_duplicate": 2,
        })
        self.assertEqual(projection["targetOnlyRows"], [{
            "estimateId": 52,
            "sectionIndex": 0,
            "itemIndex": 0,
        }])

    def test_alias_without_canonical_unit_cannot_pair_different_units(self):
        projection = build_material_projection(
            context(),
            sections(material("Alias", unit="кг")),
            sections(material("Canonical", unit="м2")),
            [{
                "id": 31,
                "alias_name": "Alias",
                "canonical_name": "Canonical",
                "canonical_unit": "",
                "active": True,
            }],
        )

        self.assertEqual(projection["changedPairs"], [])
        self.assertEqual(projection["reasonCounts"], {
            "material_unit_changed": 2,
        })

    def test_empty_material_identity_requires_review(self):
        projection = build_material_projection(
            context(),
            sections(material("", key="empty")),
            sections(),
            [],
        )

        self.assertEqual(projection["reasonCounts"], {
            "material_identity_invalid": 1,
        })


class MaterialProjectionCollectorTests(unittest.TestCase):
    def result_sets(self, *, owner_count=1, aliases=()):
        return (
            REQUIRED_SCHEMA_ROWS,
            (estimate_row(),),
            (reconciliation_row(),),
            MATERIAL_REQUIRED_SCHEMA_ROWS,
            ({
                "estimate_id": 51,
                "company_id": 4,
                "project_id": 17,
                "work_package": "Основная",
                "sections_json": json.dumps(sections(
                    material("Base private", key="stable", quantity="10"),
                )),
            }, {
                "estimate_id": 52,
                "company_id": 4,
                "project_id": 17,
                "work_package": "Основная",
                "sections_json": json.dumps(sections(
                    material("Target private", key="stable", quantity="12"),
                )),
            }),
            ({"project_name": "Private project", "owner_count": owner_count},),
            aliases,
        )

    def test_exact_source_runs_bounded_parameterized_selects_only(self):
        cursor = FakeCursor(self.result_sets())

        report = collect_material_impact_audit(cursor, source())

        self.assertTrue(report["readyForMaterialProjection"])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(report["materialImpact"]["summary"]["changedPairs"], 1)
        self.assertEqual(len(cursor.calls), 7)
        for sql, _params in cursor.calls:
            normalized = sql.upper()
            self.assertTrue(normalized.startswith("SELECT "))
            for mutation in ("INSERT ", "UPDATE ", "DELETE "):
                self.assertNotIn(mutation, normalized)
        pair_sql, pair_params = cursor.calls[4]
        self.assertIn("id=ANY(%s)", pair_sql)
        self.assertIn("company_id=%s", pair_sql)
        self.assertIn((51, 52), pair_params)
        alias_sql, alias_params = cursor.calls[6]
        self.assertIn("LIMIT %s", alias_sql)
        self.assertIn(MAX_ALIAS_ROWS + 1, alias_params)

    def test_cross_company_same_name_blocks_project_alias(self):
        aliases = ({
            "id": 31,
            "project_name": "Private project",
            "alias_name": "Base private",
            "canonical_name": "Target private",
            "canonical_unit": "кг",
            "active": True,
        },)
        cursor = FakeCursor(self.result_sets(owner_count=2, aliases=aliases))

        report = collect_material_impact_audit(cursor, source())

        self.assertFalse(report["readyForMaterialProjection"])
        self.assertEqual(report["materialImpact"]["reasonCounts"], {
            "material_alias_owner_ambiguous": 1,
        })

    def test_runner_uses_one_read_only_transaction_and_rolls_back(self):
        cursor = FakeCursor(self.result_sets())
        connection = FakeConnection(cursor)

        report = run_material_impact_audit(lambda: connection, source())

        self.assertEqual(connection.session, {
            "readonly": True,
            "autocommit": False,
            "isolation_level": "REPEATABLE READ",
        })
        self.assertEqual(connection.rollbacks, 1)
        self.assertEqual(connection.commits, 0)
        self.assertTrue(report["readOnlyTransaction"])
        self.assertTrue(report["rolledBack"])

    def test_operator_command_is_additive_and_not_registered_at_runtime(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["audit:estimate-revision-material-impact"],
            "python3 -m "
            "backend.features.estimate_revision_impact.material_projection",
        )
        for relative in (
            "backend/main.py",
            "backend/features/agent_jobs/handler_registry.py",
            "deploy.sh",
        ):
            self.assertNotIn(
                "material_projection",
                (root / relative).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
