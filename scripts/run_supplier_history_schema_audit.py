#!/usr/bin/env python3
"""Run the read-only supplier history schema report with the app DB config."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402

config.load_env_file()

from backend.db import DB_CONFIG  # noqa: E402


def main() -> int:
    psql = shutil.which("psql")
    if not psql:
        print("Не найден psql. Установите клиент PostgreSQL и повторите запуск.", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env["PGPASSWORD"] = str(DB_CONFIG["password"])
    command = [
        psql,
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        str(DB_CONFIG["host"]),
        "-p",
        str(DB_CONFIG["port"]),
        "-U",
        str(DB_CONFIG["user"]),
        "-d",
        str(DB_CONFIG["dbname"]),
        "-f",
        str(ROOT / "scripts" / "audit_supplier_history_merge_schema.sql"),
    ]
    try:
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
    except OSError as exc:
        print(f"Не удалось запустить отчёт: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
