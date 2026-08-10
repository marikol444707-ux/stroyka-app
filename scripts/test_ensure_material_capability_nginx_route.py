import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name(
    "ensure_material_capability_nginx_route.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ensure_material_capability_nginx_route",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EnsureMaterialCapabilityNginxRouteTest(unittest.TestCase):
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

    def test_adds_exact_revocation_prefix_before_known_marker(self):
        updated, added = MODULE.ensure_material_capability_route(
            self.config
        )

        marker = (
            "location ^~ /supplier-material-capability-confirmations/ {"
        )
        self.assertEqual(added, [marker])
        self.assertLess(updated.index(marker), updated.index("/site/pricing"))
        block = updated.split(marker, 1)[1].split("}", 1)[0]
        self.assertIn("proxy_pass http://127.0.0.1:8001;", block)
        self.assertIn(
            "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            block,
        )
        self.assertNotIn("try_files", block)

    def test_is_idempotent(self):
        updated, _ = MODULE.ensure_material_capability_route(self.config)

        second, added = MODULE.ensure_material_capability_route(updated)

        self.assertEqual(second, updated)
        self.assertEqual(added, [])
        self.assertEqual(
            second.count(
                "location ^~ /supplier-material-capability-confirmations/ {"
            ),
            1,
        )

    def test_refuses_conflicting_noncanonical_location(self):
        conflict = self.config.replace(
            "    location = /site/pricing {",
            "    location /supplier-material-capability-confirmations/ {\n"
            "        try_files $uri /index.html;\n"
            "    }\n\n"
            "    location = /site/pricing {",
        )

        with self.assertRaisesRegex(ValueError, "неканонический"):
            MODULE.ensure_material_capability_route(conflict)

    def test_refuses_conflicting_location_with_brace_on_next_line(self):
        conflict = self.config.replace(
            "    location = /site/pricing {",
            "    location /supplier-material-capability-confirmations/\n"
            "    {\n"
            "        try_files $uri /index.html;\n"
            "    }\n\n"
            "    location = /site/pricing {",
        )

        with self.assertRaisesRegex(ValueError, "неканонический"):
            MODULE.ensure_material_capability_route(conflict)

    def test_refuses_drifted_canonical_location(self):
        drifted, _ = MODULE.ensure_material_capability_route(self.config)
        drifted = drifted.replace(
            "proxy_pass http://127.0.0.1:8001;",
            "try_files $uri /index.html;",
            1,
        )

        with self.assertRaisesRegex(ValueError, "отличается от контракта"):
            MODULE.ensure_material_capability_route(drifted)

    def test_refuses_extra_same_path_location_after_canonical_block(self):
        canonical, _ = MODULE.ensure_material_capability_route(self.config)
        duplicate = canonical.replace(
            "    location = /site/pricing {",
            "    location /supplier-material-capability-confirmations/ {\n"
            "        try_files $uri /index.html;\n"
            "    }\n\n"
            "    location = /site/pricing {",
        )

        with self.assertRaisesRegex(ValueError, "несколько"):
            MODULE.ensure_material_capability_route(duplicate)

    def test_refuses_unknown_config(self):
        with self.assertRaisesRegex(ValueError, "site/pricing"):
            MODULE.ensure_material_capability_route(
                "server { location / { try_files $uri /index.html; } }"
            )

    def test_update_file_creates_backup_and_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "stroyka"
            backup_dir = root / "backups"
            target.write_text(self.config, encoding="utf-8")

            backup, added = MODULE.update_file(target, backup_dir)

            self.assertEqual(len(added), 1)
            self.assertIsNotNone(backup)
            self.assertEqual(
                backup.read_text(encoding="utf-8"),
                self.config,
            )
            self.assertIn(
                "location ^~ /supplier-material-capability-confirmations/",
                target.read_text(encoding="utf-8"),
            )

            second_backup, second_added = MODULE.update_file(
                target, backup_dir
            )
            self.assertIsNone(second_backup)
            self.assertEqual(second_added, [])
            self.assertEqual(len(list(backup_dir.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
