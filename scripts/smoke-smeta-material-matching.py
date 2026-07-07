#!/usr/bin/env python3
import asyncio
import importlib.machinery
import tempfile
from pathlib import Path

import openpyxl


ROOT = Path(__file__).resolve().parents[1]
CHECK_SMETA = ROOT / "scripts" / "check-smeta-parser.py"


def _load_parse_smeta():
    module = importlib.machinery.SourceFileLoader("check_smeta_parser", str(CHECK_SMETA)).load_module()
    return module._load_parse_smeta()


class FakeUpload:
    def __init__(self, path):
        self.path = Path(path)
        self.filename = self.path.name

    async def read(self):
        return self.path.read_bytes()


def _norm(value):
    return str(value or "").lower().replace("ё", "е")


def _find(items, needle):
    needle_key = _norm(needle)
    for item in items:
        if needle_key in _norm(item.get("name")):
            return item
    raise AssertionError(f"Не найдена строка сметы: {needle}")


def _build_test_smeta(path: Path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ЛСР"
    ws.append([
        "№",
        "Обоснование",
        "Наименование работ и затрат",
        "Единица измерения",
        "Количество на единицу",
        "Коэффициент",
        "Всего с учетом коэффициента",
        "Цена на единицу",
        "Коэффициент стоимости",
        "Стоимость всего",
        "Индекс",
        "Текущая стоимость",
    ])
    ws.append(["Раздел 1. Электрика"])
    ws.append([1, "ФЕРм08-03-593-03", "Светильник в подвесных потолках", "шт", 915, 1, 915, 100, 1, 91500, 1, 91500])
    ws.append(["", "101-001", "Прожектор LED 50Вт", "шт", 10, 1, 10, 1200, 1, 12000, 1, 12000])
    ws.append(["Раздел 2. Отделка"])
    ws.append([2, "ФЕР15-04-005-01", "Грунтование водно-дисперсионной грунтовкой", "100 м2", 18.46, 1, 18.46, 2500, 1, 46150, 1, 46150])
    ws.append(["", "101-002", "Грунтовка акриловая НОРТЕКС-ГРУНТ", "кг", 180, 1, 180, 120, 1, 21600, 1, 21600])
    wb.save(path)


async def main():
    parse_smeta = _load_parse_smeta()
    with tempfile.TemporaryDirectory(prefix="stroyka-smeta-smoke-") as tmp:
      path = Path(tmp) / "codex-smeta-parser-material-matching.xlsx"
      _build_test_smeta(path)
      parsed = await parse_smeta(FakeUpload(path))

    if parsed.get("error"):
        raise SystemExit(f"parse_smeta error: {parsed['error']}")
    items = parsed.get("items") or []
    if not items:
        raise SystemExit("parse_smeta returned no items")

    work_light = _find(items, "Светильник в подвесных потолках")
    if work_light.get("type") != "work":
        raise SystemExit(f"Светильник должен быть работой, получено: {work_light.get('type')}")

    material_light = _find(items, "Прожектор LED")
    if material_light.get("type") != "material":
        raise SystemExit(f"Прожектор должен быть материалом, получено: {material_light.get('type')}")
    if "Светильник" not in str(material_light.get("parentWorkName") or ""):
        raise SystemExit("Материал Прожектор LED не привязан к родительской работе")

    work_primer = _find(items, "Грунтование водно-дисперсионной грунтовкой")
    if work_primer.get("type") != "work":
        raise SystemExit(f"Грунтование должно быть работой, получено: {work_primer.get('type')}")

    material_primer = _find(items, "Грунтовка акриловая")
    if material_primer.get("type") != "material":
        raise SystemExit(f"Грунтовка должна быть материалом, получено: {material_primer.get('type')}")

    print({
        "ok": True,
        "items": len(items),
        "checked": [
            "imported work rows stay in main work estimate",
            "resource rows stay material and keep parent work link",
            "temporary xlsx is cleaned after smoke",
        ],
    })


if __name__ == "__main__":
    asyncio.run(main())
