"""Token-protected HTTP queue for the Jev Browser Worker."""

from __future__ import annotations

import hmac
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
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
    return {
        "ok": _configured(),
        "service": "stroyka-jev-browser-worker",
        "environment": (os.environ.get("QA_ENVIRONMENT") or "unconfigured").lower(),
    }


@app.post("/jobs", status_code=202)
def create_job(request: JobRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    if not _configured():
        raise HTTPException(status_code=503, detail="QA worker is not fully configured")
    job_id = uuid4().hex
    _set_job(job_id, status="queued", result=None)
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
