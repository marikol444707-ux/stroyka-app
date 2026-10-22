import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("ensure_job_candidates_nginx_route.py")
SPEC = importlib.util.spec_from_file_location("ensure_job_candidates_nginx_route", SCRIPT)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


class EnsureJobCandidatesNginxRouteTests(unittest.TestCase):
    def test_adds_internal_intake_and_all_crm_routes_before_known_marker(self):
        original = "server {\n    location = /site/pricing { proxy_pass http://127.0.0.1:8001; }\n}\n"
        updated, added = helper.ensure_job_candidates_routes(original)
        self.assertEqual(len(added), 3)
        for route in ("/internal/jev/job-candidates", "/crm/job-candidates",
                      "/crm/job-candidates/"):
            self.assertIn(f"location", updated)
            self.assertIn(route, updated)
        self.assertLess(updated.index("/crm/job-candidates/"), updated.index("/site/pricing"))
        self.assertIn("client_max_body_size 1m;", updated)
        self.assertIn("proxy_pass http://127.0.0.1:8001;", updated)

    def test_is_idempotent(self):
        original = "server {\n    location = /site/pricing { proxy_pass http://127.0.0.1:8001; }\n}\n"
        once, _ = helper.ensure_job_candidates_routes(original)
        twice, added = helper.ensure_job_candidates_routes(once)
        self.assertEqual(twice, once)
        self.assertEqual(added, [])

    def test_refuses_unknown_config_without_changing_it(self):
        with self.assertRaisesRegex(ValueError, "Конфиг не изменен"):
            helper.ensure_job_candidates_routes("server { location = /wrong { } }\n")

    def test_update_keeps_backup_and_adds_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "stroyka.conf"
            backups = root / "backups"
            target.write_text("server {\nlocation = /site/pricing { }\n}\n", encoding="utf-8")
            backup, added = helper.update_file(target, backups)
            self.assertEqual(len(added), 3)
            self.assertEqual(backup.read_text(encoding="utf-8"), "server {\nlocation = /site/pricing { }\n}\n")
            self.assertIn("/internal/jev/job-candidates", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
