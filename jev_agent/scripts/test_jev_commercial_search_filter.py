import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("jev_commercial_search.py")
SPEC = importlib.util.spec_from_file_location("jev_commercial_search", SOURCE)
jev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jev)


class CommercialAssessmentTests(unittest.TestCase):
    NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)

    def row(self, title, *, query="", source="B2B-Center", procedure_id="1234567"):
        url = f"https://www.b2b-center.ru/app/market-next/market/tender-{procedure_id}/"
        if source == "Росэлторг":
            url = f"https://www.roseltorg.ru/procedure/{procedure_id}/1"
        return {
            "source": source,
            "id": procedure_id,
            "url": url,
            "title": title,
            "place": "Ставрополь",
            "deadline": "30.10.2026 18:00",
            "regime": "Коммерческая закупка",
            "search_query": query,
        }

    def test_query_hit_with_opaque_title_goes_to_manual_review(self):
        result = jev.assess(self.row("Открытый запрос предложений", query="ремонт Пятигорск"), self.NOW)
        self.assertEqual(result["decision"], "review")
        self.assertIn("construction_scope_unclear", result["reasons"])

    def test_construction_work_not_in_current_exact_pattern_stays_reviewable(self):
        result = jev.assess(self.row("Монтаж оконных блоков в школе"), self.NOW)
        self.assertEqual(result["decision"], "review")
        self.assertIn("construction_scope_unclear", result["reasons"])

    def test_goods_only_is_still_excluded_even_when_search_query_matches(self):
        result = jev.assess(self.row("Поставка щебня", query="строительство Ставрополь"), self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("goods_purchase_not_work", result["reasons"])

    def test_building_materials_category_is_not_a_contractor_opportunity(self):
        row = self.row("Строительные материалы прочие", query="строительство")
        result = jev.assess(row, self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("goods_purchase_not_work", result["reasons"])

    def test_explicit_smr_is_recognized_as_construction_work(self):
        row = self.row("Выполнение комплекса работ по проектированию и СМР")
        row["regime"] = ""
        result = jev.assess(row, self.NOW)
        self.assertEqual(result["decision"], "review")
        self.assertNotIn("construction_scope_unclear", result["reasons"])
        self.assertIn("procurement_regime_unknown", result["reasons"])

    def test_equipment_repair_is_not_promoted_to_building_work(self):
        result = jev.assess(self.row("Ремонт насосного оборудования", query="ремонт Ставрополь"), self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("equipment_repair_not_building_work", result["reasons"])

    def test_unrelated_search_result_is_still_excluded(self):
        result = jev.assess(self.row("Лабораторные исследования овощных культур"), self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("not_construction_work", result["reasons"])

    def test_nonconstruction_title_from_other_provider_is_not_promoted_by_query(self):
        result = jev.assess(self.row("Реагенты Гидрохим для работы ТВГСиПК",
                                     query="ремонт", source="Росэлторг", procedure_id="COM123456"), self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("not_construction_work", result["reasons"])

    def test_ambiguous_b2b_result_without_stavropol_work_region_is_excluded(self):
        row = self.row("Текущий ремонт помещений в Барнауле", query="ремонт")
        row["place"] = None
        result = jev.assess(row, self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("other_region", result["reasons"])

    def test_company_name_mikhailovsky_does_not_masquerade_as_stavropol_city(self):
        row = self.row("Текущий ремонт помещений комплекса АО «Михайловский ГОК»")
        row["place"] = None
        row["region"] = "Курская область"
        result = jev.assess(row, self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("other_region", result["reasons"])

    def test_waste_service_is_not_a_construction_opportunity(self):
        result = jev.assess(self.row('Транспортировка, утилизация отходов грунта при земляных работах',
                                     source="Росэлторг", procedure_id="COM123456"), self.NOW)
        self.assertEqual(result["decision"], "excluded")
        self.assertIn("non_construction_service", result["reasons"])


if __name__ == "__main__":
    unittest.main()
