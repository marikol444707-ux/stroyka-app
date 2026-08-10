#!/usr/bin/env python3
"""Idempotently add the capability-revocation proxy to active Nginx."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROUTE_LINES = (
    "location ^~ /supplier-material-capability-confirmations/ {",
    "    limit_req zone=login_limit burst=30 nodelay;",
    "    proxy_pass http://127.0.0.1:8001;",
    "    proxy_set_header Host $host;",
    "    proxy_set_header X-Real-IP $remote_addr;",
    "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "}",
)
CANONICAL_ROUTE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)location\s+\^~\s+"
    r"/supplier-material-capability-confirmations/\s*\{"
)
SAME_PATH_ROUTE = re.compile(
    r"(?m)^[ \t]*location\b[^\n]*"
    r"/supplier-material-capability-confirmations/"
)
PRICING_MARKER = re.compile(
    r"(?m)^(?P<indent>[ \t]*)location\s*=\s*/site/pricing\s*\{"
)


def _canonical_route_lines(text: str, match: re.Match) -> tuple[str, ...]:
    remainder = text[match.end() :]
    closing = re.search(
        rf"(?m)^{re.escape(match.group('indent'))}\}}[ \t]*$",
        remainder,
    )
    if closing is None:
        return ()
    block = text[match.start() : match.end() + closing.end()]
    return tuple(line.strip() for line in block.splitlines() if line.strip())


def ensure_material_capability_route(text: str) -> tuple[str, list[str]]:
    same_path = list(SAME_PATH_ROUTE.finditer(text))
    canonical_matches = list(CANONICAL_ROUTE.finditer(text))
    if len(same_path) > 1 or len(canonical_matches) > 1:
        raise ValueError(
            "Найдено несколько location для "
            "/supplier-material-capability-confirmations/. "
            "Конфиг не изменен: проверьте конфликт вручную."
        )

    canonical = canonical_matches[0] if canonical_matches else None
    if canonical is not None:
        expected = tuple(line.strip() for line in ROUTE_LINES)
        if _canonical_route_lines(text, canonical) == expected:
            return text, []
        raise ValueError(
            "Location /supplier-material-capability-confirmations/ "
            "отличается от контракта. Конфиг не изменен: "
            "проверьте drift вручную."
        )
    if same_path:
        raise ValueError(
            "Найден неканонический location для "
            "/supplier-material-capability-confirmations/. "
            "Конфиг не изменен: проверьте конфликт вручную."
        )

    marker = PRICING_MARKER.search(text)
    if marker is None:
        raise ValueError(
            "Не найден блок 'location = /site/pricing'. Конфиг не изменен: "
            "нужно проверить активный server block вручную."
        )

    indent = marker.group("indent")
    rendered = "\n".join(f"{indent}{line}" for line in ROUTE_LINES)
    block = rendered + "\n\n"
    updated = text[: marker.start()] + block + text[marker.start() :]
    return updated, [ROUTE_LINES[0]]


def default_backup_dir(target: Path) -> Path:
    if target.parent.name in {"sites-enabled", "conf.d"}:
        return target.parent.parent / "backups"
    return target.parent / "backups"


def update_file(
    target: Path,
    backup_dir: Path | None = None,
) -> tuple[Path | None, list[str]]:
    original = target.read_text(encoding="utf-8")
    updated, added = ensure_material_capability_route(original)
    if not added:
        return None, []

    destination = backup_dir or default_backup_dir(target)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = destination / (
        f"{target.name}.before-material-capability.{stamp}"
    )
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")
    return backup, added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path, help="Активный Nginx site config")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()

    backup, added = update_file(args.config, args.backup_dir)
    if not added:
        print("Маршрут capability revocation уже настроен; изменений нет.")
        return

    print("Добавлен маршрут: " + added[0])
    print(f"Резервная копия: {backup}")


if __name__ == "__main__":
    main()
