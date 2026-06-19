#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")

STEPS = [
    {
        "name": "data-guard",
        "title": "A: защита живого объекта, смет, сотрудников и пользователей",
        "command": ["python3", "scripts/smoke-data-guard.py"],
    },
    {
        "name": "estimate-norms",
        "title": "B/C: сметы и dry-run норм материалов",
        "command": ["python3", "scripts/smoke-estimate-norms.py"],
    },
    {
        "name": "work-roles",
        "title": "D/E: работы, ЖПР, АОСР, акты, роли и кабинеты",
        "command": ["python3", "scripts/smoke-work-roles.py"],
    },
    {
        "name": "accounting-prod",
        "title": "F/G: бухгалтерия и продакшен-готовность",
        "command": ["python3", "scripts/smoke-accounting-prod.py"],
    },
]


def require_env():
    missing = [name for name in ("SMOKE_EMAIL", "SMOKE_PASSWORD") if not os.getenv(name)]
    if missing:
        raise SystemExit("Нужно задать: " + ", ".join(missing))


def preflight_login():
    payload = json.dumps(
        {
            "email": os.getenv("SMOKE_EMAIL", ""),
            "password": os.getenv("SMOKE_PASSWORD", ""),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL + "/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise SystemExit(f"Preflight login не прошел: {exc}")

    if status != 200:
        raise SystemExit(
            "Preflight login не прошел, pre-prod прогон не запускаю, "
            f"чтобы не заблокировать аккаунт. HTTP {status}: {text[:300]}"
        )


def run_step(step):
    started = time.monotonic()
    print(f"\n=== {step['name']}: {step['title']} ===", flush=True)
    proc = subprocess.run(
        step["command"],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed = round(time.monotonic() - started, 2)
    output = proc.stdout or ""
    if output.strip():
        print(output.rstrip(), flush=True)
    status = "ok" if proc.returncode == 0 else "fail"
    print(f"--- {step['name']}: {status} за {elapsed}с ---", flush=True)
    return {
        "name": step["name"],
        "title": step["title"],
        "status": status,
        "returnCode": proc.returncode,
        "seconds": elapsed,
    }


def main():
    require_env()
    preflight_login()
    results = [run_step(step) for step in STEPS]
    failed = [row for row in results if row["status"] != "ok"]
    summary = {
        "ok": not failed,
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
    }
    print("\n=== preprod summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except Exception as exc:
        print("FAIL smoke:preprod:", exc, file=sys.stderr)
        raise SystemExit(1)
