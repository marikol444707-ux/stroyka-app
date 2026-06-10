#!/usr/bin/env python3
import asyncio
import glob
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "backend" / "main.py"


def _load_parse_smeta():
    src = MAIN.read_text()
    match = re.search(
        r'@app\.post\("/parse-smeta"\)\n(.*?)\n\n@app\.get\("/estimates"\)',
        src,
        re.S,
    )
    if not match:
        raise RuntimeError("parse_smeta block not found")
    shim = """
class HTTPException(Exception):
    def __init__(self, status_code=None, detail=None):
        self.status_code = status_code
        self.detail = detail

def File(*args, **kwargs):
    return None

class UploadFile:
    pass

app = type("A", (), {"post": lambda self, *a, **k: (lambda f: f)})()
"""
    namespace = {}
    exec(shim + match.group(1), namespace)
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

    zero_work_sum = [
        item for item in items
        if item.get("type") == "work" and abs(_num(item.get("total"))) < 0.01
    ]
    if zero_work_sum:
        sample = zero_work_sum[0]
        errors.append(
            f"{Path(path).name}: zero work total in {str(sample.get('name'))[:80]}"
        )

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
