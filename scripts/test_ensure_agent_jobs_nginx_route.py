import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("ensure_agent_jobs_nginx_route.py")
SPEC = importlib.util.spec_from_file_location("ensure_agent_jobs_nginx_route", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class EnsureAgentJobsNginxRouteTest(unittest.TestCase):
    def setUp(self):
        self.config = """server {
    location = /site/leads {
        proxy_pass http://127.0.0.1:8001;
    }

    location = /site/pricing {
        proxy_pass http://127.0.0.1:8001;
    }
}
"""

    def test_adds_exact_list_and_detail_prefix_before_known_marker(self):
        updated, added = MODULE.ensure_agent_job_routes(self.config)

        self.assertEqual(
            added,
            ["location = /agent-jobs {", "location ^~ /agent-jobs/ {"],
        )
        self.assertLess(updated.index("location = /agent-jobs"), updated.index("location = /site/pricing"))
        self.assertIn("    location ^~ /agent-jobs/ {", updated)
        self.assertIn("proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;", updated)

    def test_is_idempotent(self):
        updated, _ = MODULE.ensure_agent_job_routes(self.config)

        second, added = MODULE.ensure_agent_job_routes(updated)

        self.assertEqual(second, updated)
        self.assertEqual(added, [])
        self.assertEqual(second.count("location = /agent-jobs {"), 1)
        self.assertEqual(second.count("location ^~ /agent-jobs/ {"), 1)

    def test_adds_only_missing_detail_route(self):
        config = self.config.replace(
            "    location = /site/pricing {",
            "    location = /agent-jobs {\n"
            "        proxy_pass http://127.0.0.1:8001;\n"
            "    }\n\n"
            "    location = /site/pricing {",
        )

        updated, added = MODULE.ensure_agent_job_routes(config)

        self.assertEqual(added, ["location ^~ /agent-jobs/ {"])
        self.assertEqual(updated.count("location = /agent-jobs {"), 1)

    def test_refuses_unknown_config_without_writing_location(self):
        with self.assertRaisesRegex(ValueError, "site/pricing"):
            MODULE.ensure_agent_job_routes("server { location / { try_files $uri /index.html; } }")

    def test_update_file_creates_backup_and_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "stroyka"
            backup_dir = root / "backups"
            target.write_text(self.config, encoding="utf-8")

            backup, added = MODULE.update_file(target, backup_dir)

            self.assertEqual(len(added), 2)
            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_text(encoding="utf-8"), self.config)
            self.assertIn("location = /agent-jobs", target.read_text(encoding="utf-8"))

            second_backup, second_added = MODULE.update_file(target, backup_dir)
            self.assertIsNone(second_backup)
            self.assertEqual(second_added, [])
            self.assertEqual(len(list(backup_dir.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
