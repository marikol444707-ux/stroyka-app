"""Provider-neutral model call for an optional daily-brief explanation."""

from .explanation_contract import (
    build_explanation_model_input,
    parse_explanation_model_output,
)
from ..model_gateway.contract import (
    MODEL_GATEWAY_PROVIDER_FAILED,
    ModelGatewayError,
    build_model_request,
)
from ..model_gateway.yandex_adapter import build_yandex_model_adapter


_INSTRUCTIONS = """Ты объясняешь только факты готовой директорской сводки.
Верни только JSON: headline, overview, points. points — массив объектов
sourceCode и text, максимум пять. sourceCode бери дословно только из входа.
Не добавляй числа, HTML, команды, решения, суммы или новые факты. Не предлагай
оплату, списание, перемещение либо утверждение. Пиши кратко по-русски."""


def generate_daily_brief_explanation(
    *,
    brief,
    source_job_id,
    api_key,
    folder_id,
    adapter_factory=build_yandex_model_adapter,
):
    try:
        request = build_model_request(
            capability="director_agent",
            instructions=_INSTRUCTIONS,
            input_text=build_explanation_model_input(brief),
            temperature=0.0,
            max_output_tokens=700,
            deadline_seconds=45,
        )
        gateway = adapter_factory(api_key=api_key, folder_id=folder_id)
        result = gateway.generate(request)
        return parse_explanation_model_output(
            result.output_text,
            source_job_id=source_job_id,
            brief=brief,
        )
    except ModelGatewayError:
        raise
    except Exception:
        raise ModelGatewayError(MODEL_GATEWAY_PROVIDER_FAILED) from None
