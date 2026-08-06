import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("ensure_estimate_row_transfer_nginx_route.py")
SPEC = importlib.util.spec_from_file_location(
    "ensure_estimate_row_transfer_nginx_route",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EnsureEstimateRowTransferNginxRouteTest(unittest.TestCase):
    def setUp(self):
        self.config = """server {
    location = /site/pricing {
        proxy_pass http://127.0.0.1:8001;
    }

    location / {
        try_files $uri /index.html;
    }
}
"""

    def test_adds_exact_collection_and_detail_prefix_before_known_marker(self):
        updated, added = MODULE.ensure_transfer_routes(self.config)

        self.assertEqual(
            added,
            [
                "location = /estimate-row-transfer-plans {",
                "location ^~ /estimate-row-transfer-plans/ {",
            ],
        )
        self.assertLess(
            updated.index("location = /estimate-row-transfer-plans"),
            updated.index("location = /site/pricing"),
        )
        self.assertIn("proxy_pass http://127.0.0.1:8001;", updated)
        self.assertIn("proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;", updated)

    def test_is_idempotent(self):
        updated, _ = MODULE.ensure_transfer_routes(self.config)

        second, added = MODULE.ensure_transfer_routes(updated)

        self.assertEqual(second, updated)
        self.assertEqual(added, [])
        self.assertEqual(second.count("location = /estimate-row-transfer-plans {"), 1)
        self.assertEqual(second.count("location ^~ /estimate-row-transfer-plans/ {"), 1)

    def test_adds_only_missing_detail_prefix(self):
        config = self.config.replace(
            "    location = /site/pricing {",
            "    location = /estimate-row-transfer-plans {\n"
            "        proxy_pass http://127.0.0.1:8001;\n"
            "    }\n\n"
            "    location = /site/pricing {",
        )

        updated, added = MODULE.ensure_transfer_routes(config)

        self.assertEqual(added, ["location ^~ /estimate-row-transfer-plans/ {"])
        self.assertEqual(updated.count("location = /estimate-row-transfer-plans {"), 1)

    def test_refuses_unknown_config(self):
        with self.assertRaisesRegex(ValueError, "site/pricing"):
            MODULE.ensure_transfer_routes(
                "server { location / { try_files $uri /index.html; } }"
            )

    def test_update_file_creates_one_backup_and_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "stroyka"
            backup_dir = root / "backups"
            target.write_text(self.config, encoding="utf-8")

            backup, added = MODULE.update_file(target, backup_dir)

            self.assertEqual(len(added), 2)
            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_text(encoding="utf-8"), self.config)
            self.assertIn(
                "location = /estimate-row-transfer-plans",
                target.read_text(encoding="utf-8"),
            )

            second_backup, second_added = MODULE.update_file(target, backup_dir)
            self.assertIsNone(second_backup)
            self.assertEqual(second_added, [])
            self.assertEqual(len(list(backup_dir.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
