import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("smoke-material-control-lineage.py")
SPEC = importlib.util.spec_from_file_location("smoke_material_control_lineage", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MaterialControlLineageSmokeTests(unittest.TestCase):
    def test_payload_keeps_exact_source_coordinates(self):
        candidate = {
            "estimateId": 17,
            "estimateName": "Электрика",
            "projectName": "Школа 1",
            "workPackage": "Электрика",
            "sectionIndex": 2,
            "itemIndex": 9,
            "sectionName": "Кабельные линии",
            "materialName": "Кабель ВВГнг-LS",
            "unit": "м",
            "sourceQuantity": 100,
            "quantity": 0.001,
        }

        payload = MODULE.make_request_payload([candidate], label="одиночная заявка")

        self.assertEqual(payload["requestSource"], MODULE.REQUEST_SOURCE)
        self.assertEqual(payload["items"][0]["sourceType"], MODULE.REQUEST_SOURCE)
        self.assertEqual(payload["items"][0]["estimateLineage"]["sources"][0], {
            "estimateId": 17,
            "estimateName": "Электрика",
            "sectionIndex": 2,
            "itemIndex": 9,
            "sectionName": "Кабельные линии",
            "materialName": "Кабель ВВГнг-LS",
            "unit": "м",
            "quantity": 100,
        })

    def test_multi_item_payload_uses_position_unit(self):
        base = {
            "estimateId": 17, "estimateName": "Электрика", "projectName": "Школа 1",
            "workPackage": "Электрика", "sectionIndex": 2, "itemIndex": 9,
            "sectionName": "Кабельные линии", "materialName": "Кабель", "unit": "м",
            "sourceQuantity": 100, "quantity": 0.001,
        }
        payload = MODULE.make_request_payload([base, {**base, "itemIndex": 10, "materialName": "Гофра"}], label="пакет")

        self.assertEqual(payload["quantity"], 2)
        self.assertEqual(payload["unit"], "поз.")
        self.assertEqual(len(payload["items"]), 2)


if __name__ == "__main__":
    unittest.main()
