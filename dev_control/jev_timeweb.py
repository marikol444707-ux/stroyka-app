"""Minimal Timeweb SystemOne/Jev client for Stroyka Dev Control.

This module is intentionally isolated from the production backend.  It does not
touch the database, deploy anything, or contain credentials.  The API key is
read only from TIMEWEB_AI_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_SYSTEMONE_URL = "https://api.timeweb.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


def validate_systemone_endpoint(value: str) -> str:
    parts = urlsplit(str(value or "").strip())
    if (
        parts.scheme != "https"
        or (parts.hostname or "").lower().rstrip(".") != "api.timeweb.ai"
        or (parts.port or 443) != 443
        or parts.path.rstrip("/") != "/v1/systemone"
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise JevError("JEV_SYSTEMONE_URL must be exactly the Timeweb SystemOne endpoint")
    return DEFAULT_SYSTEMONE_URL


class JevError(RuntimeError):
    """Raised when the Jev request cannot be completed or validated."""


@dataclass(frozen=True)
class JevTimewebClient:
    api_key: str
    endpoint: str = DEFAULT_SYSTEMONE_URL
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "JevTimewebClient":
        api_key = os.environ.get("TIMEWEB_AI_API_KEY", "").strip()
        if not api_key:
            raise JevError("TIMEWEB_AI_API_KEY is not configured")

        endpoint = validate_systemone_endpoint(
            os.environ.get("JEV_SYSTEMONE_URL", DEFAULT_SYSTEMONE_URL)
        )
        model = os.environ.get("JEV_MODEL", DEFAULT_MODEL).strip()
        if not model:
            raise JevError("JEV_MODEL is empty")

        return cls(api_key=api_key, endpoint=endpoint, model=model)

    def ask(
        self,
        *,
        state: Any,
        questions: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        if state is None or (isinstance(state, str) and not state.strip()):
            raise JevError("state must not be empty")
        if isinstance(state, (dict, list, tuple)) and not state:
            raise JevError("state must not be empty")
        if not questions:
            raise JevError("questions must not be empty")

        endpoint = validate_systemone_endpoint(self.endpoint)
        payload = {
            "model": self.model,
            "state": state,
            "questions": dict(questions),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
                status = getattr(response, "status", 200)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise JevError(f"Timeweb Jev HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise JevError(f"Timeweb Jev network error: {exc.reason}") from exc

        if not 200 <= int(status) < 300:
            raise JevError(f"Timeweb Jev unexpected HTTP status: {status}")

        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JevError("Timeweb Jev returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise JevError("Timeweb Jev response must be a JSON object")
        if not isinstance(data.get("answers"), dict):
            raise JevError("Timeweb Jev response has no answers object")
        return data


def _smoke_test() -> int:
    """Run one harmless classifier request.

    This is manual-only. CI never calls it because the real API key must not be
    stored in GitHub.
    """

    client = JevTimewebClient.from_env()
    response = client.ask(
        state="Проверка подключения Stroyka Dev Control к Jev. Это тестовый запрос.",
        questions={
            "is_test": {
                "type": "noul",
                "instructions": "Это сообщение является тестом подключения?",
            }
        },
    )
    print(json.dumps(response.get("answers", {}), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Stroyka Dev Control Jev client")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Send one harmless request to Timeweb Jev using env credentials",
    )
    args = parser.parse_args()
    if args.smoke_test:
        return _smoke_test()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
