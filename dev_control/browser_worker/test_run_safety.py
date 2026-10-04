import os
import unittest
from unittest.mock import Mock, patch

from dev_control.browser_worker.network_guard import (
    DEDICATED_CDP_URL,
    assert_dedicated_loopback_cdp_url,
    bootstrap_session_cookie,
    redact_boundary_url,
    request_allowed,
)
from dev_control.browser_worker.run import _assert_allowed_url, _redact_url, _sanitize_history


class BrowserWorkerUrlSafetyTest(unittest.TestCase):
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

    def test_session_cookie_bootstrap_is_https_httponly_and_local_to_context(self):
        cdp = Mock()
        with patch.dict(
            os.environ,
            {"QA_SESSION_COOKIE_NAME": "qa_session", "QA_SESSION_COOKIE_VALUE": "session-secret"},
            clear=True,
        ):
            self.assertTrue(
                bootstrap_session_cookie(
                    "https://qa.example.test/app",
                    "context-1",
                    cdp,
                )
            )
        cdp.assert_called_once()
        args, kwargs = cdp.call_args
        self.assertEqual(args[0], "Storage.setCookies")
        self.assertEqual(kwargs["browserContextId"], "context-1")
        cookie = kwargs["cookies"][0]
        self.assertEqual(cookie["name"], "qa_session")
        self.assertEqual(cookie["value"], "session-secret")
        self.assertEqual(cookie["url"], "https://qa.example.test/")
        self.assertTrue(cookie["secure"])
        self.assertTrue(cookie["httpOnly"])
        self.assertNotIn("domain", cookie)

    def test_session_cookie_bootstrap_refuses_plain_http_and_no_cookie_is_noop(self):
        cdp = Mock()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(
                bootstrap_session_cookie(
                    "https://qa.example.test/app",
                    "context-1",
                    cdp,
                )
            )
        cdp.assert_not_called()

        with patch.dict(os.environ, {"QA_SESSION_COOKIE_VALUE": "session-secret"}, clear=True):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                bootstrap_session_cookie(
                    "http://qa.example.test/app",
                    "context-1",
                    cdp,
                )


if __name__ == "__main__":
    unittest.main()
