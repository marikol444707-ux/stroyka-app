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


if __name__ == "__main__":
    unittest.main()
