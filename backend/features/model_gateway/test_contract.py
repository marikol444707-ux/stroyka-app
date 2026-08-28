import math
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from backend.features.model_gateway.contract import (
    MODEL_GATEWAY_CANCELLED,
    MODEL_GATEWAY_CONTRACT_INVALID,
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    MODEL_GATEWAY_EMPTY_OUTPUT,
    MODEL_GATEWAY_PROVIDER_FAILED,
    MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
    ModelGatewayError,
    ModelInputPart,
    build_model_request,
    build_model_result,
)
from backend.features.model_gateway.inventory import (
    run_model_access_inventory,
    scan_model_access_sources,
)
from backend.features.model_gateway.policies import MODEL_CAPABILITIES


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class ModelGatewayContractTest(unittest.TestCase):
    def test_capabilities_are_closed_and_cover_current_logical_flows(self):
        self.assertEqual(len(MODEL_CAPABILITIES), 20)
        self.assertEqual(
            set(MODEL_CAPABILITIES),
            {
                "ai_chat",
                "cable_journal_suggestion",
                "director_agent",
                "document_recognition",
                "estimate_change_price",
                "estimate_chat",
                "estimate_distribution",
                "estimate_generation",
                "hidden_works_act_prefill",
                "hidden_works_detection",
                "invoice_scan",
                "material_inspection_suggestion",
                "material_norm_suggestion",
                "platform_client_card",
                "pricelist_generation",
                "project_room_draft",
                "supply_delivery_check",
                "supply_kp_comparison",
                "tb_instruction",
                "work_journal_prefill",
            },
        )
        with self.assertRaises(TypeError):
            MODEL_CAPABILITIES["new_dynamic_capability"] = object()

    def test_text_request_is_immutable_and_provider_neutral(self):
        request = build_model_request(
            capability="estimate_chat",
            instructions="Answer using the supplied project facts.",
            input_text="Summarize the current estimate.",
            temperature=0.1,
            max_output_tokens=1200,
            deadline_seconds=30,
        )

        self.assertEqual(request.capability, "estimate_chat")
        self.assertEqual(request.input_parts, ())
        self.assertNotIn("provider", request.__dataclass_fields__)
        self.assertNotIn("model", request.__dataclass_fields__)
        self.assertNotIn("api_key", request.__dataclass_fields__)
        with self.assertRaises(FrozenInstanceError):
            request.input_text = "changed"

    def test_multipart_request_is_bounded_and_immutable(self):
        parts = (
            ModelInputPart(kind="text", value="Read the attached invoice."),
            ModelInputPart(
                kind="image_data_url",
                value="data:image/jpeg;base64,YWJj",
            ),
            ModelInputPart(kind="file_id", value="file-123"),
        )

        request = build_model_request(
            capability="invoice_scan",
            instructions="Return the established invoice JSON shape.",
            input_parts=parts,
            temperature=0.1,
            max_output_tokens=2500,
            deadline_seconds=60,
        )

        self.assertEqual(request.input_text, "")
        self.assertEqual(request.input_parts, parts)
        with self.assertRaises(FrozenInstanceError):
            parts[0].value = "changed"

    def test_request_rejects_untrusted_capability_and_invalid_bounds(self):
        invalid_values = (
            {"capability": "arbitrary-provider/model"},
            {"input_text": ""},
            {"input_text": "x", "input_parts": (ModelInputPart("text", "x"),)},
            {"temperature": math.nan},
            {"temperature": 1.1},
            {"max_output_tokens": True},
            {"max_output_tokens": 0},
            {"deadline_seconds": 0},
            {"instructions": "x" * 65_537},
        )
        base = {
            "capability": "estimate_chat",
            "instructions": "instructions",
            "input_text": "input",
            "temperature": 0.1,
            "max_output_tokens": 100,
            "deadline_seconds": 30,
        }

        for change in invalid_values:
            with self.subTest(change=change):
                values = dict(base)
                values.update(change)
                with self.assertRaises(ModelGatewayError) as raised:
                    build_model_request(**values)
                self.assertEqual(raised.exception.code, MODEL_GATEWAY_CONTRACT_INVALID)
                self.assertEqual(str(raised.exception), MODEL_GATEWAY_CONTRACT_INVALID)

    def test_input_parts_reject_unknown_kind_and_oversized_value(self):
        for part in (
            ModelInputPart(kind="provider_url", value="https://example.test"),
            ModelInputPart(kind="text", value="x" * (4 * 1024 * 1024 + 1)),
        ):
            with self.subTest(part=part.kind):
                with self.assertRaises(ModelGatewayError) as raised:
                    build_model_request(
                        capability="invoice_scan",
                        instructions="instructions",
                        input_parts=(part,),
                        temperature=0.1,
                        max_output_tokens=100,
                        deadline_seconds=30,
                    )
                self.assertEqual(raised.exception.code, MODEL_GATEWAY_CONTRACT_INVALID)

    def test_provider_result_is_detached_bounded_and_secret_free(self):
        result = build_model_result(
            provider="yandex_cloud",
            model="yandexgpt-5.1/latest",
            output_text="done",
            duration_ms=125,
        )

        self.assertEqual(result.output_text, "done")
        self.assertEqual(result.provider, "yandex_cloud")
        self.assertEqual(result.model, "yandexgpt-5.1/latest")
        self.assertEqual(result.duration_ms, 125)
        self.assertNotIn("raw_response", result.__dataclass_fields__)
        with self.assertRaises(FrozenInstanceError):
            result.output_text = "changed"

        for output in ("", "x" * (4 * 1024 * 1024 + 1)):
            with self.subTest(output_size=len(output)):
                with self.assertRaises(ModelGatewayError) as raised:
                    build_model_result(
                        provider="yandex_cloud",
                        model="yandexgpt-5.1/latest",
                        output_text=output,
                        duration_ms=1,
                    )
                self.assertEqual(raised.exception.code, MODEL_GATEWAY_EMPTY_OUTPUT)

    def test_runtime_failure_codes_are_fixed_and_non_leaking(self):
        codes = (
            MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
            MODEL_GATEWAY_PROVIDER_FAILED,
            MODEL_GATEWAY_EMPTY_OUTPUT,
            MODEL_GATEWAY_DEADLINE_EXCEEDED,
            MODEL_GATEWAY_CANCELLED,
        )
        for code in codes:
            with self.subTest(code=code):
                error = ModelGatewayError(code)
                self.assertEqual(error.code, code)
                self.assertEqual(str(error), code)
                self.assertFalse(hasattr(error, "details"))
        with self.assertRaises(ValueError):
            ModelGatewayError("provider secret sk-private-value")


class ModelAccessInventoryTest(unittest.TestCase):
    def test_current_direct_access_is_exact_and_read_only(self):
        report = run_model_access_inventory(REPOSITORY_ROOT)

        self.assertTrue(report["complete"])
        self.assertEqual(report["logicalCapabilityCount"], 20)
        self.assertEqual(report["directAccessCount"], 30)
        self.assertEqual(report["unexpected"], [])
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["writesAttempted"], 0)
        self.assertEqual(
            len({item["capability"] for item in report["accessPoints"]}),
            20,
        )

    def test_new_direct_provider_access_fails_the_inventory(self):
        sources = {
            "backend/features/new_feature/routes.py": (
                "def call_model():\n"
                "    import openai\n"
                "    client = openai.OpenAI(\n"
                "        api_key='secret',\n"
                "        base_url='https://ai.api.cloud.yandex.net/v1',\n"
                "    )\n"
                "    return client.responses.create(input='x')\n"
            ),
        }

        report = scan_model_access_sources(sources)

        self.assertFalse(report["complete"])
        self.assertEqual(report["missing"], [])
        self.assertEqual(len(report["unexpected"]), 1)
        self.assertEqual(
            report["unexpected"][0]["symbol"],
            "call_model",
        )
        rendered = repr(report)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("api_key", rendered)
        self.assertNotIn("input='x'", rendered)

    def test_provider_url_constant_is_detected_without_flagging_other_http(self):
        provider_report = scan_model_access_sources({
            "backend/provider_http.py": (
                "import urllib.request\n"
                "MODEL_URL = 'https://api.anthropic.com/v1/messages'\n"
                "def call_model():\n"
                "    return urllib.request.urlopen(MODEL_URL)\n"
            ),
        })
        ordinary_report = scan_model_access_sources({
            "backend/ordinary_http.py": (
                "import urllib.request\n"
                "UPLOAD_URL = 'https://storage.example.test/upload'\n"
                "def upload():\n"
                "    return urllib.request.urlopen(UPLOAD_URL)\n"
            ),
        })

        self.assertFalse(provider_report["complete"])
        self.assertEqual(
            provider_report["unexpected"],
            [{"file": "backend/provider_http.py", "symbol": "call_model"}],
        )
        self.assertTrue(ordinary_report["complete"])
        self.assertEqual(ordinary_report["unexpected"], [])

    def test_module_level_provider_client_is_detected(self):
        report = scan_model_access_sources({
            "backend/module_client.py": (
                "import openai\n"
                "client = openai.OpenAI(api_key='secret')\n"
            ),
        })

        self.assertFalse(report["complete"])
        self.assertEqual(
            report["unexpected"],
            [{"file": "backend/module_client.py", "symbol": "<module>"}],
        )
        self.assertNotIn("secret", repr(report))

    def test_inventory_does_not_modify_source_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "backend" / "feature.py"
            source.parent.mkdir(parents=True)
            source.write_text("def safe():\n    return 1\n", encoding="utf-8")
            before = source.read_bytes()

            report = run_model_access_inventory(root)

            self.assertFalse(report["complete"])
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(report["writesAttempted"], 0)


if __name__ == "__main__":
    unittest.main()
