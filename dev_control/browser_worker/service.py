"""Token-protected HTTP queue for the Jev Browser Worker."""

from __future__ import annotations

import hashlib
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

from dev_control.browser_worker.network_guard import (
    assert_allowed_document_url,
    assert_dedicated_loopback_cdp_url,
)
from dev_control.browser_worker.run import execute_task
from dev_control.browser_worker.viewer import VIEWER_HTML, viewer_headers


_MAX_JOB_BODY_BYTES = 32 * 1024
_API_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _worker_api_token() -> str:
    value = (os.environ.get("DEV_CONTROL_API_TOKEN") or "").strip()
    return value if _API_TOKEN_RE.fullmatch(value) else ""


def _watcher_scoped_token(token: str) -> str:
    """Derive a one-way credential that cannot authorize the general /jobs API."""
    return hmac.new(
        token.encode("ascii"),
        b"stroyka-jev-watch-read-only-v2",
        hashlib.sha256,
    ).hexdigest()


def _watcher_signature(
    scoped_token: str,
    method: str,
    path: str,
    timestamp: str,
    nonce: str,
    body: bytes = b"",
) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    message = "\n".join((
        method.upper(),
        path,
        timestamp,
        nonce,
        body_hash,
    )).encode("utf-8")
    return hmac.new(bytes.fromhex(scoped_token), message, hashlib.sha256).hexdigest()


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
        expected = _worker_api_token()
        supplied = headers.get("authorization", "")
        prefix = "Bearer "
        token = supplied[len(prefix):].strip() if supplied.startswith(prefix) else ""
        if not expected:
            response = JSONResponse(status_code=503, content={"detail": "worker API token is not securely configured"})
            await response(scope, receive, send)
            return
        if not token or not hmac.compare_digest(token, expected):
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
_active_process_lock = threading.Lock()
_active_process = None
_active_job_id = None
_accepting_jobs = True
_watcher_nonce_lock = threading.Lock()
_watcher_seen_nonces: dict[str, int] = {}
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
    display_name: str | None = Field(default=None, max_length=160)
    issue_number: int | None = Field(default=None, ge=1)
    pr_number: int | None = Field(default=None, ge=1)
    commit_sha: str | None = Field(default=None, min_length=7, max_length=64)
    read_only: bool = False

    @field_validator("commit_sha")
    @classmethod
    def commit_sha_must_be_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{7,64}", value):
            raise ValueError("commit_sha must contain only hexadecimal characters")
        return value

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

    if host in {"127.0.0.1", "localhost"}:
        return base.rstrip("/") == _selftest_base_url()

    # Remote QA is fail-closed: the operator must explicitly register the exact
    # QA origin. This prevents production IPs, subdomains and aliases from being
    # accepted merely because they were absent from a denylist.
    allowed_origin = (os.environ.get("QA_ALLOWED_ORIGIN") or "").strip().rstrip("/")
    if not allowed_origin:
        return False
    allowed = urlparse(allowed_origin)
    allowed_host = (allowed.hostname or "").lower().rstrip(".")
    if allowed.scheme != "https" or parsed.scheme != "https":
        return False
    try:
        parsed_port = parsed.port or 443
        allowed_port = allowed.port or 443
    except ValueError:
        return False
    if (parsed.scheme, host, parsed_port) != (
        allowed.scheme,
        allowed_host,
        allowed_port,
    ):
        return False
    if host in _PRODUCTION_HOSTS or host.endswith(".stroyka26.pro") or host.endswith(".stroyka.pro"):
        return False
    if host == "147.45.237.127":
        return False
    return True


def _cdp_is_dedicated_loopback() -> bool:
    try:
        assert_dedicated_loopback_cdp_url()
        return True
    except ValueError:
        return False


def _startup_selftest_enabled() -> bool:
    return (
        (os.environ.get("QA_SELFTEST_ON_START") or "").strip() == "1"
        and (os.environ.get("QA_BASE_URL") or "").strip().rstrip("/") == _selftest_base_url()
        and (os.environ.get("QA_ENVIRONMENT") or "").strip().lower() in {"qa", "test", "staging"}
        and bool((os.environ.get("TIMEWEB_AI_API_KEY") or "").strip())
        and _cdp_is_dedicated_loopback()
    )


def _chrome_alive() -> bool:
    try:
        cdp_url = assert_dedicated_loopback_cdp_url()
    except ValueError:
        return False
    try:
        with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=0.5) as response:
            return 200 <= int(getattr(response, "status", 200)) < 300
    except Exception:
        return False


def _configured() -> bool:
    return bool(
        _worker_api_token()
        and (os.environ.get("TIMEWEB_AI_API_KEY") or "").strip()
        and (os.environ.get("QA_BASE_URL") or "").strip()
        and _qa_base_is_nonproduction()
        and _cdp_is_dedicated_loopback()
        and (os.environ.get("QA_ENVIRONMENT") or "").strip().lower() in {"qa", "test", "staging"}
    )


def _authorize(authorization: str | None) -> None:
    expected = _worker_api_token()
    if not expected:
        raise HTTPException(status_code=503, detail="worker API token is not securely configured")
    prefix = "Bearer "
    supplied = authorization[len(prefix):].strip() if authorization and authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="unauthorized")



def _authorize_watcher_request(
    method: str,
    path: str,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
) -> None:
    token = _worker_api_token()
    if not token:
        raise HTTPException(status_code=503, detail="worker API token is not securely configured")
    if not timestamp or not nonce or not signature:
        raise HTTPException(status_code=401, detail="watcher authentication required")
    if not re.fullmatch(r"[0-9]{10}", timestamp):
        raise HTTPException(status_code=401, detail="invalid watcher timestamp")
    if not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise HTTPException(status_code=401, detail="invalid watcher nonce")
    if not re.fullmatch(r"[0-9a-f]{64}", signature):
        raise HTTPException(status_code=401, detail="invalid watcher signature")
    now = int(time.time())
    issued = int(timestamp)
    if abs(now - issued) > 60:
        raise HTTPException(status_code=401, detail="stale watcher request")
    scoped = _watcher_scoped_token(token)
    expected = _watcher_signature(scoped, method, path, timestamp, nonce)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid watcher signature")
    with _watcher_nonce_lock:
        cutoff = now - 120
        for seen, seen_at in list(_watcher_seen_nonces.items()):
            if seen_at < cutoff:
                _watcher_seen_nonces.pop(seen, None)
        if nonce in _watcher_seen_nonces:
            raise HTTPException(status_code=409, detail="watcher nonce replay")
        _watcher_seen_nonces[nonce] = now


def _watcher_auth(
    method: str,
    path: str,
    x_jev_watcher_time: str | None,
    x_jev_watcher_nonce: str | None,
    x_jev_watcher_signature: str | None,
) -> None:
    _authorize_watcher_request(
        method,
        path,
        x_jev_watcher_time,
        x_jev_watcher_nonce,
        x_jev_watcher_signature,
    )


def _watcher_job_is_owned(job_id: str) -> bool:
    with _jobs_lock:
        job = _jobs.get(job_id) or {}
        metadata = job.get("metadata") or {}
        return bool(metadata.get("watcher_owned") and metadata.get("read_only"))


def _watcher_smoke_request() -> JobRequest:
    base = (os.environ.get("QA_BASE_URL") or "").strip()
    host = (urlparse(base).hostname or "").lower()
    if not base or not host:
        raise HTTPException(status_code=503, detail="QA worker is not fully configured")
    return JobRequest(
        url=base,
        goal=(
            "Observe the authenticated Stroyka QA application until the navigation "
            "menu including Склад is visible. This job is server-enforced read-only."
        ),
        expect_text=["Склад"],
        expect_url_contains=[host],
        max_seconds=60.0,
        display_name="Daily QA read-only smoke",
        issue_number=311,
        read_only=True,
    )

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


def _evidence_max_bytes() -> int:
    raw = (os.environ.get("QA_EVIDENCE_MAX_BYTES") or str(8 * 1024 * 1024)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = 8 * 1024 * 1024
    return min(max(value, 1024 * 1024), 32 * 1024 * 1024)


def _evidence_non_result_bytes(folder: Path) -> int:
    return sum(
        path.stat().st_size
        for path in folder.iterdir()
        if path.is_file() and path.name != "result.json"
    )


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
            if value.get("status") in {"queued", "running", "cancelling"}
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
    return sum(
        1
        for value in _jobs.values()
        if value.get("queue_pending")
        or value.get("status") in {"queued", "running", "cancelling"}
    )


def _set_job(job_id: str, **values) -> None:
    with _jobs_lock:
        current = _jobs.setdefault(job_id, {})
        current.update(values)
        current["updated_at_ms"] = int(time.time() * 1000)
        if len(_jobs) > 100:
            finished = [
                key
                for key, value in _jobs.items()
                if key != "startup-selftest" and value.get("status") in {"passed", "failed", "cancelled"}
            ]
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


def _read_progress(job_id: str) -> dict | None:
    try:
        path = _job_evidence_dir(job_id) / "progress.json"
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _cancel_requested(job_id: str) -> bool:
    with _jobs_lock:
        return bool((_jobs.get(job_id) or {}).get("cancel_requested"))


def _stop_subprocess(process, *, timeout: float = 2.0) -> None:
    if process is None:
        return
    if process.is_alive():
        process.terminate()
    process.join(timeout=timeout)
    if process.is_alive():
        process.kill()
        process.join(timeout=1.0)


def _commit_final_state(job_id: str, report: dict) -> tuple[dict, str]:
    """Atomically arbitrate completion vs an already-acknowledged owner cancel."""
    with _jobs_lock:
        current = _jobs.setdefault(job_id, {})
        if current.get("cancel_requested") and not report.get("cancelled"):
            report = {
                "ok": False,
                "cancelled": True,
                "failures": ["cancelled_by_owner"],
                "evidence_files": list(report.get("evidence_files") or []),
            }
        final_status = "cancelled" if report.get("cancelled") else ("passed" if report.get("ok") else "failed")
        current.update(
            status=final_status,
            result=report,
            queue_pending=False,
            updated_at_ms=int(time.time() * 1000),
        )
        if len(_jobs) > 100:
            finished = [
                key
                for key, value in _jobs.items()
                if key != "startup-selftest"
                and not value.get("queue_pending")
                and value.get("status") in {"passed", "failed", "cancelled"}
            ]
            for key in finished[: len(_jobs) - 100]:
                _jobs.pop(key, None)
    return report, final_status


def _execute(job_id: str, request: JobRequest) -> None:
    with _jobs_lock:
        current = _jobs.setdefault(job_id, {})
        current["queue_pending"] = False
        if current.get("cancel_requested"):
            current.update(
                status="cancelled",
                result={"ok": False, "cancelled": True, "failures": ["cancelled_by_owner"], "evidence_files": []},
                updated_at_ms=int(time.time() * 1000),
            )
            return
        current.update(status="running", updated_at_ms=int(time.time() * 1000))
    record_dir = str(_job_evidence_dir(job_id))
    payload = {
        "url": request.url,
        "goal": request.goal,
        "record_dir": record_dir,
        "expect_text": request.expect_text,
        "forbid_text": request.forbid_text,
        "expect_url_contains": request.expect_url_contains,
        "max_seconds": request.max_seconds,
        "read_only": request.read_only,
    }

    process = None
    try:
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue(maxsize=1)
        process = ctx.Process(target=_task_process_entry, args=(payload, result_queue))
        process.start()
        global _active_process, _active_job_id
        with _active_process_lock:
            _active_process = process
            _active_job_id = job_id

        deadline = time.monotonic() + request.max_seconds
        report = None
        while time.monotonic() < deadline:
            if _cancel_requested(job_id):
                _stop_subprocess(process)
                _cleanup_qa_browser_contexts()
                report = {"ok": False, "cancelled": True, "failures": ["cancelled_by_owner"]}
                break
            remaining = max(0.05, min(0.5, deadline - time.monotonic()))
            try:
                report = result_queue.get(timeout=remaining)
                if _cancel_requested(job_id):
                    _stop_subprocess(process)
                    _cleanup_qa_browser_contexts()
                    report = {"ok": False, "cancelled": True, "failures": ["cancelled_by_owner"]}
                break
            except queue.Empty:
                if not process.is_alive():
                    break

        if report is None and _cancel_requested(job_id):
            _stop_subprocess(process)
            _cleanup_qa_browser_contexts()
            report = {"ok": False, "cancelled": True, "failures": ["cancelled_by_owner"]}
        elif report is None and process.is_alive():
            _stop_subprocess(process, timeout=3.0)
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
                _stop_subprocess(process, timeout=1.0)
    except Exception as exc:
        if process is not None:
            _stop_subprocess(process, timeout=1.0)
        _cleanup_qa_browser_contexts()
        report = {
            "ok": False,
            "failures": [f"browser subprocess startup failed: {type(exc).__name__}: {exc}"],
        }

    with _active_process_lock:
        if _active_process is process:
            _active_process = None
            _active_job_id = None

    report.pop("evidence", None)
    try:
        evidence_dir = _job_evidence_dir(job_id)
        evidence_dir.mkdir(parents=True, exist_ok=True)

        non_result_size = _evidence_non_result_bytes(evidence_dir)
        if non_result_size > _evidence_max_bytes():
            shutil.rmtree(evidence_dir, ignore_errors=True)
            raise OSError(
                f"evidence quota exceeded and was deleted: {non_result_size}>{_evidence_max_bytes()}"
            )

        result_payload = json.dumps(report, ensure_ascii=False, indent=2)
        result_bytes = result_payload.encode("utf-8")
        if non_result_size + len(result_bytes) > _evidence_max_bytes():
            shutil.rmtree(evidence_dir, ignore_errors=True)
            raise OSError("evidence quota would be exceeded by result.json; evidence deleted")

        (evidence_dir / "result.json").write_bytes(result_bytes)
        files = _evidence_files(job_id)
        report["evidence_files"] = [
            f"/jobs/{job_id}/evidence/{name}"
            for name in files
        ]
    except Exception as exc:
        report = {
            "ok": False,
            "failures": [f"evidence finalization failed: {type(exc).__name__}: {exc}"],
            "evidence_files": [],
        }

    report, final_status = _commit_final_state(job_id, report)
    if report.get("cancelled"):
        try:
            evidence_dir = _job_evidence_dir(job_id)
            if evidence_dir.is_dir():
                (evidence_dir / "result.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        except OSError:
            pass


@app.get("/watcher/health")
def watcher_health(
    x_jev_watcher_time: str | None = Header(default=None),
    x_jev_watcher_nonce: str | None = Header(default=None),
    x_jev_watcher_signature: str | None = Header(default=None),
):
    _watcher_auth(
        "GET", "/watcher/health",
        x_jev_watcher_time, x_jev_watcher_nonce, x_jev_watcher_signature,
    )
    return health()


@app.post("/watcher/smoke", status_code=202)
def watcher_create_smoke(
    x_jev_watcher_time: str | None = Header(default=None),
    x_jev_watcher_nonce: str | None = Header(default=None),
    x_jev_watcher_signature: str | None = Header(default=None),
):
    _watcher_auth(
        "POST", "/watcher/smoke",
        x_jev_watcher_time, x_jev_watcher_nonce, x_jev_watcher_signature,
    )
    request = _watcher_smoke_request()
    result = create_job(request, authorization="Bearer " + _worker_api_token())
    with _jobs_lock:
        current = _jobs.get(result["job_id"]) or {}
        metadata = current.setdefault("metadata", {})
        metadata["watcher_owned"] = True
        metadata["read_only"] = True
    return result


@app.get("/watcher/jobs/{job_id}")
def watcher_get_job(
    job_id: str,
    x_jev_watcher_time: str | None = Header(default=None),
    x_jev_watcher_nonce: str | None = Header(default=None),
    x_jev_watcher_signature: str | None = Header(default=None),
):
    path = f"/watcher/jobs/{job_id}"
    _watcher_auth(
        "GET", path,
        x_jev_watcher_time, x_jev_watcher_nonce, x_jev_watcher_signature,
    )
    if not _valid_job_id(job_id) or not _watcher_job_is_owned(job_id):
        raise HTTPException(status_code=404, detail="watcher job not found")
    with _jobs_lock:
        job = dict(_jobs.get(job_id) or {})
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "result": job.get("result"),
    }


@app.post("/watcher/jobs/{job_id}/cancel", status_code=202)
def watcher_cancel_job(
    job_id: str,
    x_jev_watcher_time: str | None = Header(default=None),
    x_jev_watcher_nonce: str | None = Header(default=None),
    x_jev_watcher_signature: str | None = Header(default=None),
):
    path = f"/watcher/jobs/{job_id}/cancel"
    _watcher_auth(
        "POST", path,
        x_jev_watcher_time, x_jev_watcher_nonce, x_jev_watcher_signature,
    )
    if not _valid_job_id(job_id) or not _watcher_job_is_owned(job_id):
        raise HTTPException(status_code=404, detail="watcher job not found")
    return cancel_job(job_id, authorization="Bearer " + _worker_api_token())


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
        stale = _job_evidence_dir("startup-selftest")
        if stale.exists():
            shutil.rmtree(stale)
        _set_job(
            "startup-selftest",
            status="queued",
            result=None,
            queue_pending=True,
            created_at_ms=int(time.time() * 1000),
        )
        _executor.submit(_run_startup_selftest)


@app.on_event("shutdown")
def shutdown_worker():
    global _accepting_jobs, _active_process, _active_job_id
    _accepting_jobs = False
    with _active_process_lock:
        process = _active_process
        _active_process = None
        _active_job_id = None
    if process is not None and process.is_alive():
        process.terminate()
        process.join(timeout=2.0)
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)
    _executor.shutdown(wait=False, cancel_futures=True)
    _cleanup_qa_browser_contexts()


@app.post("/jobs", status_code=202)
def create_job(request: JobRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    if not _accepting_jobs:
        raise HTTPException(status_code=503, detail="QA worker is shutting down")
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
        current.update(
            status="queued",
            result=None,
            cancel_requested=False,
            queue_pending=True,
            created_at_ms=int(time.time() * 1000),
            updated_at_ms=int(time.time() * 1000),
            metadata={
                "display_name": request.display_name,
                "issue_number": request.issue_number,
                "pr_number": request.pr_number,
                "commit_sha": request.commit_sha,
                "read_only": request.read_only,
            },
        )
    _executor.submit(_execute, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs")
def list_jobs(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    _cleanup_expired_evidence()
    with _jobs_lock:
        rows = [
            {
                "job_id": job_id,
                "status": value.get("status"),
                "metadata": value.get("metadata") or {},
                "created_at_ms": value.get("created_at_ms"),
                "updated_at_ms": value.get("updated_at_ms"),
            }
            for job_id, value in _jobs.items()
            if _valid_job_id(job_id)
        ]
    rows.sort(key=lambda row: row.get("created_at_ms") or 0, reverse=True)
    return {"jobs": rows[:30]}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    _cleanup_expired_evidence()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        snapshot = dict(job)
    snapshot["evidence_files"] = [
        f"/jobs/{job_id}/evidence/{name}" for name in _evidence_files(job_id)
    ]
    snapshot["progress"] = _read_progress(job_id)
    return {"job_id": job_id, **snapshot}


@app.post("/jobs/{job_id}/cancel", status_code=202)
def cancel_job(job_id: str, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    if not _valid_job_id(job_id):
        raise HTTPException(status_code=404, detail="job not found")
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        status = job.get("status")
        if status in {"passed", "failed", "cancelled"}:
            return {"job_id": job_id, "status": status, "stopped": status == "cancelled", "already_finished": True}
        job["cancel_requested"] = True
        job["status"] = "cancelled" if status == "queued" else "cancelling"
        job["updated_at_ms"] = int(time.time() * 1000)
        response_status = job["status"]
    with _active_process_lock:
        process = _active_process if _active_job_id == job_id else None
    if process is not None and process.is_alive():
        process.terminate()
    return {"job_id": job_id, "status": response_status, "stopped": response_status == "cancelled"}


@app.get("/viewer", response_class=HTMLResponse)
def viewer():
    return HTMLResponse(VIEWER_HTML, headers=viewer_headers())


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
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
