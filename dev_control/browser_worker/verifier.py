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

    status = str(state.get("status") or "")
    if status == "done":
        checks.append("agent_status=done")
    else:
        failures.append(f"agent_status={status or 'missing'}")

    page = state.get("page") or {}
    text = str(page.get("text") or "")
    url = str(page.get("url") or "")

    for needle in expect_text:
        if needle in text:
            checks.append(f"text_present:{needle}")
        else:
            failures.append(f"text_missing:{needle}")

    for needle in forbid_text:
        if needle not in text:
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
