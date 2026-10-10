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
    require_agent_done: bool = True,
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
    if require_agent_done:
        if status == "done":
            checks.append("agent_status=done")
        else:
            failures.append(f"agent_status={status or 'missing'}")
    else:
        checks.append("read_only_observation")

    page = state.get("page") or {}
    text = str(page.get("text") or "")
    full_text_value = page.get("full_text")
    full_text = str(full_text_value) if full_text_value is not None else None
    url = str(page.get("url") or "")

    for index, needle in enumerate(expect_text):
        haystack = full_text if full_text is not None else text
        if needle in haystack:
            checks.append(f"expect_text[{index}]:present")
        else:
            failures.append(f"expect_text[{index}]:missing")

    for index, needle in enumerate(forbid_text):
        if full_text is None:
            failures.append(f"forbid_text[{index}]:full_text_unavailable")
        elif needle not in full_text:
            checks.append(f"forbid_text[{index}]:absent")
        else:
            failures.append(f"forbid_text[{index}]:present")

    for index, needle in enumerate(expect_url_contains):
        if needle in url:
            checks.append(f"expect_url_contains[{index}]:present")
        else:
            failures.append(f"expect_url_contains[{index}]:missing")

    return VerificationResult(
        ok=not failures,
        checks=tuple(checks),
        failures=tuple(failures),
    )
