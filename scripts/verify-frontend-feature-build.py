#!/usr/bin/env python3
"""Fail a release when an enabled warehouse UI was removed from its build."""
import json
import sys
from pathlib import Path


def verify(build_dir: Path, build_environment: str) -> None:
    flags = dict(
        line.split("=", 1)
        for line in build_environment.splitlines()
        if "=" in line
    )
    warehouse_enabled = (
        flags.get("REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED") == "true"
    )
    capability_enabled = (
        flags.get("REACT_APP_SUPPLIER_MATERIAL_CAPABILITY_RUNTIME_ENABLED")
        == "true"
    )
    if not warehouse_enabled and not capability_enabled:
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


if __name__ == "__main__":
    try:
        verify(Path(sys.argv[1]), sys.stdin.read())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
