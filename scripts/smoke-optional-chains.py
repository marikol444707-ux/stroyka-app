#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time


OPTIONAL_STEPS = [
    {
        "name": "password-reset",
        "title": "Восстановление пароля",
        "command": ["npm", "run", "smoke:password-reset"],
        "enabled": lambda: True,
        "skip": "",
    },
    {
        "name": "telegram-expense",
        "title": "Telegram -> мои траты -> расходы объекта",
        "command": ["npm", "run", "smoke:telegram-expense"],
        "enabled": lambda: bool(os.getenv("SMOKE_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_API_TOKEN")),
        "skip": "SMOKE_TELEGRAM_BOT_TOKEN не задан",
    },
]


def run_step(step):
    print(f"\n=== {step['name']}: {step['title']} ===", flush=True)
    started = time.time()
    proc = subprocess.run(step["command"], env=os.environ.copy())
    elapsed = round(time.time() - started, 2)
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
    results = []
    skipped = []
    for step in OPTIONAL_STEPS:
        if not step["enabled"]():
            skipped.append({"name": step["name"], "reason": step["skip"]})
            print(f"SKIP {step['name']}: {step['skip']}", flush=True)
            continue
        results.append(run_step(step))

    failed = [item for item in results if item["status"] != "ok"]
    summary = {
        "ok": not failed,
        "passed": len([item for item in results if item["status"] == "ok"]),
        "failed": len(failed),
        "skipped": skipped,
        "results": results,
    }
    print("\n=== optional summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
