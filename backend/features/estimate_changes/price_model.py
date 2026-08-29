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


def generate_estimate_change_price_legacy(
    user_text,
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

    def call(model_id):
        try:
            response = client.responses.create(
                model="gpt://" + str(yandex_folder_id or "") + "/" + model_id,
                temperature=0.2,
                instructions=instructions,
                input=user_text,
                max_output_tokens=800,
            )
            return response.output_text or "", None
        except Exception as exc:
            return "", str(exc)

    answer, error = call("qwen3.6-35b-a3b/latest")
    if not answer.strip():
        answer, error = call("yandexgpt-5.1/latest")
    return answer, error


def generate_estimate_change_price_gateway(
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


def generate_estimate_change_price(
    user_text,
    instructions,
    yandex_api_key,
    yandex_folder_id,
    model_gateway_enabled=False,
):
    arguments = (
        user_text,
        instructions,
        yandex_api_key,
        yandex_folder_id,
    )
    if model_gateway_enabled is True:
        return generate_estimate_change_price_gateway(*arguments)
    return generate_estimate_change_price_legacy(*arguments)
