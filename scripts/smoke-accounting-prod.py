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
        "name": "prod-api",
        "title": "Базовый production smoke и apiErrors",
        "command": ["bash", "scripts/prod-smoke-check.sh"],
        "requires_login": True,
    },
    {
        "name": "data-guard",
        "title": "Защита живого объекта, смет, сотрудников и пользователей",
        "command": ["python3", "scripts/smoke-data-guard.py"],
        "requires_login": False,
    },
    {
        "name": "supply-chain",
        "title": "Поставка -> приход -> накладная -> история снабжения",
        "command": ["python3", "scripts/smoke-supply-chain.py"],
        "requires_login": True,
    },
    {
        "name": "work-doc-chain",
        "title": "ЖПР -> акт исполнителя -> оплата -> платеж объекта",
        "command": ["python3", "scripts/smoke-work-doc-chain.py"],
        "requires_login": True,
    },
    {
        "name": "own-expense",
        "title": "Мои траты -> расходы объекта -> возмещение",
        "command": ["python3", "scripts/smoke-own-expense-chain.py"],
        "requires_login": True,
    },
    {
        "name": "password-reset",
        "title": "Восстановление пароля",
        "command": ["python3", "scripts/smoke-password-reset.py"],
        "requires_login": False,
    },
    {
        "name": "telegram-expense",
        "title": "Telegram трата -> мои траты -> расходы объекта",
        "command": ["python3", "scripts/smoke-telegram-own-expense.py"],
        "requires_login": False,
        "enabled_env": "SMOKE_TELEGRAM_BOT_TOKEN",
        "skip": "SMOKE_TELEGRAM_BOT_TOKEN не задан",
    },
]


def has_login_env():
    return bool(os.getenv("SMOKE_EMAIL") and os.getenv("SMOKE_PASSWORD"))


def preflight_login():
    if not has_login_env():
        raise SystemExit("Нужно задать SMOKE_EMAIL и SMOKE_PASSWORD")
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
            "Preflight login не прошел, бухгалтерские/prod цепочки не запускаю, "
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
    preflight_login()
    results = []
    skipped = []
    for step in STEPS:
        enabled_env = step.get("enabled_env")
        if enabled_env and not os.getenv(enabled_env):
            skipped.append({"name": step["name"], "reason": step.get("skip") or f"{enabled_env} не задан"})
            print(f"SKIP {step['name']}: {skipped[-1]['reason']}", flush=True)
            continue
        results.append(run_step(step))

    failed = [item for item in results if item["status"] != "ok"]
    summary = {
        "ok": not failed,
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "skipped": skipped,
        "results": results,
    }
    print("\n=== accounting-prod summary ===")
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
        print("FAIL smoke:accounting-prod:", exc, file=sys.stderr)
        raise SystemExit(1)
