"""Sensitive value redaction helpers.

Provide a small utility to scrub likely-sensitive keys from incoming
payloads before they are used in error logs or stored in error records.

This file is deliberately small and conservative: it does not attempt
to deeply transform all possible shapes, just removes or masks common
secrets keys in dicts.
"""

from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "auth",
    "cookie",
    "cookies",
    "password",
    "pass",
    "pwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "api-key",
    "x-stroyka-webhook-token",
}


def _redact_value(v: Any) -> Any:
    if v is None:
        return v
    if isinstance(v, str):
        if not v:
            return v
        # short mask to preserve length hints but avoid leaking the value
        return v[:4] + "...[redacted]"
    if isinstance(v, (int, float, bool)):
        return "[redacted]"
    if isinstance(v, dict):
        return redact_dict(v)
    if isinstance(v, list):
        return [_redact_value(i) for i in v]
    return "[redacted]"


def redact_dict(d: dict) -> dict:
    """Return a shallow-copied dict with sensitive keys redacted.

    Only top-level keys are redacted to keep behavior predictable and
    avoid over-aggressive transformations in production paths.
    """
    if not isinstance(d, dict):
        return d
    out = {}
    for k, v in d.items():
        if not isinstance(k, str):
            out[k] = v
            continue
        lk = k.strip().lower()
        if lk in SENSITIVE_KEYS or any(sk in lk for sk in ("password", "secret", "token", "key", "cookie")):
            out[k] = _redact_value(v)
        else:
            # recurse into nested structures to redact nested sensitive keys
            if isinstance(v, dict) or isinstance(v, list):
                out[k] = _redact_value(v)
            else:
                out[k] = v
    return out
