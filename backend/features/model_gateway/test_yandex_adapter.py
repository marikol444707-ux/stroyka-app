import asyncio
import unittest
from types import SimpleNamespace

from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_CANCELLED,
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    MODEL_GATEWAY_EMPTY_OUTPUT,
    MODEL_GATEWAY_PROVIDER_FAILED,
    MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
    ModelGatewayError,
    ModelInputPart,
    build_model_request,
)
from backend.features.model_gateway.policies import MODEL_CAPABILITIES
from backend.features.model_gateway.yandex_adapter import (
    YANDEX_CAPABILITY_MODELS,
    YANDEX_OPENAI_BASE_URL,
    build_yandex_model_adapter,
)


class FakeResponses:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **values):
        self.calls.append(values)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if hasattr(outcome, "output_text"):
            return outcome
        return SimpleNamespace(output_text=outcome)


class FakeClient:
    def __init__(self, outcomes):
        self.responses = FakeResponses(outcomes)


def clock_from(*values):
    remaining = list(values)
    return lambda: remaining.pop(0)


class YandexModelAdapterTest(unittest.TestCase):
    def test_success_emits_safe_per_capability_usage_measurement(self):
        events = []
        response = SimpleNamespace(
            output_text="PRIVATE MODEL OUTPUT",
            usage=SimpleNamespace(
                input_tokens=430,
                output_tokens=70,
                total_tokens=500,
            ),
        )
        adapter = build_yandex_model_adapter(
            api_key="private-test-key",
            folder_id="folder-1",
            client_factory=lambda **_values: FakeClient([response]),
            clock=clock_from(10.0, 10.0, 11.25),
            telemetry_sink=lambda **fields: events.append(fields),
            correlation_id_factory=(
                lambda: "0123456789abcdef0123456789abcdef"
            ),
        )
        request = build_model_request(
            capability="hidden_works_detection",
            instructions="PRIVATE INSTRUCTIONS",
            input_text="PRIVATE ESTIMATE",
            temperature=0.1,
            max_output_tokens=2_000,
            deadline_seconds=30,
        )

        result = adapter.generate(request)

        self.assertEqual(result.output_text, "PRIVATE MODEL OUTPUT")
        self.assertEqual(events, [{
            "capability": "hidden_works_detection",
            "provider": "yandex_cloud",
            "model": "yandexgpt-5.1/latest",
            "outcome": "success",
            "duration_ms": 1250,
            "input_tokens": 430,
            "output_tokens": 70,
            "total_tokens": 500,
            "correlation_id": "0123456789abcdef0123456789abcdef",
        }])
        self.assertNotIn("PRIVATE", repr(events))

    def test_invalid_response_emits_fixed_failure_without_raw_details(self):
        events = []
        adapter = build_yandex_model_adapter(
            api_key="key",
            folder_id="folder-1",
            client_factory=lambda **_values: FakeClient([
                SimpleNamespace(
                    output_text="",
                    usage={"input_tokens": "PRIVATE"},
                ),
            ]),
            telemetry_sink=lambda **fields: events.append(fields),
            correlation_id_factory=(
                lambda: "fedcba9876543210fedcba9876543210"
            ),
        )
        request = build_model_request(
            capability="estimate_chat",
            instructions="PRIVATE INSTRUCTIONS",
            input_text="PRIVATE PROMPT",
            temperature=0.3,
            max_output_tokens=1500,
            deadline_seconds=30,
        )

        with self.assertRaises(ModelGatewayError) as raised:
            adapter.generate(request)

        self.assertEqual(raised.exception.code, MODEL_GATEWAY_EMPTY_OUTPUT)
        self.assertEqual(events[0]["outcome"], "invalid_response")
        self.assertEqual(events[0]["capability"], "estimate_chat")
        self.assertNotIn("model", events[0])
        self.assertNotIn("PRIVATE", repr(events))

    def test_measurement_failure_cannot_break_model_result(self):
        def broken_sink(**_fields):
            raise RuntimeError("telemetry unavailable PRIVATE")

        adapter = build_yandex_model_adapter(
            api_key="key",
            folder_id="folder-1",
            client_factory=lambda **_values: FakeClient(["answer"]),
            telemetry_sink=broken_sink,
            correlation_id_factory=lambda: "PRIVATE CORRELATION",
        )
        request = build_model_request(
            capability="estimate_chat",
            instructions="instructions",
            input_text="prompt",
            temperature=0.3,
            max_output_tokens=1500,
            deadline_seconds=30,
        )

        result = adapter.generate(request)

        self.assertEqual(result.output_text, "answer")

    def test_routes_are_closed_and_cover_every_capability(self):
        self.assertEqual(
            dict(YANDEX_CAPABILITY_MODELS),
            {
                "ai_chat": (
                    "yandexgpt-5.1/latest",
                    "qwen3.6-35b-a3b/latest",
                ),
                "cable_journal_suggestion": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "director_agent": ("yandexgpt-lite/latest",),
                "document_recognition": ("yandexgpt-5.1/latest",),
                "estimate_change_price": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "estimate_chat": ("yandexgpt-5.1/latest",),
                "estimate_distribution": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "estimate_generation": ("qwen3.6-35b-a3b/latest",),
                "hidden_works_act_prefill": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "hidden_works_detection": ("yandexgpt-5.1/latest",),
                "invoice_scan": ("qwen3.6-35b-a3b/latest",),
                "material_inspection_suggestion": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "material_norm_suggestion": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "platform_client_card": ("qwen3.6-35b-a3b/latest",),
                "pricelist_generation": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
                "project_room_draft": ("qwen3.6-35b-a3b/latest",),
                "supply_delivery_check": ("yandexgpt-5.1/latest",),
                "supply_kp_comparison": ("yandexgpt-5.1/latest",),
                "tb_instruction": (
                    "yandexgpt-5.1/latest",
                    "qwen3.6-35b-a3b/latest",
                ),
                "work_journal_prefill": (
                    "qwen3.6-35b-a3b/latest",
                    "yandexgpt-5.1/latest",
                ),
            },
        )
        self.assertEqual(set(YANDEX_CAPABILITY_MODELS), set(MODEL_CAPABILITIES))
        with self.assertRaises(TypeError):
            YANDEX_CAPABILITY_MODELS["estimate_chat"] = ("other/latest",)

    def test_text_request_preserves_current_responses_arguments(self):
        client = FakeClient(["answer"])
        captured = {}

        def factory(**values):
            captured.update(values)
            return client

        adapter = build_yandex_model_adapter(
            api_key="private-test-key",
            folder_id="folder-1",
            client_factory=factory,
            clock=clock_from(10.0, 10.0, 10.125),
        )
        request = build_model_request(
            capability="estimate_chat",
            instructions="instructions",
            input_text="prompt",
            temperature=0.3,
            max_output_tokens=1500,
            deadline_seconds=30,
        )

        result = adapter.generate(request)

        self.assertEqual(
            captured,
            {
                "api_key": "private-test-key",
                "base_url": YANDEX_OPENAI_BASE_URL,
                "project": "folder-1",
            },
        )
        self.assertEqual(
            client.responses.calls,
            [{
                "model": "gpt://folder-1/yandexgpt-5.1/latest",
                "temperature": 0.3,
                "instructions": "instructions",
                "input": "prompt",
                "max_output_tokens": 1500,
                "timeout": 30.0,
            }],
        )
        self.assertEqual(result.provider, "yandex_cloud")
        self.assertEqual(result.model, "yandexgpt-5.1/latest")
        self.assertEqual(result.output_text, "answer")
        self.assertEqual(result.duration_ms, 125)
        self.assertFalse(hasattr(adapter, "api_key"))
        self.assertNotIn("private-test-key", repr(adapter))

    def test_multipart_request_maps_only_allowlisted_part_shapes(self):
        client = FakeClient(["{}"])
        adapter = build_yandex_model_adapter(
            api_key="key",
            folder_id="folder-1",
            client_factory=lambda **_values: client,
            clock=clock_from(1.0, 1.0, 1.01),
        )
        request = build_model_request(
            capability="invoice_scan",
            instructions="json only",
            input_parts=(
                ModelInputPart("image_data_url", "data:image/jpeg;base64,YWJj"),
                ModelInputPart("file_id", "file-123"),
                ModelInputPart("text", "read invoice"),
            ),
            temperature=0.1,
            max_output_tokens=12_000,
            deadline_seconds=60,
        )

        adapter.generate(request)

        self.assertEqual(
            client.responses.calls[0]["input"],
            [{
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": "data:image/jpeg;base64,YWJj",
                    },
                    {"type": "input_file", "file_id": "file-123"},
                    {"type": "input_text", "text": "read invoice"},
                ],
            }],
        )

    def test_empty_primary_uses_the_existing_fallback_order(self):
        client = FakeClient(["", "valid json"])
        adapter = build_yandex_model_adapter(
            api_key="key",
            folder_id="folder-1",
            client_factory=lambda **_values: client,
            clock=clock_from(2.0, 2.0, 2.1, 2.2),
        )
        request = build_model_request(
            capability="pricelist_generation",
            instructions="json only",
            input_text="prompt",
            temperature=0.2,
            max_output_tokens=5000,
            deadline_seconds=30,
        )

        result = adapter.generate(request)

        self.assertEqual(
            [call["model"] for call in client.responses.calls],
            [
                "gpt://folder-1/qwen3.6-35b-a3b/latest",
                "gpt://folder-1/yandexgpt-5.1/latest",
            ],
        )
        self.assertEqual(client.responses.calls[1]["timeout"], 29.9)
        self.assertEqual(result.model, "yandexgpt-5.1/latest")
        self.assertEqual(result.duration_ms, 200)

    def test_fixed_errors_do_not_leak_configuration_or_provider_details(self):
        with self.assertRaises(ModelGatewayError) as missing:
            build_yandex_model_adapter(api_key="", folder_id="folder-1")
        self.assertEqual(missing.exception.code, MODEL_GATEWAY_PROVIDER_UNAVAILABLE)

        def broken_factory(**_values):
            raise RuntimeError("provider leaked private-test-key")

        with self.assertRaises(ModelGatewayError) as unavailable:
            build_yandex_model_adapter(
                api_key="private-test-key",
                folder_id="folder-1",
                client_factory=broken_factory,
            )
        self.assertEqual(
            unavailable.exception.code,
            MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
        )
        self.assertNotIn("private-test-key", str(unavailable.exception))

        request = build_model_request(
            capability="estimate_chat",
            instructions="instructions",
            input_text="prompt",
            temperature=0.3,
            max_output_tokens=1500,
            deadline_seconds=30,
        )
        for outcome, code in (
            ([""], MODEL_GATEWAY_EMPTY_OUTPUT),
            ([RuntimeError("raw provider failure secret")], MODEL_GATEWAY_PROVIDER_FAILED),
        ):
            with self.subTest(code=code):
                adapter = build_yandex_model_adapter(
                    api_key="key",
                    folder_id="folder-1",
                    client_factory=lambda **_values: FakeClient(outcome),
                )
                with self.assertRaises(ModelGatewayError) as raised:
                    adapter.generate(request)
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("secret", str(raised.exception))

    def test_timeout_and_cancellation_have_distinct_fixed_errors(self):
        request = build_model_request(
            capability="estimate_chat",
            instructions="instructions",
            input_text="prompt",
            temperature=0.3,
            max_output_tokens=1500,
            deadline_seconds=30,
        )
        for outcome, code in (
            (TimeoutError("provider timeout details"), MODEL_GATEWAY_DEADLINE_EXCEEDED),
            (asyncio.CancelledError("cancel details"), MODEL_GATEWAY_CANCELLED),
        ):
            with self.subTest(code=code):
                adapter = build_yandex_model_adapter(
                    api_key="key",
                    folder_id="folder-1",
                    client_factory=lambda **_values: FakeClient([outcome]),
                    timeout_error_types=(TimeoutError,),
                )
                with self.assertRaises(ModelGatewayError) as raised:
                    adapter.generate(request)
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("details", str(raised.exception))

    def test_broad_timeout_type_cannot_swallow_result_validation(self):
        adapter = build_yandex_model_adapter(
            api_key="key",
            folder_id="folder-1",
            client_factory=lambda **_values: FakeClient([
                "x" * (4 * 1024 * 1024 + 1),
            ]),
            timeout_error_types=(Exception,),
        )
        request = build_model_request(
            capability="estimate_chat",
            instructions="instructions",
            input_text="prompt",
            temperature=0.3,
            max_output_tokens=1500,
            deadline_seconds=30,
        )

        with self.assertRaises(ModelGatewayError) as raised:
            adapter.generate(request)

        self.assertEqual(raised.exception.code, MODEL_GATEWAY_EMPTY_OUTPUT)

    def test_api_key_rejects_nonprinting_characters_before_client_creation(self):
        called = False

        def factory(**_values):
            nonlocal called
            called = True
            return FakeClient(["unused"])

        with self.assertRaises(ModelGatewayError) as raised:
            build_yandex_model_adapter(
                api_key="key\x7f",
                folder_id="folder-1",
                client_factory=factory,
                timeout_error_types=(TimeoutError,),
            )

        self.assertEqual(
            raised.exception.code,
            MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
        )
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
