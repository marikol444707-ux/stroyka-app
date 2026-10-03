"""Offline #275 image smoke: use installed 47943c2 code, never runtime patches.

Run in stroyka-jev:47943c2 with --network none, no secret env-file and only
this script plus the immutable original probe mounted read-only. Reuse only
its local fixture and child_probe; never call its copying/patching launcher.
This does not test a model, service lifecycle, new child targets or Stroyka QA.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

BASE_HASH = "4299cc3ccbac19a24bed67b8cc1a5269fa3e9a788db0936c40e235fab4689d31"
DAEMON_HASH = "c91b78c5bf6bd8858721bc6f834104666f0191965ae2946b01c832af004aca46"
GUARD_BLOB = "e9a3d6ca0af0457e92690afaac61319c236dc011"
BASE_PATH = Path("/app/cdp-probe-base.py")


def passed(result: dict) -> bool:
    return (
        all(result.get(key) is True for key in
            ("opened", "clicked", "guard_blocked", "native_image_files_verified"))
        and type(result.get("out_of_scope_requests_received")) is int
        and result["out_of_scope_requests_received"] == 0
        and result.get("child_exit") == 0
        and not any(result.get(key) for key in
                    ("error", "cleanup_error", "guard_error"))
    )


def unit_tests() -> None:
    good = {"opened": True, "clicked": True, "guard_blocked": True,
            "native_image_files_verified": True, "child_exit": 0,
            "out_of_scope_requests_received": 0}
    assert passed(good)
    for key in ("opened", "clicked", "guard_blocked", "native_image_files_verified"):
        assert not passed({**good, key: False})
        assert not passed({k: v for k, v in good.items() if k != key})
    for key, value in (("out_of_scope_requests_received", 1),
                       ("out_of_scope_requests_received", False),
                       ("child_exit", 2), ("error", "timeout"),
                       ("cleanup_error", "close failed"), ("guard_error", "failed")):
        assert not passed({**good, key: value})
    print("INSTALLED_IMAGE_PROBE_UNIT_TESTS_OK", flush=True)


def verify_installed_files() -> None:
    dist = importlib.metadata.distribution("browser-harness")
    if dist.version != "0.1.13":
        raise ValueError("Unexpected installed browser-harness version")
    raw = Path(dist.locate_file("browser_harness/daemon.py")).read_bytes()
    if hashlib.sha256(raw).hexdigest() != DAEMON_HASH:
        raise ValueError("Installed daemon is not the pinned build-time output")
    raw = Path("/app/dev_control/browser_worker/network_guard.py").read_bytes()
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != GUARD_BLOB:
        raise ValueError("Unexpected installed network guard")


def load_base():
    if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() != BASE_HASH:
        raise ValueError("Original probe checksum mismatch")
    spec = importlib.util.spec_from_file_location("original_probe", BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_native(base, root: Path) -> dict:
    allowed, _ = base.fixture()
    denied, denied_handler = base.fixture()
    chrome = None
    report = {"ok": False, "scope": "installed_image_local_browser",
              "image_revision": "47943c2", "model_calls": 0,
              "runtime_patch_applied": False, "temporary_package_copy": False}
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(root),
           "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "/app",
           "BH_HOME": str(root / "harness"), "BU_NAME": "default"}
    url = f"http://127.0.0.1:{allowed.server_port}/probe"
    blocked = f"http://127.0.0.1:{denied.server_port}/must-not-be-requested"
    try:
        profile = root / "chrome"
        with (root / "chrome.log").open("wb") as log:
            chrome = subprocess.Popen([
                "google-chrome-stable", "--headless=new", "--disable-background-networking",
                "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                f"--user-data-dir={profile}", "about:blank"
            ], env=env, stdout=log, stderr=log)
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not active.exists():
            if chrome.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("Dedicated Chrome did not start")
            time.sleep(.1)
        port = int(active.read_text().splitlines()[0])
        env.update(BU_CDP_URL=f"http://127.0.0.1:{port}", QA_BASE_URL=url)
        completed = subprocess.run(
            [sys.executable, str(BASE_PATH), "--child", url, blocked],
            env=env, capture_output=True, text=True, timeout=22,
        )
        rows = [line[len("PROBE_RESULT "):] for line in completed.stdout.splitlines()
                if line.startswith("PROBE_RESULT ")]
        if len(rows) != 1:
            raise RuntimeError("Expected exactly one browser result")
        result = json.loads(rows[0])
        if not isinstance(result, dict):
            raise ValueError("Browser result must be an object")
        for key in ("opened", "clicked", "guard_blocked", "error", "cleanup_error", "guard_error"):
            if key in result:
                report[key] = result[key]
        report["child_exit"] = completed.returncode
        verify_installed_files()  # Read only; files must still match after the run.
        report["native_image_files_verified"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {str(exc)[:220]}"
    finally:
        if chrome is not None:
            try:
                chrome.terminate()
                try:
                    chrome.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    chrome.kill()
                    chrome.wait(timeout=2)
            except Exception as exc:
                report["cleanup_error"] = type(exc).__name__
        for server in (allowed, denied):
            server.shutdown()
            server.server_close()
        report["out_of_scope_requests_received"] = denied_handler.hits
    report["ok"] = passed(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", action="store_true")
    args = parser.parse_args()
    unit_tests()
    if args.unit:
        return 0
    # No secrets are needed or permitted even accidentally in this test process.
    if any(os.environ.get(k) for k in
           ("TIMEWEB_AI_API_KEY", "DEV_CONTROL_API_TOKEN", "QA_SESSION_COOKIE_VALUE",
            "TYPESAFE_API_KEY", "TEXT_MODEL_API_KEY")):
        raise ValueError("Run the offline probe without secret environment variables")
    verify_installed_files()
    base = load_base()
    print("START: installed image; no runtime fixes; no model", flush=True)
    with tempfile.TemporaryDirectory(prefix="jev-native-275-") as tmp:
        report = run_native(base, Path(tmp))
    print(json.dumps(report, ensure_ascii=False), flush=True)
    print("INSTALLED_IMAGE_BROWSER_CHECKS_PASSED" if report["ok"]
          else "INSTALLED_IMAGE_BROWSER_CHECKS_NOT_PASSED", flush=True)
    print("NOT_A_JEV_MODEL_OR_STROYKA_QA_TEST", flush=True)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "phase": "preflight_or_cleanup",
                          "error": f"{type(exc).__name__}: {str(exc)[:220]}"}), flush=True)
        raise SystemExit(2)
