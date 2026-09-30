"""Caller-local model transport and rollback for hidden-works detection."""

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


def generate_hidden_works_detection(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    try:
        request = build_model_request(
            capability="hidden_works_detection",
            instructions=instructions,
            input_text=prompt,
            temperature=0.1,
            max_output_tokens=2000,
            deadline_seconds=120,
        )
        gateway = build_yandex_model_adapter(
            api_key=yandex_api_key,
            folder_id=yandex_folder_id,
        )
        return gateway.generate(request).output_text
    except ModelGatewayError:
        raise
    except Exception:
        raise ModelGatewayError(MODEL_GATEWAY_PROVIDER_FAILED) from None
