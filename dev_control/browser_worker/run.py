"""Run one isolated Jev browser-QA task and persist evidence."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from dev_control.browser_worker.network_guard import assert_allowed_document_url, install_safe_browser
from dev_control.browser_worker.provider import install_timeweb_provider
from dev_control.browser_worker.verifier import verify_final_state


def _assert_allowed_url(url: str, base_url: str) -> None:
    # Backward-compatible name used by offline tests.
    assert_allowed_document_url(url, base_url)


_SENSITIVE_PATH_MARKERS = frozenset({
    "reset", "password-reset", "magic", "magic-link", "verify", "verification",
    "invite", "invitation", "callback", "oauth", "token",
})


def _bounded_unquote_path(path: str) -> str | None:
    current = str(path or "")
    for _ in range(8):
        decoded = unquote(current)
        if decoded == current:
            return decoded.replace("\\", "/")
        current = decoded
    return None


def _redact_path(path: str) -> str:
    decoded = _bounded_unquote_path(path)
    if decoded is None:
        return "/[REDACTED]"
    segments = decoded.split("/")
    redact_next = False
    output = []
    for segment in segments:
        lowered = segment.lower()
        if redact_next and segment:
            output.append("[REDACTED]")
            redact_next = False
            continue
        output.append(segment)
        if lowered in _SENSITIVE_PATH_MARKERS:
            redact_next = True
    return "/".join(output)


def _bounded_unquote_query_key(value: str) -> str | None:
    current = str(value or "")
    for _ in range(8):
        decoded = unquote(current)
        if decoded == current:
            return decoded
        current = decoded
    return None


_SENSITIVE_QUERY_MARKERS = (
    "token", "code", "invite", "password", "secret", "key", "auth", "signature", "sig", "session",
)


def _redact_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(str(url))
    safe_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        decoded_key = _bounded_unquote_query_key(key)
        if decoded_key is None:
            safe_query.append(("[REDACTED_KEY]", "[REDACTED]"))
            continue
        lowered = decoded_key.lower()
        safe_query.append(
            (decoded_key, "[REDACTED]")
            if any(marker in lowered for marker in _SENSITIVE_QUERY_MARKERS)
            else (decoded_key, value)
        )
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port is not None else ""
    authority = f"{host}{port}"
    return urlunsplit((parts.scheme, authority, _redact_path(parts.path), urlencode(safe_query), ""))


def _sanitize_history(history: list[dict] | None) -> list[dict]:
    """Keep action metadata but never persist typed field values or helper output."""

    return [
        {
            "step": item.get("step"),
            "action": item.get("action"),
            "kind": item.get("kind"),
            "page_changed": item.get("page_changed"),
            "url": _redact_url(item.get("url")),
            "operation": item.get("operation"),
            "target": item.get("target"),
            "elapsed_ms": item.get("elapsed_ms"),
        }
        for item in (history or [])
    ]


def _sanitize_decisions(decisions: list[dict] | None) -> list[dict]:
    return [
        {
            "operation": item.get("operation"),
            "target": item.get("target"),
            "confidence": item.get("confidence"),
            "latency_ms": item.get("latency_ms"),
            "usage": item.get("usage", {}),
        }
        for item in (decisions or [])
    ]


def _evidence_dir(value: str | None) -> Path:
    if value:
        path = Path(value)
    else:
        root = Path(os.environ.get("QA_EVIDENCE_DIR", "/tmp/stroyka-qa-evidence"))
        path = root / time.strftime("%Y%m%d-%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_progress(
    evidence: Path,
    state: dict | None,
    phase: str,
    *,
    verified_ok: bool | None = None,
    checks: list[str] | tuple[str, ...] = (),
    failures: list[str] | tuple[str, ...] = (),
) -> None:
    """Persist a small redacted live-view snapshot without typed values or prompts."""

    state = state or {}
    payload = {
        "phase": phase,
        "status": state.get("status"),
        "current_url": _redact_url((state.get("page") or {}).get("url")),
        "elapsed_ms": state.get("elapsed_ms"),
        "history": _sanitize_history(state.get("history")),
        "decisions": _sanitize_decisions(state.get("decisions")),
        "updated_at_ms": int(time.time() * 1000),
    }
    if verified_ok is not None:
        payload.update(
            verified_ok=bool(verified_ok),
            checks=list(checks),
            failures=list(failures),
        )
    temporary = evidence / ".progress.json.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, evidence / "progress.json")
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _refresh_live_observation(agent, state: dict, base_url: str) -> dict:
    browser = agent.browser
    boundary = getattr(browser, "_qa_boundary", None)
    if boundary is not None:
        boundary.raise_if_failed()
    live_url = str(browser.evaluate("location.href") or "")
    _assert_allowed_url(live_url, base_url)
    full_text = browser.evaluate("document.body ? document.body.innerText : ''") or ""
    if boundary is not None:
        boundary.raise_if_failed()
    page = state.setdefault("page", {})
    page["url"] = live_url
    page["full_text"] = str(full_text)
    return state


def execute_task(
    *,
    url: str,
    goal: str,
    record_dir: str | None = None,
    expect_text: list[str] | None = None,
    forbid_text: list[str] | None = None,
    expect_url_contains: list[str] | None = None,
    max_seconds: float = 90.0,
    read_only: bool = False,
) -> dict:
    base_url = (os.environ.get("QA_BASE_URL") or "").strip()
    if not base_url:
        raise ValueError("QA_BASE_URL is required; arbitrary browsing is disabled")
    _assert_allowed_url(url, base_url)
    if not goal.strip():
        raise ValueError("goal must not be empty")
    if not any((expect_text or (), forbid_text or (), expect_url_contains or ())):
        raise ValueError("at least one deterministic browser assertion is required")

    evidence = _evidence_dir(record_dir)
    provider_patch = None if read_only else install_timeweb_provider()
    install_safe_browser(base_url, read_only=read_only)

    from jev_ultrafast import Agent

    started = time.monotonic()
    final_state = None
    error = None
    try:
        with Agent(url, goal, record_dir=evidence, screenshots=True) as agent:
            _write_progress(evidence, agent.snapshot(), "observed")
            if read_only:
                # Hard read-only mode: never invoke agent.run(), so the model
                # cannot click, type, select, submit, or mutate application data.
                deadline = started + min(max_seconds, 30.0)
                while True:
                    final_state = agent.snapshot()
                    try:
                        final_state = _refresh_live_observation(agent, final_state, base_url)
                    except Exception as exc:
                        error = f"read_only_live_observation_failed: {type(exc).__name__}: {exc}"
                        break
                    probe = verify_final_state(
                        final_state,
                        expect_text=expect_text or (),
                        forbid_text=forbid_text or (),
                        expect_url_contains=expect_url_contains or (),
                        require_agent_done=False,
                    )
                    _write_progress(
                        evidence,
                        final_state,
                        "read_only_observation",
                        verified_ok=probe.ok,
                        checks=probe.checks,
                        failures=probe.failures,
                    )
                    if probe.ok or time.monotonic() >= deadline:
                        break
                    time.sleep(1.0)
            else:
                for state in agent.run():
                    final_state = state
                    _write_progress(evidence, final_state, "action_complete")
                    current_url = str((state.get("page") or {}).get("url") or "")
                    try:
                        _assert_allowed_url(current_url, base_url)
                    except ValueError as exc:
                        error = f"outside_qa_scope: {exc}"
                        break
                    if time.monotonic() - started > max_seconds:
                        error = f"worker_timeout>{max_seconds}s"
                        break
                if final_state is None:
                    final_state = agent.snapshot()
                final_state = _refresh_live_observation(agent, final_state, base_url)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        final_state = final_state or {"status": "error", "page": {}}
    finally:
        if provider_patch is not None:
            provider_patch.restore()

    result = verify_final_state(
        final_state,
        expect_text=expect_text or (),
        forbid_text=forbid_text or (),
        expect_url_contains=expect_url_contains or (),
        require_agent_done=not read_only,
    )
    if read_only and (
        (final_state or {}).get("history") or (final_state or {}).get("decisions")
    ):
        result = type(result)(
            ok=False,
            checks=result.checks,
            failures=result.failures + ("read_only_action_detected",),
        )
    if error:
        result = type(result)(
            ok=False,
            checks=result.checks,
            failures=result.failures + (error,),
        )

    _write_progress(
        evidence,
        final_state,
        "verification_complete",
        verified_ok=result.ok,
        checks=result.checks,
        failures=result.failures,
    )

    report = {
        "ok": result.ok,
        "checks": list(result.checks),
        "failures": list(result.failures),
        "status": final_state.get("status"),
        "final_url": _redact_url((final_state.get("page") or {}).get("url")),
        "elapsed_ms": final_state.get("elapsed_ms"),
        "history": _sanitize_history(final_state.get("history")),
        "decisions": _sanitize_decisions(final_state.get("decisions")),
        "read_only": bool(read_only),
        "evidence": str(evidence),
    }
    (evidence / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stroyka Jev Browser QA worker")
    parser.add_argument("--url", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--record-dir")
    parser.add_argument("--expect-text", action="append", default=[])
    parser.add_argument("--forbid-text", action="append", default=[])
    parser.add_argument("--expect-url-contains", action="append", default=[])
    parser.add_argument("--max-seconds", type=float, default=90.0)
    args = parser.parse_args()

    try:
        report = execute_task(
            url=args.url,
            goal=args.goal,
            record_dir=args.record_dir,
            expect_text=args.expect_text,
            forbid_text=args.forbid_text,
            expect_url_contains=args.expect_url_contains,
            max_seconds=args.max_seconds,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2

    print(json.dumps({
        "ok": report["ok"],
        "status": report["status"],
        "final_url": report["final_url"],
        "checks": report["checks"],
        "failures": report["failures"],
        "evidence": report["evidence"],
    }, ensure_ascii=False))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
