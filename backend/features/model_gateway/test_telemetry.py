import io
import json
import unittest

from backend.features.model_gateway.telemetry import (
    build_model_gateway_event,
    emit_model_gateway_event,
)


class ModelGatewayTelemetryTest(unittest.TestCase):
    def test_event_contains_only_bounded_operational_metadata(self):
        event = build_model_gateway_event(
            capability="hidden_works_detection",
            provider="yandex_cloud",
            model="yandexgpt-5.1/latest",
            outcome="success",
            duration_ms=1_250,
            input_tokens=430,
            output_tokens=70,
            total_tokens=500,
            correlation_id="0123456789abcdef0123456789abcdef",
            timestamp="2026-08-30T10:00:00+00:00",
        )

        self.assertEqual(event, {
            "timestamp": "2026-08-30T10:00:00+00:00",
            "event": "model_gateway_call",
            "correlationId": "0123456789abcdef0123456789abcdef",
            "capability": "hidden_works_detection",
            "provider": "yandex_cloud",
            "model": "yandexgpt-5.1/latest",
            "outcome": "success",
            "durationMs": 1250,
            "durationBucket": "le5s",
            "tokenUsageState": "measured",
            "inputTokens": 430,
            "outputTokens": 70,
            "totalTokens": 500,
            "costState": "unpriced",
        })
        rendered = json.dumps(event, sort_keys=True)
        for forbidden in (
            "prompt", "instructions", "input_text", "output_text",
            "company", "project", "user", "document", "api_key",
        ):
            self.assertNotIn(forbidden, rendered.lower())

    def test_missing_or_invalid_usage_is_reported_without_payload_details(self):
        event = build_model_gateway_event(
            capability="estimate_chat",
            provider="yandex_cloud",
            model=None,
            outcome="invalid_response",
            duration_ms=999_999_999,
            input_tokens=-1,
            output_tokens="PRIVATE RESPONSE",
            total_tokens=None,
            correlation_id="fedcba9876543210fedcba9876543210",
            timestamp="2026-08-30T10:00:00+00:00",
        )

        self.assertEqual(event["durationMs"], 3_600_000)
        self.assertEqual(event["durationBucket"], "gt120s")
        self.assertEqual(event["tokenUsageState"], "unavailable")
        self.assertEqual(event["costState"], "unpriced")
        self.assertNotIn("model", event)
        self.assertNotIn("inputTokens", event)
        self.assertNotIn("outputTokens", event)
        self.assertNotIn("totalTokens", event)
        self.assertNotIn("PRIVATE", json.dumps(event))

        with self.assertRaises(ValueError) as raised:
            build_model_gateway_event(
                capability="estimate_chat",
                provider="yandex_cloud",
                model="PRIVATE-MODEL/latest",
                outcome="success",
                duration_ms=1,
            )
        self.assertNotIn("PRIVATE", str(raised.exception))

        private_timestamp = build_model_gateway_event(
            capability="estimate_chat",
            provider="yandex_cloud",
            model=None,
            outcome="provider_error",
            duration_ms=1,
            timestamp="PRIVATE BUSINESS VALUE",
        )
        self.assertNotIn("PRIVATE", private_timestamp["timestamp"])

    def test_emitter_writes_one_compact_json_record(self):
        stream = io.StringIO()

        emit_model_gateway_event(
            stream=stream,
            capability="estimate_chat",
            provider="yandex_cloud",
            model=None,
            outcome="provider_error",
            duration_ms=25,
            correlation_id="0123456789abcdef0123456789abcdef",
            timestamp="2026-08-30T10:00:00+00:00",
        )

        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["event"], "model_gateway_call")


if __name__ == "__main__":
    unittest.main()
