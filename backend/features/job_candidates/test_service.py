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

    def test_maps_confirmed_review_and_separate_government_rows_from_jev_report(self):
        items = jev_report_items({
            "region": "Ставропольский край",
            "confirmed": [{"source": "B2B-Center", "id": "42", "url": "https://example.org/42",
                           "title": "Ремонт кровли", "price": "1 250 000 ₽",
                           "deadline_msk": "2026-11-01T12:00:00+03:00"}],
            "review": [{"source": "Росэлторг", "url": "https://example.org/43", "title": "Строительство",
                        "reasons": ["work_location_unknown"]}],
            "government_review": [{"source": "ЕИС", "provider": "ЕИС · 44-ФЗ", "id": "0123456789012345678",
                                   "url": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0123456789012345678",
                                   "title": "Капремонт школы", "regime": "44-ФЗ",
                                   "region_scope": "not_filtered", "search_query": "капитальный ремонт Ставрополь",
                                   "search_queries": ["капитальный ремонт Ставрополь", "ремонт школы"],
                                   "reasons": ["manual_check"]}],
            "excluded": [{"source": "Сбер А", "id": "44", "url": "https://example.org/44", "title": "Поставка кирпича"}],
        })

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["source"], "browser_agent")
        self.assertEqual(items[0]["sourceName"], "B2B-Center")
        self.assertEqual(items[0]["sourceItemId"], "B2B-Center:42")
        self.assertEqual(items[0]["region"], "Ставропольский край")
        self.assertEqual(items[0]["price"], "1250000")
        self.assertEqual(items[0]["deadline"], "2026-11-01T12:00:00+03:00")
        self.assertEqual(items[1]["evidence"], "work_location_unknown")
        self.assertEqual(items[2]["sourceName"], "ЕИС · 44-ФЗ")
        self.assertEqual(items[2]["sourceItemId"], "ЕИС · 44-ФЗ:0123456789012345678")
        self.assertEqual(items[2]["region"], "")
        self.assertIn("44-ФЗ", items[2]["evidence"])
        self.assertIn("ремонт школы", items[2]["evidence"])
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
