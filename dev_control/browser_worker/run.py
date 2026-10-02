"""Run one isolated Jev browser-QA task and persist evidence."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from dev_control.browser_worker.provider import install_timeweb_provider
from dev_control.browser_worker.verifier import verify_final_state


def _assert_allowed_url(url: str, base_url: str) -> None:
    target = urlparse(url)
    base = urlparse(base_url)
    if target.scheme not in {"http", "https"}:
        raise ValueError("QA URL must use http or https")
    if not base.scheme or not base.netloc:
        raise ValueError("QA_BASE_URL must be an absolute URL")
    if (target.scheme, target.netloc) != (base.scheme, base.netloc):
        raise ValueError("QA URL is outside QA_BASE_URL origin")
    base_path = base.path.rstrip("/")
    if base_path and not (target.path == base_path or target.path.startswith(base_path + "/")):
        raise ValueError("QA URL is outside QA_BASE_URL path")


def _evidence_dir(value: str | None) -> Path:
    if value:
        path = Path(value)
    else:
        root = Path(os.environ.get("QA_EVIDENCE_DIR", "/tmp/stroyka-qa-evidence"))
        path = root / time.strftime("%Y%m%d-%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


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

    base_url = (os.environ.get("QA_BASE_URL") or "").strip()
    if not base_url:
        raise SystemExit("QA_BASE_URL is required; arbitrary browsing is disabled")
    _assert_allowed_url(args.url, base_url)

    evidence = _evidence_dir(args.record_dir)
    install_timeweb_provider()

    from jev_ultrafast import Agent

    started = time.monotonic()
    final_state = None
    error = None
    try:
        with Agent(args.url, args.goal, record_dir=evidence, screenshots=True) as agent:
            for state in agent.run():
                final_state = state
                if time.monotonic() - started > args.max_seconds:
                    error = f"worker_timeout>{args.max_seconds}s"
                    break
            if final_state is None:
                final_state = agent.snapshot()
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        final_state = final_state or {"status": "error", "page": {}}

    result = verify_final_state(
        final_state,
        expect_text=args.expect_text,
        forbid_text=args.forbid_text,
        expect_url_contains=args.expect_url_contains,
    )
    if error:
        result = type(result)(
            ok=False,
            checks=result.checks,
            failures=result.failures + (error,),
        )

    report = {
        "ok": result.ok,
        "checks": list(result.checks),
        "failures": list(result.failures),
        "status": final_state.get("status"),
        "final_url": (final_state.get("page") or {}).get("url"),
        "elapsed_ms": final_state.get("elapsed_ms"),
        "history": final_state.get("history", []),
        "decisions": [
            {
                "operation": item.get("operation"),
                "target": item.get("target"),
                "confidence": item.get("confidence"),
                "latency_ms": item.get("latency_ms"),
                "usage": item.get("usage", {}),
            }
            for item in final_state.get("decisions", [])
        ],
    }
    (evidence / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "ok": report["ok"],
        "status": report["status"],
        "final_url": report["final_url"],
        "checks": report["checks"],
        "failures": report["failures"],
        "evidence": str(evidence),
    }, ensure_ascii=False))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
