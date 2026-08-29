"""Caller-local model transport and rollback for supply-delivery checks."""

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


def generate_supply_delivery_check_legacy(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    import openai as oa

    client = oa.OpenAI(
        api_key=yandex_api_key,
        base_url="https://ai.api.cloud.yandex.net/v1",
        project=yandex_folder_id,
    )
    response = client.responses.create(
        model="gpt://" + yandex_folder_id + "/yandexgpt-5.1/latest",
        temperature=0.1,
        instructions=instructions,
        input=prompt,
        max_output_tokens=500,
    )
    return (response.output_text or "").strip()


def generate_supply_delivery_check_gateway(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    try:
        request = build_model_request(
            capability="supply_delivery_check",
            instructions=instructions,
            input_text=prompt,
            temperature=0.1,
            max_output_tokens=500,
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


def generate_supply_delivery_check(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
    model_gateway_enabled=False,
):
    arguments = (
        prompt,
        instructions,
        yandex_api_key,
        yandex_folder_id,
    )
    if model_gateway_enabled is True:
        return generate_supply_delivery_check_gateway(*arguments)
    return generate_supply_delivery_check_legacy(*arguments)
