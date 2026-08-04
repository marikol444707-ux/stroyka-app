import unittest
from io import BytesIO
from inspect import iscoroutinefunction

import openpyxl

from backend.features.smeta_parser.routes import register_smeta_parser_module


class FakeApp:
    def __init__(self):
        self.routes = {}

    def post(self, path):
        def decorator(handler):
            self.routes[("POST", path)] = handler
            return handler
        return decorator


class FakeUpload:
    def __init__(self, filename, content=b""):
        self.filename = filename
        self.file = BytesIO(content)


class SmetaParserRouteTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FakeApp()
        register_smeta_parser_module(self.app, {"get_current_user": lambda: {}})

    def test_registers_same_url(self):
        self.assertIn(("POST", "/parse-smeta"), self.app.routes)
        self.assertFalse(iscoroutinefunction(self.app.routes[("POST", "/parse-smeta")]))

    def test_rejects_non_excel_extension(self):
        handler = self.app.routes[("POST", "/parse-smeta")]
        result = handler(file=FakeUpload("smeta.xls"), _current_user={})
        self.assertIn("error", result)
        self.assertIn(".xlsx", result["error"])

    def test_rejects_oversized_file(self):
        handler = self.app.routes[("POST", "/parse-smeta")]
        result = handler(file=FakeUpload("smeta.xlsx", b"x" * (15 * 1024 * 1024 + 1)), _current_user={})
        self.assertIn("error", result)
        self.assertIn("15", result["error"])

    def test_rejects_completed_work_act_as_estimate(self):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet["A1"] = "Акт о приемке выполненных работ № 7"
        sheet["A2"] = "Наименование работ"
        content = BytesIO()
        workbook.save(content)

        handler = self.app.routes[("POST", "/parse-smeta")]
        result = handler(file=FakeUpload("выполнение.xlsx", content.getvalue()), _current_user={})

        self.assertIn("error", result)
        self.assertIn("акт", result["error"].lower())
        self.assertIn("ЛСР", result["error"])

    def test_uses_explicit_grand_total_and_keeps_all_position_costs(self):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet["A1"] = "Индексы изменения сметной стоимости. Письмо Минстроя России № 69894-ИФ/09"
        sheet["A2"] = "Сметная стоимость"
        sheet["D2"] = 20.8
        sheet["E2"] = "тыс.руб."
        headers = {
            "A3": "№ п/п",
            "B3": "Обоснование",
            "C3": "Наименование работ и затрат",
            "H3": "Единица измерения",
            "I3": "на единицу измерения",
            "J3": "коэффициенты",
            "K3": "всего с учетом коэффициентов",
            "L3": "на единицу измерения в базисном уровне цен",
            "M3": "индекс",
            "N3": "на единицу измерения в текущем уровне цен",
            "O3": "коэффициенты",
            "P3": "всего в текущем уровне цен",
        }
        for cell, value in headers.items():
            sheet[cell] = value
        sheet.append([1, "ГЭСНм08-01", "Монтаж оборудования", None, None, None, None, "шт", 1, 1, 1])
        sheet.append([None, "1", "ОТ(ЗТ)", None, None, None, None, "чел.-ч", None, None, 1, None, None, None, None, 10000])
        sheet.append([None, "1", "ОТм(ЗТм)", None, None, None, None, "чел.-ч", None, None, 1, None, None, None, None, 2000])
        sheet.append([None, "4", "М", None, None, None, None, None, None, None, None, None, None, None, None, 3000])
        sheet.append([1.1, "421/пр_2020", "Вспомогательные ненормируемые материальные ресурсы", None, None, None, None, "%", 2, None, 2, None, None, None, None, 500])
        sheet.append([None, "Пр/812", "НР Монтажные работы", None, None, None, None, "%", 80, None, 80, None, None, None, None, 4000])
        sheet.append([None, "Пр/774", "СП Монтажные работы", None, None, None, None, "%", 20, None, 20, None, None, None, None, 1000])
        sheet.append([None, None, "Всего по позиции", None, None, None, None, None, None, None, None, None, None, 19000, None, 20500])
        sheet.append([2, "ФСБЦ-01", "Кабель", None, None, None, None, "м", 2, 1, 2, 100, 1.5, 150, 1, 300])
        sheet.append([None, None, "Всего по позиции", None, None, None, None, None, None, None, None, None, None, 150, None, 300])
        sheet.append([None, None, "ВСЕГО по смете", None, None, None, None, None, None, None, None, None, None, None, None, 20800])
        content = BytesIO()
        workbook.save(content)

        handler = self.app.routes[("POST", "/parse-smeta")]
        result = handler(file=FakeUpload("сети-связи.xlsx", content.getvalue()), _current_user={})

        self.assertNotIn("error", result)
        self.assertEqual(result["meta"]["declaredTotal"], 20800)
        self.assertEqual(result["meta"]["parsedTotal"], 20800)
        self.assertFalse(result["meta"]["totalMismatch"])
        cable = next(item for item in result["items"] if item["name"] == "Кабель")
        self.assertEqual(cable["total"], 300)
        self.assertFalse(any(item.get("importKind") == "reconciliation" for item in result["items"]))


if __name__ == "__main__":
    unittest.main()
