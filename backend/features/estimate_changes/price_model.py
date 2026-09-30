"""Caller-local model transport and rollback for estimate-change pricing."""

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


def generate_estimate_change_price(
    user_text,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    try:
        request = build_model_request(
            capability="estimate_change_price",
            instructions=instructions,
            input_text=user_text,
            temperature=0.2,
            max_output_tokens=800,
            deadline_seconds=120,
        )
        gateway = build_yandex_model_adapter(
            api_key=yandex_api_key,
            folder_id=yandex_folder_id,
        )
        response = gateway.generate(request)
        return response.output_text, None
    except ModelGatewayError as error:
        return "", error.code
    except Exception:
        return "", MODEL_GATEWAY_PROVIDER_FAILED
