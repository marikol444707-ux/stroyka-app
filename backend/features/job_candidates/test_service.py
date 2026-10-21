import unittest

from .service import build_candidate_record, jev_report_items


class JobCandidateNormalizationTests(unittest.TestCase):
    def test_canonicalizes_url_and_uses_source_identity_for_deduplication(self):
        candidate = build_candidate_record({
            "source": "eis",
            "sourceItemId": "  012345  ",
            "url": "HTTPS://zakupki.gov.ru/notice/123/?utm_source=mail#top",
            "title": "  Ремонт кровли  ",
            "description": "Работы по ремонту кровли",
            "region": " Ставропольский край ",
            "workTypes": ["ремонт", " кровля "],
            "evidence": "Извещение о закупке",
        })

        self.assertEqual(candidate["url"], "https://zakupki.gov.ru/notice/123")
        self.assertEqual(candidate["identity_key"], "id:012345")
        self.assertEqual(candidate["title"], "Ремонт кровли")
        self.assertEqual(candidate["work_types"], ["ремонт", "кровля"])
        self.assertEqual(candidate["status"], "Нужно проверить")

    def test_url_is_fallback_identity_when_source_item_id_is_missing(self):
        candidate = build_candidate_record({
            "source": "public_web",
            "url": "https://example.org/orders/8?ref=feed",
            "title": "Ремонт фасада",
        })

        self.assertTrue(candidate["identity_key"].startswith("url:"))
        self.assertEqual(len(candidate["identity_key"]), 68)

    def test_rejects_unsafe_or_incomplete_candidate(self):
        invalid = [
            {"source": "eis", "url": "javascript:alert(1)", "title": "Работа"},
            {"source": "eis", "url": "https://example.org/x"},
            {"source": "", "url": "https://example.org/x", "title": "Работа"},
        ]

        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                build_candidate_record(payload)

    def test_maps_only_confirmed_and_review_rows_from_jev_report(self):
        items = jev_report_items({
            "region": "Ставропольский край",
            "confirmed": [{"source": "B2B-Center", "id": "42", "url": "https://example.org/42",
                           "title": "Ремонт кровли", "price": "1 250 000 ₽",
                           "deadline_msk": "2026-11-01T12:00:00+03:00"}],
            "review": [{"source": "Росэлторг", "url": "https://example.org/43", "title": "Строительство",
                        "reasons": ["work_location_unknown"]}],
            "excluded": [{"source": "Сбер А", "id": "44", "url": "https://example.org/44", "title": "Поставка кирпича"}],
        })

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["source"], "browser_agent")
        self.assertEqual(items[0]["sourceName"], "B2B-Center")
        self.assertEqual(items[0]["sourceItemId"], "B2B-Center:42")
        self.assertEqual(items[0]["region"], "Ставропольский край")
        self.assertEqual(items[0]["price"], "1250000")
        self.assertEqual(items[0]["deadline"], "2026-11-01T12:00:00+03:00")
        self.assertEqual(items[1]["evidence"], "work_location_unknown")
        dotted_amount = jev_report_items({"confirmed": [{"url": "https://example.org/2",
                                                          "title": "Ремонт", "price": "1.250.000"}]})
        self.assertEqual(dotted_amount[0]["price"], "1250000")

    def test_rejects_malformed_jev_buckets_and_oversized_reports(self):
        with self.assertRaises(ValueError):
            jev_report_items({"confirmed": "bad"})
        report = {"confirmed": [{"url": f"https://example.org/{i}", "title": "Ремонт"}
                                 for i in range(201)]}
        with self.assertRaises(ValueError):
            jev_report_items(report)


if __name__ == "__main__":
    unittest.main()
