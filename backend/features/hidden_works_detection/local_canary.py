"""Fail-closed contract for an opt-in local hidden-works model canary."""

import json
import os
import sys
from dataclasses import dataclass

try:
    from backend.features.model_gateway.telemetry import (
        new_model_gateway_correlation_id,
        safe_model_gateway_correlation_id,
    )
except ModuleNotFoundError:
    from features.model_gateway.telemetry import (
        new_model_gateway_correlation_id,
        safe_model_gateway_correlation_id,
    )


FEATURE_FLAG = "HIDDEN_WORKS_LOCAL_MODEL_ENABLED"
COMPANY_ALLOWLIST = "HIDDEN_WORKS_LOCAL_MODEL_COMPANY_IDS"

_EVENT_NAME = "hidden_works_local_canary"
_MAX_COMPANIES = 100
_MAX_COMPANY_ID = 9_223_372_036_854_775_807
_MAX_CANDIDATES = 2_000
_MAX_NAME_LENGTH = 2_048
_MAX_RESPONSE_BYTES = 65_536


@dataclass(frozen=True)
class LocalHiddenWorksCanaryResult:
    hidden_names: tuple
    method: str = "local_ai_canary"
    production_traffic_allowed: bool = False


def _valid_company_id(value):
    return type(value) is int and 0 < value <= _MAX_COMPANY_ID


def _company_allowlist(value):
    if type(value) is not str or not value:
        return None
    parts = value.split(",")
    if not 1 <= len(parts) <= _MAX_COMPANIES:
        return None

    company_ids = []
    for part in parts:
        if (
            not part
            or not part.isascii()
            or not part.isdecimal()
            or (len(part) > 1 and part.startswith("0"))
        ):
            return None
        company_id = int(part)
        if not _valid_company_id(company_id) or company_id in company_ids:
            return None
        company_ids.append(company_id)
    return frozenset(company_ids)


def local_hidden_works_canary_enabled(company_id):
    """Return true only for an explicit flag and a strict company allowlist."""
    if not _valid_company_id(company_id):
        return False
    if os.getenv(FEATURE_FLAG) != "true":
        return False
    company_ids = _company_allowlist(os.getenv(COMPANY_ALLOWLIST))
    return company_ids is not None and company_id in company_ids


def _candidate_names(names):
    if type(names) not in (list, tuple):
        return None
    if not 1 <= len(names) <= _MAX_CANDIDATES:
        return None

    validated = []
    for name in names:
        if (
            type(name) is not str
            or not name
            or len(name) > _MAX_NAME_LENGTH
            or name in validated
        ):
            return None
        validated.append(name)
    return tuple(validated)


def _parse_response(output, names):
    if type(output) is not str:
        return None
    if not output or len(output.encode("utf-8")) > _MAX_RESPONSE_BYTES:
        return None

    def reject_duplicate_keys(pairs):
        payload = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError("duplicate response key")
            payload[key] = value
        return payload

    try:
        payload = json.loads(output, object_pairs_hook=reject_duplicate_keys)
    except (TypeError, ValueError):
        return None
    if type(payload) is not dict or set(payload) != {"hidden"}:
        return None

    hidden = payload["hidden"]
    if type(hidden) is not list or len(hidden) > len(names):
        return None
    selected = []
    allowed = set(names)
    for name in hidden:
        if type(name) is not str or name not in allowed or name in selected:
            return None
        selected.append(name)
    selected_set = set(selected)
    return tuple(name for name in names if name in selected_set)


def _correlation_id(factory):
    try:
        value = factory()
    except Exception:
        value = None
    return safe_model_gateway_correlation_id(value)


def _emit(log_fn, record):
    try:
        log_fn(json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        ))
    except Exception:
        pass


def try_local_hidden_works_canary(
    *,
    names,
    company_id,
    generate,
    correlation_id_factory=new_model_gateway_correlation_id,
    log_fn=None,
):
    """Try the local canary or return ``None`` for the existing fallback."""
    if not local_hidden_works_canary_enabled(company_id):
        return None

    validated_names = _candidate_names(names)
    output = log_fn or (lambda line: print(line, file=sys.stdout))
    correlation_id = _correlation_id(correlation_id_factory)
    base_event = {
        "event": _EVENT_NAME,
        "correlationId": correlation_id,
        "outcome": "fallback",
        "reason": "invalid_response",
        "candidateCount": len(names) if type(names) in (list, tuple) else 0,
    }
    if validated_names is None or not callable(generate):
        _emit(output, base_event)
        return None

    try:
        raw_response = generate()
    except Exception:
        base_event["reason"] = "provider_error"
        _emit(output, base_event)
        return None

    hidden_names = _parse_response(raw_response, validated_names)
    if hidden_names is None:
        _emit(output, base_event)
        return None

    _emit(output, {
        "event": _EVENT_NAME,
        "correlationId": correlation_id,
        "outcome": "success",
        "candidateCount": len(validated_names),
        "selectedCount": len(hidden_names),
    })
    return LocalHiddenWorksCanaryResult(hidden_names=hidden_names)
