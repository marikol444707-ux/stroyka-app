#!/usr/bin/env python3
"""Idempotently add the JEV intake and CRM review routes to the Nginx site."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROUTES = (
    (
        re.compile(r"(?m)^\s*location\s*=\s*/internal/jev/job-candidates\s*\{"),
        (
            "location = /internal/jev/job-candidates {",
            "    limit_req zone=login_limit burst=5 nodelay;",
            "    client_max_body_size 1m;",
            "    proxy_connect_timeout 6s;",
            "    proxy_send_timeout 10s;",
            "    proxy_read_timeout 30s;",
            "    proxy_pass http://127.0.0.1:8001;",
            "    proxy_set_header Host $host;",
            "    proxy_set_header X-Real-IP $remote_addr;",
            "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "    proxy_set_header X-Forwarded-Proto $scheme;",
            "}",
        ),
    ),
    (
        re.compile(r"(?m)^\s*location\s*=\s*/crm/job-candidates\s*\{"),
        (
            "location = /crm/job-candidates {",
            "    limit_req zone=login_limit burst=30 nodelay;",
            "    client_max_body_size 5m;",
            "    proxy_pass http://127.0.0.1:8001;",
            "    proxy_set_header Host $host;",
            "    proxy_set_header X-Real-IP $remote_addr;",
            "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "    proxy_set_header X-Forwarded-Proto $scheme;",
            "}",
        ),
    ),
    (
        re.compile(r"(?m)^\s*location\s+\^~\s+/crm/job-candidates/\s*\{"),
        (
            "location ^~ /crm/job-candidates/ {",
            "    limit_req zone=login_limit burst=30 nodelay;",
            "    client_max_body_size 5m;",
            "    proxy_pass http://127.0.0.1:8001;",
            "    proxy_set_header Host $host;",
            "    proxy_set_header X-Real-IP $remote_addr;",
            "    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "    proxy_set_header X-Forwarded-Proto $scheme;",
            "}",
        ),
    ),
)
INSERT_MARKER = re.compile(r"(?m)^(?P<indent>[ \t]*)location\s*=\s*/site/pricing\s*\{")


def ensure_job_candidates_routes(text: str) -> tuple[str, list[str]]:
    missing = [lines for pattern, lines in ROUTES if pattern.search(text) is None]
    if not missing:
        return text, []

    marker = INSERT_MARKER.search(text)
    if marker is None:
        raise ValueError(
            "Не найден блок 'location = /site/pricing'. Конфиг не изменен; "
            "проверьте активный server block вручную."
        )

    indent = marker.group("indent")
    block = "\n\n".join(
        "\n".join(f"{indent}{line}" for line in lines) for lines in missing
    ) + "\n\n"
    return text[: marker.start()] + block + text[marker.start() :], [lines[0] for lines in missing]


def default_backup_dir(target: Path) -> Path:
    if target.parent.name in {"sites-enabled", "conf.d"}:
        return target.parent.parent / "backups"
    return target.parent / "backups"


def update_file(target: Path, backup_dir: Path | None = None) -> tuple[Path | None, list[str]]:
    original = target.read_text(encoding="utf-8")
    updated, added = ensure_job_candidates_routes(original)
    if not added:
        return None, []

    destination = backup_dir or default_backup_dir(target)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = destination / f"{target.name}.before-job-candidates.{stamp}"
    shutil.copy2(target, backup)
    target.write_text(updated, encoding="utf-8")
    return backup, added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=Path("/etc/nginx/sites-enabled/stroyka"),
        help="Активный Nginx site config (по умолчанию /etc/nginx/sites-enabled/stroyka)",
    )
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()

    backup, added = update_file(args.config, args.backup_dir)
    if not added:
        print("Маршруты JEV/кандидатов заказов уже настроены; изменений нет.")
        return

    print("Добавлены маршруты: " + ", ".join(added))
    print(f"Резервная копия: {backup}")


if __name__ == "__main__":
    main()
