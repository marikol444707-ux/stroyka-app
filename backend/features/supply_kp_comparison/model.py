"""Gateway-backed model transport for supply KP comparison."""

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


def generate_supply_kp_comparison(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    try:
        request = build_model_request(
            capability="supply_kp_comparison",
            instructions=instructions,
            input_text=prompt,
            temperature=0.2,
            max_output_tokens=400,
            deadline_seconds=120,
        )
        gateway = build_yandex_model_adapter(
            api_key=yandex_api_key,
            folder_id=yandex_folder_id,
        )
        response = gateway.generate(request)
        return response.output_text.strip()
    except ModelGatewayError:
        raise
    except Exception:
        raise ModelGatewayError(MODEL_GATEWAY_PROVIDER_FAILED) from None
