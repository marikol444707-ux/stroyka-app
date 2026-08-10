import inspect
import unittest
from unittest import mock

from backend.features.supply_recommendation_preview import (
    material_capability_schema as schema,
)
from backend.features.supply_recommendation_preview import (
    material_capability_schema_probe as probe,
)
from backend.features.supply_recommendation_preview.test_material_capability_schema import (
    absent_catalog,
    exact_catalog,
)


class MaterialCapabilitySchemaProbeTests(unittest.TestCase):
    def test_migration_keeps_the_existing_catalog_patch_point(self):
        self.assertIs(
            schema._collect_catalog,
            probe.collect_material_capability_schema_catalog,
        )

    def test_readiness_is_complete_only_for_the_exact_zero_change_contract(self):
        cursor = object()
        with mock.patch.object(
            probe,
            "collect_material_capability_schema_catalog",
            return_value=exact_catalog(),
        ) as collect:
            result = probe.collect_material_capability_schema_readiness(cursor)

        collect.assert_called_once_with(cursor)
        self.assertEqual(result, {
            "contractVersion": schema.CONTRACT_VERSION,
            "complete": True,
            "blockers": [],
        })

    def test_readiness_fails_closed_for_missing_or_inconsistent_schema(self):
        cases = (
            absent_catalog(),
            {"not": "a catalog"},
        )
        for catalog in cases:
            with self.subTest(catalog=catalog), mock.patch.object(
                probe,
                "collect_material_capability_schema_catalog",
                return_value=catalog,
            ):
                result = probe.collect_material_capability_schema_readiness(
                    object()
                )

            self.assertEqual(result["contractVersion"], schema.CONTRACT_VERSION)
            self.assertFalse(result["complete"])
            self.assertTrue(result["blockers"])

    def test_probe_has_no_dependency_on_the_migration_runtime(self):
        source = inspect.getsource(probe)

        self.assertNotIn("import material_capability_schema\n", source)
        self.assertNotIn("run_material_capability_schema_migration", source)


if __name__ == "__main__":
    unittest.main()
