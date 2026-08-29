"""Caller-local model transport and rollback for work-journal prefill."""

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


def generate_work_journal_prefill_legacy(
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

    def call(model_id):
        try:
            response = client.responses.create(
                model="gpt://" + yandex_folder_id + "/" + model_id,
                temperature=0.1,
                instructions=instructions,
                input=prompt,
                max_output_tokens=2000,
            )
            return (response.output_text or ""), None
        except Exception as error:
            return "", str(error)

    answer, error = call("qwen3.6-35b-a3b/latest")
    if not (answer or "").strip():
        print(
            "AI-PREFILL work_journal primary empty, fallback. err="
            + str(error)
        )
        answer, error = call("yandexgpt-5.1/latest")
    return answer, error


def generate_work_journal_prefill_gateway(
    prompt,
    instructions,
    yandex_api_key,
    yandex_folder_id,
):
    try:
        request = build_model_request(
            capability="work_journal_prefill",
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
        return gateway.generate(request).output_text, None
    except ModelGatewayError as error:
        return "", error.code
    except Exception:
        return "", MODEL_GATEWAY_PROVIDER_FAILED


def generate_work_journal_prefill(
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
        return generate_work_journal_prefill_gateway(*arguments)
    return generate_work_journal_prefill_legacy(*arguments)
