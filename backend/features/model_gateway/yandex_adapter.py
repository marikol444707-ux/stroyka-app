"""OpenAI-compatible Yandex transport with no runtime registration."""

import asyncio
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


YANDEX_OPENAI_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
_FOLDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_ALLOWED_MODEL_IDS = frozenset({
    "qwen3.6-35b-a3b/latest",
    "yandexgpt-5.1/latest",
    "yandexgpt-lite/latest",
})

YANDEX_CAPABILITY_MODELS = MappingProxyType({
    "ai_chat": ("yandexgpt-5.1/latest", "qwen3.6-35b-a3b/latest"),
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
            content.append({"type": "input_image", "image_url": part.value})
        elif part.kind == "file_id":
            content.append({"type": "input_file", "file_id": part.value})
        else:
            _error(MODEL_GATEWAY_CONTRACT_INVALID)
    return [{"role": "user", "content": content}]


class YandexModelAdapter:
    """One adapter around an SDK client, with fixed secret-safe failures."""

    __slots__ = ("_client", "_clock", "_folder_id", "_timeout_error_types")

    def __init__(self, *, client, folder_id, clock, timeout_error_types):
        self._client = client
        self._folder_id = folder_id
        self._clock = clock
        self._timeout_error_types = timeout_error_types

    def generate(self, request):
        request = _validated_request(request)
        provider_input = _provider_input(request)
        started_at = self._clock()
        saw_empty = False
        saw_timeout = False

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
                )
            except asyncio.CancelledError:
                _error(MODEL_GATEWAY_CANCELLED)
            except self._timeout_error_types:
                saw_timeout = True
                continue
            except Exception:
                continue

            output_text = getattr(response, "output_text", None)
            if type(output_text) is not str or not output_text.strip():
                saw_empty = True
                continue
            duration_ms = max(0, round((self._clock() - started_at) * 1000))
            try:
                return build_model_result(
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

        if saw_empty:
            _error(MODEL_GATEWAY_EMPTY_OUTPUT)
        if saw_timeout:
            _error(MODEL_GATEWAY_DEADLINE_EXCEEDED)
        _error(MODEL_GATEWAY_PROVIDER_FAILED)


def build_yandex_model_adapter(
    *,
    api_key,
    folder_id,
    client_factory=None,
    clock=time.monotonic,
    timeout_error_types=None,
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
    )
