import unittest
from pathlib import Path

from backend.features.crm.ad_sources import AD_SOURCES, utm_columns, website_lead_source


class AdSourceTests(unittest.TestCase):
    def test_known_codes_use_human_names_and_unknown_codes_stay_readable(self):
        self.assertEqual(website_lead_source("Сайт", "netip"), "Сайт / Нетипичный Ставрополь")
        self.assertEqual(website_lead_source("NETIP", "NeTiP"), "Сайт / Нетипичный Ставрополь")
        self.assertEqual(
            website_lead_source("Сайт: партнерская заявка", "bloknot", partner=True),
            "Сайт: партнерская заявка / Блокнот",
        )
        self.assertEqual(website_lead_source("Сайт", "city_ads"), "Сайт / city_ads")
        self.assertEqual(website_lead_source("Сайт", ""), "Сайт")
        self.assertEqual(website_lead_source("Чужой текст", "netip"), "Сайт / Нетипичный Ставрополь")

    def test_utm_columns_are_nullable_and_limited(self):
        self.assertEqual(utm_columns({}), (None, None, None))
        self.assertEqual(utm_columns({"utm": {"utm_source": "  netip  "}}), ("netip", None, None))
        long_value = "x" * 200
        self.assertEqual(utm_columns({"utm": {"utm_campaign": long_value}})[2], "x" * 120)

    def test_public_link_doc_lists_every_code(self):
        document = Path(__file__).resolve().parents[3] / "docs" / "ad-source-links.md"
        text = document.read_text(encoding="utf-8")
        for code, label in AD_SOURCES.items():
            self.assertIn(label, text)
            self.assertIn(
                f"https://stroyka26.pro/?utm_source={code}&utm_medium=telegram&utm_campaign=ads",
                text,
            )


if __name__ == "__main__":
    unittest.main()
