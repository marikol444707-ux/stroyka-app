"""Runtime configuration for the Stroyka backend."""

import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")


def load_env_file(path: str = ENV_PATH) -> None:
    if not os.path.exists(path):
        return
    with open(path) as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


load_env_file()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")
VK_TOKEN = os.getenv("VK_TOKEN", "")
AUTH_SECRET = os.getenv("AUTH_SECRET") or (os.getenv("DB_PASSWORD", "password") + "|stroyka-auth")
AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))
AI_CONTROL_RUN_TOKEN = os.getenv("AI_CONTROL_RUN_TOKEN", "").strip()
TELEGRAM_BOT_API_TOKEN = os.getenv("TELEGRAM_BOT_API_TOKEN", "").strip()
MAX_BOT_API_TOKEN = os.getenv("MAX_BOT_API_TOKEN", "").strip()
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "").strip()
MAX_INITDATA_TTL_SECONDS = env_int("MAX_INITDATA_TTL_SECONDS", 3600)
WORKFLOW_TOKEN = os.getenv("WORKFLOW_TOKEN", "").strip() or os.getenv("STROYKA_WORKFLOW_TOKEN", "").strip()
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "https://stroyka26.pro").rstrip("/")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = env_int("SMTP_PORT", 465 if os.getenv("SMTP_SSL", "true").lower() in ("1", "true", "yes") else 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
SMTP_PLACEHOLDER_EMAILS = {
    "your@email.com",
    "you@example.com",
    "noreply@example.com",
    "no-reply@example.com",
    "твоя_почта@домен.ru",
}


def valid_smtp_email(value: str) -> bool:
    raw = (value or "").strip()
    return bool(raw and "@" in raw and raw.lower() not in SMTP_PLACEHOLDER_EMAILS)


def smtp_from_value() -> str:
    raw = os.getenv("SMTP_FROM", "").strip()
    if valid_smtp_email(raw):
        return raw
    if valid_smtp_email(SMTP_USER):
        return SMTP_USER
    return ""


SMTP_FROM = smtp_from_value()
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ("1", "true", "yes")
SMTP_SSL = os.getenv("SMTP_SSL", "true").lower() in ("1", "true", "yes")
PUBLIC_LEAD_RATE_LIMIT_SECONDS = env_int("PUBLIC_LEAD_RATE_LIMIT_SECONDS", 30)
PUBLIC_LEAD_LAST_SUBMIT: dict[str, float] = {}
CLIENT_ERROR_LOGGING_ENABLED = os.getenv("CLIENT_ERROR_LOGGING_ENABLED", "true").lower() in ("1", "true", "yes")
CLIENT_ERROR_RATE_LIMIT_SECONDS = env_int("CLIENT_ERROR_RATE_LIMIT_SECONDS", 10)
CLIENT_ERROR_LAST_SUBMIT: dict[str, float] = {}

CORS_ORIGINS = env_list("CORS_ORIGINS", [
    "https://stroyka26.pro",
    "https://www.stroyka26.pro",
    "http://stroyka26.pro",
    "http://www.stroyka26.pro",
    "http://147.45.237.127",
    "https://147.45.237.127",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
])
