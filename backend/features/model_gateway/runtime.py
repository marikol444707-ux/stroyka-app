"""Small composition helper for existing Yandex-backed business callers."""

try:
    from backend.features.model_gateway.contract import (
        MODEL_GATEWAY_PROVIDER_FAILED,
        ModelGatewayError,
        build_model_request,
    )
    from backend.features.model_gateway.yandex_adapter import (
        build_yandex_model_adapter,
    )
except ModuleNotFoundError:
    from features.model_gateway.contract import (
        MODEL_GATEWAY_PROVIDER_FAILED,
        ModelGatewayError,
        build_model_request,
    )
    from features.model_gateway.yandex_adapter import build_yandex_model_adapter


def generate_yandex_text(
    *,
    capability,
    instructions,
    input_text,
    temperature,
    max_output_tokens,
    api_key,
    folder_id,
):
    try:
        request = build_model_request(
            capability=capability,
            instructions=instructions,
            input_text=input_text,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            deadline_seconds=120,
        )
        gateway = build_yandex_model_adapter(
            api_key=api_key,
            folder_id=folder_id,
        )
        return gateway.generate(request).output_text
    except ModelGatewayError:
        raise
    except Exception:
        raise ModelGatewayError(MODEL_GATEWAY_PROVIDER_FAILED) from None
