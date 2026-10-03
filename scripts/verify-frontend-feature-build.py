#!/usr/bin/env python3
"""Reject mismatched work-material modes and missing enabled feature workflows."""
import json
from html.parser import HTMLParser
import sys
from pathlib import Path


class FeatureBuildMetadata(HTMLParser):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.values = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("name") == self.name:
            self.values.append(values.get("content"))


def verify(build_dir: Path, build_environment: str) -> None:
    flags = dict(
        line.split("=", 1)
        for line in build_environment.splitlines()
        if "=" in line
    )
    for key, metadata_name, label in (
        ("REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED", "stroyka-work-material-accounting", "учёта материалов"),
        ("REACT_APP_WORK_ACCEPTANCE_ENABLED", "stroyka-work-acceptance", "приёмки работ"),
    ):
        mode = flags.get(key)
        if mode is None:
            continue
        if mode not in {"0", "1"}:
            raise ValueError(f"Некорректный режим {label} в сборке")
        metadata = FeatureBuildMetadata(metadata_name)
        metadata.feed((build_dir / "index.html").read_text(encoding="utf-8"))
        if metadata.values != [mode]:
            raise ValueError(f"Frontend собран с другим режимом {label}")
    work_enabled = flags.get("REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED") == "1"
    acceptance_enabled = flags.get("REACT_APP_WORK_ACCEPTANCE_ENABLED") == "1"
    warehouse_enabled = (
        flags.get("REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED") == "true"
    )
    capability_enabled = (
        flags.get("REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED")
        == "true"
    )
    intercompany_enabled = (
        flags.get("REACT_APP_INTERCOMPANY_WAREHOUSE_TRANSFERS_ENABLED")
        == "true"
    )
    if not warehouse_enabled and not capability_enabled and not intercompany_enabled and not work_enabled and not acceptance_enabled:
        return

    manifest = json.loads(
        (build_dir / "asset-manifest.json").read_text(encoding="utf-8")
    )
    javascript = []
    for relative_path in manifest.get("files", {}).values():
        if isinstance(relative_path, str) and relative_path.endswith(".js"):
            path = build_dir / relative_path.lstrip("/")
            if path.is_file():
                javascript.append(path.read_text(encoding="utf-8"))
    bundle = "\n".join(javascript)

    if work_enabled:
        missing = [marker for marker in ("materialAccountingVersion", "stroyka:work-material-batch:v2:")
                   if marker not in bundle]
        if missing:
            raise ValueError("Frontend собран без безопасной отправки работ: " + ", ".join(missing))

    if acceptance_enabled and any(marker not in bundle for marker in ("/acceptance", "/resubmit")):
        raise ValueError("Frontend собран без новой приёмки работ")

    if warehouse_enabled:
        if (
            flags.get("REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED")
            != "true"
        ):
            raise ValueError(
                "Распределение склада включено без двухэтапных перемещений"
            )
        missing = [
            marker
            for marker in ("warehouse-distributions", "/transfers", "two-stage-v1")
            if marker not in bundle
        ]
        if missing:
            raise ValueError(
                "Frontend собран без включённого складского маршрута: "
                + ", ".join(missing)
            )

    if capability_enabled:
        missing = [
            marker
            for marker in (
                "material-capability-proof",
                "material-capability-confirmations",
                "supplier-material-capability-confirmations",
            )
            if marker not in bundle
        ]
        if missing:
            raise ValueError(
                "Frontend собран без включённой проверки материалов: "
                + ", ".join(missing)
            )

    if intercompany_enabled:
        if not warehouse_enabled:
            raise ValueError(
                "Межфирменные перемещения включены без складского рабочего пространства"
            )
        if "/intercompany-warehouse-transfers" not in bundle:
            raise ValueError(
                "Frontend собран без маршрута межфирменных перемещений"
            )


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]), sys.stdin.read())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
