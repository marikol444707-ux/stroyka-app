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
    if len(result.stdout) > 100_000:
        return None
    # systemctl is-active/is-enabled return nonzero for healthy inactive/
    # disabled states. Preserve their exact stdout without masking errors
    # for Docker commands or treating arbitrary output as a valid state.
    if result.returncode != 0 and not (
        len(args) == 3
        and args[:2] in (["systemctl", "is-active"], ["systemctl", "is-enabled"])
        and args[2] in {"stroyka-jev-watch.timer", "stroyka-jev-watch.service"}
    ):
        return None
    return result.stdout.strip() or None


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
        "network_mode": ".HostConfig.NetworkMode",
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

    # EVERY running container may own the watcher port, not just stroyka-*.
    # Keep detailed reporting restricted to the recognized QA containers.
    raw_container_names = [n for n in raw_names.splitlines() if n]
    if any(not SAFE_CONTAINER.fullmatch(n) for n in raw_container_names):
        blockers.append("UNINSPECTABLE_CONTAINER_NAME")
    names = sorted(set(n for n in raw_container_names if SAFE_CONTAINER.fullmatch(n)))
    all_containers: dict[str, dict] = {}
    for name in names:
        details = _inspect(name, command)
        if details is None:
            blockers.append("DOCKER_INSPECT_FAILED")
            continue
        all_containers[name] = details
    containers = {
        name: details for name, details in all_containers.items()
        if name.startswith("stroyka-")
        and ("jev" in name or name in NEEDED_QA or name == "stroyka-qa-db")
    }

    for name in NEEDED_QA:
        if (containers.get(name) or {}).get("state") != "running":
            blockers.append("QA_COMPONENT_NOT_RUNNING:" + name)

    active_jev = sorted(n for n, d in containers.items()
                        if "jev" in n and d.get("state") == "running")
    if len(active_jev) > 1:
        blockers.append("MULTIPLE_ACTIVE_JEV_WORKERS")
    if EXPECTED_WORKER not in active_jev:
        blockers.append("EXPECTED_JEV_WORKER_NOT_RUNNING")

    # Stopped containers do not own active host TCP listeners.
    owners = _host_port_owners({n: d for n, d in all_containers.items()
                                if d.get("state") == "running"})
    watcher_owners = owners.get(WATCH_PORT, [])
    # Host-network containers have no PortBindings; no read-only inventory
    # can establish whether they listen on 18088. Fail closed.
    if any(d.get("state") == "running" and d.get("network_mode") == "host"
           for d in all_containers.values()):
        blockers.append("HOST_NETWORK_PORT_18088_UNVERIFIED")
    if watcher_owners != [EXPECTED_WORKER]:
        blockers.append("WATCH_PORT_18088_NOT_OWNED_BY_EXPECTED_WORKER")

    for name, details in containers.items():
        if details.get("privileged") is True:
            blockers.append("PRIVILEGED_CONTAINER:" + name)
        opts = details.get("security") or []
        if any("unconfined" in str(opt).lower() for opt in opts):
            blockers.append("UNCONFINED_CONTAINER_SECURITY:" + name)
        # Jev exposes screenshots/session evidence. Never publish its HTTP API
        # on a host-wide interface, even if access currently needs a token.
        if "jev" in name and details.get("state") == "running":
            for bindings in (details.get("ports") or {}).values():
                if not isinstance(bindings, list):
                    continue
                for bind in bindings:
                    if isinstance(bind, dict) and bind.get("HostIp") not in {"127.0.0.1", "::1"}:
                        blockers.append("JEV_WORKER_NOT_LOOPBACK_ONLY:" + name)

    service_active = command(["systemctl", "is-active", "stroyka-jev-watch.service"])
    service_enabled = command(["systemctl", "is-enabled", "stroyka-jev-watch.service"])
    if service_active == "active":
        blockers.append("WATCHER_SERVICE_ACTIVE_BEFORE_ACCEPTANCE")
    if service_enabled == "enabled":
        blockers.append("WATCHER_SERVICE_ENABLED_BEFORE_ACCEPTANCE")
    if service_active not in {"active", "inactive", "failed"}:
        blockers.append("WATCHER_SERVICE_STATE_UNKNOWN")
    if service_enabled not in {"enabled", "disabled", "static"}:
        blockers.append("WATCHER_SERVICE_ENABLE_STATE_UNKNOWN")

    timer_active = command(["systemctl", "is-active", "stroyka-jev-watch.timer"])
    timer_enabled = command(["systemctl", "is-enabled", "stroyka-jev-watch.timer"])
    # Until #345 (write-on-GET) and #346 (unverified auth bootstrap) are
    # resolved, ANY active/enabled watcher timer is unsafe, even on the
    # expected port. Read-only preflight must never change timer state.
    if timer_active == "active":
        blockers.append("WATCHER_TIMER_ACTIVE_BEFORE_ACCEPTANCE")
    if timer_enabled == "enabled":
        blockers.append("WATCHER_TIMER_ENABLED_BEFORE_ACCEPTANCE")
    if timer_active not in {"active", "inactive", "failed"}:
        blockers.append("WATCHER_TIMER_STATE_UNKNOWN")
    if timer_enabled not in {"enabled", "disabled", "static"}:
        blockers.append("WATCHER_TIMER_ENABLE_STATE_UNKNOWN")
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
        "watcher_service": {
            "active": service_active if service_active in {"active", "inactive", "failed"} else "unknown",
            "enabled": service_enabled if service_enabled in {"enabled", "disabled", "static"} else "unknown",
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
