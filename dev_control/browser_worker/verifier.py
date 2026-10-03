"""Deterministic final-state verification for browser QA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


def verify_final_state(
    state: dict,
    *,
    expect_text: Iterable[str] = (),
    forbid_text: Iterable[str] = (),
    expect_url_contains: Iterable[str] = (),
) -> VerificationResult:
    """Verify observable browser outcome; Jev's DONE alone is insufficient."""

    failures: list[str] = []
    checks: list[str] = []

    expect_text = tuple(expect_text)
    forbid_text = tuple(forbid_text)
    expect_url_contains = tuple(expect_url_contains)
    assertions = expect_text + forbid_text + expect_url_contains
    if not assertions:
        failures.append("no_deterministic_assertions")
    elif any(not str(value).strip() for value in assertions):
        failures.append("blank_deterministic_assertion")

    status = str(state.get("status") or "")
    if status == "done":
        checks.append("agent_status=done")
    else:
        failures.append(f"agent_status={status or 'missing'}")

    page = state.get("page") or {}
    text = str(page.get("text") or "")
    full_text_value = page.get("full_text")
    full_text = str(full_text_value) if full_text_value is not None else None
    url = str(page.get("url") or "")

    for needle in expect_text:
        haystack = full_text if full_text is not None else text
        if needle in haystack:
            checks.append(f"text_present:{needle}")
        else:
            failures.append(f"text_missing:{needle}")

    for needle in forbid_text:
        if full_text is None:
            failures.append(f"full_text_unavailable:{needle}")
        elif needle not in full_text:
            checks.append(f"text_absent:{needle}")
        else:
            failures.append(f"forbidden_text_present:{needle}")

    for needle in expect_url_contains:
        if needle in url:
            checks.append(f"url_contains:{needle}")
        else:
            failures.append(f"url_missing:{needle}")

    return VerificationResult(
        ok=not failures,
        checks=tuple(checks),
        failures=tuple(failures),
    )
