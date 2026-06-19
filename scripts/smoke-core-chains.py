#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_URL = os.getenv("BASE_URL", "https://stroyka26.pro").rstrip("/")


CHAIN_STEPS = [
    {
        "name": "prod-api",
        "title": "Базовый production smoke",
        "command": ["bash", "scripts/prod-smoke-check.sh"],
    },
    {
        "name": "data-guard",
        "title": "Защита живого объекта, смет, сотрудников и пользователей",
        "command": ["python3", "scripts/smoke-data-guard.py"],
    },
    {
        "name": "staff-access",
        "title": "Персонал -> системный доступ -> ограничения по объекту/пакету",
        "command": ["python3", "scripts/smoke-staff-access.py"],
    },
    {
        "name": "role-package",
        "title": "Роли -> видимость пакетов -> запрет чужого ЖПР",
        "command": ["python3", "scripts/smoke-role-package-access.py"],
    },
    {
        "name": "work-doc-chain",
        "title": "ЖПР -> АОСР -> акт исполнителя -> платеж объекта",
        "command": ["python3", "scripts/smoke-work-doc-chain.py"],
    },
    {
        "name": "supply-chain",
        "title": "Сметный материал -> заявка -> КП -> поставка -> приход",
        "command": ["python3", "scripts/smoke-supply-chain.py"],
    },
    {
        "name": "own-expense",
        "title": "Мои траты -> расходы объекта -> возмещение",
        "command": ["python3", "scripts/smoke-own-expense-chain.py"],
    },
]


OPTIONAL_STEPS = [
    {
        "name": "telegram-expense",
        "title": "Telegram трата -> мои траты -> расходы объекта",
        "command": ["python3", "scripts/smoke-telegram-own-expense.py"],
        "enabled_env": "SMOKE_TELEGRAM_BOT_TOKEN",
    },
    {
        "name": "password-reset",
        "title": "Восстановление пароля",
        "command": ["python3", "scripts/smoke-password-reset.py"],
        "enabled_env": "SMOKE_INCLUDE_PASSWORD_RESET",
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
            "Preflight login не прошел, цепочки не запускаю, чтобы не заблокировать аккаунт. "
            f"HTTP {status}: {text[:300]}"
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
    steps = list(CHAIN_STEPS)
    skipped = []
    for step in OPTIONAL_STEPS:
        env_name = step["enabled_env"]
        if os.getenv(env_name):
            steps.append(step)
        else:
            skipped.append({"name": step["name"], "reason": f"{env_name} не задан"})

    results = [run_step(step) for step in steps]
    failed = [row for row in results if row["status"] != "ok"]
    summary = {
        "ok": not failed,
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "skipped": skipped,
        "results": results,
    }
    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
