#!/usr/bin/env python3
"""Read-only inventory of the dedicated Stroyka QA VPS.

Never starts/stops containers, calls worker HTTP APIs, opens secrets or reads
container environments. Run from an account allowed to inspect Docker.
The result is a *preflight*, never an acceptance/authorization to deploy.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Callable

WATCH_PORT = 18088
EXPECTED_WORKER = "stroyka-jev-qa"
NEEDED_QA = ("stroyka-qa-backend", "stroyka-qa-gateway")
SAFE_CONTAINER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def _command(args: list[str]) -> str | None:
    """Do not surface stderr: Docker errors may include sensitive host metadata."""
    try:
        result = subprocess.run(
            args, check=False, text=True, capture_output=True, timeout=8,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or len(result.stdout) > 100_000:
        return None
    return result.stdout.strip()


def _read_setting(path: str) -> str:
    try:
        return Path(path).read_text(encoding="ascii").strip()[:40]
    except (OSError, UnicodeError):
        return "unknown"


def _inspect(name: str, command: Callable[[list[str]], str | None]) -> dict | None:
    if not SAFE_CONTAINER.fullmatch(name):
        return None
    # Docker's Go template does not support arbitrary dict construction.
    # Read only explicitly allowlisted fields, never Config.Env or mounts.
    fields = {
        "state": ".State.Status",
        "user": ".Config.User",
        "ports": ".HostConfig.PortBindings",
        "privileged": ".HostConfig.Privileged",
        "security": ".HostConfig.SecurityOpt",
        "pid_mode": ".HostConfig.PidMode",
    }
    data = {}
    for key, field in fields.items():
        raw = command(["docker", "inspect", "--format", "{{json " + field + "}}", name])
        if raw is None:
            return None
        try:
            data[key] = json.loads(raw)
        except (ValueError, TypeError):
            return None
    return data


def _host_port_owners(containers: dict[str, dict]) -> dict[int, list[str]]:
    owners: dict[int, list[str]] = {}
    for name, details in containers.items():
        portmap = details.get("ports")
        if not isinstance(portmap, dict):
            continue
        for bindings in portmap.values():
            if not isinstance(bindings, list):
                continue
            for binding in bindings:
                if not isinstance(binding, dict):
                    continue
                try:
                    port = int(binding.get("HostPort"))
                except (ValueError, TypeError):
                    continue
                owners.setdefault(port, []).append(name)
    return owners


def inspect_host(command: Callable[[list[str]], str | None] = _command) -> dict:
    blockers: list[str] = []
    observations: list[str] = []
    raw_names = command(["docker", "ps", "-a", "--format", "{{.Names}}"])
    if raw_names is None:
        return {
            "status": "blocked",
            "blockers": ["DOCKER_INSPECTION_UNAVAILABLE"],
            "observations": ["No container changes attempted"],
            "containers": {},
            "sandbox": {},
            "verified": "inventory_only",
        }

    names = sorted(
        n for n in raw_names.splitlines()
        if SAFE_CONTAINER.fullmatch(n) and n.startswith("stroyka-")
        and ("jev" in n or n in NEEDED_QA or n == "stroyka-qa-db")
    )
    containers: dict[str, dict] = {}
    for name in names:
        details = _inspect(name, command)
        if details is None:
            blockers.append("DOCKER_INSPECT_FAILED")
            continue
        containers[name] = details

    for name in NEEDED_QA:
        if (containers.get(name) or {}).get("state") != "running":
            blockers.append("QA_COMPONENT_NOT_RUNNING:" + name)

    active_jev = sorted(n for n, d in containers.items()
                        if "jev" in n and d.get("state") == "running")
    if len(active_jev) > 1:
        blockers.append("MULTIPLE_ACTIVE_JEV_WORKERS")
    if EXPECTED_WORKER not in active_jev:
        blockers.append("EXPECTED_JEV_WORKER_NOT_RUNNING")

    # Stopped containers do not own active host TCP listeners.\n    owners = _host_port_owners({n: d for n, d in containers.items()\n                                if d.get("state") == "running"})
    watcher_owners = owners.get(WATCH_PORT, [])
    if watcher_owners != [EXPECTED_WORKER]:
        blockers.append("WATCH_PORT_18088_NOT_OWNED_BY_EXPECTED_WORKER")

    for name, details in containers.items():
        if details.get("privileged") is True:
            blockers.append("PRIVILEGED_CONTAINER:" + name)
        opts = details.get("security") or []
        if any("unconfined" in str(opt).lower() for opt in opts):
            observations.append("UNCONFINED_SECURITY_OPTION_REQUIRES_REVIEW:" + name)

    timer_active = command(["systemctl", "is-active", "stroyka-jev-watch.timer"])
    timer_enabled = command(["systemctl", "is-enabled", "stroyka-jev-watch.timer"])
    if timer_active == "active":
        observations.append("WATCHER_TIMER_ALREADY_ACTIVE")
    if timer_active == "active" and watcher_owners != [EXPECTED_WORKER]:
        blockers.append("ACTIVE_TIMER_WITH_WRONG_WATCHER_ENDPOINT")

    return {
        "status": "blocked" if blockers else "review_required",
        "blockers": sorted(set(blockers)),
        "observations": sorted(set(observations)),
        "containers": {
            name: {
                "state": details.get("state"),
                "user": details.get("user"),
                "privileged": details.get("privileged"),
                "pid_mode": details.get("pid_mode"),
                "security_options_review": bool(details.get("security")),
            }
            for name, details in containers.items()
        },
        "watch_port": {
            "port": WATCH_PORT, "owners": watcher_owners,
        },
        "watcher_timer": {
            "active": timer_active if timer_active in {"active", "inactive", "failed"} else "unknown",
            "enabled": timer_enabled if timer_enabled in {"enabled", "disabled", "static"} else "unknown",
        },
        "sandbox": {
            "unprivileged_userns_clone": _read_setting("/proc/sys/kernel/unprivileged_userns_clone"),
            "max_user_namespaces": _read_setting("/proc/sys/user/max_user_namespaces"),
        },
        "verified": "inventory_only",
        "not_verified": [
            "QA session and exact target origin",
            "Chrome user-namespace sandbox inside this host container",
            "Signed watcher identity, authenticated smoke, tenant boundaries",
            "Image digest, secret safety, restart persistence and business verifier",
        ],
        "changes_made": False,
    }


if __name__ == "__main__":
    result = inspect_host()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(2 if result["status"] == "blocked" else 0)
