"""Pure immutable values for model gateway callers and adapters."""

import math
import re
from dataclasses import dataclass

from backend.features.model_gateway.policies import MODEL_CAPABILITIES


MODEL_GATEWAY_CONTRACT_INVALID = "model_gateway_contract_invalid"
MODEL_GATEWAY_PROVIDER_UNAVAILABLE = "model_gateway_provider_unavailable"
MODEL_GATEWAY_PROVIDER_FAILED = "model_gateway_provider_failed"
MODEL_GATEWAY_EMPTY_OUTPUT = "model_gateway_empty_output"
MODEL_GATEWAY_DEADLINE_EXCEEDED = "model_gateway_deadline_exceeded"
MODEL_GATEWAY_CANCELLED = "model_gateway_cancelled"

_ERROR_CODES = frozenset({
    MODEL_GATEWAY_CONTRACT_INVALID,
    MODEL_GATEWAY_PROVIDER_UNAVAILABLE,
    MODEL_GATEWAY_PROVIDER_FAILED,
    MODEL_GATEWAY_EMPTY_OUTPUT,
    MODEL_GATEWAY_DEADLINE_EXCEEDED,
    MODEL_GATEWAY_CANCELLED,
})
_PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_MAX_INSTRUCTIONS_BYTES = 64 * 1024
_MAX_PART_BYTES = 4 * 1024 * 1024
_MAX_RESULT_BYTES = 4 * 1024 * 1024
_MAX_DEADLINE_SECONDS = 120


class ModelGatewayError(ValueError):
    """One fixed, non-leaking gateway failure."""

    def __init__(self, code):
        if type(code) is not str or code not in _ERROR_CODES:
            raise ValueError(MODEL_GATEWAY_CONTRACT_INVALID)
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelInputPart:
    kind: str
    value: str


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    instructions: str
    input_text: str
    input_parts: tuple
    temperature: float
    max_output_tokens: int
    deadline_seconds: int


@dataclass(frozen=True)
class ModelResult:
    provider: str
    model: str
    output_text: str
    duration_ms: int


def _fail(code=MODEL_GATEWAY_CONTRACT_INVALID):
    raise ModelGatewayError(code) from None


def _bounded_text(value, *, max_bytes, allow_empty=False):
    if type(value) is not str:
        _fail()
    if not allow_empty and not value.strip():
        _fail()
    if len(value.encode("utf-8")) > max_bytes:
        _fail()
    return value


def _validated_parts(parts, policy):
    if type(parts) is not tuple or len(parts) > policy.max_parts:
        _fail()
    validated = []
    total_bytes = 0
    for part in parts:
        if type(part) is not ModelInputPart:
            _fail()
        if type(part.kind) is not str or part.kind not in policy.allowed_input_kinds:
            _fail()
        value = _bounded_text(part.value, max_bytes=_MAX_PART_BYTES)
        total_bytes += len(value.encode("utf-8"))
        validated.append(part)
    if total_bytes > policy.max_input_bytes:
        _fail()
    return tuple(validated)


def build_model_request(
    *,
    capability,
    instructions,
    input_text="",
    input_parts=(),
    temperature,
    max_output_tokens,
    deadline_seconds,
):
    if type(capability) is not str:
        _fail()
    policy = MODEL_CAPABILITIES.get(capability)
    if policy is None:
        _fail()
    instructions = _bounded_text(
        instructions,
        max_bytes=_MAX_INSTRUCTIONS_BYTES,
    )
    input_text = _bounded_text(
        input_text,
        max_bytes=policy.max_input_bytes,
        allow_empty=True,
    )
    input_parts = _validated_parts(input_parts, policy)
    has_text = bool(input_text.strip())
    has_parts = bool(input_parts)
    if has_text == has_parts:
        _fail()
    if type(temperature) not in (int, float) or not math.isfinite(temperature):
        _fail()
    if temperature < 0 or temperature > 1:
        _fail()
    if type(max_output_tokens) is not int:
        _fail()
    if not 1 <= max_output_tokens <= policy.max_output_tokens:
        _fail()
    if type(deadline_seconds) is not int:
        _fail()
    if not 1 <= deadline_seconds <= _MAX_DEADLINE_SECONDS:
        _fail()
    return ModelRequest(
        capability=capability,
        instructions=instructions,
        input_text=input_text,
        input_parts=input_parts,
        temperature=float(temperature),
        max_output_tokens=max_output_tokens,
        deadline_seconds=deadline_seconds,
    )


def build_model_result(*, provider, model, output_text, duration_ms):
    if type(provider) is not str or _PROVIDER_RE.fullmatch(provider) is None:
        _fail()
    if type(model) is not str or _MODEL_RE.fullmatch(model) is None:
        _fail()
    if type(output_text) is not str or not output_text.strip():
        _fail(MODEL_GATEWAY_EMPTY_OUTPUT)
    if len(output_text.encode("utf-8")) > _MAX_RESULT_BYTES:
        _fail(MODEL_GATEWAY_EMPTY_OUTPUT)
    if type(duration_ms) is not int or duration_ms < 0:
        _fail()
    return ModelResult(
        provider=provider,
        model=model,
        output_text=output_text,
        duration_ms=duration_ms,
    )
