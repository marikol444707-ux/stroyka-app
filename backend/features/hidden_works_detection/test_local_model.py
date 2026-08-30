import json
import unittest
from pathlib import Path
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
    _large_estimate_candidate_names,
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
                        "content": '{"hidden":[0]}',
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
                            "type": "integer",
                            "enum": [0, 1],
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
        self.assertIn('"id": 0', body["messages"][1]["content"])
        self.assertIn('{"hidden": [0, 2]}', body["messages"][1]["content"])
        self.assertEqual(kwargs, {
            "authorization": "Bearer " + "a" * 32,
            "timeout_seconds": 60,
            "max_response_bytes": 128 * 1024,
        })

    def test_index_response_rejects_duplicates_and_unknown_positions(self):
        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
        }
        invalid_outputs = (
            '{"hidden":[0,0]}',
            '{"hidden":[2]}',
            '{"hidden":[true]}',
            '{"hidden":["0"]}',
        )
        with patch.dict("os.environ", environment, clear=True):
            for output in invalid_outputs:
                with self.subTest(output=output):
                    with self.assertRaises(LocalHiddenWorksModelError) as caught:
                        generate_local_hidden_works(
                            ("Армирование", "Окраска"),
                            post_json=lambda *_args, output=output, **_kwargs: {
                                "choices": [{"message": {"content": output}}],
                            },
                        )
                    self.assertEqual(
                        caught.exception.code,
                        LOCAL_MODEL_RESPONSE_INVALID,
                    )

    def test_large_estimate_sends_only_plausible_hidden_work_candidates(self):
        calls = []
        names = tuple(
            [f"Окраска открытой поверхности {position}" for position in range(132)]
            + [
                "Армирование монолитной плиты",
                "Монтаж вентиляционной решётки",
                "Прокладка кабеля в штробе",
            ]
        )

        def post_json(_url, body, **_kwargs):
            calls.append(body)
            return {
                "choices": [{
                    "message": {"content": '{"hidden":[0,2]}'},
                }],
            }

        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
        }
        with patch.dict("os.environ", environment, clear=True):
            output = generate_local_hidden_works(names, post_json=post_json)

        self.assertEqual(json.loads(output), {
            "hidden": [
                "Армирование монолитной плиты",
                "Прокладка кабеля в штробе",
            ],
        })
        self.assertEqual(len(calls), 1)
        prompt = calls[0]["messages"][1]["content"]
        self.assertIn("Армирование монолитной плиты", prompt)
        self.assertIn("Монтаж вентиляционной решётки", prompt)
        self.assertIn("Прокладка кабеля в штробе", prompt)
        self.assertNotIn("Окраска открытой поверхности", prompt)
        self.assertEqual(
            calls[0]["response_format"]["schema"]["properties"]
            ["hidden"]["items"]["enum"],
            [0, 1, 2],
        )

    def test_large_candidate_set_is_batched_and_merged_in_source_order(self):
        names = tuple(
            f"Прокладка кабеля в штробе, участок {position}"
            for position in range(45)
        )
        calls = []

        def post_json(_url, body, **_kwargs):
            calls.append(body)
            batch_size = len(
                body["response_format"]["schema"]["properties"]
                ["hidden"]["items"]["enum"],
            )
            selected = list(range(0, batch_size, 2))
            return {
                "choices": [{
                    "message": {
                        "content": json.dumps({"hidden": selected}),
                    },
                }],
            }

        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
        }
        with patch.dict("os.environ", environment, clear=True):
            output = generate_local_hidden_works(names, post_json=post_json)

        self.assertGreater(len(calls), 1)
        self.assertTrue(all(
            len(
                body["response_format"]["schema"]["properties"]
                ["hidden"]["items"]["enum"],
            ) <= 20
            for body in calls
        ))
        self.assertTrue(all(
            len(body["messages"][1]["content"].encode("utf-8"))
            <= 6 * 1024
            for body in calls
        ))
        expected = []
        offset = 0
        for body in calls:
            batch_size = len(
                body["response_format"]["schema"]["properties"]
                ["hidden"]["items"]["enum"],
            )
            expected.extend(names[offset:offset + batch_size:2])
            offset += batch_size
        self.assertEqual(json.loads(output), {"hidden": expected})

    def test_batch_failure_discards_every_partial_model_result(self):
        names = tuple(
            f"Прокладка кабеля в штробе, участок {position}"
            for position in range(25)
        )
        call_count = 0

        def post_json(_url, _body, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "choices": [{
                        "message": {"content": '{"hidden":[0]}'},
                    }],
                }
            raise RuntimeError("PRIVATE provider failure")

        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
        }
        with patch.dict("os.environ", environment, clear=True):
            with self.assertRaises(LocalHiddenWorksModelError) as caught:
                generate_local_hidden_works(names, post_json=post_json)

        self.assertEqual(call_count, 2)
        self.assertEqual(caught.exception.code, LOCAL_MODEL_TRANSPORT_FAILED)
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_too_many_model_batches_fail_closed_before_network_access(self):
        names = tuple(
            f"Прокладка кабеля в штробе, длинный участок {position}"
            for position in range(100)
        )
        called = False

        def post_json(_url, _body, **_kwargs):
            nonlocal called
            called = True
            return {
                "choices": [{"message": {"content": '{"hidden":[]}'}}],
            }

        environment = {
            LOCAL_MODEL_PORT: "18080",
            LOCAL_MODEL_API_KEY: "a" * 32,
        }
        with patch.dict("os.environ", environment, clear=True):
            with self.assertRaises(LocalHiddenWorksModelError) as caught:
                generate_local_hidden_works(names, post_json=post_json)

        self.assertFalse(called)
        self.assertEqual(caught.exception.code, LOCAL_MODEL_RESPONSE_INVALID)

    def test_large_estimate_prefilter_keeps_all_non_holdout_hidden_examples(self):
        root = Path(__file__).resolve().parents[1] / "model_gateway" / "evaluation_sets"
        for filename in (
            "hidden_works_detection.v1.json",
            "hidden_works_detection.tuning.v1.json",
            "hidden_works_detection.tuning.v2.json",
        ):
            document = json.loads((root / filename).read_text(encoding="utf-8"))
            for case in document["cases"]:
                expected = set(case["expectedHiddenIds"])
                works = case["works"]
                selected = set(_large_estimate_candidate_names(
                    tuple(work["name"] for work in works),
                ))
                missing = [
                    work["name"]
                    for work in works
                    if work["id"] in expected and work["name"] not in selected
                ]
                self.assertEqual(missing, [], f"{filename}:{case['id']}")

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
