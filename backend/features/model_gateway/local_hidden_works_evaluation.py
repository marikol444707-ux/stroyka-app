"""Pure prompt/response boundary for approved hidden-works evaluations."""

import json
import re
import time
import urllib.request
from dataclasses import dataclass

from backend.features.model_gateway.evaluation_set import (
    EvaluationWork,
    HiddenWorksEvaluationCase,
)
from backend.features.model_gateway.offline_evaluation import (
    OfflineEvaluationObservation,
    build_offline_observation,
)
from backend.features.hidden_works_detection.prompt import (
    HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
    HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
    build_hidden_works_detection_prompt,
    build_hidden_works_response_format,
)


_MAX_OUTPUT_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 128 * 1024
_LOCAL_MODEL_ALIAS = "qwen3-4b-q4-k-m"
LOCAL_EVALUATION_RESPONSE_INVALID = "local_evaluation_response_invalid"
LOCAL_EVALUATION_TRANSPORT_FAILED = "local_evaluation_transport_failed"


class LocalHiddenWorksEvaluationError(ValueError):
    def __init__(self, code):
        if code not in {
            LOCAL_EVALUATION_RESPONSE_INVALID,
            LOCAL_EVALUATION_TRANSPORT_FAILED,
        }:
            code = LOCAL_EVALUATION_RESPONSE_INVALID
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class LocalHiddenWorksEvaluationResult:
    observation: OfflineEvaluationObservation
    production_traffic_allowed: bool = False


@dataclass(frozen=True)
class LocalHiddenWorksWarmupResult:
    duration_ms: int
    production_traffic_allowed: bool = False


_LOCAL_WARMUP_CASE = HiddenWorksEvaluationCase(
    case_id="hw-999",
    works=(
        EvaluationWork(
            "w1",
            "Локальная проверка открытой окрашенной поверхности",
        ),
        EvaluationWork(
            "w2",
            "Локальная установка съёмной декоративной панели",
        ),
    ),
    expected_hidden_ids=(),
)


class _RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, url):
        return None


def _post_local_json(
    url,
    body,
    *,
    authorization,
    timeout_seconds,
    max_response_bytes,
):
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(_RejectRedirect)
    with opener.open(request, timeout=timeout_seconds) as response:
        payload = response.read(max_response_bytes + 1)
    if len(payload) > max_response_bytes:
        raise LocalHiddenWorksEvaluationError(
            LOCAL_EVALUATION_RESPONSE_INVALID,
        )
    try:
        document = json.loads(payload.decode("utf-8"))
    except Exception:
        raise LocalHiddenWorksEvaluationError(
            LOCAL_EVALUATION_RESPONSE_INVALID,
        ) from None
    return document


def build_hidden_works_evaluation_prompt(case):
    if type(case) is not HiddenWorksEvaluationCase:
        raise TypeError("hidden_works_evaluation_case_invalid")
    return build_hidden_works_detection_prompt([
        work.name for work in case.works
    ])


def parse_hidden_works_evaluation_output(case, output_text):
    if (
        type(case) is not HiddenWorksEvaluationCase
        or type(output_text) is not str
        or len(output_text.encode("utf-8")) > _MAX_OUTPUT_BYTES
    ):
        return ()
    try:
        match = re.search(r"\{.*\}", output_text.strip(), re.DOTALL)
        if match is None:
            return ()
        document = json.loads(match.group(0))
        hidden = document.get("hidden")
        if type(hidden) is not list:
            return ()
        selected_names = {
            item.strip()
            for item in hidden
            if type(item) is str
        }
    except Exception:
        return ()
    return tuple(
        work.work_id
        for work in case.works
        if work.name in selected_names
    )


def run_local_hidden_works_evaluation_case(
    case,
    *,
    port,
    api_key,
    post_json=None,
):
    if (
        type(case) is not HiddenWorksEvaluationCase
        or type(port) is not int
        or not 1024 <= port <= 65535
        or type(api_key) is not str
        or re.fullmatch(r"[A-Za-z0-9_-]{32,128}", api_key) is None
    ):
        raise LocalHiddenWorksEvaluationError(
            LOCAL_EVALUATION_RESPONSE_INVALID,
        ) from None
    request_body = {
        "model": _LOCAL_MODEL_ALIAS,
        "messages": [
            {
                "role": "system",
                "content": HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": build_hidden_works_evaluation_prompt(case),
            },
        ],
        "temperature": 0.1,
        "max_tokens": HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
        "response_format": build_hidden_works_response_format([
            work.name for work in case.works
        ]),
        "stream": False,
    }
    started_ns = time.monotonic_ns()
    try:
        response = (post_json or _post_local_json)(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            request_body,
            authorization="Bearer " + api_key,
            timeout_seconds=120,
            max_response_bytes=_MAX_RESPONSE_BYTES,
        )
    except LocalHiddenWorksEvaluationError:
        raise
    except Exception:
        raise LocalHiddenWorksEvaluationError(
            LOCAL_EVALUATION_TRANSPORT_FAILED,
        ) from None
    duration_ms = (time.monotonic_ns() - started_ns) // 1_000_000
    try:
        if type(response) is not dict:
            raise ValueError
        choices = response["choices"]
        usage = response["usage"]
        if type(choices) is not list or len(choices) != 1:
            raise ValueError
        message = choices[0]["message"]
        output_text = message["content"]
        input_tokens = usage["prompt_tokens"]
        output_tokens = usage["completion_tokens"]
        if (
            type(message) is not dict
            or type(output_text) is not str
            or type(usage) is not dict
            or type(input_tokens) is not int
            or type(output_tokens) is not int
            or input_tokens < 0
            or output_tokens < 0
        ):
            raise ValueError
        observation = build_offline_observation(
            case_id=case.case_id,
            predicted_hidden_ids=parse_hidden_works_evaluation_output(
                case,
                output_text,
            ),
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except Exception:
        raise LocalHiddenWorksEvaluationError(
            LOCAL_EVALUATION_RESPONSE_INVALID,
        ) from None
    return LocalHiddenWorksEvaluationResult(observation=observation)


def warm_local_hidden_works_evaluation(
    *,
    port,
    api_key,
    post_json=None,
):
    result = run_local_hidden_works_evaluation_case(
        _LOCAL_WARMUP_CASE,
        port=port,
        api_key=api_key,
        post_json=post_json,
    )
    return LocalHiddenWorksWarmupResult(
        duration_ms=result.observation.duration_ms,
    )
