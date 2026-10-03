import unittest

from dev_control.browser_worker.network_guard import request_allowed
from dev_control.browser_worker.run import _assert_allowed_url, _sanitize_history


class BrowserWorkerUrlSafetyTest(unittest.TestCase):
    def test_allows_same_origin_and_base_path(self):
        _assert_allowed_url(
            "https://qa.example.test/app/warehouse",
            "https://qa.example.test/app",
        )

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
    def test_rejects_non_http_scheme(self):
        with self.assertRaisesRegex(ValueError, "http"):
            _assert_allowed_url(
                "file:///etc/passwd",
                "https://qa.example.test",
            )


if __name__ == "__main__":
    unittest.main()
