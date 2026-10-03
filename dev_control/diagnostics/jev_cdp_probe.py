"""One-shot, offline A/B probe of browser-harness 0.1.13 Target session routing.

Run only inside the disposable stroyka-jev:5beafb6 container, with --network none,
no environment secret file, no published ports, and the tested Chrome seccomp
profile. The installed package, base image and PR #244 are never modified.
Only a temporary copy of daemon.py is patched for the candidate process.
No Agent/model call is made. This is not evidence of a successful Jev QA run.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OLD_ROUTE = 'sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)'
NEW_ROUTE = ('sid = (req.get("session_id") if method == "Target.setAutoAttach" '
             'else None) if method.startswith("Target.") '
             'else (req.get("session_id") or self.session)')


def patch_source(source: str) -> str:
    if source.count(OLD_ROUTE) != 1:
        raise ValueError("Unexpected daemon.py: patch not applied")
    result = source.replace(OLD_ROUTE, NEW_ROUTE, 1)
    ast.parse(result)
    return result


def routing_tests() -> None:
    class Default:
        session = "default-session"
    cases = (
        ("Target.setAutoAttach", "job-session", "job-session"),
        ("Target.setAutoAttach", None, None),
        ("Target.createBrowserContext", "job-session", None),
        ("Target.createTarget", "job-session", None),
        ("Target.disposeBrowserContext", "job-session", None),
        ("Target.attachToTarget", "job-session", None),
        ("Page.navigate", "job-session", "job-session"),
        ("Runtime.evaluate", None, "default-session"),
    )
    for method, supplied, expected in cases:
        state = {"method": method, "req": {"session_id": supplied}, "self": Default()}
        exec(NEW_ROUTE, {}, state)
        if state["sid"] != expected:
            raise AssertionError((method, state["sid"], expected))
    # The exact old dispatcher loses the target session; preserve this regression.
    state = {"method": "Target.setAutoAttach", "req": {"session_id": "job-session"}, "self": Default()}
    exec(OLD_ROUTE, {}, state)
    if state["sid"] is not None:
        raise AssertionError("baseline routing changed")
    sample = "def route(method, req, self):\n    " + OLD_ROUTE + "\n    return sid\n"
    if patch_source(sample).count(NEW_ROUTE) != 1:
        raise AssertionError("patch mismatch")
    for invalid in ("", sample + sample):
        try:
            patch_source(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("unexpected source was not rejected")


def child_probe(url: str, blocked_url: str) -> int:
    result = {"opened": False, "clicked": False, "guard_blocked": False}
    browser = None
    try:
        from dev_control.browser_worker.network_guard import install_safe_browser
        browser_class = install_safe_browser(url)
        browser = browser_class(url)
        result["opened"] = browser.evaluate("document.getElementById('result').textContent") == "LOCAL_PAGE_READY"
        browser.evaluate("document.getElementById('probe').click()")
        result["clicked"] = browser.evaluate("document.getElementById('result').textContent") == "LOCAL_CLICK_OK"
        browser.evaluate("void fetch(" + json.dumps(blocked_url) + ").catch(() => {})")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                browser._qa_boundary.raise_if_failed()
            except Exception as exc:
                result["guard_blocked"] = "blocked out-of-scope browser request:" in str(exc)
                if not result["guard_blocked"]:
                    result["guard_error"] = type(exc).__name__
                break
            time.sleep(.05)
    except Exception as exc:
        result["error"] = (type(exc).__name__ + ": " + str(exc))[:400]
    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception as exc:
                result["cleanup_error"] = type(exc).__name__
    print("PROBE_RESULT " + json.dumps(result), flush=True)
    return 0


def fixture():
    class Handler(BaseHTTPRequestHandler):
        hits = 0
        def do_GET(self):
            type(self).hits += 1
            body = (b"<!doctype html><p id='result'>LOCAL_PAGE_READY</p>"
                    b"<button id='probe' onclick=\"document.getElementById('result').textContent='LOCAL_CLICK_OK'\">Click</button>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except OSError:
                pass
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, Handler


def case(mode: str, root: Path, package: Path) -> dict:
    home = root / mode
    home.mkdir()
    shadow = home / "lib"
    shadow.mkdir()
    copy = shadow / "browser_harness"
    shutil.copytree(package, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    daemon = copy / "daemon.py"
    if mode == "candidate":
        daemon.write_text(patch_source(daemon.read_text(encoding="utf-8")), encoding="utf-8")
    allowed, _ = fixture()
    denied, denied_handler = fixture()
    url = f"http://127.0.0.1:{allowed.server_port}/probe"
    blocked = f"http://127.0.0.1:{denied.server_port}/must-not-be-requested"
    # Build a clean environment; do not inherit API keys, cookies or CDP overrides.
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
           "HOME": str(home), "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": f"{shadow}:/app",
           "BH_HOME": str(home / "harness"), "BU_NAME": "default", "QA_BASE_URL": url}
    chrome = None
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if b"LOCAL_PAGE_READY" not in response.read():
                raise RuntimeError("local fixture unavailable")
        profile = home / "chrome"
        with (home / "chrome.log").open("wb") as log:
            chrome = subprocess.Popen([
                "google-chrome-stable", "--headless=new", "--disable-background-networking",
                "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                f"--user-data-dir={profile}", "about:blank"
            ], env=env, stdout=log, stderr=log)
            active = profile / "DevToolsActivePort"
            deadline = time.monotonic() + 10
            while not active.exists():
                if chrome.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("dedicated Chrome did not start")
                time.sleep(.1)
            port = int(active.read_text().splitlines()[0])
            env["BU_CDP_URL"] = f"http://127.0.0.1:{port}"
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--child", url, blocked],
                env=env, capture_output=True, text=True, timeout=22,
            )
            lines = [line.removeprefix("PROBE_RESULT ") for line in completed.stdout.splitlines()
                     if line.startswith("PROBE_RESULT ")]
            if not lines:
                result = {"error": "child exited without probe result", "exit": completed.returncode,
                          "stderr": completed.stderr[-400:]}
            else:
                result = json.loads(lines[-1])
        result["out_of_scope_requests_received"] = denied_handler.hits
        return {"case": mode, **result}
    except subprocess.TimeoutExpired:
        return {"case": mode, "error": "probe subprocess timeout (22s)",
                "out_of_scope_requests_received": denied_handler.hits}
    except Exception as exc:
        return {"case": mode, "error": (type(exc).__name__ + ": " + str(exc))[:400]}
    finally:
        if chrome is not None:
            chrome.terminate()
            try:
                chrome.wait(timeout=2)
            except subprocess.TimeoutExpired:
                chrome.kill()
                chrome.wait(timeout=2)
        allowed.shutdown()
        denied.shutdown()
        allowed.server_close()
        denied.server_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", action="store_true")
    parser.add_argument("--child", nargs=2)
    args = parser.parse_args()
    if args.child:
        return child_probe(*args.child)
    routing_tests()
    print("ROUTING_TESTS_OK", flush=True)
    if args.unit:
        return 0
    if importlib.metadata.version("browser-harness") != "0.1.13":
        raise SystemExit("Expected browser-harness 0.1.13; nothing changed")
    spec = importlib.util.find_spec("browser_harness")
    package = Path(next(iter(spec.submodule_search_locations)))
    source = (package / "daemon.py").read_text(encoding="utf-8")
    patch_source(source)  # Validate both the shape and syntax before any browser action.
    with tempfile.TemporaryDirectory(prefix="jev-route-probe-") as temp:
        results = []
        for mode in ("baseline", "candidate"):
            print("START " + mode, flush=True)
            result = case(mode, Path(temp), package)
            print(json.dumps(result), flush=True)
            results.append(result)
    candidate = results[-1]
    good = all(candidate.get(key) for key in ("opened", "clicked", "guard_blocked"))
    good = good and candidate.get("out_of_scope_requests_received") == 0
    print("CANDIDATE_PROBE_PASSED" if good else "CANDIDATE_PROBE_NOT_PASSED", flush=True)
    return 0 if good else 2


if __name__ == "__main__":
    raise SystemExit(main())
