"""Bounded loopback transport for the hidden-works local model canary."""

import json
import os
import re
import urllib.request

try:
    from backend.features.hidden_works_detection.prompt import (
        HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
        build_indexed_hidden_works_detection_prompt,
        build_hidden_works_response_format,
        parse_hidden_work_indices,
    )
except ModuleNotFoundError:
    from features.hidden_works_detection.prompt import (
        HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
        build_indexed_hidden_works_detection_prompt,
        build_hidden_works_response_format,
        parse_hidden_work_indices,
    )


LOCAL_MODEL_PORT = "HIDDEN_WORKS_LOCAL_MODEL_PORT"
LOCAL_MODEL_API_KEY = "HIDDEN_WORKS_LOCAL_MODEL_API_KEY"

LOCAL_MODEL_CONFIG_INVALID = "local_model_config_invalid"
LOCAL_MODEL_RESPONSE_INVALID = "local_model_response_invalid"
LOCAL_MODEL_TRANSPORT_FAILED = "local_model_transport_failed"

_ERROR_CODES = frozenset({
    LOCAL_MODEL_CONFIG_INVALID,
    LOCAL_MODEL_RESPONSE_INVALID,
    LOCAL_MODEL_TRANSPORT_FAILED,
})
_MODEL_ALIAS = "qwen3-4b-q4-k-m"
_MAX_OUTPUT_BYTES = 64 * 1024
_MAX_RESPONSE_BYTES = 128 * 1024
_TIMEOUT_SECONDS = 60
_MAX_BATCH_CANDIDATES = 20
_MAX_BATCHES = 4
_MAX_BATCH_PROMPT_BYTES = 6 * 1024
_API_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")

# This is deliberately a high-recall filter.  It is used only when a complete
# estimate is too large for the pinned 4096-token model context.  The model
# still makes the final decision, including rejecting visible endpoints such
# as ventilation grilles.
_LARGE_ESTIMATE_CANDIDATE_STEMS = (
    "анкер",
    "арматур",
    "армиров",
    "бетон",
    "битум",
    "водопровод",
    "воздуховод",
    "вентиляц",
    "герметизац",
    "гидроизол",
    "грунт",
    "дренаж",
    "заземлен",
    "заземлён",
    "закладн",
    "закрыт",
    "засып",
    "звукоизол",
    "изоляц",
    "кабел",
    "канализац",
    "каркас",
    "котлован",
    "мембран",
    "молниезащит",
    "монолит",
    "обратн",
    "огнезащ",
    "основан",
    "опалуб",
    "пароизол",
    "подготов",
    "праймер",
    "примыкан",
    "провод",
    "проходк",
    "разводк",
    "ростверк",
    "рулонн",
    "сва",
    "сетк",
    "скрыт",
    "стяжк",
    "теплоизол",
    "транше",
    "труб",
    "уплотнен",
    "уплотнён",
    "утепл",
    "фундамент",
    "штроб",
)


class LocalHiddenWorksModelError(ValueError):
    def __init__(self, code):
        self.code = code if code in _ERROR_CODES else LOCAL_MODEL_RESPONSE_INVALID
        super().__init__(self.code)


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
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _RejectRedirect,
    )
    with opener.open(request, timeout=timeout_seconds) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise LocalHiddenWorksModelError(LOCAL_MODEL_TRANSPORT_FAILED)
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                if int(content_length) > max_response_bytes:
                    raise LocalHiddenWorksModelError(
                        LOCAL_MODEL_RESPONSE_INVALID,
                    )
            except ValueError:
                raise LocalHiddenWorksModelError(
                    LOCAL_MODEL_RESPONSE_INVALID,
                ) from None
        payload = response.read(max_response_bytes + 1)
    if len(payload) > max_response_bytes:
        raise LocalHiddenWorksModelError(LOCAL_MODEL_RESPONSE_INVALID)
    try:
        document = json.loads(payload.decode("utf-8"))
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_RESPONSE_INVALID,
        ) from None
    return document


def _configuration():
    raw_port = os.getenv(LOCAL_MODEL_PORT)
    api_key = os.getenv(LOCAL_MODEL_API_KEY)
    if (
        type(raw_port) is not str
        or not raw_port
        or not raw_port.isascii()
        or not raw_port.isdecimal()
        or (len(raw_port) > 1 and raw_port.startswith("0"))
        or type(api_key) is not str
        or _API_KEY_RE.fullmatch(api_key) is None
    ):
        raise LocalHiddenWorksModelError(LOCAL_MODEL_CONFIG_INVALID)
    port = int(raw_port)
    if not 1024 <= port <= 65535:
        raise LocalHiddenWorksModelError(LOCAL_MODEL_CONFIG_INVALID)
    return port, api_key


def _large_estimate_candidate_names(names):
    """Keep plausible hidden works when a full estimate exceeds context."""
    return tuple(
        name
        for name in names
        if type(name) is str
        and any(
            stem in name.casefold()
            for stem in _LARGE_ESTIMATE_CANDIDATE_STEMS
        )
    )


def _candidate_batches(names):
    batches = []
    current = []
    for name in names:
        proposed = tuple(current + [name])
        prompt_size = len(
            build_indexed_hidden_works_detection_prompt(proposed).encode(
                "utf-8",
            ),
        )
        if current and (
            len(proposed) > _MAX_BATCH_CANDIDATES
            or prompt_size > _MAX_BATCH_PROMPT_BYTES
        ):
            batches.append(tuple(current))
            current = [name]
        else:
            current.append(name)
    if current:
        batches.append(tuple(current))
    if (
        len(batches) > _MAX_BATCHES
        or any(
            len(build_indexed_hidden_works_detection_prompt(batch).encode(
                "utf-8",
            )) > _MAX_BATCH_PROMPT_BYTES
            for batch in batches
        )
    ):
        raise LocalHiddenWorksModelError(LOCAL_MODEL_RESPONSE_INVALID)
    return tuple(batches)


def _request_batch(batch, *, port, api_key, post_json):
    request_body = {
        "model": _MODEL_ALIAS,
        "messages": [
            {
                "role": "system",
                "content": HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": build_indexed_hidden_works_detection_prompt(batch),
            },
        ],
        "temperature": 0.1,
        "max_tokens": HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
        # Supported by the exact pinned llama.cpp server revision:
        # https://github.com/ggml-org/llama.cpp/blob/c1d0e7a004015f23bc0233470b747b596f29b264/tools/server/README.md#post-v1chatcompletions-openai-compatible-chat-completions-api
        "response_format": build_hidden_works_response_format(batch),
        "stream": False,
    }
    try:
        response = (post_json or _post_local_json)(
            f"http://127.0.0.1:{port}/v1/chat/completions",
            request_body,
            authorization="Bearer " + api_key,
            timeout_seconds=_TIMEOUT_SECONDS,
            max_response_bytes=_MAX_RESPONSE_BYTES,
        )
    except LocalHiddenWorksModelError:
        raise
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_TRANSPORT_FAILED,
        ) from None
    try:
        if type(response) is not dict:
            raise ValueError
        choices = response["choices"]
        if type(choices) is not list or len(choices) != 1:
            raise ValueError
        choice = choices[0]
        if type(choice) is not dict:
            raise ValueError
        message = choice["message"]
        if type(message) is not dict:
            raise ValueError
        output_text = message["content"]
        if (
            type(output_text) is not str
            or not output_text
            or len(output_text.encode("utf-8")) > _MAX_OUTPUT_BYTES
        ):
            raise ValueError
        return parse_hidden_work_indices(output_text, batch)
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_RESPONSE_INVALID,
        ) from None


def generate_local_hidden_works(names, *, post_json=None):
    """Return the raw model JSON text or one fixed, non-leaking error."""
    port, api_key = _configuration()
    try:
        build_hidden_works_response_format(names)
        validated_names = tuple(names)
        full_prompt_size = len(
            build_indexed_hidden_works_detection_prompt(
                validated_names,
            ).encode("utf-8"),
        )
        model_names = (
            validated_names
            if full_prompt_size <= _MAX_BATCH_PROMPT_BYTES
            else _large_estimate_candidate_names(validated_names)
        )
        batches = _candidate_batches(model_names) if model_names else ()
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_RESPONSE_INVALID,
        ) from None
    selected_names = []
    try:
        for batch in batches:
            selected_names.extend(_request_batch(
                batch,
                port=port,
                api_key=api_key,
                post_json=post_json,
            ))
    except LocalHiddenWorksModelError:
        raise
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_TRANSPORT_FAILED,
        ) from None
    selected = set(selected_names)
    return json.dumps(
        {
            "hidden": [
                name for name in validated_names if name in selected
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
