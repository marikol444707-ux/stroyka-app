#!/usr/bin/env python3
"""Generate a ONE-TIME QA seccomp diagnostic profile, NOT a deployment policy.

Starts from a specific SHA-verified upstream Moby default seccomp profile.
By default adds exactly two unshare(2) flag combinations already proven
under a disposable seccomp-unconfined test. An explicit opt-in adds a
single narrowly masked clone(2) CLONE_NEWUSER-only namespace diagnostic.
Neither mode is a deployed Chrome sandbox policy. clone3(), setns(),
socket(), and other baseline restrictions are not relaxed.

Only generate as part of a human-reviewed, read-only QA host probe.
Do not configure this for production, Docker daemon defaults, or the running
Jev worker. No Docker, SSH or host configuration actions occur here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen

PINNED_SOURCE = (
    "https://raw.githubusercontent.com/moby/profiles/refs/tags/"
    "seccomp/v0.2.1/seccomp/default.json"
)
PINNED_GIT_BLOB_SHA1 = "ea5a494afb8d64898fa0f4f47ae0c4f5ba9cbbc9"
MAX_SOURCE_BYTES = 65536
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000
# Only the two tested flag sets, not arbitrary namespace combinations.
ALLOWED_UNSHARE_FLAGS = (CLONE_NEWUSER, CLONE_NEWUSER | CLONE_NEWPID)
# Upstream default clone(2) restriction for all Linux NEW* namespace bits.
CLONE_NAMESPACE_MASK = 0x7E020000


def verified_source(raw: bytes) -> dict:
    """Refuse updates or altered upstream content unless reviewed and repinned."""
    header = ("blob " + str(len(raw)) + "\0").encode("ascii")
    actual = hashlib.sha1(header + raw).hexdigest()
    if actual != PINNED_GIT_BLOB_SHA1:
        raise ValueError("upstream seccomp source blob SHA does not match pinned review")
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("invalid upstream seccomp JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("upstream seccomp profile must be an object")
    return data


def make_probe_profile(data: dict, *, clone_userns_probe: bool = False) -> dict:
    """Copy the default policy and add only explicitly requested QA exceptions."""
    if data.get("defaultAction") != "SCMP_ACT_ERRNO" or data.get("defaultErrnoRet") != 1:
        raise ValueError("upstream seccomp must be deny-by-default")
    rules = data.get("syscalls")
    if not isinstance(rules, list) or not rules:
        raise ValueError("upstream seccomp allowlist is missing")
    if not any(
        "unshare" in entry.get("names", [])
        and entry.get("includes", {}).get("caps") == ["CAP_SYS_ADMIN"]
        and entry.get("action") == "SCMP_ACT_ALLOW"
        for entry in rules
    ):
        raise ValueError("upstream CAP_SYS_ADMIN unshare rule changed")
    if not any(
        entry.get("names") == ["clone3"]
        and entry.get("action") == "SCMP_ACT_ERRNO"
        for entry in rules
    ):
        raise ValueError("upstream clone3 fallback restriction changed")
    for entry in rules:
        if "unshare" in entry.get("names", []) and (
            entry.get("action") == "SCMP_ACT_ALLOW" and
            not entry.get("args") and not entry.get("includes")
        ):
            raise ValueError("unrestricted unshare rule exists upstream")
    changed = json.loads(json.dumps(data))
    for flags in ALLOWED_UNSHARE_FLAGS:
        changed["syscalls"].append({
            "names": ["unshare"],
            "action": "SCMP_ACT_ALLOW",
            "args": [{"index": 0, "value": flags, "op": "SCMP_CMP_EQ"}],
        })
    if clone_userns_probe:
        # Chromium probes clone(CLONE_NEWUSER). Allow *only* NEWUSER
        # in the namespace-bit mask, without opening NEWNET, NEWPID,
        # NEWNS, NEWUTS, NEWIPC, or NEWCGROUP clone flag combinations.
        changed["syscalls"].append({
            "names": ["clone"],
            "action": "SCMP_ACT_ALLOW",
            "args": [{
                "index": 0,
                "value": CLONE_NAMESPACE_MASK,
                "valueTwo": CLONE_NEWUSER,
                "op": "SCMP_CMP_MASKED_EQ",
            }],
        })
    return changed


def create_profile(destination: Path, *, clone_userns_probe: bool = False) -> Path:
    with urlopen(PINNED_SOURCE, timeout=15) as response:
        raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("upstream seccomp source too large")
    content = make_probe_profile(
        verified_source(raw), clone_userns_probe=clone_userns_probe
    )
    payload = (json.dumps(content, indent=2) + "\n").encode("utf-8")
    # Root could run this for a disposable QA test: never follow symlinks or
    # overwrite an existing profile that may already have been reviewed.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a pinned, disposable unshare QA probe seccomp profile")
    parser.add_argument("--output", required=True, type=Path, help="New path (must not exist)")
    parser.add_argument(
        "--clone-userns-probe", action="store_true",
        help="Add precisely masked clone(CLONE_NEWUSER) diagnostic; NOT for deployment",
    )
    args = parser.parse_args()
    path = create_profile(args.output, clone_userns_probe=args.clone_userns_probe)
    print("Created one-time diagnostic seccomp profile: " + str(path))
    print("No Docker runtime configuration or containers were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
