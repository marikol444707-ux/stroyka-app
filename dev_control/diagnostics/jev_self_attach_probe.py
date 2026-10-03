"""Offline candidate for #275: preserve target routing and ignore registered sessions.

Diagnostic only. Reuses the immutable baseline probe; runs exactly one candidate
inside a disposable --network none container without keys or published ports.
Only a temporary daemon copy and one in-memory handler are changed. Never edits
installed packages, the base image, main, or PR #244. Not a Jev/model success.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace

BASE_HASH = "4299cc3ccbac19a24bed67b8cc1a5269fa3e9a788db0936c40e235fab4689d31"
GUARD_BLOB = "e9156cd0e3f1dff5487ea02ab7394047a53ea7e2"


def idempotent_handler(original, counts):
    def handle(self, params):
        sid = params.get("sessionId")
        if sid and sid in self._guarded_sessions:
            counts["ignored_registered_sessions"] += 1
            return None
        counts["delegated_new_sessions"] += 1
        return original(self, params)
    return handle


def passed(result):
    return (
        all(result.get(name) is True for name in ("opened", "clicked", "guard_blocked"))
        and result.get("out_of_scope_requests_received") == 0
        and result.get("ignored_registered_sessions", 0) >= 1
        and not any(result.get(name) for name in ("error", "cleanup_error", "guard_error"))
    )


def unit_tests():
    calls = []
    counts = {"ignored_registered_sessions": 0, "delegated_new_sessions": 0}
    guard = SimpleNamespace(_guarded_sessions={"root", "already-guarded"})
    def original(self, params):
        calls.append(dict(params))
        sid = params.get("sessionId")
        if sid:
            self._guarded_sessions.add(sid)
        return "original-return"
    handle = idempotent_handler(original, counts)
    assert handle(guard, {"sessionId": "root"}) is None
    assert handle(guard, {"sessionId": "already-guarded"}) is None
    assert calls == []
    assert handle(guard, {"sessionId": "new-child"}) == "original-return"
    assert handle(guard, {"sessionId": "new-child"}) is None
    assert handle(guard, {}) == "original-return"
    assert calls == [{"sessionId": "new-child"}, {}]
    assert counts == {"ignored_registered_sessions": 3, "delegated_new_sessions": 2}
    good = {"opened": True, "clicked": True, "guard_blocked": True,
            "out_of_scope_requests_received": 0, "ignored_registered_sessions": 1}
    assert passed(good)
    for name in ("opened", "clicked", "guard_blocked"):
        assert not passed({**good, name: False})
    assert not passed({**good, "out_of_scope_requests_received": 1})
    assert not passed({**good, "ignored_registered_sessions": 0})
    assert not passed({**good, "error": "navigation timeout"})
    print("SELF_ATTACH_UNIT_TESTS_OK", flush=True)


def load_base():
    path = Path("/app/cdp-probe-base.py")
    if hashlib.sha256(path.read_bytes()).hexdigest() != BASE_HASH:
        raise ValueError("Original probe checksum mismatch; stop")
    spec = importlib.util.spec_from_file_location("base_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(Path(__file__).resolve())
    return module


def child(base, urls):
    from browser_harness import daemon as installed_daemon
    from dev_control.browser_worker import network_guard
    # Importing the module does not start the daemon. Verify the temporary route
    # before using it; the launcher starts the daemon with this same PYTHONPATH.
    daemon_source = Path(installed_daemon.__file__).read_text()
    if daemon_source.count(base.NEW_ROUTE) != 1:
        raise ValueError("Candidate routing patch is not loaded; stop")
    raw = Path(network_guard.__file__).read_bytes()
    blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
    if hashlib.sha1(blob).hexdigest() != GUARD_BLOB:
        raise ValueError("Unexpected network_guard revision; stop")
    counts = {"ignored_registered_sessions": 0, "delegated_new_sessions": 0}
    original = network_guard.NetworkBoundary._handle_attached_target
    network_guard.NetworkBoundary._handle_attached_target = idempotent_handler(original, counts)
    buffer = StringIO()
    try:
        with redirect_stdout(buffer):
            base.child_probe(*urls)
    finally:
        network_guard.NetworkBoundary._handle_attached_target = original
    lines = [line.removeprefix("PROBE_RESULT ") for line in buffer.getvalue().splitlines()
             if line.startswith("PROBE_RESULT ")]
    if not lines:
        raise RuntimeError("Browser probe produced no report")
    report = json.loads(lines[-1])
    report.update(counts)
    report["candidate_route_verified"] = True
    print("PROBE_RESULT " + json.dumps(report), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", action="store_true")
    parser.add_argument("--child", nargs=2)
    args = parser.parse_args()
    if args.unit:
        unit_tests()
        return 0
    base = load_base()
    if args.child:
        return child(base, args.child)
    unit_tests()
    base.routing_tests()
    if importlib.metadata.version("browser-harness") != "0.1.13":
        raise SystemExit("Expected browser-harness 0.1.13; stop")
    spec = importlib.util.find_spec("browser_harness")
    package = Path(next(iter(spec.submodule_search_locations)))
    base.patch_source((package / "daemon.py").read_text())
    with tempfile.TemporaryDirectory(prefix="jev-self-attach-275-") as tmp:
        print("START: routing + registered-session check; no model", flush=True)
        result = base.case("candidate", Path(tmp), package)
        print(json.dumps(result), flush=True)
    ok = passed(result)
    print("CANDIDATE_BROWSER_CHECKS_PASSED" if ok else "CANDIDATE_NOT_PASSED", flush=True)
    print("NOT_A_JEV_MODEL_TEST", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
