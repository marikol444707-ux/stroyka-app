import os
import sys
import threading
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dev_control.browser_worker.network_guard import (
    DEDICATED_CDP_URL,
    NetworkBoundary,
    assert_dedicated_loopback_cdp_url,
    bootstrap_session_cookie,
    redact_boundary_url,
    request_allowed,
)
from dev_control.jev_timeweb import JevError
from dev_control.browser_worker.run import (
    _assert_allowed_url, _redact_url, _sanitize_history,
    _refresh_live_observation, _capture_final_frame, execute_task,
)


class BrowserWorkerFinalScreenshotTest(unittest.TestCase):
    def test_final_capture_converts_png_to_valid_jpeg(self):
        from pathlib import Path
        from PIL import Image

        def fake_capture(path=None, **_kwargs):
            Image.new("RGB", (24, 16), (12, 34, 56)).save(path, format="PNG")
            return path

        with tempfile.TemporaryDirectory() as directory, patch(
            "browser_harness.helpers.capture_screenshot", side_effect=fake_capture
        ):
            root = Path(directory)
            _capture_final_frame(root)
            self.assertFalse((root / "final.png").exists())
            with Image.open(root / "final.jpg") as image:
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(image.size, (24, 16))

    def test_final_capture_failure_does_not_leave_misleading_jpeg(self):
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory, patch(
            "browser_harness.helpers.capture_screenshot",
            side_effect=RuntimeError("screenshot timeout")
        ):
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "screenshot timeout"):
                _capture_final_frame(root)
            self.assertFalse((root / "final.jpg").exists())


class BrowserWorkerUrlSafetyTest(unittest.TestCase):
    def test_bootstrap_lifecycle_uses_one_context_rechecks_identity_and_destroys_guarded_context(self):
        import json
        from types import ModuleType
        from dev_control.browser_worker.network_guard import install_safe_browser
        from dev_control.browser_worker.qa_identity import QAIdentityNotEstablished
        from dev_control.browser_worker.test_qa_identity import valid_response

        for changed_identity in (False, True):
            events, storage = [], {}
            state = {"url": "about:blank", "loader": 0, "probes": 0}
            def cdp(method, **kwargs):
                events.append((method, kwargs))
                if method == "Target.createBrowserContext": return {"browserContextId": "isolated"}
                if method == "Target.createTarget":
                    self.assertEqual(kwargs["browserContextId"], "isolated")
                    return {"targetId": "page"}
                if method == "Target.attachToTarget": return {"sessionId": "page-session"}
                if method == "Network.setCookie": return {"success": True}
                if method == "Page.navigate":
                    state["url"] = kwargs["url"]
                    state["loader"] += 1
                    return {"loaderId": str(state["loader"])}
                if method == "Page.getFrameTree":
                    return {"frameTree": {"frame": {"id": "frame", "url": state["url"],
                                                      "loaderId": str(state["loader"])}}}
                if method == "Page.createIsolatedWorld": return {"executionContextId": 77}
                if method == "Runtime.evaluate":
                    state["probes"] += 1
                    payload = valid_response()
                    if changed_identity and state["probes"] == 2:
                        payload["user"]["id"] = 999
                    return {"result": {"value": {"url": "https://qa.example.test/api/users/qa-readonly-context/identity",
                        "status": 200, "content_type": "application/json", "payload": payload}}}
                if method == "DOMStorage.setDOMStorageItem": storage[kwargs["key"]] = kwargs["value"]
                if method == "DOMStorage.getDOMStorageItems": return {"entries": list(storage.items())}
                return {}
            class Browser:
                def call(self, method, **kwargs): return cdp(method, session_id=self.session, **kwargs)
                def evaluate(self, expression):
                    self_test.assertEqual(expression, "document.readyState")
                    return "complete"
            self_test = self
            root, agent, browser_module = (ModuleType(name) for name in (
                "jev_ultrafast", "jev_ultrafast.agent", "jev_ultrafast.browser"))
            root.agent, root.browser, browser_module.Browser = agent, browser_module, Browser
            harness, admin, helpers = (ModuleType(name) for name in (
                "browser_harness", "browser_harness.admin", "browser_harness.helpers"))
            harness.admin, harness.helpers = admin, helpers
            admin.ensure_daemon = lambda: None
            helpers.cdp, helpers.drain_events = cdp, lambda: []
            modules = {m.__name__: m for m in (root, agent, browser_module, harness, admin, helpers)}
            def start(boundary):
                self.assertTrue(boundary._bootstrap_only)
                events.append(("GUARD_START", {}))
            with self.subTest(changed_identity=changed_identity), patch.dict(sys.modules, modules), patch.dict(
                os.environ, {"QA_SESSION_COOKIE_VALUE": "dummy-cookie"}, clear=True,
            ), patch.object(NetworkBoundary, "start", start):
                safe = install_safe_browser("https://qa.example.test/app", read_only=True)
                if changed_identity:
                    with self.assertRaises(QAIdentityNotEstablished): safe("https://qa.example.test/app")
                else:
                    browser = safe("https://qa.example.test/app")
                    self.assertTrue(browser._qa_identity_verified)
                    self.assertTrue(browser._qa_bootstrap_only)
                    browser.close()
            methods = [method for method, _ in events]
            self.assertEqual(methods.count("Target.createBrowserContext"), 1)
            self.assertEqual(methods.count("Page.navigate"), 2)
            self.assertEqual(state["probes"], 2)
            self.assertLess(methods.index("GUARD_START"), methods.index("Page.navigate"))
            self.assertLess(methods.index("Runtime.evaluate"), methods.index("DOMStorage.setDOMStorageItem"))
            self.assertLess(methods.index("DOMStorage.setDOMStorageItem"),
                            len(methods) - 1 - methods[::-1].index("Page.navigate"))
            self.assertNotIn("Fetch.disable", methods)
            self.assertIn("Target.disposeBrowserContext", methods)
            self.assertNotIn("authToken", storage)
            self.assertEqual(json.loads(storage["user"])["id"], 21)

    def test_bootstrap_guard_blocks_all_business_reads_and_reports_exclusion(self):
        for path, method, resource, excluded in (
            ("/projects", "GET", "XHR", True),
            ("/api/supply-history", "GET", "Fetch", True),
            ("/users/company-context", "GET", "XHR", True),
            ("/csrf-token", "GET", "Fetch", True),
            ("/projects", "POST", "XHR", False),
            ("/api/supply-history", "GET", "Image", False),
        ):
            with self.subTest(path=path, method=method, resource=resource):
                guard = NetworkBoundary.__new__(NetworkBoundary)
                guard._cdp = Mock()
                guard._session_id = "root"
                guard._base_url = "https://qa.example.test/app"
                guard._read_only = guard._bootstrap_only = True
                guard._error = None
                guard.blocked_data_reads = guard.blocked_presence_pings = 0
                guard._stop = threading.Event()
                def events():
                    guard._stop.set()
                    return [{"method": "Fetch.requestPaused", "session_id": "root", "params": {
                        "requestId": "r", "resourceType": resource,
                        "request": {"url": "https://qa.example.test" + path, "method": method}}}]
                guard._drain_events = events
                guard._loop()
                guard._cdp.assert_called_once_with("Fetch.failRequest", session_id="root",
                                                   requestId="r", errorReason="BlockedByClient")
                self.assertEqual(guard.blocked_data_reads, int(excluded))
                self.assertEqual(guard._error is None, excluded)

    def test_bootstrap_body_text_without_real_shell_never_reports_success(self):
        class Browser:
            _qa_identity_verified = True
            _qa_bootstrap_only = True
            _qa_boundary = SimpleNamespace(_bootstrap_only=True, blocked_data_reads=3,
                blocked_presence_pings=0, raise_if_failed=lambda: None)
            def evaluate(self, expression):
                if expression == "location.href": return "https://qa.example.test/app"
                if "app-authenticated-shell" in expression: return False
                return "Public page mentions Склад"
        class Agent:
            def __init__(self, *_args, **_kwargs): self.browser = Browser()
            def __enter__(self): return self
            def __exit__(self, *_args): return False
            def snapshot(self): return {"status": "observed", "page": {}, "history": [], "decisions": []}
            def run(self): raise AssertionError("No model actions")
        with tempfile.TemporaryDirectory() as evidence, patch.dict(os.environ, {
            "QA_BASE_URL": "https://qa.example.test/app", "QA_ALLOWED_ORIGIN": "https://qa.example.test",
            "QA_ENVIRONMENT": "qa", "QA_SESSION_COOKIE_VALUE": "dummy-cookie",
        }, clear=True), patch.dict(sys.modules, {"jev_ultrafast": SimpleNamespace(Agent=Agent)}), patch(
            "dev_control.browser_worker.run.install_safe_browser",
        ), patch("dev_control.browser_worker.run.time.monotonic", side_effect=[0, 10]), patch(
            "dev_control.browser_worker.run._write_progress",
        ) as progress, patch("dev_control.browser_worker.run._capture_final_frame") as capture:
            result = execute_task(url="https://qa.example.test/app", goal="observe menu",
                record_dir=evidence, read_only=True, expect_text=["Склад"], max_seconds=5)
        self.assertFalse(result["ok"])
        self.assertIn("AUTHENTICATED_SHELL_MENU_NOT_VERIFIED", result["failures"])
        self.assertEqual(result["scope"], "bootstrap_only")
        self.assertEqual(result["data_status"], "NOT_TESTED")
        self.assertTrue(all(call.kwargs.get("verified_ok") is not True for call in progress.call_args_list))
        capture.assert_not_called()

    def test_bootstrap_observation_rejects_same_document_url_escape(self):
        browser = SimpleNamespace(
            _qa_bootstrap_only=True,
            _qa_boundary=SimpleNamespace(raise_if_failed=lambda: None),
        )
        for path in ("/application", "/app/other", "/app?other=1", "/app#other"):
            with self.subTest(path=path):
                browser.evaluate = lambda expression: (
                    "https://qa.example.test" + path if expression == "location.href"
                    else True if "app-authenticated-shell" in expression else "Склад"
                )
                with self.assertRaisesRegex(ValueError, "BOOTSTRAP_DOCUMENT_SCOPE_NOT_ENFORCED"):
                    _refresh_live_observation(SimpleNamespace(browser=browser), {}, "https://qa.example.test")

    def test_bootstrap_profile_allows_only_identity_app_and_static_assets(self):
        base = "https://qa.example.test/app"
        self.assertTrue(request_allowed(base, "https://qa.example.test", "Document",
                                        read_only=True, bootstrap_only=True))
        self.assertFalse(request_allowed("https://qa.example.test/admin", "https://qa.example.test", "Document",
                                         read_only=True, bootstrap_only=True))
        allowed = (
            (base, "Document"),
            ("https://qa.example.test/static/js/main.abc123.js", "Script"),
            ("https://qa.example.test/static/css/main.abc123.css", "Stylesheet"),
            ("https://qa.example.test/api/users/qa-readonly-context/identity", "Fetch"),
        )
        for url, kind in allowed:
            with self.subTest(url=url):
                self.assertTrue(request_allowed(url, base, kind, read_only=True, bootstrap_only=True))
        for path in ("/projects", "/users/company-context", "/api/supply-history", "/csrf-token",
                     "/app/data", "/static/../projects", "/static/js/%2e%2e/secret",
                     "/api/users/qa-readonly-context/identity?other=1"):
            for kind in ("XHR", "Image", "Document"):
                with self.subTest(path=path, kind=kind):
                    self.assertFalse(request_allowed("https://qa.example.test" + path, base, kind,
                                                     read_only=True, bootstrap_only=True))
        for method in ("POST", "PUT", "DELETE", "OPTIONS"):
            self.assertFalse(request_allowed(allowed[-1][0], base, "Fetch", request_method=method,
                                             read_only=True, bootstrap_only=True))

    def test_direct_execute_task_rejects_production_before_model_or_browser(self):
        for base in (
            "https://stroyka.pro",
            "https://www.stroyka26.pro/app",
            "https://qa.stroyka.pro/app",
            "https://147.45.237.127",
        ):
            env = {
                "QA_ENVIRONMENT": "staging",
                "QA_BASE_URL": base,
                "QA_ALLOWED_ORIGIN": base.split("/app")[0],
            }
            with self.subTest(base=base), patch.dict(os.environ, env, clear=True), patch(
                "dev_control.browser_worker.run.install_timeweb_provider"
            ) as model, patch(
                "dev_control.browser_worker.run.install_safe_browser"
            ) as browser:
                with self.assertRaisesRegex(ValueError, "nonproduction"):
                    execute_task(
                        url=base, goal="Attempt unsafe production access",
                        expect_text=["Something"], read_only=False,
                    )
                model.assert_not_called()
                browser.assert_not_called()

    def test_direct_execute_task_requires_explicit_qa_label_and_origin(self):
        base = "https://qa.example.test/app"
        cases = (
            {"QA_BASE_URL": base, "QA_ALLOWED_ORIGIN": "https://qa.example.test"},
            {"QA_BASE_URL": base, "QA_ENVIRONMENT": "qa"},
            {"QA_BASE_URL": base, "QA_ALLOWED_ORIGIN": "https://evil.test", "QA_ENVIRONMENT": "qa"},
            {"QA_BASE_URL": base, "QA_ALLOWED_ORIGIN": "https://qa.example.test/other", "QA_ENVIRONMENT": "qa"},
        )
        for env in cases:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), patch(
                "dev_control.browser_worker.run.install_safe_browser"
            ) as browser:
                with self.assertRaises(ValueError):
                    execute_task(url=base, goal="Observe", expect_text=["Test"], read_only=True)
                browser.assert_not_called()

    def test_allows_same_origin_and_base_path(self):
        _assert_allowed_url(
            "https://qa.example.test/app/warehouse",
            "https://qa.example.test/app",
        )

    def test_default_https_port_is_canonicalized(self):
        _assert_allowed_url(
            "https://qa.example.test/app/warehouse",
            "https://qa.example.test:443/app",
        )
        self.assertTrue(request_allowed(
            "https://qa.example.test/app/data",
            "https://qa.example.test:443/app",
            "XHR",
        ))
    def test_rejects_other_origin(self):
        with self.assertRaisesRegex(ValueError, "origin"):
            _assert_allowed_url(
                "https://evil.example/steal",
                "https://qa.example.test",
            )

    def test_rejects_sibling_path_when_base_has_path(self):
        with self.assertRaisesRegex(ValueError, "path"):
            _assert_allowed_url(
                "https://qa.example.test/admin",
                "https://qa.example.test/app",
            )

    def test_rejects_dot_segment_and_encoded_dot_segment_bypass(self):
        for url in (
            "https://qa.example.test/app/../admin",
            "https://qa.example.test/app/%2e%2e/admin",
            "https://qa.example.test/app/%252e%252e/admin",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(ValueError, "dot path segments"):
                    _assert_allowed_url(url, "https://qa.example.test/app")

    def test_data_and_blob_are_never_allowed_as_document_navigation(self):
        base = "https://qa.example.test/app"
        for url in ("data:text/html,<h1>x</h1>", "blob:https://qa.example.test/abc"):
            with self.subTest(url=url):
                self.assertFalse(request_allowed(url, base, "Document"))
                self.assertTrue(request_allowed(url, base, "Image"))

    def test_network_guard_blocks_external_before_request(self):
        self.assertFalse(request_allowed(
            "https://evil.example/steal",
            "https://qa.example.test/app",
            "Document",
        ))
        self.assertFalse(request_allowed(
            "https://qa.example.test/admin",
            "https://qa.example.test/app",
            "Document",
        ))
        self.assertTrue(request_allowed(
            "https://qa.example.test/api/data",
            "https://qa.example.test/app",
            "XHR",
        ))
    def test_sanitized_history_never_persists_typed_text(self):
        history = _sanitize_history([
            {
                "step": 1,
                "action": "Password",
                "kind": "fill",
                "text": "super-secret-password",
                "text_helper": "helper-model",
                "url": "https://qa.example.test/login",
                "operation": "TYPE_TEXT",
                "target": "2",
                "page_changed": True,
                "elapsed_ms": 42,
            }
        ])
        self.assertEqual(len(history), 1)
        self.assertNotIn("text", history[0])
        self.assertNotIn("text_helper", history[0])
        self.assertNotIn("super-secret-password", repr(history))

    def test_sensitive_query_values_and_fragments_are_redacted(self):
        redacted = _redact_url(
            "https://qa.example.test/callback?code=abc123&next=warehouse&access_token=secret#fragment-token"
        )
        self.assertIn("code=%5BREDACTED%5D", redacted)
        self.assertIn("access_token=%5BREDACTED%5D", redacted)
        self.assertIn("next=warehouse", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("fragment-token", redacted)



    def test_encoded_sensitive_path_markers_are_redacted(self):
        samples = (
            "https://qa.example.test/app/%72eset/VERYSECRET",
            "https://qa.example.test/app/invite%2FVERYSECRET",
            "https://qa.example.test/app/%2569nvite%252FVERYSECRET",
        )
        for url in samples:
            with self.subTest(url=url):
                persisted = _redact_url(url)
                boundary = redact_boundary_url(url)
                self.assertNotIn("VERYSECRET", persisted)
                self.assertNotIn("VERYSECRET", boundary)
                self.assertIn("[REDACTED]", persisted)
                self.assertIn("[REDACTED]", boundary)

    def test_excessive_path_encoding_fails_closed_to_redacted_path(self):
        encoded = "invite/VERYSECRET"
        for _ in range(10):
            from urllib.parse import quote
            encoded = quote(encoded, safe="")
        url = "https://qa.example.test/app/" + encoded
        self.assertNotIn("VERYSECRET", _redact_url(url))
        self.assertNotIn("VERYSECRET", redact_boundary_url(url))
        self.assertIn("[REDACTED]", _redact_url(url))
        self.assertIn("[REDACTED]", redact_boundary_url(url))

    def test_double_encoded_and_excessive_query_keys_hide_secrets(self):
        from urllib.parse import quote

        for url in (
            "https://qa.example.test/app?%2574oken=VERYSECRET&next=ok",
            "https://qa.example.test/app?%2569nvite=VERYSECRET",
        ):
            for redact in (_redact_url, redact_boundary_url):
                with self.subTest(url=url, redact=redact.__name__):
                    result = redact(url)
                    self.assertNotIn("VERYSECRET", result)
                    self.assertIn("%5BREDACTED%5D", result)

        encoded_key = "%74oken"
        for _ in range(15):
            encoded_key = quote(encoded_key, safe="")
        url = "https://qa.example.test/app?" + encoded_key + "=VERYSECRET"
        for redact in (_redact_url, redact_boundary_url):
            with self.subTest(redact=redact.__name__):
                self.assertNotIn("VERYSECRET", redact(url))

    def test_boundary_errors_redact_sensitive_urls(self):
        redacted = redact_boundary_url(
            "https://evil.example/reset/secret-token?code=abc123&next=ok#fragment"
        )
        self.assertNotIn("secret-token", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("fragment", redacted)
        self.assertIn("[REDACTED]", redacted)


    def test_stroyka_invite_query_is_redacted(self):
        redacted = _redact_url(
            "https://qa.example.test/?invite=company-membership-code&next=register"
        )
        self.assertNotIn("company-membership-code", redacted)
        self.assertIn("invite=%5BREDACTED%5D", redacted)
        self.assertIn("next=register", redacted)

    def test_boundary_redactor_hides_stroyka_invite_query(self):
        redacted = redact_boundary_url(
            "https://qa.example.test/?invite=company-membership-code"
        )
        self.assertNotIn("company-membership-code", redacted)
        self.assertIn("invite=%5BREDACTED%5D", redacted)

    def test_sensitive_path_token_is_redacted(self):
        redacted = _redact_url(
            "https://qa.example.test/password-reset/super-secret-token?next=warehouse"
        )
        self.assertIn("/password-reset/[REDACTED]", redacted)
        self.assertNotIn("super-secret-token", redacted)
        self.assertIn("next=warehouse", redacted)

    def test_url_userinfo_is_removed_from_evidence(self):
        redacted = _redact_url(
            "https://qa-user:qa-password@qa.example.test/app?next=ok"
        )
        self.assertNotIn("qa-user", redacted)
        self.assertNotIn("qa-password", redacted)
        self.assertEqual(redacted, "https://qa.example.test/app?next=ok")

        boundary = redact_boundary_url(
            "https://qa-user:qa-password@qa.example.test/app"
        )
        self.assertNotIn("qa-user", boundary)
        self.assertNotIn("qa-password", boundary)
    def test_rejects_non_http_scheme(self):
        with self.assertRaisesRegex(ValueError, "http"):
            _assert_allowed_url(
                "file:///etc/passwd",
                "https://qa.example.test",
            )

    def test_rejects_credentials_embedded_in_qa_urls(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            _assert_allowed_url(
                "https://user:password@qa.example.test/app",
                "https://qa.example.test/app",
            )

    def test_cdp_must_be_exact_dedicated_loopback_endpoint(self):
        self.assertEqual(assert_dedicated_loopback_cdp_url(), DEDICATED_CDP_URL)
        for value in (
            "http://localhost:9222",
            "http://127.0.0.1:9222/",
            "http://10.0.0.5:9222",
            "https://127.0.0.1:9222",
            "ws://127.0.0.1:9222",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "dedicated loopback"):
                assert_dedicated_loopback_cdp_url(value)

    def test_cdp_rejects_websocket_override_even_if_url_is_loopback(self):
        with patch.dict(
            os.environ,
            {"BU_CDP_URL": DEDICATED_CDP_URL, "BU_CDP_WS": "ws://10.0.0.5:9222/devtools/browser/foreign"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "BU_CDP_WS"):
                assert_dedicated_loopback_cdp_url()

    def test_session_cookie_bootstrap_is_https_httponly_and_target_scoped(self):
        cdp = Mock(return_value={"success": True})
        with patch.dict(
            os.environ,
            {"QA_SESSION_COOKIE_NAME": "qa_session", "QA_SESSION_COOKIE_VALUE": "session-secret"},
            clear=True,
        ):
            self.assertTrue(bootstrap_session_cookie(
                "https://qa.example.test/app", "page-session-1", cdp,
            ))
        cdp.assert_called_once()
        args, kwargs = cdp.call_args
        self.assertEqual(args[0], "Network.setCookie")
        self.assertEqual(kwargs["session_id"], "page-session-1")
        self.assertNotIn("browserContextId", kwargs)
        self.assertEqual(kwargs["name"], "qa_session")
        self.assertEqual(kwargs["value"], "session-secret")
        self.assertEqual(kwargs["url"], "https://qa.example.test/")
        self.assertTrue(kwargs["secure"])
        self.assertTrue(kwargs["httpOnly"])
        self.assertEqual(kwargs["sameSite"], "Lax")
        self.assertNotIn("domain", kwargs)

    def test_session_cookie_bootstrap_uses_real_backend_cookie_name_by_default(self):
        cdp = Mock(return_value={"success": True})
        with patch.dict(
            os.environ, {"QA_SESSION_COOKIE_VALUE": "opaque-test-session"}, clear=True,
        ):
            self.assertTrue(bootstrap_session_cookie(
                "https://qa.example.test/app", "page-session-1", cdp,
            ))
        kwargs = cdp.call_args.kwargs
        self.assertEqual(kwargs["name"], "stroyka_session")
        self.assertTrue(kwargs["httpOnly"])
        self.assertTrue(kwargs["secure"])

    def test_session_cookie_bootstrap_fails_closed_if_not_confirmed(self):
        with patch.dict(os.environ, {"QA_SESSION_COOKIE_VALUE": "opaque-test-session"}, clear=True):
            for result in ({}, {"success": False}, None):
                with self.subTest(result=result):
                    cdp = Mock(return_value=result)
                    with self.assertRaisesRegex(ValueError, "not confirmed"):
                        bootstrap_session_cookie("https://qa.example.test/", "page-session-1", cdp)
            cdp = Mock()
            with self.assertRaisesRegex(ValueError, "browser session"):
                bootstrap_session_cookie("https://qa.example.test/", "", cdp)
            cdp.assert_not_called()

    def test_session_cookie_bootstrap_refuses_plain_http_and_no_cookie_is_noop(self):
        cdp = Mock()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(bootstrap_session_cookie(
                "https://qa.example.test/app", "page-session-1", cdp,
            ))
        cdp.assert_not_called()

        with patch.dict(os.environ, {"QA_SESSION_COOKIE_VALUE": "session-secret"}, clear=True):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                bootstrap_session_cookie(
                    "http://qa.example.test/app", "page-session-1", cdp,
                )
            cdp.assert_not_called()

    def test_read_only_drops_presence_ping_but_rejects_other_writes(self):
        # The real Stroyka frontend POSTs /api/online upon login. The
        # observer must block it on the wire without failing every smoke.
        def check(method, url):
            guard = NetworkBoundary.__new__(NetworkBoundary)
            guard._cdp = Mock()
            guard._base_url = "https://qa.example.test/app"
            guard._read_only = True
            guard._session_id = "root"
            guard._stop = threading.Event()
            guard._error = None
            guard.blocked_presence_pings = 0

            def one_event():
                guard._stop.set()
                return [{
                    "method": "Fetch.requestPaused",
                    "session_id": "root",
                    "params": {
                        "requestId": "req-1",
                        "resourceType": "XHR",
                        "request": {"url": url, "method": method},
                    },
                }]
            guard._drain_events = one_event
            guard._loop()
            return guard

        presence = check("POST", "https://qa.example.test/api/online")
        presence._cdp.assert_called_once_with(
            "Fetch.failRequest",
            session_id="root",
            requestId="req-1",
            errorReason="BlockedByClient",
        )
        self.assertIsNone(presence._error)
        self.assertEqual(presence.blocked_presence_pings, 1)

        for url in (
            "https://qa.example.test/api/projects",
            "https://evil.example/api/online",
            "https://qa.example.test/api/online?token=secret",
        ):
            with self.subTest(url=url):
                unsafe = check("POST", url)
                self.assertIn("blocked", unsafe._error)
                self.assertEqual(unsafe.blocked_presence_pings, 0)

        read = check("GET", "https://qa.example.test/api/projects")
        read._cdp.assert_called_once_with(
            "Fetch.continueRequest", session_id="root", requestId="req-1",
        )
        self.assertIsNone(read._error)

    def test_read_only_execute_never_runs_agent_actions(self):
        run_called = []

        class FakeBrowser:
            def __init__(self):
                self._qa_boundary = SimpleNamespace(_bootstrap_only=True, blocked_data_reads=7,
                    blocked_presence_pings=1, raise_if_failed=lambda: None)
                self._qa_bootstrap_only = True

            def evaluate(self, expression):
                if expression == "location.href":
                    return "https://qa.example.test/app"
                if "app-authenticated-shell" in expression:
                    return True
                return "СтройКа\nСклад\nСнабжение"

        class FakeAgent:
            def __init__(self, url, goal, record_dir=None, screenshots=False):
                self.url = url
                self.goal = goal
                self.record_dir = record_dir
                self.screenshots = screenshots
                self.browser = FakeBrowser()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def snapshot(self):
                return {
                    "status": "observed",
                    "page": {"url": self.url, "text": "СтройКа Склад Снабжение"},
                    "history": [],
                    "decisions": [],
                }

            def run(self):
                run_called.append(True)
                raise AssertionError("read-only mode must never call agent.run()")

        fake_jev = SimpleNamespace(Agent=FakeAgent)
        with tempfile.TemporaryDirectory() as evidence, patch.dict(
            os.environ,
            {
                "QA_BASE_URL": "https://qa.example.test/app",
                "QA_ALLOWED_ORIGIN": "https://qa.example.test",
                "QA_ENVIRONMENT": "qa",
            },
            clear=True,
        ), patch.dict(
            sys.modules,
            {"jev_ultrafast": fake_jev},
        ), patch(
            "dev_control.browser_worker.run.install_safe_browser",
        ), patch(
            "dev_control.browser_worker.run._capture_final_frame",
        ):
            report = execute_task(
                url="https://qa.example.test/app",
                goal="Observe the QA menu without actions.",
                record_dir=evidence,
                expect_text=["Склад"],
                expect_url_contains=["qa.example.test"],
                max_seconds=5,
                read_only=True,
            )
            # A matching menu is not evidence that the injected cookie
            # corresponds to an authenticated, company-scoped QA user.
            with patch.dict(os.environ, {"QA_SESSION_COOKIE_VALUE": "dummy-qa-cookie"}):
                cookie_report = execute_task(
                    url="https://qa.example.test/app",
                    goal="Observe authenticated QA menu without actions.",
                    record_dir=evidence,
                    expect_text=["Склад"],
                    expect_url_contains=["qa.example.test"],
                    max_seconds=5,
                    read_only=True,
                )
                # Mock the SafeBrowser internal flag only. In production it
                # is set exclusively by the isolated-world server probe.
                FakeBrowser._qa_identity_verified = True
                verified_report = execute_task(
                    url="https://qa.example.test/app",
                    goal="Observe server-verified QA menu without actions.",
                    record_dir=evidence,
                    expect_text=["Склад"],
                    expect_url_contains=["qa.example.test"],
                    max_seconds=5,
                    read_only=True,
                )

        self.assertTrue(verified_report["ok"])
        self.assertEqual(verified_report["scope"], "bootstrap_only")
        self.assertEqual(verified_report["data_status"], "NOT_TESTED")
        self.assertEqual(verified_report["blocked_data_reads"], 7)
        self.assertEqual(verified_report["blocked_presence_writes"], 1)
        self.assertFalse(cookie_report["ok"])
        self.assertIn("AUTH_NOT_ESTABLISHED", cookie_report["failures"])
        self.assertNotIn("dummy-qa-cookie", repr(cookie_report))
        self.assertTrue(report["ok"])
        self.assertTrue(report["read_only"])
        self.assertIn("read_only_observation", report["checks"])
        self.assertEqual(run_called, [])
        self.assertEqual(report["history"], [])
        self.assertEqual(report["decisions"], [])

    def test_delayed_boundary_failure_after_agent_exit_is_not_pass(self):
        class LateBoundary:
            failed = False
            def raise_if_failed(self):
                if self.failed:
                    raise JevError("blocked read-only write during shutdown")
        boundary = LateBoundary()
        class FakeBrowser:
            _qa_boundary = boundary
            def evaluate(self, expression):
                if expression == "location.href":
                    return "https://qa.example.test/app"
                return "Склад"
        class FakeAgent:
            def __init__(self, url, goal, record_dir=None, screenshots=False):
                self.browser = FakeBrowser()
                self.url = url
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                boundary.failed = True
            def snapshot(self):
                return {"status": "observed", "page": {"url": self.url}, "history": [], "decisions": []}
            def run(self):
                raise AssertionError("read-only must not perform actions")

        with tempfile.TemporaryDirectory() as evidence, patch.dict(
            os.environ,
            {"QA_ENVIRONMENT": "qa", "QA_BASE_URL": "https://qa.example.test/app",
             "QA_ALLOWED_ORIGIN": "https://qa.example.test"},
            clear=True,
        ), patch.dict(
            sys.modules, {"jev_ultrafast": SimpleNamespace(Agent=FakeAgent)},
        ), patch("dev_control.browser_worker.run.install_safe_browser"):
            result = execute_task(
                url="https://qa.example.test/app", goal="observe menu",
                record_dir=evidence, read_only=True, expect_text=["Склад"],
                expect_url_contains=["qa.example.test"], max_seconds=5,
            )
        self.assertFalse(result["ok"])
        self.assertTrue(any("during shutdown" in f for f in result["failures"]))

    def test_only_exact_https_qa_allowlist_is_accepted(self):
        from dev_control.browser_worker.network_guard import qa_base_is_nonproduction
        base = "https://qa.example.test/app"
        for allowed in ("http://qa.example.test", "ftp://qa.example.test",
                        "https://qa.example.test:0", "https://qa.example.test:444",
                        "https://other.example.test"):
            with self.subTest(allowed=allowed), patch.dict(os.environ, {
                "QA_ALLOWED_ORIGIN": allowed, "QA_ENVIRONMENT": "qa",
                "QA_BASE_URL": base,
            }, clear=True):
                self.assertFalse(qa_base_is_nonproduction())
        with patch.dict(os.environ, {
            "QA_ALLOWED_ORIGIN": "https://qa.example.test", "QA_ENVIRONMENT": "qa",
            "QA_BASE_URL": base,
        }, clear=True):
            self.assertTrue(qa_base_is_nonproduction())

    def test_boundary_shutdown_without_thread_exit_fails_closed(self):
        guard = NetworkBoundary.__new__(NetworkBoundary)
        guard._stop = threading.Event()
        guard._thread_started = True
        guard._thread = Mock()
        guard._thread.is_alive.return_value = True
        guard._error = None
        guard._child_targets = set()
        guard._cdp = Mock()
        guard._session_id = "root"
        guard.close()
        with self.assertRaisesRegex(JevError, "did not stop cleanly"):
            guard.raise_if_failed()

    def test_read_only_live_url_overrides_stale_cached_snapshot(self):
        class FakeBrowser:
            _qa_boundary = None
            def evaluate(self, expression):
                if expression == "location.href":
                    return "https://qa.example.test/login"
                return "Login page"

        agent = SimpleNamespace(browser=FakeBrowser())
        state = {
            "status": "observed",
            "page": {"url": "https://qa.example.test/app", "text": "Склад"},
            "history": [],
            "decisions": [],
        }
        refreshed = _refresh_live_observation(
            agent, state, "https://qa.example.test"
        )
        self.assertEqual(refreshed["page"]["url"], "https://qa.example.test/login")
        self.assertEqual(refreshed["page"]["full_text"], "Login page")

    def test_live_observation_fails_closed_on_boundary_error_before_pass(self):
        class Boundary:
            def raise_if_failed(self):
                raise JevError("blocked out-of-scope browser request")

        class FakeBrowser:
            _qa_boundary = Boundary()
            def evaluate(self, _expression):
                return "https://qa.example.test/app"

        agent = SimpleNamespace(browser=FakeBrowser())
        state = {"status": "observed", "page": {}, "history": [], "decisions": []}
        with self.assertRaisesRegex(JevError, "blocked out-of-scope"):
            _refresh_live_observation(agent, state, "https://qa.example.test")

    def test_qa_alert_is_acknowledged_and_stops_unsafe_retry(self):
        guard = NetworkBoundary.__new__(NetworkBoundary)
        guard._cdp = Mock()
        guard._session_id = "root"
        guard._guarded_sessions = {"root"}
        guard._error = None
        guard._handle_javascript_dialog({
            "method": "Page.javascriptDialogOpening",
            "session_id": "root",
            "params": {"type": "alert", "message": "private error detail"},
        })
        guard._cdp.assert_called_once_with(
            "Page.handleJavaScriptDialog", session_id="root", accept=True,
        )
        self.assertIn("alert observed", guard._error)
        self.assertNotIn("private error detail", guard._error)

    def test_confirm_prompt_and_beforeunload_are_never_approved(self):
        for kind in ("confirm", "prompt", "beforeunload"):
            with self.subTest(kind=kind):
                guard = NetworkBoundary.__new__(NetworkBoundary)
                guard._cdp = Mock()
                guard._session_id = "root"
                guard._guarded_sessions = {"root"}
                guard._error = None
                guard._handle_javascript_dialog({
                    "session_id": "root", "params": {"type": kind},
                })
                guard._cdp.assert_called_once_with(
                    "Page.handleJavaScriptDialog", session_id="root", accept=False,
                )
                self.assertIn("without approval", guard._error)

    def test_dialog_from_unguarded_session_fails_closed(self):
        guard = NetworkBoundary.__new__(NetworkBoundary)
        guard._cdp = Mock()
        guard._session_id = "root"
        guard._guarded_sessions = {"root"}
        guard._error = None
        guard._handle_javascript_dialog({
            "session_id": "foreign", "params": {"type": "alert"},
        })
        guard._cdp.assert_not_called()
        self.assertIn("unguarded", guard._error)



    def test_page_domain_is_enabled_for_dialog_events(self):
        guard = NetworkBoundary.__new__(NetworkBoundary)
        guard._cdp = Mock(return_value={})
        guard._session_id = "root"
        guard._guarded_sessions = set()
        guard._enable_session("root", "page")
        methods = [call.args[0] for call in guard._cdp.call_args_list]
        self.assertIn("Page.enable", methods)
        self.assertLess(methods.index("Page.enable"), methods.index("Page.addScriptToEvaluateOnNewDocument"))
        self.assertIn("root", guard._guarded_sessions)



if __name__ == "__main__":
    unittest.main()
