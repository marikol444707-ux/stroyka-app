"""Bind upstream jev-ultrafast to Timeweb SystemOne without exposing secrets."""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import ModuleType
from typing import MutableMapping

from dev_control.jev_timeweb import DEFAULT_MODEL, DEFAULT_SYSTEMONE_URL, JevError, JevTimewebClient


UPSTREAM_TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"


@dataclass
class ProviderPatch:
    model_module: ModuleType
    original_post_json: object

    def restore(self) -> None:
        self.model_module.post_json = self.original_post_json


def install_timeweb_provider(
    *,
    model_module: ModuleType | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> ProviderPatch:
    """Redirect only upstream Jev SystemOne calls to Timeweb."""

    env = environ if environ is not None else os.environ
    key = (env.get("TIMEWEB_AI_API_KEY") or "").strip()
    if not key:
        raise JevError("TIMEWEB_AI_API_KEY is not configured")

    endpoint = (env.get("JEV_SYSTEMONE_URL") or DEFAULT_SYSTEMONE_URL).strip()
    model = (env.get("JEV_MODEL") or DEFAULT_MODEL).strip()
    if not endpoint.startswith("https://"):
        raise JevError("JEV_SYSTEMONE_URL must use https://")
    if not model:
        raise JevError("JEV_MODEL is empty")

    if model_module is None:
        import jev_ultrafast.model as model_module

    original = model_module.post_json
    client = JevTimewebClient(api_key=key, endpoint=endpoint, model=model)

    def patched_post_json(url, _provider_key, body):
        if str(url).rstrip("/") == UPSTREAM_TYPESAFE_URL:
            try:
                state = body["state"]
                questions = body["questions"]
            except (KeyError, TypeError) as exc:
                raise JevError("Upstream Jev request has no state/questions") from exc
            result = client.ask(state=state, questions=questions)
            result.setdefault("model", model)
            result.setdefault("usage", {})
            return result
        return original(url, _provider_key, body)

    model_module.post_json = patched_post_json

    # Upstream choose() checks these env vars before post_json. Keep the real
    # Timeweb secret out of TYPESAFE_API_KEY so an upstream URL change fails closed.
    env["TYPESAFE_API_KEY"] = "timeweb-adapter-no-secret"
    env["TYPESAFE_MODEL"] = model

    text_model = (env.get("TIMEWEB_TEXT_MODEL") or "").strip()
    if text_model:
        env.setdefault("TEXT_MODEL_API_KEY", key)
        env.setdefault("TEXT_MODEL_BASE_URL", "https://api.timeweb.ai/v1")
        env.setdefault("TEXT_MODEL", text_model)
        env.setdefault("TEXT_MODEL_REASONING", "none")

    return ProviderPatch(model_module=model_module, original_post_json=original)
