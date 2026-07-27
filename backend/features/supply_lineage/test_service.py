import json
import unittest

from backend.features.supply_lineage.service import (
    MATERIAL_CONTROL_REQUEST_SOURCE,
    MaterialControlLineageError,
    validate_material_control_request_lineage,
)


def material_item(name="Смесь штукатурная", unit="кг"):
    return {
        "itemType": "material",
        "name": name,
        "unit": unit,
        "quantity": 25,
    }


def estimate_row(**patch):
    row = {
        "id": 14,
        "company_id": 1,
        "project_id": 3,
        "project_name": "Школа 1",
        "status": "Активная",
        "smeta_type": "Материалы",
        "work_package": "Отделка",
        "sections_json": json.dumps([
            {"name": "Подготовка", "items": []},
            {"name": "Фасад", "items": []},
            {"name": "Штукатурные работы", "items": [material_item()]},
        ], ensure_ascii=False),
    }
    row.update(patch)
    return row


def request_item(**patch):
    item = {
        "materialName": "Смесь штукатурная",
        "quantity": 10,
        "unit": "кг",
        "workPackage": "Отделка",
        "sourceType": MATERIAL_CONTROL_REQUEST_SOURCE,
        "estimateLineage": {
            "version": 1,
            "projectName": "Школа 1",
            "workPackage": "Отделка",
            "sources": [{
                "estimateId": 14,
                "sectionIndex": 2,
                "itemIndex": 0,
                "sectionName": "Штукатурные работы",
                "materialName": "Смесь штукатурная",
                "unit": "кг",
                "quantity": 25,
            }],
        },
    }
    item.update(patch)
    return item


class SupplyLineageServiceTests(unittest.TestCase):
    def validate(self, items=None, estimates=None, resolver=None):
        return validate_material_control_request_lineage(
            request_source=MATERIAL_CONTROL_REQUEST_SOURCE,
            request_notes="",
            project_name="Школа 1",
            company_id=1,
            work_package="Отделка",
            items=items or [request_item()],
            estimates_by_id=estimates or {14: estimate_row()},
            parse_sections=lambda value: json.loads(value),
            item_type=lambda item, _section: item.get("itemType"),
            item_plan_issue=lambda _item, _section: "",
            material_key=resolver or (lambda _project, name, unit: (name.lower(), unit.lower())),
            normalize_unit=lambda value: value.lower(),
            item_quantity=lambda item: item.get("quantity") or 0,
        )

    def test_accepts_exact_active_estimate_row(self):
        validated = self.validate()

        self.assertEqual(validated[0]["estimateLineage"]["validated"], True)
        self.assertEqual(validated[0]["estimateLineage"]["sourceCount"], 1)

    def test_accepts_confirmed_alias_identity(self):
        item = request_item(materialName="Штукатурка Knauf")

        validated = self.validate(
            items=[item],
            resolver=lambda _project, name, unit: (
                "смесь штукатурная" if name == "Штукатурка Knauf" else name.lower(),
                unit.lower(),
            ),
        )

        self.assertTrue(validated[0]["estimateLineage"]["validated"])

    def test_rejects_material_control_item_without_lineage(self):
        item = request_item()
        item.pop("estimateLineage")

        with self.assertRaisesRegex(MaterialControlLineageError, "нет проверяемой связи"):
            self.validate(items=[item])

    def test_rejects_foreign_estimate_owner(self):
        with self.assertRaisesRegex(MaterialControlLineageError, "другой компании"):
            self.validate(estimates={14: estimate_row(company_id=2)})

    def test_rejects_wrong_project_or_package(self):
        with self.assertRaisesRegex(MaterialControlLineageError, "другому объекту"):
            self.validate(estimates={14: estimate_row(project_name="Другой объект")})

        with self.assertRaisesRegex(MaterialControlLineageError, "другому пакету"):
            self.validate(estimates={14: estimate_row(work_package="Электрика")})

    def test_rejects_stale_source_coordinates(self):
        item = request_item()
        item["estimateLineage"]["sources"][0]["itemIndex"] = 4

        with self.assertRaisesRegex(MaterialControlLineageError, "строка сметы не найдена"):
            self.validate(items=[item])

    def test_rejects_fractional_or_boolean_source_coordinates(self):
        fractional = request_item()
        fractional["estimateLineage"]["sources"][0]["sectionIndex"] = 1.5
        with self.assertRaisesRegex(MaterialControlLineageError, "конкретной строкой сметы"):
            self.validate(items=[fractional])

        boolean_id = request_item()
        boolean_id["estimateLineage"]["sources"][0]["estimateId"] = True
        with self.assertRaisesRegex(MaterialControlLineageError, "конкретной строкой сметы"):
            self.validate(items=[boolean_id])

    def test_rejects_source_identity_changed_in_estimate(self):
        with self.assertRaisesRegex(MaterialControlLineageError, "материал изменился"):
            self.validate(estimates={
                14: estimate_row(sections_json=json.dumps([
                    {"name": "Подготовка", "items": []},
                    {"name": "Фасад", "items": []},
                    {"name": "Штукатурные работы", "items": [material_item("Грунтовка")]},
                ], ensure_ascii=False)),
            })

    def test_rejects_source_quantity_changed_in_estimate(self):
        with self.assertRaisesRegex(MaterialControlLineageError, "объём исходной строки"):
            self.validate(
                estimates={14: estimate_row(sections_json=json.dumps([
                    {"name": "Подготовка", "items": []},
                    {"name": "Фасад", "items": []},
                    {"name": "Штукатурные работы", "items": [
                        material_item() | {"quantity": 30},
                    ]},
                ], ensure_ascii=False))},
                resolver=lambda _project, name, unit: (name.lower(), unit.lower()),
            )

    def test_ignores_manual_request_without_material_control_source(self):
        self.assertEqual(
            validate_material_control_request_lineage(
                request_source="",
                request_notes="",
                project_name="Школа 1",
                company_id=1,
                work_package="Отделка",
                items=[{"materialName": "Ручная позиция"}],
                estimates_by_id={},
                parse_sections=lambda value: value,
                item_type=lambda *_args: "material",
                item_plan_issue=lambda *_args: "",
                material_key=lambda *_args: ("", ""),
                normalize_unit=lambda value: value,
            ),
            [{"materialName": "Ручная позиция"}],
        )

    def test_rejects_legacy_cached_material_control_payload(self):
        with self.assertRaisesRegex(MaterialControlLineageError, "обновите приложение"):
            validate_material_control_request_lineage(
                request_source="",
                request_notes="Создано из контроля материалов: строка `Докупить`.",
                project_name="Школа 1",
                company_id=1,
                work_package="Отделка",
                items=[{"materialName": "Смесь штукатурная"}],
                estimates_by_id={},
                parse_sections=lambda value: value,
                item_type=lambda *_args: "material",
                item_plan_issue=lambda *_args: "",
                material_key=lambda *_args: ("", ""),
                normalize_unit=lambda value: value,
            )


if __name__ == "__main__":
    unittest.main()
