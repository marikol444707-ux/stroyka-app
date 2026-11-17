"""OpenAI-compatible Yandex transport with no runtime registration."""

import asyncio
import json
import math
import re
import time
from types import MappingProxyType

try:
    from backend.features.model_gateway.contract import (
        MODEL_GATEWAY_CANCELLED,
        MODEL_GATEWAY_CONTRACT_INVALID,
        MODEL_GATEWAY_DEADLINE_EXCEEDED,
        MODEL_GATEWAY_EMPTY_OUTPUT,
        MODEL_GATEWAY_PROVIDER_FAILED,
        MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
        ModelGatewayError,
        ModelInputPart,
        ModelRequest,
        build_model_request,
        build_model_result,
    )
    from backend.features.model_gateway.policies import MODEL_CAPABILITIES
    from backend.features.model_gateway.telemetry import (
        MODEL_GATEWAY_TELEMETRY_MODELS,
        emit_model_gateway_event,
        new_model_gateway_correlation_id,
        safe_model_gateway_correlation_id,
    )
except ModuleNotFoundError:
    from features.model_gateway.contract import (
        MODEL_GATEWAY_CANCELLED,
        MODEL_GATEWAY_CONTRACT_INVALID,
        MODEL_GATEWAY_DEADLINE_EXCEEDED,
        MODEL_GATEWAY_EMPTY_OUTPUT,
        MODEL_GATEWAY_PROVIDER_FAILED,
        MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
        ModelGatewayError,
        ModelInputPart,
        ModelRequest,
        build_model_request,
        build_model_result,
    )
    from features.model_gateway.policies import MODEL_CAPABILITIES
    from features.model_gateway.telemetry import (
        MODEL_GATEWAY_TELEMETRY_MODELS,
        emit_model_gateway_event,
        new_model_gateway_correlation_id,
        safe_model_gateway_correlation_id,
    )


YANDEX_OPENAI_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_ALLOWED_MODEL_IDS = MODEL_GATEWAY_TELEMETRY_MODELS

YANDEX_CAPABILITY_MODELS = MappingProxyType({
    "ai_chat": ("yandexgpt-5.1/latest", "qwen3.6-35b-a3b/latest"),
    "ai_chat_json": ("qwen3.6-35b-a3b/latest", "yandexgpt-5.1/latest"),
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
    "platform_client_card": (
        "yandexgpt-5.1/latest",
        "qwen3.6-35b-a3b/latest",
    ),
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
})


def _error(code):
    raise ModelGatewayError(code) from None


def _validate_static_routes():
    if set(YANDEX_CAPABILITY_MODELS) != set(MODEL_CAPABILITIES):
        raise RuntimeError("Yandex model routes must cover gateway capabilities")
    for models in YANDEX_CAPABILITY_MODELS.values():
        if (
            type(models) is not tuple
            or not models
            or len(models) != len(set(models))
            or any(model not in _ALLOWED_MODEL_IDS for model in models)
        ):
            raise RuntimeError("Yandex model routes must be closed and unique")


_validate_static_routes()


def _validated_request(request):
    if type(request) is not ModelRequest:
        _error(MODEL_GATEWAY_CONTRACT_INVALID)
    return build_model_request(
        capability=request.capability,
        instructions=request.instructions,
        input_text=request.input_text,
        input_parts=request.input_parts,
        temperature=request.temperature,
        max_output_tokens=request.max_output_tokens,
        deadline_seconds=request.deadline_seconds,
    )


def _provider_input(request):
    if request.input_text:
        return request.input_text
    content = []
    for part in request.input_parts:
        if part.kind == "text":
            content.append({"type": "input_text", "text": part.value})
        elif part.kind == "image_data_url":
            content.append({
                "type": "input_image",
                "image_url": part.value,
                "detail": "auto",
            })
        elif part.kind == "file_id":
            content.append({"type": "input_file", "file_id": part.value})
        elif part.kind == "file_data_url":
            content.append({
                "type": "input_file",
                "filename": part.filename,
                "file_data": part.value,
            })
        else:
            _error(MODEL_GATEWAY_CONTRACT_INVALID)
    return [{"role": "user", "content": content}]


_INVOICE_DIAGNOSTIC_EXCEPTION_TYPES = frozenset({
    "BadRequestError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "UnprocessableEntityError",
    "RateLimitError",
    "InternalServerError",
    "APIConnectionError",
    "APITimeoutError",
    "APIStatusError",
    "APIError",
    "TypeError",
    "ValueError",
})
_INVOICE_DIAGNOSTIC_ERROR_MENTIONS = (
    "temperature",
    "max_output_tokens",
    "image_url",
    "detail",
    "model",
    "input_file",
    "file_data",
    "mime",
    "format",
    "size",
    "context_length",
)
_INVOICE_DIAGNOSTIC_OUTPUT_TYPES = frozenset({
    "message",
    "reasoning",
    "function_call",
    "web_search_call",
    "file_search_call",
    "image_generation_call",
})
_INVOICE_DIAGNOSTIC_CONTENT_TYPES = frozenset({
    "output_text",
    "text",
    "refusal",
})


def _invoice_input_counts(request):
    parts = getattr(request, "input_parts", ())
    return {
        "images": sum(getattr(part, "kind", None) == "image_data_url" for part in parts),
        "files": sum(
            getattr(part, "kind", None) in ("file_id", "file_data_url")
            for part in parts
        ),
    }


def _invoice_provider_error_diagnostic(error, request, stage):
    status_code = getattr(error, "status_code", None)
    error_name = type(error).__name__
    body = str(getattr(error, "body", ""))[:65536].lower()
    return {
        "stage": stage,
        "httpStatus": (
            status_code
            if type(status_code) is int and 400 <= status_code <= 599
            else None
        ),
        "exceptionType": (
            error_name
            if error_name in _INVOICE_DIAGNOSTIC_EXCEPTION_TYPES
            else "other"
        ),
        "mentions": [
            field for field in _INVOICE_DIAGNOSTIC_ERROR_MENTIONS if field in body
        ],
        **_invoice_input_counts(request),
    }


def _invoice_response_diagnostic(response, request):
    def response_value(value, name):
        return value.get(name) if type(value) is dict else getattr(value, name, None)

    def safe_number(value):
        return value if type(value) is int and 0 <= value <= 10_000_000 else None

    status = response_value(response, "status")
    if type(status) is not str or status not in {
        "completed", "incomplete", "failed", "in_progress", "queued", "cancelled"
    }:
        status = "other"

    incomplete_details = response_value(response, "incomplete_details")
    incomplete_reason = response_value(incomplete_details, "reason")
    if type(incomplete_reason) is not str or incomplete_reason not in {
        "max_output_tokens", "content_filter", "max_tokens", "length"
    }:
        incomplete_reason = None

    output = response_value(response, "output")
    output = output[:64] if type(output) in (list, tuple) else ()
    output_types = {}
    content_types = {}
    message_text_chars = 0
    for item in output:
        item_type = response_value(item, "type")
        if type(item_type) is not str or item_type not in _INVOICE_DIAGNOSTIC_OUTPUT_TYPES:
            item_type = "other"
        output_types[item_type] = output_types.get(item_type, 0) + 1
        if item_type != "message":
            continue
        content = response_value(item, "content")
        content = content[:64] if type(content) in (list, tuple) else ()
        for part in content:
            part_type = response_value(part, "type")
            if type(part_type) is not str or part_type not in _INVOICE_DIAGNOSTIC_CONTENT_TYPES:
                part_type = "other"
            content_types[part_type] = content_types.get(part_type, 0) + 1
            if part_type in ("output_text", "text"):
                text = response_value(part, "text")
                if type(text) is str:
                    message_text_chars += len(text)

    usage = response_value(response, "usage")
    token_details = response_value(usage, "output_tokens_details")
    output_text = response_value(response, "output_text")
    return {
        "status": status,
        "incompleteReason": incomplete_reason,
        "outputTypes": output_types,
        "contentTypes": content_types,
        "outputTextChars": (
            min(len(output_text), 10_000_000)
            if type(output_text) is str
            else 0
        ),
        "messageTextChars": min(message_text_chars, 10_000_000),
        "inputTokens": safe_number(response_value(usage, "input_tokens")),
        "outputTokens": safe_number(response_value(usage, "output_tokens")),
        "reasoningTokens": safe_number(response_value(token_details, "reasoning_tokens")),
        **_invoice_input_counts(request),
    }


def _log_invoice_diagnostic(event, details):
    print(
        event,
        json.dumps(details, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )


def _usage_value(usage, name):
    if isinstance(usage, dict):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    if type(value) is not int or value < 0:
        return None
    return value


def _response_usage(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None, None
    input_tokens = _usage_value(usage, "input_tokens")
    output_tokens = _usage_value(usage, "output_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    if (
        input_tokens is None
        or output_tokens is None
        or total_tokens is None
        or input_tokens + output_tokens != total_tokens
    ):
        return None, None, None
    return input_tokens, output_tokens, total_tokens


_TELEMETRY_OUTCOMES = {
    MODEL_GATEWAY_EMPTY_OUTPUT: "invalid_response",
    MODEL_GATEWAY_DEADLINE_EXCEEDED: "deadline",
    MODEL_GATEWAY_CANCELLED: "cancelled",
    MODEL_GATEWAY_PROVIDER_UNAVAILABLE: "provider_unavailable",
    MODEL_GATEWAY_PROVIDER_FAILED: "provider_error",
    MODEL_GATEWAY_CONTRACT_INVALID: "provider_error",
}


class YandexModelAdapter:
    """One adapter around an SDK client, with fixed secret-safe failures."""

    __slots__ = (
        "_client", "_clock", "_correlation_id_factory", "_folder_id",
        "_telemetry_sink", "_timeout_error_types",
    )

    def __init__(
        self,
        *,
        client,
        folder_id,
        clock,
        timeout_error_types,
        telemetry_sink,
        correlation_id_factory,
    ):
        self._client = client
        self._folder_id = folder_id
        self._clock = clock
        self._timeout_error_types = timeout_error_types
        self._telemetry_sink = telemetry_sink
        self._correlation_id_factory = correlation_id_factory

    def _correlation_id(self):
        try:
            value = self._correlation_id_factory()
        except Exception:
            value = None
        return safe_model_gateway_correlation_id(value)

    def _duration_ms(self, started_at):
        try:
            elapsed = self._clock() - started_at
        except Exception:
            return 0
        if not math.isfinite(elapsed):
            return 0
        return max(0, round(elapsed * 1000))

    def _emit(self, **fields):
        try:
            self._telemetry_sink(**fields)
        except Exception:
            return

    def generate(self, request):
        request = _validated_request(request)
        provider_input = _provider_input(request)
        started_at = self._clock()
        correlation_id = self._correlation_id()
        saw_empty = False
        saw_timeout = False
        try:
            for model_id in YANDEX_CAPABILITY_MODELS[request.capability]:
                elapsed = self._clock() - started_at
                remaining = request.deadline_seconds - elapsed
                if not math.isfinite(remaining) or remaining <= 0:
                    _error(MODEL_GATEWAY_DEADLINE_EXCEEDED)
                try:
                    response = self._client.responses.create(
                        model="gpt://" + self._folder_id + "/" + model_id,
                        temperature=request.temperature,
                        instructions=request.instructions,
                        input=provider_input,
                        max_output_tokens=request.max_output_tokens,
                        timeout=float(remaining),
                        **(
                            {"reasoning": {"effort": "none"}}
                            if request.capability == "invoice_scan"
                            and model_id == "qwen3.6-35b-a3b/latest"
                            else {}
                        ),
                    )
                except asyncio.CancelledError:
                    _error(MODEL_GATEWAY_CANCELLED)
                except self._timeout_error_types:
                    saw_timeout = True
                    continue
                except Exception as error:
                    if request.capability == "invoice_scan":
                        try:
                            _log_invoice_diagnostic(
                                "STROYKA_INVOICE_PROVIDER_DIAG",
                                _invoice_provider_error_diagnostic(error, request, "provider"),
                            )
                        except Exception:
                            pass
                    continue

                output_text = getattr(response, "output_text", None)
                if request.capability == "invoice_scan":
                    try:
                        details = _invoice_response_diagnostic(response, request)
                        details["requestedOutputTokens"] = request.max_output_tokens
                        _log_invoice_diagnostic("STROYKA_INVOICE_RESPONSE_DIAG", details)
                    except Exception:
                        pass
                if type(output_text) is not str or not output_text.strip():
                    saw_empty = True
                    continue
                duration_ms = self._duration_ms(started_at)
                try:
                    result = build_model_result(
                        provider="yandex_cloud",
                        model=model_id,
                        output_text=output_text,
                        duration_ms=duration_ms,
                    )
                except ModelGatewayError as error:
                    if error.code == MODEL_GATEWAY_EMPTY_OUTPUT:
                        saw_empty = True
                        continue
                    raise
                input_tokens, output_tokens, total_tokens = _response_usage(
                    response,
                )
                self._emit(
                    capability=request.capability,
                    provider="yandex_cloud",
                    model=model_id,
                    outcome="success",
                    duration_ms=duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    correlation_id=correlation_id,
                )
                return result

            if saw_empty:
                _error(MODEL_GATEWAY_EMPTY_OUTPUT)
            if saw_timeout:
                _error(MODEL_GATEWAY_DEADLINE_EXCEEDED)
            _error(MODEL_GATEWAY_PROVIDER_FAILED)
        except ModelGatewayError as error:
            self._emit(
                capability=request.capability,
                provider="yandex_cloud",
                outcome=_TELEMETRY_OUTCOMES.get(
                    error.code,
                    "provider_error",
                ),
                duration_ms=self._duration_ms(started_at),
                correlation_id=correlation_id,
            )
            raise
        except Exception as error:
            if request.capability == "invoice_scan":
                try:
                    _log_invoice_diagnostic(
                        "STROYKA_INVOICE_PROVIDER_DIAG",
                        _invoice_provider_error_diagnostic(error, request, "adapter"),
                    )
                except Exception:
                    pass
            raise


def build_yandex_model_adapter(
    *,
    api_key,
    folder_id,
    client_factory=None,
    clock=time.monotonic,
    timeout_error_types=None,
    telemetry_sink=emit_model_gateway_event,
    correlation_id_factory=new_model_gateway_correlation_id,
):
    if (
        type(api_key) is not str
        or not api_key
        or api_key.strip() != api_key
        or len(api_key) > 8192
        or any(not character.isprintable() for character in api_key)
        or type(folder_id) is not str
        or _FOLDER_ID_RE.fullmatch(folder_id) is None
    ):
        _error(MODEL_GATEWAY_PROVIDER_UNAVAILABLE)
    if not callable(telemetry_sink) or not callable(correlation_id_factory):
        _error(MODEL_GATEWAY_CONTRACT_INVALID)
    try:
        if client_factory is None or timeout_error_types is None:
            from openai import APITimeoutError, OpenAI

            if client_factory is None:
                client_factory = OpenAI
            if timeout_error_types is None:
                timeout_error_types = (TimeoutError, APITimeoutError)
        if (
            type(timeout_error_types) is not tuple
            or not timeout_error_types
            or any(
                type(error_type) is not type
                or not issubclass(error_type, Exception)
                for error_type in timeout_error_types
            )
        ):
            _error(MODEL_GATEWAY_CONTRACT_INVALID)
        client = client_factory(
            api_key=api_key,
            base_url=YANDEX_OPENAI_BASE_URL,
            project=folder_id,
        )
        create = getattr(getattr(client, "responses", None), "create", None)
        if not callable(create):
            _error(MODEL_GATEWAY_PROVIDER_UNAVAILABLE)
    except ModelGatewayError:
        raise
    except Exception:
        _error(MODEL_GATEWAY_PROVIDER_UNAVAILABLE)
    return YandexModelAdapter(
        client=client,
        folder_id=folder_id,
        clock=clock,
        timeout_error_types=timeout_error_types,
        telemetry_sink=telemetry_sink,
        correlation_id_factory=correlation_id_factory,
    )
