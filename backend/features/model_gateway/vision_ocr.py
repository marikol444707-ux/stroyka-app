"""Bounded, secret-safe Yandex Vision OCR transport."""

import base64
import json
import mimetypes
import urllib.request
import urllib.error
import socket


YANDEX_VISION_OCR_URL = "https://ai.api.cloud.yandex.net/ocr/v1/recognizeText"
YANDEX_VISION_OCR_MAX_BYTES = 10 * 1024 * 1024
YANDEX_VISION_OCR_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, _request, _file_pointer, _code, _message, _headers, _new_url):
        return None


def _vision_mime(filename: str, content_type: str) -> str:
    name = (filename or "").casefold()
    mime_type = (content_type or mimetypes.guess_type(filename or "")[0] or "").casefold()
    if mime_type in ("image/jpeg", "image/jpg") or name.endswith((".jpg", ".jpeg")):
        return "JPEG"
    if mime_type == "image/png" or name.endswith(".png"):
        return "PNG"
    if mime_type == "application/pdf" or name.endswith(".pdf"):
        return "PDF"
    return ""


def recognize_text_with_vision(
    content: bytes,
    filename: str,
    content_type: str,
    api_key: str,
    folder_id: str,
    *,
    open_request=None,
) -> tuple[str, str]:
    mime_type = _vision_mime(filename, content_type)
    if not mime_type or not content or not api_key or not folder_id:
        return "", ""
    if len(content) > YANDEX_VISION_OCR_MAX_BYTES:
        return "", "Изображение больше 10 МБ: отдельный OCR пропущен, использован AI-анализ."
    payload = json.dumps({
        "mimeType": mime_type,
        "languageCodes": ["ru", "en"],
        "model": "page",
        "content": base64.b64encode(content).decode("ascii"),
    }).encode("utf-8")
    request = urllib.request.Request(
        YANDEX_VISION_OCR_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Api-Key " + api_key,
            "x-folder-id": folder_id,
            "x-data-logging-enabled": "false",
        },
    )
    try:
        requester = open_request or urllib.request.build_opener(_NoRedirect()).open
        with requester(request, timeout=45) as response:
            raw = response.read(YANDEX_VISION_OCR_MAX_RESPONSE_BYTES + 1)
        if len(raw) > YANDEX_VISION_OCR_MAX_RESPONSE_BYTES:
            raise ValueError("OCR response is too large")
        data = json.loads(raw.decode("utf-8"))
        result = data.get("result") if isinstance(data, dict) else None
        annotation = result.get("textAnnotation") if isinstance(result, dict) else None
        if not isinstance(annotation, dict):
            raise ValueError("Unexpected OCR response envelope")
        text = annotation.get("fullText", "")
        if not isinstance(text, str):
            raise ValueError("Unexpected OCR text type")
        text = text.strip()[:32000]
        if text:
            return text, ""
    except urllib.error.HTTPError as error:
        explanations = {
            400: "сервис отклонил файл или параметры запроса",
            401: "ключ не прошёл проверку",
            403: "нет доступа к OCR: проверьте права ключа и сервисного аккаунта",
            429: "превышен лимит запросов",
        }
        reason = explanations.get(error.code, "ошибка сервиса распознавания")
        return "", f"OCR: {reason} (HTTP {error.code})."
    except (TimeoutError, socket.timeout):
        return "", "OCR: сервис не ответил за 45 секунд."
    except urllib.error.URLError:
        return "", "OCR: не удалось соединиться с сервисом распознавания."
    except (ValueError, UnicodeError):
        return "", "OCR: сервис вернул некорректный ответ."
    except Exception:
        return "", "OCR: внутренняя ошибка обработки ответа."

    return "", "OCR: сервис не нашёл текст в файле."
