"""Bounded, secret-safe Yandex Vision OCR transport."""

import base64
import json
import mimetypes
import urllib.request


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
        annotation = data.get("textAnnotation") if isinstance(data, dict) else None
        text = annotation.get("fullText") if isinstance(annotation, dict) else ""
        text = str(text or "").strip()[:32000]
        if text:
            return text, ""
    except Exception:
        pass
    return "", "Текст изображения не распознан отдельным OCR; использован AI-анализ."
