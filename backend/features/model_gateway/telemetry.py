"""Privacy-safe structured measurements for provider gateway calls."""

import json
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    from backend.features.model_gateway.policies import MODEL_CAPABILITIES
except ModuleNotFoundError:
    from features.model_gateway.policies import MODEL_CAPABILITIES


_EVENT_NAME = "model_gateway_call"
_PROVIDERS = frozenset({"yandex_cloud"})
_OUTCOMES = frozenset({
    "success",
    "invalid_response",
    "deadline",
    "cancelled",
    "provider_unavailable",
    "provider_error",
})
MODEL_GATEWAY_TELEMETRY_MODELS = frozenset({
    "qwen3.6-35b-a3b/latest",
    "yandexgpt-5.1/latest",
    "yandexgpt-lite/latest",
})
_CORRELATION_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MAX_DURATION_MS = 3_600_000
_MAX_TOKENS = 10_000_000


def new_model_gateway_correlation_id():
    return secrets.token_hex(16)


def safe_model_gateway_correlation_id(value):
    if type(value) is str and _CORRELATION_ID_RE.fullmatch(value):
        return value
    return new_model_gateway_correlation_id()


def _bounded_duration(value):
    if type(value) is not int:
        return 0
    return min(_MAX_DURATION_MS, max(0, value))


def _duration_bucket(duration_ms):
    if duration_ms <= 1_000:
        return "le1s"
    if duration_ms <= 5_000:
        return "le5s"
    if duration_ms <= 15_000:
        return "le15s"
    if duration_ms <= 35_000:
        return "le35s"
    if duration_ms <= 120_000:
        return "le120s"
    return "gt120s"


def _measured_tokens(input_tokens, output_tokens, total_tokens):
    values = (input_tokens, output_tokens, total_tokens)
    if any(
        type(value) is not int or not 0 <= value <= _MAX_TOKENS
        for value in values
    ):
        return None
    if input_tokens + output_tokens != total_tokens:
        return None
    return values


def _safe_timestamp(value):
    if type(value) is str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.utcoffset() == timedelta(0):
                return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat()


def build_model_gateway_event(
    *,
    capability,
    provider,
    model,
    outcome,
    duration_ms,
    input_tokens=None,
    output_tokens=None,
    total_tokens=None,
    correlation_id=None,
    timestamp=None,
):
    """Build one closed metadata record without accepting business payloads."""
    if capability not in MODEL_CAPABILITIES:
        raise ValueError("model gateway telemetry capability is invalid")
    if provider not in _PROVIDERS:
        raise ValueError("model gateway telemetry provider is invalid")
    if outcome not in _OUTCOMES:
        raise ValueError("model gateway telemetry outcome is invalid")
    if model is not None and model not in MODEL_GATEWAY_TELEMETRY_MODELS:
        raise ValueError("model gateway telemetry model is invalid")

    duration_ms = _bounded_duration(duration_ms)
    record = {
        "timestamp": _safe_timestamp(timestamp),
        "event": _EVENT_NAME,
        "correlationId": safe_model_gateway_correlation_id(correlation_id),
        "capability": capability,
        "provider": provider,
        "outcome": outcome,
        "durationMs": duration_ms,
        "durationBucket": _duration_bucket(duration_ms),
        "tokenUsageState": "unavailable",
        "costState": "unpriced",
    }
    if model is not None:
        record["model"] = model

    tokens = _measured_tokens(input_tokens, output_tokens, total_tokens)
    if tokens is not None:
        record.update({
            "tokenUsageState": "measured",
            "inputTokens": tokens[0],
            "outputTokens": tokens[1],
            "totalTokens": tokens[2],
        })
    return record


def emit_model_gateway_event(*, stream=None, **fields):
    output = stream or sys.stdout
    record = build_model_gateway_event(**fields)
    output.write(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    output.flush()
