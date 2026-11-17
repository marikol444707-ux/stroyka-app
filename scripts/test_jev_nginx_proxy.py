import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


class JevNginxProxyTests(unittest.TestCase):
    def test_ingest_and_crm_review_paths_are_forwarded_to_backend(self):
        config = (ROOT / "ops-nginx-stroyka-public-api.conf").read_text()
        self.assertIn("location = /internal/jev/job-candidates", config)
        self.assertIn("location = /crm/job-candidates", config)
        self.assertIn("location ^~ /crm/job-candidates/", config)
        for path in ("/internal/jev/job-candidates", "/crm/job-candidates",
                     "/crm/job-candidates/"):
            with self.subTest(path=path):
                self.assertRegex(
                    config,
                    rf"location (?:=|\^~) {re.escape(path)}[^{{]*\{{[^}}]*proxy_pass http://127\.0\.0\.1:8001;",
                )
        self.assertRegex(config, r"location = /internal/jev/job-candidates\s*\{[^}]*client_max_body_size 1m;")

    def test_public_proxy_smoke_detects_an_unproxied_post_as_failure(self):
        smoke = (ROOT / "scripts/check-public-api-proxy.sh").read_text()
        self.assertIn('"/crm/job-candidates" "401 403 429"', smoke)
        self.assertIn('"/internal/jev/job-candidates" "401 422 429 503"', smoke)


if __name__ == "__main__":
    unittest.main()
