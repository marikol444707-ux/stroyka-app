"""Bind upstream jev-ultrafast to Timeweb SystemOne without exposing secrets."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from types import ModuleType
from typing import MutableMapping

from dev_control.browser_worker.network_guard import redact_boundary_url
from dev_control.jev_timeweb import DEFAULT_MODEL, DEFAULT_SYSTEMONE_URL, JevError, JevTimewebClient


UPSTREAM_TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"


def _sanitize_state_for_provider(state):
    """Remove credentials from Jev state before it leaves the worker."""

    safe = copy.deepcopy(state)
    if not isinstance(safe, dict):
        return safe

    page = safe.get("page")
    if isinstance(page, dict) and page.get("url"):
        page["url"] = redact_boundary_url(str(page["url"]))

    for key in ("recent_actions", "history"):
        items = safe.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("url"):
                item["url"] = redact_boundary_url(str(item["url"]))
            for secret_key in ("text", "value", "typed_text", "input", "text_helper"):
                if secret_key in item:
                    item[secret_key] = "[REDACTED]"
    return safe


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
            result = client.ask(state=_sanitize_state_for_provider(state), questions=questions)
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
    inherited_text = {
        name: (env.get(name) or "").strip()
        for name in ("TEXT_MODEL_API_KEY", "TEXT_MODEL_BASE_URL", "TEXT_MODEL")
    }
    if not text_model and any(inherited_text.values()):
        raise JevError("inherited TEXT_MODEL_* configuration is forbidden without TIMEWEB_TEXT_MODEL")
    if text_model:
        existing = {
            name: (env.get(name) or "").strip()
            for name in ("TEXT_MODEL_API_KEY", "TEXT_MODEL_BASE_URL", "TEXT_MODEL")
        }
        if any(existing.values()) and not all(existing.values()):
            raise JevError("partial TEXT_MODEL_* configuration is unsafe")
        if all(existing.values()):
            if existing["TEXT_MODEL_BASE_URL"].rstrip("/") != "https://api.timeweb.ai/v1":
                raise JevError("TIMEWEB_TEXT_MODEL cannot be mixed with another TEXT_MODEL_BASE_URL")
            if existing["TEXT_MODEL_API_KEY"] != key or existing["TEXT_MODEL"] != text_model:
                raise JevError("TIMEWEB_TEXT_MODEL conflicts with existing TEXT_MODEL_* configuration")
        env["TEXT_MODEL_API_KEY"] = key
        env["TEXT_MODEL_BASE_URL"] = "https://api.timeweb.ai/v1"
        env["TEXT_MODEL"] = text_model
        env["TEXT_MODEL_REASONING"] = "none"

    return ProviderPatch(model_module=model_module, original_post_json=original)
