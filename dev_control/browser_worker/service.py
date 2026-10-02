"""Token-protected HTTP queue for the Jev Browser Worker."""

from __future__ import annotations

import hmac
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from dev_control.browser_worker.run import execute_task


app = FastAPI(title="Stroyka Dev Control Browser Worker", docs_url=None, redoc_url=None)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-qa")
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


class JobRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    goal: str = Field(min_length=3, max_length=6000)
    expect_text: list[str] = Field(default_factory=list, max_length=20)
    forbid_text: list[str] = Field(default_factory=list, max_length=20)
    expect_url_contains: list[str] = Field(default_factory=list, max_length=20)
    max_seconds: float = Field(default=90.0, ge=5.0, le=180.0)


def _selftest_base_url() -> str:
    port = (os.environ.get("PORT") or "8080").strip()
    if not port.isdigit():
        port = "8080"
    return f"http://127.0.0.1:{port}"


def _startup_selftest_enabled() -> bool:
    return (
        (os.environ.get("QA_SELFTEST_ON_START") or "").strip() == "1"
        and (os.environ.get("QA_BASE_URL") or "").strip().rstrip("/") == _selftest_base_url()
        and (os.environ.get("QA_ENVIRONMENT") or "").strip().lower() in {"qa", "test", "staging"}
        and bool((os.environ.get("TIMEWEB_AI_API_KEY") or "").strip())
    )


def _configured() -> bool:
    return bool(
        (os.environ.get("DEV_CONTROL_API_TOKEN") or "").strip()
        and (os.environ.get("TIMEWEB_AI_API_KEY") or "").strip()
        and (os.environ.get("QA_BASE_URL") or "").strip()
        and (os.environ.get("QA_ENVIRONMENT") or "").strip().lower() in {"qa", "test", "staging"}
    )


def _authorize(authorization: str | None) -> None:
    expected = (os.environ.get("DEV_CONTROL_API_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="worker API token is not configured")
    prefix = "Bearer "
    supplied = authorization[len(prefix):].strip() if authorization and authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _max_pending_jobs() -> int:
    raw = (os.environ.get("QA_MAX_PENDING_JOBS") or "2").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 2
    return min(max(value, 1), 10)


def _pending_job_count() -> int:
    return sum(
        1
        for value in _jobs.values()
        if value.get("status") in {"queued", "running"}
    )


def _set_job(job_id: str, **values) -> None:
    with _jobs_lock:
        current = _jobs.setdefault(job_id, {})
        current.update(values)
        # Keep bounded in-memory history; durable reporting belongs to Work Control.
        if len(_jobs) > 100:
            finished = [key for key, value in _jobs.items() if value.get("status") in {"passed", "failed"}]
            for key in finished[: len(_jobs) - 100]:
                _jobs.pop(key, None)


def _execute(job_id: str, request: JobRequest) -> None:
    _set_job(job_id, status="running")
    root = Path(os.environ.get("QA_EVIDENCE_DIR", "/tmp/stroyka-qa-evidence"))
    record_dir = str(root / job_id)
    try:
        report = execute_task(
            url=request.url,
            goal=request.goal,
            record_dir=record_dir,
            expect_text=request.expect_text,
            forbid_text=request.forbid_text,
            expect_url_contains=request.expect_url_contains,
            max_seconds=request.max_seconds,
        )
    except Exception as exc:
        _set_job(
            job_id,
            status="failed",
            result={"ok": False, "failures": [f"{type(exc).__name__}: {exc}"]},
        )
        return
    _set_job(job_id, status="passed" if report.get("ok") else "failed", result=report)


@app.get("/health")
def health():
    with _jobs_lock:
        selftest = _jobs.get("startup-selftest")
        selftest_status = selftest.get("status") if selftest else "not_requested"
    return {
        "ok": _configured(),
        "service": "stroyka-jev-browser-worker",
        "environment": (os.environ.get("QA_ENVIRONMENT") or "unconfigured").lower(),
        "startup_selftest": selftest_status,
    }


@app.get("/selftest-page", response_class=HTMLResponse)
def selftest_page():
    return """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Stroyka Jev Self Test</title></head>
<body>
  <h1>Stroyka Jev Browser Self Test</h1>
  <p id="result">WAITING</p>
  <button id="run-test" onclick="document.getElementById('result').textContent='JEV_BROWSER_OK'; this.disabled=true">
    Run browser self-test
  </button>
</body>
</html>"""


def _run_startup_selftest() -> None:
    # Uvicorn begins accepting connections immediately after startup returns.
    time.sleep(1.0)
    request = JobRequest(
        url=f"{_selftest_base_url()}/selftest-page",
        goal="Click the Run browser self-test button. Finish only when JEV_BROWSER_OK is visibly present.",
        expect_text=["JEV_BROWSER_OK"],
        forbid_text=[],
        expect_url_contains=["/selftest-page"],
        max_seconds=60.0,
    )
    _execute("startup-selftest", request)


@app.on_event("startup")
def schedule_startup_selftest():
    if _startup_selftest_enabled():
        _set_job("startup-selftest", status="queued", result=None)
        _executor.submit(_run_startup_selftest)


@app.post("/jobs", status_code=202)
def create_job(request: JobRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    if not _configured():
        raise HTTPException(status_code=503, detail="QA worker is not fully configured")
    with _jobs_lock:
        if _pending_job_count() >= _max_pending_jobs():
            raise HTTPException(status_code=429, detail="QA queue is full")
        job_id = uuid4().hex
        current = _jobs.setdefault(job_id, {})
        current.update(status="queued", result=None)
    _executor.submit(_execute, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {"job_id": job_id, **job}
