import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.features.model_gateway import runtime
from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_PROVIDER_FAILED,
    ModelGatewayError,
)


class _Gateway:
    def __init__(self, output="answer", error=None):
        self.output = output
        self.error = error
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=self.output)


class ModelGatewayRuntimeTest(unittest.TestCase):
    def test_generate_yandex_text_builds_the_exact_neutral_request(self):
        gateway = _Gateway()
        with patch.object(
            runtime,
            "build_yandex_model_adapter",
            lambda **values: self._capture_adapter(values, gateway),
        ):
            answer = runtime.generate_yandex_text(
                capability="material_norm_suggestion",
                instructions="instructions",
                input_text="prompt",
                temperature=0.1,
                max_output_tokens=3000,
                api_key="private-key",
                folder_id="folder-1",
            )

        self.assertEqual(answer, "answer")
        self.assertEqual(
            self.adapter_values,
            {"api_key": "private-key", "folder_id": "folder-1"},
        )
        request = gateway.requests[0]
        self.assertEqual(request.capability, "material_norm_suggestion")
        self.assertEqual(request.instructions, "instructions")
        self.assertEqual(request.input_text, "prompt")
        self.assertEqual(request.temperature, 0.1)
        self.assertEqual(request.max_output_tokens, 3000)
        self.assertEqual(request.deadline_seconds, 120)

    def test_unexpected_failures_are_fixed_and_secret_safe(self):
        gateway = _Gateway(error=RuntimeError("private-key leaked"))
        with patch.object(
            runtime,
            "build_yandex_model_adapter",
            lambda **_values: gateway,
        ):
            with self.assertRaises(ModelGatewayError) as caught:
                runtime.generate_yandex_text(
                    capability="tb_instruction",
                    instructions="instructions",
                    input_text="prompt",
                    temperature=0.2,
                    max_output_tokens=2000,
                    api_key="private-key",
                    folder_id="folder-1",
                )

        self.assertEqual(caught.exception.code, MODEL_GATEWAY_PROVIDER_FAILED)
        self.assertNotIn("private-key", str(caught.exception))

    def _capture_adapter(self, values, gateway):
        self.adapter_values = values
        return gateway


if __name__ == "__main__":
    unittest.main()
