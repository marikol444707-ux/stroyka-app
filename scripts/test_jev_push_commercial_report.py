import unittest
from urllib.parse import urlsplit

from scripts.jev_push_commercial_report import build_request


class JevReportPushTests(unittest.TestCase):
    def test_builds_https_company_scoped_report_request(self):
        report = {
            "region": "Ставропольский край",
            "confirmed": [{"source": "B2B-Center", "id": "123", "url": "https://example.org/123",
                           "title": "Ремонт кровли", "price": "1 250 000 ₽",
                           "deadline": "25.10.2026 16:00"}],
            "review": [], "excluded": {"goods_purchase_not_work": 4},
        }
        request, count = build_request(report, api_url="https://stroyka26.pro", ingest_key="s" * 40)
        self.assertEqual(request.full_url, "https://stroyka26.pro/api/internal/jev/job-candidates")
        self.assertEqual(urlsplit(request.full_url).scheme, "https")
        self.assertEqual(request.get_header("X-jev-ingest-key"), "s" * 40)
        self.assertEqual(count, 1)

    def test_rejects_non_https_and_short_secret(self):
        report = {"confirmed": [{"url": "https://example.org/1", "title": "Ремонт"}]}
        for url, key in (("http://stroyka26.pro", "s" * 40), ("https://stroyka26.pro", "short")):
            with self.subTest(url=url), self.assertRaises(ValueError):
                build_request(report, api_url=url, ingest_key=key)

    def test_rejects_empty_candidates(self):
        with self.assertRaises(ValueError):
            build_request({"confirmed": [], "review": [], "excluded": {}},
                          api_url="https://stroyka26.pro", ingest_key="s" * 40)

    def test_allows_empty_results_when_source_checks_exist(self):
        report = {"confirmed": [], "review": [], "sources": [
            {"provider": "B2B-Center", "query": "ремонт", "ok": True, "rows": 0},
        ]}
        request, count = build_request(
            report, api_url="https://stroyka26.pro", ingest_key="s" * 40,
        )
        self.assertEqual(count, 0)
        self.assertIn(b'"sources"', request.data)


if __name__ == "__main__":
    unittest.main()
