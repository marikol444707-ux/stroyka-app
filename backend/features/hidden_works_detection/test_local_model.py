import unittest
from unittest.mock import patch

from backend.features.hidden_works_detection.local_model import (
    LOCAL_MODEL_API_KEY,
    LOCAL_MODEL_CONFIG_INVALID,
    LOCAL_MODEL_PORT,
    LOCAL_MODEL_RESPONSE_INVALID,
    LOCAL_MODEL_TRANSPORT_FAILED,
    LocalHiddenWorksModelError,
    _RejectRedirect,
    _post_local_json,
    generate_local_hidden_works,
)


class HiddenWorksLocalModelTest(unittest.TestCase):
    def test_http_boundary_disables_proxies_redirects_and_bounds_reads(self):
        self.assertIsNone(_RejectRedirect().redirect_request(
            None,
            None,
            302,
            "redirect",
            {},
            "http://attacker.invalid",
        ))

        captured_handlers = []

        class FakeResponse:
            status = 200
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, limit):
                self.limit = limit
                return b"x" * limit

        response = FakeResponse()

        class FakeOpener:
            def open(self, _request, timeout):
                self.timeout = timeout
                return response

        def build_opener(*handlers):
            captured_handlers.extend(handlers)
            return FakeOpener()

        with patch(
            "backend.features.hidden_works_detection.local_model.urllib.request.build_opener",
            build_opener,
        ):
            with self.assertRaises(LocalHiddenWorksModelError) as caught:
                _post_local_json(
                    "http://127.0.0.1:18080/v1/chat/completions",
                    {},
                    authorization="Bearer " + "a" * 32,
                    timeout_seconds=20,
                    max_response_bytes=8,
                )

        self.assertEqual(caught.exception.code, LOCAL_MODEL_RESPONSE_INVALID)
        self.assertEqual(response.limit, 9)
        proxy_handler = captured_handlers[0]
        self.assertEqual(proxy_handler.proxies, {})
        self.assertIs(captured_handlers[1], _RejectRedirect)

    def test_request_uses_only_fixed_loopback_and_the_accepted_model_contract(self):
        calls = []

        def post_json(url, body, **kwargs):
            calls.append((url, body, kwargs))
            return {
                "choices": [{
                    "message": {
                        "content": '{"hidden":["Армирование основания"]}',
                    },
                }],
            }

        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
            "HIDDEN_WORKS_LOCAL_MODEL_URL": "https://attacker.invalid",
        }
        with patch.dict("os.environ", environment, clear=True):
            output = generate_local_hidden_works(
                ("Армирование основания", "Окраска поверхности"),
                post_json=post_json,
            )

        self.assertEqual(output, '{"hidden":["Армирование основания"]}')
        self.assertEqual(len(calls), 1)
        url, body, kwargs = calls[0]
        self.assertEqual(
            url,
            "http://127.0.0.1:18080/v1/chat/completions",
        )
        self.assertNotIn("attacker", url)
        self.assertEqual(body["model"], "qwen3-4b-q4-k-m")
        self.assertEqual(body["temperature"], 0.1)
        self.assertEqual(body["max_tokens"], 128)
        self.assertEqual(body["reasoning_effort"], "none")
        self.assertEqual(body["response_format"], {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "hidden": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "Армирование основания",
                                "Окраска поверхности",
                            ],
                        },
                        "maxItems": 2,
                    },
                },
                "required": ["hidden"],
                "additionalProperties": False,
            },
        })
        self.assertEqual(body["chat_template_kwargs"], {
            "enable_thinking": False,
        })
        self.assertFalse(body["stream"])
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][1]["role"], "user")
        self.assertIn("Армирование основания", body["messages"][1]["content"])
        self.assertEqual(kwargs, {
            "authorization": "Bearer " + "a" * 32,
            "timeout_seconds": 20,
            "max_response_bytes": 128 * 1024,
        })

    def test_configuration_is_strict_and_fails_closed(self):
        invalid_environments = (
            {},
            {LOCAL_MODEL_PORT: "18080"},
            {LOCAL_MODEL_API_KEY: "a" * 32},
            {LOCAL_MODEL_PORT: "08080", LOCAL_MODEL_API_KEY: "a" * 32},
            {LOCAL_MODEL_PORT: "80", LOCAL_MODEL_API_KEY: "a" * 32},
            {LOCAL_MODEL_PORT: "65536", LOCAL_MODEL_API_KEY: "a" * 32},
            {LOCAL_MODEL_PORT: "abc", LOCAL_MODEL_API_KEY: "a" * 32},
            {LOCAL_MODEL_PORT: "18080", LOCAL_MODEL_API_KEY: "short"},
            {LOCAL_MODEL_PORT: "18080", LOCAL_MODEL_API_KEY: "a key" * 8},
        )
        for environment in invalid_environments:
            with self.subTest(environment=environment):
                with patch.dict("os.environ", environment, clear=True):
                    with self.assertRaises(LocalHiddenWorksModelError) as caught:
                        generate_local_hidden_works(
                            ("Армирование",),
                            post_json=lambda *_args, **_kwargs: {},
                        )
                self.assertEqual(caught.exception.code, LOCAL_MODEL_CONFIG_INVALID)

    def test_transport_and_response_failures_use_fixed_non_leaking_codes(self):
        private = "PRIVATE api-key and provider payload"
        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
        }
        cases = (
            (
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError(private),
                ),
                LOCAL_MODEL_TRANSPORT_FAILED,
            ),
            (lambda *_args, **_kwargs: {}, LOCAL_MODEL_RESPONSE_INVALID),
            (
                lambda *_args, **_kwargs: {"choices": []},
                LOCAL_MODEL_RESPONSE_INVALID,
            ),
            (
                lambda *_args, **_kwargs: {
                    "choices": [{"message": {"content": None}}],
                },
                LOCAL_MODEL_RESPONSE_INVALID,
            ),
            (
                lambda *_args, **_kwargs: {
                    "choices": [{
                        "message": {"content": "x" * (64 * 1024 + 1)},
                    }],
                },
                LOCAL_MODEL_RESPONSE_INVALID,
            ),
        )
        with patch.dict("os.environ", environment, clear=True):
            for post_json, expected_code in cases:
                with self.subTest(expected_code=expected_code):
                    with self.assertRaises(LocalHiddenWorksModelError) as caught:
                        generate_local_hidden_works(
                            ("Армирование",),
                            post_json=post_json,
                        )
                    self.assertEqual(caught.exception.code, expected_code)
                    self.assertNotIn(private, str(caught.exception))


if __name__ == "__main__":
    unittest.main()
