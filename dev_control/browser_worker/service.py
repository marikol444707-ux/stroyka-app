"""Token-protected HTTP queue for the Jev Browser Worker."""

from __future__ import annotations

import hmac
import multiprocessing
import os
import shutil
import threading
import queue
import re
import time
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from dev_control.browser_worker.network_guard import assert_allowed_document_url
from dev_control.browser_worker.run import execute_task


_MAX_JOB_BODY_BYTES = 32 * 1024


class PreAuthBodyLimitMiddleware:
    """Authenticate /jobs and cap request bytes before FastAPI parses JSON."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not (
            scope.get("method") == "POST" and scope.get("path") == "/jobs"
        ):
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        expected = (os.environ.get("DEV_CONTROL_API_TOKEN") or "").strip()
        supplied = headers.get("authorization", "")
        prefix = "Bearer "
        token = supplied[len(prefix):].strip() if supplied.startswith(prefix) else ""
        if not expected or not token or not hmac.compare_digest(token, expected):
            response = JSONResponse(status_code=401, content={"detail": "unauthorized"})
            await response(scope, receive, send)
            return

        content_length = headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > _MAX_JOB_BODY_BYTES:
                    response = JSONResponse(status_code=413, content={"detail": "request body too large"})
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(status_code=400, content={"detail": "invalid content-length"})
                await response(scope, receive, send)
                return

        total = 0
        buffered = []
        more = True
        while more:
            message = await receive()
            if message.get("type") == "http.disconnect":
                response = JSONResponse(status_code=400, content={"detail": "client disconnected"})
                try:
                    await response(scope, receive, send)
                except Exception:
                    pass
                return
            if message.get("type") != "http.request":
                continue
            body = message.get("body", b"")
            total += len(body)
            if total > _MAX_JOB_BODY_BYTES:
                response = JSONResponse(status_code=413, content={"detail": "request body too large"})
                await response(scope, receive, send)
                return
            buffered.append(body)
            more = bool(message.get("more_body"))

        payload = b"".join(buffered)
        delivered = False

        async def replay_receive():
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": payload, "more_body": False}

        await self.app(scope, replay_receive, send)


app = FastAPI(title="Stroyka Dev Control Browser Worker", docs_url=None, redoc_url=None)
app.add_middleware(PreAuthBodyLimitMiddleware)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jev-qa")
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_PRODUCTION_HOSTS = frozenset({
    "stroyka26.pro",
    "www.stroyka26.pro",
    "stroyka.pro",
    "www.stroyka.pro",
})


class JobRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    goal: str = Field(min_length=3, max_length=6000)
    expect_text: list[str] = Field(default_factory=list, max_length=20)
    forbid_text: list[str] = Field(default_factory=list, max_length=20)
    expect_url_contains: list[str] = Field(default_factory=list, max_length=20)
    max_seconds: float = Field(default=90.0, ge=5.0, le=180.0)

    @field_validator("expect_text", "forbid_text", "expect_url_contains")
    @classmethod
    def assertions_must_be_nonblank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("assertions must contain non-whitespace text")
        return cleaned


def _selftest_base_url() -> str:
    port = (os.environ.get("PORT") or "8080").strip()
    if not port.isdigit():
        port = "8080"
    return f"http://127.0.0.1:{port}"


def _qa_base_is_nonproduction() -> bool:
    base = (os.environ.get("QA_BASE_URL") or "").strip()
    parsed = urlparse(base)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or parsed.scheme not in {"http", "https"}:
        return False
    try:
        assert_allowed_document_url(base, base)
    except ValueError:
        return False
    if host in _PRODUCTION_HOSTS:
        return False
    if host in {"127.0.0.1", "localhost"}:
        return base.rstrip("/") == _selftest_base_url()
    return True


def _startup_selftest_enabled() -> bool:
    return (
        (os.environ.get("QA_SELFTEST_ON_START") or "").strip() == "1"
        and (os.environ.get("QA_BASE_URL") or "").strip().rstrip("/") == _selftest_base_url()
        and (os.environ.get("QA_ENVIRONMENT") or "").strip().lower() in {"qa", "test", "staging"}
        and bool((os.environ.get("TIMEWEB_AI_API_KEY") or "").strip())
    )


def _chrome_alive() -> bool:
    cdp_url = (os.environ.get("BU_CDP_URL") or "http://127.0.0.1:9222").rstrip("/")
    try:
        with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=0.5) as response:
            return 200 <= int(getattr(response, "status", 200)) < 300
    except Exception:
        return False


def _configured() -> bool:
    return bool(
        (os.environ.get("DEV_CONTROL_API_TOKEN") or "").strip()
        and (os.environ.get("TIMEWEB_AI_API_KEY") or "").strip()
        and (os.environ.get("QA_BASE_URL") or "").strip()
        and _qa_base_is_nonproduction()
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


def _evidence_ttl_seconds() -> int:
    raw = (os.environ.get("QA_EVIDENCE_TTL_SECONDS") or "3600").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 3600
    return min(max(value, 60), 86400)


def _evidence_root() -> Path:
    return Path(os.environ.get("QA_EVIDENCE_DIR", "/tmp/stroyka-qa-evidence"))


def _cleanup_expired_evidence() -> None:
    root = _evidence_root()
    if not root.exists():
        return
    cutoff = time.time() - _evidence_ttl_seconds()
    with _jobs_lock:
        active = {
            job_id
            for job_id, value in _jobs.items()
            if value.get("status") in {"queued", "running"}
        }
    for child in root.iterdir():
        try:
            if not _valid_job_id(child.name):
                continue
            if child.name in active:
                continue
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child)
        except OSError:
            continue


def _pending_job_count() -> int:
    return sum(1 for value in _jobs.values() if value.get("status") in {"queued", "running"})


def _set_job(job_id: str, **values) -> None:
    with _jobs_lock:
        current = _jobs.setdefault(job_id, {})
        current.update(values)
        if len(_jobs) > 100:
            finished = [key for key, value in _jobs.items() if value.get("status") in {"passed", "failed"}]
            for key in finished[: len(_jobs) - 100]:
                _jobs.pop(key, None)


def _task_process_entry(payload: dict, result_queue) -> None:
    try:
        report = execute_task(**payload)
    except Exception as exc:
        result_queue.put({"ok": False, "failures": [f"{type(exc).__name__}: {exc}"]})
        return
    result_queue.put(report)


_JOB_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _valid_job_id(job_id: str) -> bool:
    return job_id == "startup-selftest" or bool(_JOB_ID_RE.fullmatch(job_id))


def _job_evidence_dir(job_id: str) -> Path:
    if not _valid_job_id(job_id):
        raise ValueError("invalid job id")
    root = _evidence_root().resolve()
    path = (root / job_id).resolve()
    if path.parent != root:
        raise ValueError("evidence path escapes root")
    return path


def _cleanup_qa_browser_contexts() -> None:
    """Best-effort cleanup after a killed subprocess; contexts are QA-owned only."""

    try:
        from browser_harness.helpers import cdp
        contexts = cdp("Target.getBrowserContexts").get("browserContextIds", [])
        for context_id in contexts:
            try:
                cdp("Target.disposeBrowserContext", browserContextId=context_id)
            except Exception:
                pass
    except Exception:
        pass


def _evidence_files(job_id: str) -> list[str]:
    try:
        root = _job_evidence_dir(job_id)
    except ValueError:
        return []
    if not root.is_dir():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_file() and (path.suffix.lower() == ".jpg" or path.name == "result.json")
    )


def _execute(job_id: str, request: JobRequest) -> None:
    _set_job(job_id, status="running")
    record_dir = str(_job_evidence_dir(job_id))
    payload = {
        "url": request.url,
        "goal": request.goal,
        "record_dir": record_dir,
        "expect_text": request.expect_text,
        "forbid_text": request.forbid_text,
        "expect_url_contains": request.expect_url_contains,
        "max_seconds": request.max_seconds,
    }

    process = None
    try:
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue(maxsize=1)
        process = ctx.Process(target=_task_process_entry, args=(payload, result_queue))
        process.start()

        deadline = time.monotonic() + request.max_seconds
        report = None
        while time.monotonic() < deadline:
            remaining = max(0.05, min(0.5, deadline - time.monotonic()))
            try:
                report = result_queue.get(timeout=remaining)
                break
            except queue.Empty:
                if not process.is_alive():
                    break

        if report is None and process.is_alive():
            process.terminate()
            process.join(timeout=3.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)
            _cleanup_qa_browser_contexts()
            report = {"ok": False, "failures": [f"worker_timeout>{request.max_seconds}s"]}
        elif report is None:
            process.join(timeout=1.0)
            _cleanup_qa_browser_contexts()
            report = {
                "ok": False,
                "failures": [f"browser subprocess exited without result (code={process.exitcode})"],
            }
        else:
            process.join(timeout=3.0)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1.0)
    except Exception as exc:
        if process is not None and process.is_alive():
            process.terminate()
            process.join(timeout=1.0)
        _cleanup_qa_browser_contexts()
        report = {
            "ok": False,
            "failures": [f"browser subprocess startup failed: {type(exc).__name__}: {exc}"],
        }

    report.pop("evidence", None)
    evidence_dir = _job_evidence_dir(job_id)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    files = _evidence_files(job_id)
    report["evidence_files"] = [
        f"/jobs/{job_id}/evidence/{name}"
        for name in files
    ]
    _set_job(job_id, status="passed" if report.get("ok") else "failed", result=report)


@app.get("/health")
def health():
    _cleanup_expired_evidence()
    with _jobs_lock:
        selftest = _jobs.get("startup-selftest")
        selftest_status = selftest.get("status") if selftest else "not_requested"

    ready = _configured() and _chrome_alive()
    if _startup_selftest_enabled():
        ready = ready and selftest_status == "passed"

    payload = {
        "ok": ready,
        "service": "stroyka-jev-browser-worker",
        "environment": (os.environ.get("QA_ENVIRONMENT") or "unconfigured").lower(),
        "startup_selftest": selftest_status,
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


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
    time.sleep(1.0)
    request = JobRequest(
        url=f"{_selftest_base_url()}/selftest-page",
        goal="Click the Run browser self-test button. Finish only when JEV_BROWSER_OK is visibly present.",
        expect_text=["JEV_BROWSER_OK"],
        expect_url_contains=["/selftest-page"],
        max_seconds=60.0,
    )
    _execute("startup-selftest", request)


@app.on_event("startup")
def schedule_startup_selftest():
    _cleanup_expired_evidence()
    if _startup_selftest_enabled():
        _set_job("startup-selftest", status="queued", result=None)
        _executor.submit(_run_startup_selftest)


@app.post("/jobs", status_code=202)
def create_job(request: JobRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    _cleanup_expired_evidence()
    if not _configured():
        raise HTTPException(status_code=503, detail="QA worker is not fully configured")
    if not any((request.expect_text, request.forbid_text, request.expect_url_contains)):
        raise HTTPException(status_code=422, detail="at least one deterministic browser assertion is required")
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
    _cleanup_expired_evidence()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return {"job_id": job_id, **job}


@app.get("/jobs/{job_id}/evidence/{filename}")
def get_evidence(job_id: str, filename: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    _cleanup_expired_evidence()
    if not _valid_job_id(job_id) or "/" in filename or "\\" in filename or filename not in _evidence_files(job_id):
        raise HTTPException(status_code=404, detail="evidence not found")
    try:
        path = _job_evidence_dir(job_id) / filename
    except ValueError:
        raise HTTPException(status_code=404, detail="evidence not found")
    media_type = "application/json" if filename == "result.json" else "image/jpeg"
    return FileResponse(path, media_type=media_type, filename=filename)
