"""Bounded loopback transport for the hidden-works local model canary."""

import json
import os
import re
import urllib.request

try:
    from backend.features.hidden_works_detection.prompt import (
        HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
        build_hidden_works_detection_prompt,
        build_hidden_works_response_format,
    )
except ModuleNotFoundError:
    from features.hidden_works_detection.prompt import (
        HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
        build_hidden_works_detection_prompt,
        build_hidden_works_response_format,
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
_TIMEOUT_SECONDS = 20
_API_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


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


def generate_local_hidden_works(names, *, post_json=None):
    """Return the raw model JSON text or one fixed, non-leaking error."""
    port, api_key = _configuration()
    try:
        prompt = build_hidden_works_detection_prompt(names)
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_RESPONSE_INVALID,
        ) from None

    request_body = {
        "model": _MODEL_ALIAS,
        "messages": [
            {
                "role": "system",
                "content": HIDDEN_WORKS_DETECTION_INSTRUCTIONS,
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": HIDDEN_WORKS_DETECTION_MAX_OUTPUT_TOKENS,
        "chat_template_kwargs": {"enable_thinking": False},
        "reasoning_effort": "none",
        # Supported by the exact pinned llama.cpp server revision:
        # https://github.com/ggml-org/llama.cpp/blob/c1d0e7a004015f23bc0233470b747b596f29b264/tools/server/README.md#post-v1chatcompletions-openai-compatible-chat-completions-api
        "response_format": build_hidden_works_response_format(names),
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
    except Exception:
        raise LocalHiddenWorksModelError(
            LOCAL_MODEL_RESPONSE_INVALID,
        ) from None
    return output_text
