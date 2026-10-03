"""Offline trace for #275, not a fix. Requires the immutable original probe.

Temporary library copy only. Never runs Agent, calls a model, reads env files,
or changes the installed image. Use --network none and no secrets/mounts other
than these two read-only scripts. Records only CDP method names and routing IDs.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time

BASE_HASH = "4299cc3ccbac19a24bed67b8cc1a5269fa3e9a788db0936c40e235fab4689d31"
EVENT_LINE = "            self._record_event(method, params, session_id)"
SEND_LINE = '            return {"result": await self.cdp.send_raw(method, params, session_id=sid)}'
MAIN_LINE = 'if __name__ == "__main__":'
# Module-level code injected in a temporary copy; request data and URLs omitted.
HELPER = '''
_jev_diag_count = 0

def _jev_diag(kind, method, params, sid):
    global _jev_diag_count
    if _jev_diag_count >= 160:
        return
    _jev_diag_count += 1
    data = {"kind": kind, "method": method, "sid": sid,
            "at": round(time.monotonic(), 3)}
    if method == "Target.attachedToTarget":
        data["child_sid"] = params.get("sessionId")
        data["target_type"] = (params.get("targetInfo") or {}).get("type")
    if method.startswith("Fetch."):
        data["request_id"] = params.get("requestId")
    try:
        with (paths.tmp_dir() / "wire-trace.jsonl").open("a") as stream:
            stream.write(json.dumps(data) + "\\n")
    except OSError:
        pass

'''


def instrument(source: str) -> str:
    for needle in (EVENT_LINE, SEND_LINE, MAIN_LINE):
        if source.count(needle) != 1:
            raise ValueError("Unexpected installed daemon; tracing not applied")
    source = source.replace(EVENT_LINE, '            _jev_diag("event", method, params, session_id)\n' + EVENT_LINE)
    source = source.replace(SEND_LINE,
        '            _jev_diag("send", method, params, sid)\n'
        '            result = await self.cdp.send_raw(method, params, session_id=sid)\n'
        '            _jev_diag("reply", method, {}, sid)\n'
        '            return {"result": result}')
    source = source.replace(MAIN_LINE, HELPER + MAIN_LINE)
    ast.parse(source)
    return source


def load_base():
    path = Path("/app/cdp-probe-base.py")
    if hashlib.sha256(path.read_bytes()).hexdigest() != BASE_HASH:
        raise ValueError("Original probe checksum mismatch; stop")
    spec = importlib.util.spec_from_file_location("base_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Make the original launcher invoke this trace wrapper for its child.
    module.__file__ = str(Path(__file__).resolve())
    return module


def child(base, urls):
    from browser_harness import helpers, paths
    from dev_control.browser_worker import network_guard
    trace_path = paths.tmp_dir() / "guard-trace.jsonl"
    count = 0

    def record(kind, method, sid=None, extra=None):
        nonlocal count
        if count >= 160:
            return
        count += 1
        row = {"kind": kind, "method": method, "sid": sid,
               "at": round(time.monotonic(), 3)}
        if extra:
            row.update(extra)
        with trace_path.open("a") as stream:
            stream.write(json.dumps(row) + "\n")

    original_cdp, original_drain = helpers.cdp, helpers.drain_events
    original_init = network_guard.NetworkBoundary.__init__
    guards = []

    def traced_cdp(method, session_id=None, **params):
        record("send", method, session_id)
        try:
            value = original_cdp(method, session_id=session_id, **params)
        except Exception as exc:
            record("error", method, session_id, {"error_type": type(exc).__name__})
            raise
        record("reply", method, session_id)
        return value

    def traced_drain():
        events = original_drain()
        for event in events:
            if event.get("method", "").startswith(("Fetch.", "Target.")):
                record("delivered_event", event.get("method"), event.get("session_id"),
                       {"child_sid": (event.get("params") or {}).get("sessionId")})
        return events

    def traced_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        guards.append(self)

    helpers.cdp, helpers.drain_events = traced_cdp, traced_drain
    network_guard.NetworkBoundary.__init__ = traced_init
    try:
        return base.child_probe(*urls)
    finally:
        for guard in guards:
            record("guard_final", "", extra={"error": guard._error,
                   "thread_alive": guard._thread.is_alive()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs=2)
    args = parser.parse_args()
    base = load_base()
    if args.child:
        return child(base, args.child)
    if importlib.metadata.version("browser-harness") != "0.1.13":
        raise SystemExit("Expected browser-harness 0.1.13")
    spec = importlib.util.find_spec("browser_harness")
    installed = Path(next(iter(spec.submodule_search_locations)))
    with tempfile.TemporaryDirectory(prefix="jev-trace-275-") as temp:
        root = Path(temp)
        package = root / "source" / "browser_harness"
        shutil.copytree(installed, package, ignore=shutil.ignore_patterns("*.pyc", "__pycache__"))
        daemon = package / "daemon.py"
        original = daemon.read_text()
        daemon.write_text(instrument(original))
        print("TRACE_ONLY: routing unchanged; no model calls", flush=True)
        print(json.dumps(base.case("baseline", root, package)), flush=True)
        logs = root / "baseline" / "harness" / "tmp"
        for name in ("wire-trace.jsonl", "guard-trace.jsonl"):
            print("=== " + name + " ===", flush=True)
            path = logs / name
            if not path.is_file():
                print("TRACE_FILE_MISSING", flush=True)
                continue
            lines = path.read_text().splitlines()
            interesting = [line for line in lines if any(term in line for term in
                           ("Fetch.", "Target.", "Page.navigate", "guard_final", "error"))]
            print("\n".join(interesting[-45:]), flush=True)
    print("TRACE_COMPLETE_NOT_A_JEV_SUCCESS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
