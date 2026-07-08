#!/usr/bin/env python3
import asyncio
import glob
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "backend" / "main.py"


def _parse_smeta_route_block(src):
    match = re.search(
        r'@app\.post\("/parse-smeta"\)\n(.*?)\n\n@app\.get\("/estimates"\)',
        src,
        re.S,
    )
    if not match:
        raise RuntimeError("parse_smeta block not found")
    return match.group(1)


def _assert_parse_smeta_route_hardened(src, block):
    route_header = block.split("\n", 1)[0]
    if "Depends(get_current_user)" not in route_header:
        raise RuntimeError("parse_smeta route must require get_current_user")
    required_guards = (
        "SMETA_PARSE_MAX_BYTES",
        "SMETA_PARSE_ALLOWED_EXTENSIONS",
        "filename",
    )
    missing = [name for name in required_guards if name not in block]
    if missing:
        raise RuntimeError("parse_smeta upload guard missing: " + ", ".join(missing))


def _load_parse_smeta():
    src = MAIN.read_text()
    block = _parse_smeta_route_block(src)
    _assert_parse_smeta_route_hardened(src, block)
    shim = """
class HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail

def File(*args, **kwargs):
    return None

def Depends(*args, **kwargs):
    return None

def get_current_user(*args, **kwargs):
    return {"id": 1, "role": "директор", "name": "Parser Test"}

class UploadFile:
    pass

app = type("A", (), {"post": lambda self, *a, **k: (lambda f: f)})()
"""
    namespace = {}
    exec(shim + block, namespace)
    return namespace["parse_smeta"]


class FakeUpload:
    def __init__(self, path):
        self.path = Path(path)
        self.filename = self.path.name

    async def read(self):
        return self.path.read_bytes()


def _num(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _norm_text(value):
    return str(value or "").lower().replace("ё", "е").replace("\xa0", " ").strip()


def _looks_material_resource(value):
    text = _norm_text(value)
    if not text:
        return False
    work_starts = (
        "монтаж", "демонтаж", "устройство", "установка", "разбор",
        "разборка", "снятие", "очистка", "отбивка", "облицовка",
        "окраска", "грунтование", "штукатурка поверхностей", "стяжка",
        "смена", "прокладка", "подключение", "ремонт"
    )
    if any(text.startswith(prefix) for prefix in work_starts):
        return False
    material_words = (
        "материал", "труба", "кабель", "провод", "смесь", "раствор",
        "штукатурка", "шпатлев", "шпаклев", "клей", "краска", "акрил",
        "грунтовка", "цемент", "бетон", "кирпич", "блок", "лист",
        "профиль", "саморез", "плитка", "керамогранит", "гранит",
        "линолеум", "арматур", "битум", "бризол", "лак", "мастик",
        "утеплитель", "рубероид", "пвх", "уголок", "панель", "плинтус",
        "наличник", "дюбел", "втулк", "скреп", "крепеж"
    )
    return any(word in text for word in material_words)


def _find_items(items, needle):
    needle = _norm_text(needle)
    return [item for item in items if needle in _norm_text(item.get("name"))]


def _assert_close(errors, file_name, label, actual, expected, tolerance=0.01):
    if abs(_num(actual) - float(expected)) > tolerance:
        errors.append(f"{file_name}: {label} expected={expected} actual={actual}")


def _assert_regression_item(errors, file_name, items, needle, *, item_type=None,
                            unit=None, quantity=None, total_min=None):
    hits = _find_items(items, needle)
    if not hits:
        errors.append(f"{file_name}: regression item not found: {needle}")
        return
    item = hits[0]
    if item_type and item.get("type") != item_type:
        errors.append(
            f"{file_name}: {needle} type expected={item_type} actual={item.get('type')}"
        )
    if unit and item.get("unit") != unit:
        errors.append(
            f"{file_name}: {needle} unit expected={unit} actual={item.get('unit')}"
        )
    if quantity is not None:
        _assert_close(errors, file_name, f"{needle} quantity", item.get("quantity"), quantity)
    if total_min is not None and _num(item.get("total")) < float(total_min):
        errors.append(
            f"{file_name}: {needle} total too low expected>={total_min} actual={item.get('total')}"
        )


def _check_known_regressions(file_name, items, errors):
    """Закрепляет реальные ошибки импорта, которые уже ломали рабочую смету."""
    if file_name == "Общестрой на 102 121 191,67.xlsx":
        _assert_regression_item(
            errors, file_name, items,
            "Отбивка штукатурки с поверхностей: стен и потолков кирпичных",
            item_type="work", unit="м2", quantity=7210, total_min=1,
        )
        _assert_regression_item(
            errors, file_name, items,
            "Грунтование водно-дисперсионной грунтовкой",
            item_type="work", unit="м2", quantity=1846, total_min=1,
        )
        _assert_regression_item(
            errors, file_name, items,
            "Грунтовка акриловая НОРТЕКС-ГРУНТ",
            item_type="material", unit="кг", total_min=1,
        )
        _assert_regression_item(
            errors, file_name, items,
            "Дюбели монтажные",
            item_type="material", unit="шт", quantity=39.678, total_min=1,
        )
        _assert_regression_item(
            errors, file_name, items,
            "Клинья пластиковые монтажные",
            item_type="material", unit="шт", quantity=81.6, total_min=1,
        )
    elif file_name == "Электрика на 12 208 784,66.xlsx":
        _assert_regression_item(
            errors, file_name, items,
            "Втулки В22",
            item_type="material", unit="шт", quantity=1072.99, total_min=1,
        )
        _assert_regression_item(
            errors, file_name, items,
            "Светильник в подвесных потолках",
            item_type="work", unit="шт", quantity=915, total_min=1,
        )
    elif file_name == "Отопление 8166 593,50.1.xlsx":
        _assert_regression_item(
            errors, file_name, items,
            "Демонтаж: радиаторов весом до 80 кг",
            item_type="work", unit="шт", quantity=133, total_min=1,
        )
    elif file_name in ("СК_ Лицей 5.xlsx", "СК_ Лицей 4_корр.2_05.05.2026.xlsx", "СК_ Л®ж•© 4_™Ѓаа.2_05.05.2026.xlsx"):
        _assert_regression_item(
            errors, file_name, items,
            "Раствор готовый отделочный",
            item_type="adjustment",
        )
        _assert_regression_item(
            errors, file_name, items,
            "Линолеум поливинилхлоридный",
            item_type="adjustment",
        )


async def _check_file(parse_smeta, path):
    data = await parse_smeta(FakeUpload(path))
    if data.get("error"):
        return [f"{Path(path).name}: parser error: {data['error']}"]

    items = data.get("items", [])
    meta = data.get("meta", {})
    errors = []

    declared = _num(meta.get("declaredTotal"))
    parsed = _num(meta.get("parsedTotal"))
    if declared and parsed and abs(declared - parsed) > max(1000, declared * 0.01):
        errors.append(
            f"{Path(path).name}: total mismatch declared={declared:.2f} parsed={parsed:.2f}"
        )

    big_qty = [
        item for item in items
        if abs(_num(item.get("quantity"))) > 1_000_000
    ]
    if big_qty:
        sample = big_qty[0]
        errors.append(
            f"{Path(path).name}: huge quantity {sample.get('quantity')} "
            f"{sample.get('unit')} in {str(sample.get('name'))[:80]}"
        )

    service_material_rows = [
        item for item in items
        if item.get("type") == "material"
        and _norm_text(item.get("name")) in ("материалы", "материал", "строительные материалы")
    ]
    if service_material_rows:
        sample = service_material_rows[0]
        errors.append(
            f"{Path(path).name}: service row imported as material: {str(sample.get('name'))[:80]}"
        )

    negative_material_rows = [
        item for item in items
        if item.get("type") in ("material", "equipment", "transport")
        and (_num(item.get("quantity")) < 0 or _num(item.get("lineTotal") or item.get("total")) < 0)
    ]
    if negative_material_rows:
        sample = negative_material_rows[0]
        errors.append(
            f"{Path(path).name}: negative resource imported as material: "
            f"{sample.get('quantity')} {sample.get('unit')} in {str(sample.get('name'))[:80]}"
        )

    negative_resource_work_rows = [
        item for item in items
        if item.get("type") == "work"
        and (_num(item.get("quantity")) < 0 or _num(item.get("lineTotal") or item.get("total")) < 0)
        and _looks_material_resource(item.get("name"))
    ]
    if negative_resource_work_rows:
        sample = negative_resource_work_rows[0]
        errors.append(
            f"{Path(path).name}: negative resource imported as work: "
            f"{sample.get('quantity')} {sample.get('unit')} in {str(sample.get('name'))[:80]}"
        )

    zero_work_sum = [
        item for item in items
        if item.get("type") == "work" and abs(_num(item.get("total"))) < 0.01
    ]
    if zero_work_sum:
        sample = zero_work_sum[0]
        errors.append(
            f"{Path(path).name}: zero work total in {str(sample.get('name'))[:80]}"
        )

    _check_known_regressions(Path(path).name, items, errors)

    print(
        f"OK {Path(path).name}: items={len(items)} "
        f"declared={declared:.2f} parsed={parsed:.2f}"
    )
    return errors


async def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "Kislovodsk"
    if target.is_dir():
        files = sorted(glob.glob(str(target / "*.xlsx")))
    else:
        files = sorted(glob.glob(str(target)))
    files = [path for path in files if not Path(path).name.startswith("~$")]
    if not files:
        raise SystemExit(f"No xlsx files found: {target}")

    parse_smeta = _load_parse_smeta()
    errors = []
    for path in files:
        errors.extend(await _check_file(parse_smeta, path))

    if errors:
        print("\nFAILED")
        for error in errors:
            print("-", error)
        raise SystemExit(1)
    print("\nSmeta parser check OK")


if __name__ == "__main__":
    asyncio.run(main())
