"""#275: one paid Jev decision and a locally verified click; NOT a release gate.

Use the existing 5beafb6 image and the two checksum-pinned, read-only probes.
Only a temporary browser-harness copy is patched. No production, arbitrary URL,
login, text helper, published port, automatic retry or image modification.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

BASE_HASH = "4299cc3ccbac19a24bed67b8cc1a5269fa3e9a788db0936c40e235fab4689d31"
PATCH_HASH = "929e142cda5d50ba3ef4b25bd67595b885359c69d52162aa5f2f265f67cf19d5"
SYSTEMONE = "https://api.timeweb.ai/v1/systemone"
UPSTREAM = "https://api.typesafe.ai/v1/systemone"
HTML = b'''<!doctype html><html><head><title>Jev local click test</title></head>
<body><h1>Local test</h1><p id="result">WAITING</p>
<button id="probe" data-clicks="0" onclick="this.dataset.clicks=String(Number(this.dataset.clicks)+1);document.getElementById('result').textContent='JEV_BROWSER_OK';this.disabled=true">Run Jev test</button>
</body></html>'''
SNAPSHOT = """(() => {const b=document.getElementById('probe');return {
url:location.href, text:document.getElementById('result')?.textContent,
clicks:Number(b?.dataset.clicks), disabled:b?.disabled};})()"""


def load_checked(path, digest, name):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("diagnostic source checksum mismatch")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the API key to another endpoint.


class OneCall:
    def __init__(self, delegate):
        self.delegate, self.calls = delegate, 0

    def __call__(self, url, key, body):
        if url != UPSTREAM or self.calls:
            raise RuntimeError("only one Timeweb Jev request is allowed")
        self.calls += 1
        return self.delegate(url, key, body)


def passed(before, after, expected_url, calls, operation, history):
    return (
        before.get("url") == expected_url and before.get("text") == "WAITING"
        and before.get("clicks") == 0 and before.get("disabled") is False
        and after.get("url") == expected_url and after.get("text") == "JEV_BROWSER_OK"
        and after.get("clicks") == 1 and after.get("disabled") is True
        and calls == 1 and operation == "CLICK" and len(history) == 1
        and history[0].get("kind") == "click" and history[0].get("operation") == "CLICK"
    )


def fixture():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/probe":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(HTML)))
            self.end_headers()
            try:
                self.wfile.write(HTML)
            except OSError:
                pass
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_probe(root, base, candidate, package, api_key):
    shadow = root / "lib"
    copy = shadow / "browser_harness"
    shutil.copytree(package, copy, ignore=shutil.ignore_patterns("*.pyc", "__pycache__"))
    daemon = copy / "daemon.py"
    daemon.write_text(base.patch_source(daemon.read_text()))
    # No inherited cookie, proxy, text-provider or remote-CDP settings.
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
           "HOME": str(root), "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": f"{shadow}:/app",
           "BH_HOME": str(root / "harness"), "BU_NAME": "default"}
    os.environ.clear()
    os.environ.update(env)
    sys.path.insert(0, str(shadow))
    from browser_harness import daemon as loaded_daemon
    from dev_control.browser_worker import network_guard
    if not Path(loaded_daemon.__file__).is_relative_to(shadow):
        raise RuntimeError("temporary daemon was not loaded")
    if Path(loaded_daemon.__file__).read_text().count(base.NEW_ROUTE) != 1:
        raise RuntimeError("candidate routing not active")
    raw = Path(network_guard.__file__).read_bytes()
    if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != candidate.GUARD_BLOB:
        raise RuntimeError("unexpected base-image network guard")
    counts = {"ignored_registered_sessions": 0, "delegated_new_sessions": 0}
    original_handler = network_guard.NetworkBoundary._handle_attached_target
    network_guard.NetworkBoundary._handle_attached_target = candidate.idempotent_handler(original_handler, counts)
    server, chrome, agent, provider_patch, budget = None, None, None, None, None
    report = {"ok": False, "scope": "one_local_model_click", "model_calls": 0}
    phase = "browser_start"
    try:
        server = fixture()
        url = f"http://127.0.0.1:{server.server_port}/probe"
        profile = root / "chrome"
        with (root / "chrome.log").open("wb") as log:
            chrome = subprocess.Popen([
                "google-chrome-stable", "--headless=new", "--disable-background-networking",
                "--no-first-run", "--no-default-browser-check", "--disable-dev-shm-usage",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                f"--user-data-dir={profile}", "about:blank"
            ], env=dict(os.environ), stdout=log, stderr=log)
        active = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 10
        while not active.exists():
            if chrome.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("dedicated Chrome did not start")
            time.sleep(.1)
        port = int(active.read_text().splitlines()[0])
        os.environ["BU_CDP_URL"] = f"http://127.0.0.1:{port}"
        os.environ["QA_BASE_URL"] = url
        network_guard.install_safe_browser(url)
        from jev_ultrafast import Agent
        phase = "page_observation"
        # Chrome and the daemon are started before the key enters worker env.
        agent = Agent(url, "Click the Run Jev test button once. The result must change from WAITING to JEV_BROWSER_OK. Do not type or navigate elsewhere.")
        before = agent.browser.evaluate(SNAPSHOT)
        agent.browser._qa_boundary.raise_if_failed()
        if before.get("clicks") != 0 or before.get("text") != "WAITING":
            raise RuntimeError("fixture initial state invalid")
        from dev_control.browser_worker.provider import install_timeweb_provider
        from dev_control import jev_timeweb
        import jev_ultrafast.model as model
        os.environ.update(TIMEWEB_AI_API_KEY=api_key, JEV_MODEL="jev-latest", JEV_SYSTEMONE_URL=SYSTEMONE)
        provider_patch = install_timeweb_provider()
        opener = build_opener(ProxyHandler({}), NoRedirect())
        def strict_urlopen(request, timeout):
            if request.full_url != SYSTEMONE or request.get_method() != "POST":
                raise RuntimeError("unexpected provider request rejected")
            return opener.open(request, timeout=min(timeout, 30.0))
        # Test-process-only transport restriction; installed files stay unchanged.
        jev_timeweb.urlopen = strict_urlopen
        budget = OneCall(model.post_json)
        model.post_json = budget
        phase = "timeweb_jev_decision"
        predicted = agent.command("predict")
        operation = (predicted.get("decision") or {}).get("operation")
        report["operation"] = operation if operation in {"CLICK", "DONE", "BLOCKED", "WAIT", "TYPE_TEXT", "SELECT"} else "OTHER"
        agent.browser._qa_boundary.raise_if_failed()
        if operation != "CLICK":
            raise RuntimeError("Jev did not select CLICK; no action executed")
        phase = "browser_click"
        final_state = agent.command("act", {"fingerprint": agent.state["page"]["fingerprint"]})
        agent.browser._qa_boundary.raise_if_failed()
        after = agent.browser.evaluate(SNAPSHOT)
        agent.browser._qa_boundary.raise_if_failed()
        report.update(
            ok=passed(before, after, url, budget.calls, operation, final_state.get("history", [])),
            opened=before.get("text") == "WAITING",
            clicked_once=after.get("clicks") == 1,
            marker_verified=after.get("text") == "JEV_BROWSER_OK",
            same_page=after.get("url") == url,
            model="jev-latest",
        )
        phase = "verification_complete"
    except Exception as exc:
        # Never print arbitrary provider response, URL, goal, headers or secret.
        report.update(ok=False, error_type=type(exc).__name__)
        match = re.search(r"\bHTTP (\d{3})\b", str(exc))
        if match:
            report["provider_http_status"] = int(match.group(1))
    finally:
        report["phase"] = phase
        report["model_calls"] = budget.calls if budget else 0
        os.environ.pop("TIMEWEB_AI_API_KEY", None)
        if agent:
            try:
                agent.close()
            except Exception as exc:
                report.update(ok=False, cleanup_error=type(exc).__name__)
        if provider_patch:
            provider_patch.restore()
        network_guard.NetworkBoundary._handle_attached_target = original_handler
        try:
            from browser_harness.helpers import _send
            _send({"meta": "shutdown"}, response_timeout=2.0)
        except Exception:
            pass
        if chrome:
            chrome.terminate()
            try:
                chrome.wait(timeout=2)
            except subprocess.TimeoutExpired:
                chrome.kill()
                chrome.wait(timeout=2)
        if server:
            server.shutdown()
            server.server_close()
    report.update(counts)
    return report


def unit_tests():
    url = "http://127.0.0.1:1234/probe"
    before = dict(url=url, text="WAITING", clicks=0, disabled=False)
    after = dict(url=url, text="JEV_BROWSER_OK", clicks=1, disabled=True)
    hist = [{"kind": "click", "operation": "CLICK"}]
    assert passed(before, after, url, 1, "CLICK", hist)
    for update in ({"clicks": 0}, {"clicks": 2}, {"disabled": False}, {"url": "https://elsewhere.test"}, {"text": "WAITING"}):
        assert not passed(before, {**after, **update}, url, 1, "CLICK", hist)
    assert not passed(before, after, url, 0, "CLICK", hist)
    assert not passed(before, after, url, 1, "DONE", hist)
    assert not passed(before, after, url, 1, "CLICK", [])
    sent = []
    budget = OneCall(lambda *args: sent.append(args) or {"answers": {}})
    assert budget(UPSTREAM, "fake-test-key", {}) == {"answers": {}}
    for addr in (UPSTREAM, "https://another-provider.test"):
        try:
            budget(addr, "fake-test-key", {})
        except RuntimeError:
            pass
        else:
            raise AssertionError("call budget did not reject")
    assert len(sent) == 1 and budget.calls == 1
    assert NoRedirect().redirect_request(None, None, 302, "", {}, "https://elsewhere.test") is None
    print("MODEL_CLICK_UNIT_TESTS_OK", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", action="store_true")
    args = parser.parse_args()
    unit_tests()
    if args.unit:
        return 0
    key = os.environ.pop("TIMEWEB_AI_API_KEY", "").strip()
    if not key:
        raise ValueError("TIMEWEB_AI_API_KEY missing")
    base = load_checked("/app/cdp-probe-base.py", BASE_HASH, "base_probe")
    candidate = load_checked("/app/self-attach-probe.py", PATCH_HASH, "candidate_probe")
    base.routing_tests()
    candidate.unit_tests()
    if importlib.metadata.version("browser-harness") != "0.1.13":
        raise RuntimeError("expected browser-harness 0.1.13")
    package = Path(next(iter(importlib.util.find_spec("browser_harness").submodule_search_locations)))
    print("START: one paid Jev decision; fixed local page; no login", flush=True)
    with tempfile.TemporaryDirectory(prefix="jev-model-click-275-") as tmp:
        report = run_probe(Path(tmp), base, candidate, package, key)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    print("JEV_MODEL_CLICK_PASSED" if report.get("ok") else "JEV_MODEL_CLICK_NOT_PASSED", flush=True)
    print("NOT_A_STROYKA_QA_ACCEPTANCE", flush=True)
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "phase": "preflight_or_cleanup", "error_type": type(exc).__name__}), flush=True)
        raise SystemExit(2)
