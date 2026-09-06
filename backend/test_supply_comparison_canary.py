"""Production configuration planning, without touching a live service."""
import unittest
import contextlib
import io
import json
import shutil
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts import enable_supply_comparison as canary
from scripts.enable_supply_comparison import build_files


ROOT = Path(__file__).resolve().parents[1]
SITE = """server {
    listen 80;
    server_name stroyka26.pro;
}
server {
    listen 443 ssl http2;
    server_name stroyka26.pro www.stroyka26.pro;
    include /etc/nginx/snippets/warehouse-anomaly-preview.conf;
    location ~* ^/(health|supply-requests|supplier-offers) {
        proxy_pass http://127.0.0.1:8001;
    }
    location / { try_files $uri /index.html; }
}
"""


class SupplyComparisonCanaryTests(unittest.TestCase):
    def setUp(self):
        self.fragment = (ROOT / "ops-nginx-supply-technical-comparison.conf").read_text()

    def test_exact_location_precedes_generic_api_and_preserves_site(self):
        files = build_files(SITE, self.fragment, "")
        added = "    include /etc/nginx/snippets/supply-technical-comparison.conf;\n"
        self.assertEqual(files["site"].replace(added, ""), SITE)
        self.assertLess(files["site"].index(added), files["site"].index("location ~*"))
        self.assertEqual(files["zones"].count("limit_req_zone "), 1)
        self.assertEqual(files["zones"].count("limit_conn_zone "), 1)
        self.assertNotIn("location", files["zones"])
        self.assertIn("location @supply_technical_comparison_429", files["snippet"])
        self.assertIn("COMPANY_IDS=1", files["dropin"])

    def test_only_supply_build_flags_are_replaced_and_persist(self):
        original = "# existing\nOTHER_SETTING=unchanged\nREACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED=false\nexport REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS = '9'\n"
        files = build_files(SITE, self.fragment, original)
        self.assertEqual(files["frontend"], "# existing\nOTHER_SETTING=unchanged\nREACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED=true\nREACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS=1\n")

    def test_missing_duplicate_or_wrong_server_anchor_fails_before_writes(self):
        anchor = "    include /etc/nginx/snippets/warehouse-anomaly-preview.conf;\n"
        for site in (SITE.replace(anchor, ""), SITE.replace(anchor, anchor * 2), SITE.replace("listen 443", "listen 8443")):
            with self.subTest(site=site), self.assertRaises(ValueError):
                build_files(site, self.fragment, "")

    def test_generic_regex_before_anchor_is_not_silently_accepted(self):
        site = SITE.replace("    include", "    location ~ ^/supply-requests { return 404; }\n    include", 1)
        with self.assertRaises(ValueError):
            build_files(site, self.fragment, "")

    def test_overlapping_priority_prefix_is_rejected(self):
        for prefix in ("/", "/supply", "/supply-requests/"):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                build_files(SITE + f"\nlocation ^~ {prefix} {{ }}\n", self.fragment, "")

    def test_existing_canary_or_bad_fragment_is_not_overwritten(self):
        with self.assertRaises(ValueError):
            build_files(SITE + "# supply-technical-comparison", self.fragment, "")
        with self.assertRaises(ValueError):
            build_files(SITE, self.fragment.replace("limit_conn_zone", "# limit_conn_zone"), "")


class CanaryLifecycleTests(unittest.TestCase):
    """Real temporary files; external services and npm are controlled fakes."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="supply-canary-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.app = self.root / "app"
        self.nginx = self.root / "nginx"
        self.evidence = self.root / "evidence"
        for path in (self.app, self.nginx, self.evidence):
            path.mkdir()
        self.site = self.nginx / "site"
        self.site.write_text(SITE)
        self.original_frontend_env = "UNRELATED_FLAG=preserved\n"
        self.targets = {key: self.root / (key + ".conf") for key in canary.TARGETS}
        self.targets["frontend"].write_text(self.original_frontend_env)
        shutil.copy(ROOT / "ops-nginx-supply-technical-comparison.conf", self.app)
        (self.app / "build").mkdir()
        (self.app / "build/index.html").write_text("old frontend")
        self.calls = []
        self.fail = None
        self.failed_once = False
        for name, value in (("APP_ROOT", self.app), ("NGINX_ROOT", self.nginx),
                            ("EVIDENCE_ROOT", self.evidence), ("SITE_LINK", self.site),
                            ("TARGETS", self.targets)):
            self.enter(patch.object(canary, name, value))
        self.enter(patch.object(canary, "run", side_effect=self.fake_run))
        self.enter(patch.object(canary, "health"))
        self.enter(patch.object(canary, "wait_for_backend"))
        self.enter(patch.object(canary, "verify_running_flags"))
        self.published_check = self.enter(patch.object(canary, "check_published_frontend"))
        self.api_check = self.enter(patch.object(canary, "check_anonymous"))
        # Test machines need not be root. Byte/mode replacement is still real.
        self.enter(patch.object(canary.os, "fchown"))
        self.enter(contextlib.redirect_stdout(io.StringIO()))

    def enter(self, manager):
        result = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        return result

    def fake_run(self, args, *, capture=False, env=None):
        self.calls.append(args)
        if self.fail and self.fail(args) and not self.failed_once:
            self.failed_once = True
            raise RuntimeError("injected_operation_failure")
        if args == ["git", "rev-parse", "HEAD"]:
            return canary.EXPECTED_COMMIT + "\n"
        if args == ["nginx", "-T"]:
            return SITE
        if args[:3] == ["systemctl", "show", "stroyka"]:
            return "SECRET=must-not-be-logged"
        if args[:2] == ["bash", "scripts/resolve-frontend-build-env.sh"]:
            return "REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED=true\nREACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_COMPANY_IDS=1\n"
        if args == ["npm", "run", "build"]:
            self.assertEqual(env["REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS"], "1")
            self.assertEqual(env["REACT_APP_ASSIGNMENT_DAILY_DRAFT_PREVIEW_ENABLED"], "true")
            (Path(env["BUILD_PATH"]) / "index.html").write_text("new frontend")
        if args[:2] == ["bash", "scripts/publish-frontend.sh"]:
            shutil.copytree(args[2], args[3], dirs_exist_ok=True)
        return "" if capture else None

    def assert_original_state(self):
        self.assertEqual(self.site.read_text(), SITE)
        self.assertEqual(self.targets["frontend"].read_text(), self.original_frontend_env)
        self.assertEqual((self.app / "build/index.html").read_text(), "old frontend")
        for key in ("zones", "snippet", "dropin"):
            self.assertFalse(self.targets[key].exists())

    def test_default_preflight_has_no_configuration_or_build_writes(self):
        canary.execute(False)
        self.assert_original_state()
        self.assertEqual(list(self.evidence.iterdir()), [])
        self.assertNotIn(["npm", "run", "build"], self.calls)

    def test_success_persists_flags_preserves_other_feature_and_manual_rollback(self):
        canary.execute(True)
        self.assertIn("COMPANY_IDS=1", self.targets["frontend"].read_text())
        self.assertIn("UNRELATED_FLAG=preserved", self.targets["frontend"].read_text())
        self.assertEqual((self.app / "build/index.html").read_text(), "new frontend")
        self.assertEqual(self.api_check.call_count, 2)
        self.assertEqual(self.published_check.call_count, 1)
        evidence = next(self.evidence.iterdir())
        canary.restore(evidence)
        self.assert_original_state()
        self.assertTrue((evidence / "dropin.disabled").is_file())

    def test_build_failure_never_changes_live_configuration(self):
        self.fail = lambda args: args == ["npm", "run", "build"]
        with self.assertRaises(RuntimeError):
            canary.execute(True)
        self.assert_original_state()
        self.assertNotIn(["systemctl", "restart", "stroyka"], self.calls)

    def test_nginx_rejection_rolls_back_without_backend_restart(self):
        self.fail = lambda args: args == ["nginx", "-t"]
        with self.assertRaises(RuntimeError):
            canary.execute(True)
        self.assert_original_state()
        self.assertNotIn(["systemctl", "restart", "stroyka"], self.calls)

    def test_smoke_failure_restores_previous_frontend_and_configuration(self):
        self.fail = lambda args: args == ["bash", "scripts/prod-smoke-check.sh"]
        with self.assertRaises(RuntimeError):
            canary.execute(True)
        self.assert_original_state()
        self.assertEqual(self.calls.count(["systemctl", "restart", "stroyka"]), 2)

    def test_public_old_bundle_rolls_back_even_if_smoke_would_pass(self):
        self.published_check.side_effect = ValueError("public_frontend_version_mismatch")
        with self.assertRaises(ValueError):
            canary.execute(True)
        self.assert_original_state()

    def test_anonymous_boundary_failure_does_not_publish_frontend(self):
        self.api_check.side_effect = ValueError("boundary_failed")
        with self.assertRaises(ValueError):
            canary.execute(True)
        self.assert_original_state()
        self.assertFalse(any(args[:2] == ["bash", "scripts/publish-frontend.sh"] for args in self.calls))


class HttpBoundaryTests(unittest.TestCase):
    def test_anonymous_probe_checks_route_specific_401_and_company_headers(self):
        error = urllib.error.HTTPError("https://example.test", 401, "Unauthorized",
                                       {"Cache-Control": "no-store"},
                                       io.BytesIO(b'{"detail":"supply_technical_comparison_authentication_required"}'))
        with patch.object(canary.urllib.request, "urlopen", side_effect=error) as request:
            canary.check_anonymous("https://example.test")
        headers = dict(request.call_args.args[0].header_items())
        self.assertEqual(headers["X-company-id"], "1")
        self.assertEqual(headers["X-company-mode"], "company")
        self.assertNotIn("Cookie", headers)
        self.assertNotIn("Authorization", headers)

    def test_anonymous_success_wrong_route_or_cached_error_is_not_success(self):
        for code, headers, body in (
            (200, {}, b"{}"),
            (422, {}, b"{}"),
            (401, {"Cache-Control": "no-store"}, b'{"detail":"other_route"}'),
            (401, {}, b'{"detail":"supply_technical_comparison_authentication_required"}'),
        ):
            kwargs = {"return_value": io.BytesIO(body)} if code == 200 else {
                "side_effect": urllib.error.HTTPError("https://example.test", code, "", headers, io.BytesIO(body)),
            }
            with self.subTest(code=code, body=body), patch.object(canary.urllib.request, "urlopen", **kwargs):
                with self.assertRaises(ValueError):
                    canary.check_anonymous("https://example.test")

    def test_public_manifest_must_match_the_new_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            manifest = {"files": {"main.js": "/static/js/new.js"}}
            (path / "asset-manifest.json").write_text(json.dumps(manifest))
            with patch.object(canary.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(manifest).encode())):
                canary.check_published_frontend(path)
            with patch.object(canary.urllib.request, "urlopen", return_value=io.BytesIO(b'{"files":{"main.js":"old.js"}}')):
                with self.assertRaises(ValueError):
                    canary.check_published_frontend(path)


if __name__ == "__main__":
    unittest.main()
