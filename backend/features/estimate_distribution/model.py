"""Caller-local model transport and rollback for estimate distribution."""

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


def generate_estimate_distribution_legacy(
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
    raw = ""
    for model_id in ("qwen3.6-35b-a3b/latest", "yandexgpt-5.1/latest"):
        try:
            response = client.responses.create(
                model="gpt://" + yandex_folder_id + "/" + model_id,
                temperature=0.1,
                instructions=instructions,
                input=prompt,
                max_output_tokens=4000,
            )
            raw = (response.output_text or "").strip()
            if raw:
                break
        except Exception as error:
            print("AI-DISTRIBUTE ERROR:", str(error))
    return raw


def generate_estimate_distribution_gateway(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    try:
        request = build_model_request(
            capability="estimate_distribution",
            instructions=instructions,
            input_text=prompt,
            temperature=0.1,
            max_output_tokens=4000,
            deadline_seconds=120,
        )
        gateway = build_yandex_model_adapter(
            api_key=yandex_api_key,
            folder_id=yandex_folder_id,
        )
        response = gateway.generate(request)
        return response.output_text.strip()
    except ModelGatewayError as error:
        print("AI-DISTRIBUTE ERROR:", error.code)
    except Exception:
        print("AI-DISTRIBUTE ERROR:", MODEL_GATEWAY_PROVIDER_FAILED)
    return ""


def generate_estimate_distribution(
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
        return generate_estimate_distribution_gateway(*arguments)
    return generate_estimate_distribution_legacy(*arguments)
