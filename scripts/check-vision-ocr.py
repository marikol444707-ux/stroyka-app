"""Probe Vision OCR with synthetic digits; never print keys or customer text."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from backend.config import YANDEX_API_KEY, YANDEX_FOLDER_ID
    from backend.features.model_gateway.vision_ocr import recognize_text_with_vision

    if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
        print("FAIL OCR: серверный ключ или каталог не настроен.")
        return 1
    image = ROOT / "scripts" / "fixtures" / "vision-ocr-probe.png"
    text, warning = recognize_text_with_vision(
        image.read_bytes(), image.name, "image/png", YANDEX_API_KEY, YANDEX_FOLDER_ID,
    )
    if warning:
        print("FAIL " + warning)
        return 1
    if re.sub(r"\D", "", text) != "1234567890":
        print("FAIL OCR: доступ работает, но тестовые цифры распознаны неверно.")
        return 1
    print("OK OCR: доступ работает, все тестовые цифры распознаны правильно.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
