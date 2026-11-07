#!/usr/bin/env python3
"""Idempotently add the anonymous public-site analytics proxy route."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROUTE = (
    "location = /site/analytics/pageview {",
    "    limit_req zone=login_limit burst=60 nodelay;",
    "    client_max_body_size 2k;",
    "    proxy_connect_timeout 6s;",
    "    proxy_send_timeout 10s;",
    "    proxy_read_timeout 10s;",
    "    proxy_pass http://127.0.0.1:8001;",
    "    proxy_set_header Host $host;",
    "    proxy_set_header X-Real-IP $remote_addr;",
    "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "    proxy_set_header X-Forwarded-Proto $scheme;",
    "}",
)
TARGET = re.compile(r"(?m)^(?P<indent>[ \t]*)location\s*=\s*/site/analytics/pageview\s*\{")
MARKER = re.compile(r"(?m)^(?P<indent>[ \t]*)location\s*=\s*/site/pricing\s*\{")


def ensure_route(text: str) -> tuple[str, bool]:
    matches = list(TARGET.finditer(text))
    if len(matches) > 1:
        raise ValueError("Найдено несколько location для pageview; конфиг не менял")
    if matches:
        remainder = text[matches[0].end():]
        close = re.search(rf"(?m)^{re.escape(matches[0].group('indent'))}}}[ \t]*$", remainder)
        if close is None:
            raise ValueError("Не удалось проверить существующий location; конфиг не менял")
        existing = tuple(line.strip() for line in text[matches[0].start():matches[0].end() + close.end()].splitlines() if line.strip())
        if existing != ROUTE:
            raise ValueError("Location pageview отличается от ожидаемого; проверь конфиг вручную")
        return text, False
    marker = MARKER.search(text)
    if marker is None:
        raise ValueError("Не найден location /site/pricing; конфиг не менял")
    block = "\n".join(f"{marker.group('indent')}{line}" for line in ROUTE) + "\n\n"
    return text[:marker.start()] + block + text[marker.start():], True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    original = args.config.read_text(encoding="utf-8")
    updated, changed = ensure_route(original)
    if not changed:
        print("Nginx pageview route already matches.")
        return
    backup_dir = args.config.parent.parent / "backups"
    if args.config.parent.name not in {"sites-enabled", "conf.d"}:
        backup_dir = args.config.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = backup_dir / f"{args.config.name}.before-pageview.{stamp}"
    shutil.copy2(args.config, backup)
    args.config.write_text(updated, encoding="utf-8")
    print(f"Добавлен маршрут pageview. Резервная копия: {backup}")


if __name__ == "__main__":
    main()
