"""Bind upstream jev-ultrafast to Timeweb SystemOne without exposing secrets."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from types import ModuleType
from typing import MutableMapping

from dev_control.browser_worker.network_guard import redact_boundary_url
from dev_control.jev_timeweb import (
    DEFAULT_MODEL,
    DEFAULT_SYSTEMONE_URL,
    JevError,
    JevTimewebClient,
    validate_systemone_endpoint,
)


UPSTREAM_TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"

# Task-agnostic guidance for form completion; no CSS selectors, field values,
# warehouse-specific rules or automatic execution overrides.
QA_FORM_POLICY = (
    "For forms, complete the explicitly requested required controls before optional fields. "
    "When a goal explicitly names a visible unchecked checkbox, select that checkbox before "
    "filling unrelated notes or comments. When a requested dropdown value is already selected, "
    "do not change it; never undo a correct selection just to take another action. "
    "After selecting a checkbox, observe again for conditionally revealed required fields "
    "(including numeric inputs) and fill those before submitting. "
    "Do not fill optional notes/comments unless the goal explicitly asks for them. "
    "A field marked [LAST_ENTRY_CONFIRMED] already contains the last text you entered; "
    "do not type into it again. Continue to the next unfinished required control. "
    "Do not repeat a field action that made no relevant progress. "
    "Do not submit, modify records, or claim success unless the user's task authorizes it. "
    "BLOCKED is appropriate only when no supported action can progress the goal."
)

_SENSITIVE_CONTROL_MARKERS = (
    "password", "secret", "token", "cookie", "session", "credential",
    "authorization", "api key", "2fa", "otp", "пароль", "секрет",
    "токен", "код подтверждения",
)


def _visible_select_value(value, control):
    """Expose only short, non-secret native SELECT labels already visible in QA UI."""
    if not isinstance(control, dict) or control.get("role") != "combobox":
        return "[POPULATED]"
    label = str(control.get("label") or "").lower()
    if any(marker in label for marker in _SENSITIVE_CONTROL_MARKERS):
        return "[POPULATED]"
    if not isinstance(value, str) or len(value) > 120:
        return "[POPULATED]"
    return value


def _redact_nested_option_values(value):
    if isinstance(value, list):
        return [_redact_nested_option_values(item) for item in value]
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            if key == "value":
                safe[key] = "[REDACTED]"
            else:
                safe[key] = _redact_nested_option_values(item)
        return safe
    return value


def _with_form_policy(questions):
    """Add generic decision guidance without changing the TypeSafe answer schema."""
    safe = copy.deepcopy(questions)
    for key in ("operation", "click_target", "select_target", "type_text_target"):
        question = safe.get(key)
        if not isinstance(question, dict):
            continue
        instructions = question.get("instructions")
        if not isinstance(instructions, dict):
            continue
        rules = instructions.get("rules")
        if isinstance(rules, str):
            instructions["rules"] = rules + "\n" + QA_FORM_POLICY
        elif isinstance(rules, list):
            instructions["rules"] = [*rules, QA_FORM_POLICY]
    return safe


def _sanitize_state_for_provider(state):
    """Remove credentials from Jev state before it leaves the worker."""

    safe = copy.deepcopy(state)
    if not isinstance(safe, dict):
        return safe

    page = safe.get("page")
    if isinstance(page, dict) and page.get("url"):
        page["url"] = redact_boundary_url(str(page["url"]))

    # Compare the actual visible value with the last locally executed fill.
    # Only a confirmation marker is sent to Timeweb, never the typed value.
    last_fills = {}
    recent = safe.get("recent_actions")
    if isinstance(recent, list):
        for item in recent:
            if not isinstance(item, dict) or item.get("kind") != "fill":
                continue
            label, entered = item.get("action"), item.get("text")
            if isinstance(label, str) and isinstance(entered, str) and entered.strip():
                last_fills[label] = entered

    elements = safe.get("elements")
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue
            if "options" in element:
                element["options"] = _redact_nested_option_values(element.get("options"))
            value = element.get("value")
            if value in (None, ""):
                continue
            if element.get("role") == "combobox":
                element["value"] = _visible_select_value(value, element)
                continue
            label = element.get("label")
            last = last_fills.get(label) if isinstance(label, str) else None
            element["value"] = (
                "[LAST_ENTRY_CONFIRMED]"
                if isinstance(value, str) and last is not None and value == last
                else "[POPULATED]"
            )

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


def _sanitize_questions_for_provider(questions):
    safe = copy.deepcopy(questions)
    if not isinstance(safe, dict):
        return safe
    for question in safe.values():
        if not isinstance(question, dict):
            continue
        if "current_value" in question and question["current_value"] not in (None, ""):
            question["current_value"] = "[POPULATED]"
        criteria = question.get("criteria")
        if isinstance(criteria, dict):
            for value in criteria.values():
                if isinstance(value, dict) and "current_value" in value and value["current_value"] not in (None, ""):
                    value["current_value"] = _visible_select_value(value["current_value"], value)
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

    endpoint = validate_systemone_endpoint(
        env.get("JEV_SYSTEMONE_URL") or DEFAULT_SYSTEMONE_URL
    )
    model = (env.get("JEV_MODEL") or DEFAULT_MODEL).strip()
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
            result = client.ask(
                state=_sanitize_state_for_provider(state),
                questions=_with_form_policy(_sanitize_questions_for_provider(questions)),
            )
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
