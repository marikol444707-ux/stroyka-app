import unittest

from .service import build_candidate_record


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


if __name__ == "__main__":
    unittest.main()
