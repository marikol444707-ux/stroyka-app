import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("verify-frontend-feature-build.py")
spec = importlib.util.spec_from_file_location("verify_frontend_feature_build", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FrontendFeatureBuildTests(unittest.TestCase):
    def make_build(self, source):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        asset = root / "static/js/main.js"
        asset.parent.mkdir(parents=True)
        asset.write_text(source, encoding="utf-8")
        (root / "asset-manifest.json").write_text(
            json.dumps({"files": {"main.js": "/static/js/main.js"}}),
            encoding="utf-8",
        )
        self.addCleanup(temporary.cleanup)
        return root

    def test_accepts_enabled_warehouse_bundle_with_distribution_and_transfer_routes(self):
        root = self.make_build("warehouse-distributions /transfers two-stage-v1")
        module.verify(root, "REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true\n"
                            "REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=true\n")

    def test_rejects_enabled_warehouse_bundle_without_the_new_workflow(self):
        root = self.make_build("warehouse-movements")
        with self.assertRaisesRegex(ValueError, "Frontend собран без"):
            module.verify(root, "REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=true\n"
                                "REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=true\n")

    def test_disabled_warehouse_build_needs_no_distribution_markers(self):
        root = self.make_build("warehouse-movements")
        module.verify(root, "REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED=false\n"
                            "REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED=false\n")

    def test_accepts_enabled_material_capability_bundle_with_all_routes(self):
        root = self.make_build(
            "material-capability-proof material-capability-confirmations "
            "supplier-material-capability-confirmations"
        )
        module.verify(
            root,
            "REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true\n",
        )

    def test_rejects_enabled_material_capability_bundle_without_write_routes(self):
        root = self.make_build("material-capability-proof")
        with self.assertRaisesRegex(ValueError, "проверки материалов"):
            module.verify(
                root,
                "REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=true\n",
            )

    def test_disabled_material_capability_needs_no_route_markers(self):
        root = self.make_build("ordinary-supply-request")
        module.verify(
            root,
            "REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED=false\n",
        )


if __name__ == "__main__":
    unittest.main()
