#!/usr/bin/env python3
"""Run the read-only supplier history schema report with the app DB config."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import config  # noqa: E402

config.load_env_file()

from backend.db import DB_CONFIG  # noqa: E402


def escape_pgpass_field(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace(":", "\\:")


def main() -> int:
    psql = shutil.which("psql")
    if not psql:
        print("Не найден psql. Установите клиент PostgreSQL и повторите запуск.", file=sys.stderr)
        return 2

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
    pgpass_line = ":".join(
        escape_pgpass_field(DB_CONFIG[key])
        for key in ("host", "port", "dbname", "user", "password")
    )
    descriptor, pgpass_path = tempfile.mkstemp(prefix="stroyka-history-audit-pgpass-")
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as pgpass:
            pgpass.write(pgpass_line + "\n")
        env = os.environ.copy()
        env.pop("PGPASSWORD", None)
        env["PGPASSFILE"] = pgpass_path
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
    except OSError as exc:
        print(f"Не удалось запустить отчёт: {exc}", file=sys.stderr)
        return 2
    finally:
        try:
            os.unlink(pgpass_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
