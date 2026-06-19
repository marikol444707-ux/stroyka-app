#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SMETA_DIR = Path.home() / "Desktop" / "Kislovodsk"


def run(command, env=None):
    proc = subprocess.run(
        command,
        cwd=ROOT,
        env={**os.environ, **(env or {})},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if proc.stdout.strip():
        print(proc.stdout.rstrip())
    return proc.returncode


def main():
    failures = []
    skipped = []

    smeta_target = Path(os.getenv("SMOKE_SMETA_DIR", str(DEFAULT_SMETA_DIR)))
    if smeta_target.exists():
        print("\n=== smeta-parser: XLSX импорт смет ===", flush=True)
        code = run(["python3", "scripts/check-smeta-parser.py", str(smeta_target)])
        if code:
            failures.append({"name": "smeta-parser", "returnCode": code})
    else:
        skipped.append({"name": "smeta-parser", "reason": f"файлы не найдены: {smeta_target}"})

    if os.getenv("SMOKE_EMAIL") and os.getenv("SMOKE_PASSWORD"):
        print("\n=== norms-dry-run: нормы материалов без записи ===", flush=True)
        code = run(["python3", "scripts/smoke-norms-dry-run.py"])
        if code:
            failures.append({"name": "norms-dry-run", "returnCode": code})
    else:
        skipped.append({"name": "norms-dry-run", "reason": "SMOKE_EMAIL/SMOKE_PASSWORD не заданы"})

    result = {
        "ok": not failures,
        "failed": failures,
        "skipped": skipped,
    }
    print("\n=== estimate-norms summary ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
