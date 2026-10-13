"""Opt-in stateless MCP HTTP adapter for the Timeweb AI chat. QA-only."""
import hmac
import json
import os
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from scripts.jev_qa_watch import (
    call_worker, worker_base, QA_URL, ALLOWED_QA_ENVIRONMENTS, WatchError,
)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
TOOLS = [
    {"name": "jev_qa_capabilities", "description": "List Jev QA capabilities and release gates; no actions.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "jev_qa_status", "description": "Check isolated QA worker readiness without browser actions.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "jev_qa_start_smoke", "description": "Start one fixed read-only QA smoke only after owner-approved security gates.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def _valid_origin(value):
    try:
        u = urlsplit(value)
        host = (u.hostname or "").lower().rstrip(".")
        return (u.scheme == "https" and bool(host) and not u.username and not u.password
                and u.path in ("", "/") and not u.query and not u.fragment
                and u.port != 0 and host not in ("stroyka.pro", "stroyka26.pro")
                and not host.endswith((".stroyka.pro", ".stroyka26.pro")))
    except (ValueError, TypeError):
        return False


def _authorized(headers):
    if os.getenv("JEV_MCP_ENABLED") != "1":
        return False
    origin = os.getenv("JEV_MCP_ALLOWED_ORIGIN", "")
    if not _valid_origin(origin):
        return False
    if headers.get("origin") is not None and headers["origin"] != origin.rstrip("/"):
        return False
    token = os.getenv("JEV_MCP_BEARER_TOKEN", "")
    header = headers.get("authorization", "")
    return (32 <= len(token) <= 255 and header.startswith("Bearer ")
            and hmac.compare_digest(header[7:], token))


def _worker(method, path):
    return call_worker(worker_base(os.getenv("JEV_WATCH_PORT", "18084")),
                       os.getenv("JEV_WATCHER_TOKEN", ""), method, path)


def _tool(name, args):
    if args != {}:
        return {"status": "BLOCKED", "reason": "INVALID_ARGUMENTS"}
    if name == "jev_qa_capabilities":
        return {"status": "AVAILABLE", "scenario": "authenticated-qa-menu-smoke",
                "scope": "QA_ONLY", "screenshots": "PRIVATE_VIEWER_ONLY",
                "production": "DENIED", "arbitrary_commands": "DENIED"}
    if name not in ("jev_qa_status", "jev_qa_start_smoke"):
        return {"status": "BLOCKED", "reason": "UNKNOWN_TOOL"}
    if name == "jev_qa_start_smoke" and (
        os.getenv("JEV_MCP_SMOKE_ENABLED") != "1"
        or os.getenv("JEV_MCP_OWNER_APPROVED") != "1"
    ):
        return {"status": "BLOCKED", "reason": "QA_RELEASE_GATES_NOT_APPROVED"}
    health = _worker("GET", "/watcher/health")
    ready = (type(health) is dict and health.get("ok") is True
             and health.get("environment") in ALLOWED_QA_ENVIRONMENTS
             and health.get("watcher_target") == QA_URL)
    if name == "jev_qa_status":
        return {"status": "READY" if ready else "BLOCKED", "scope": "QA_ONLY"}
    if not ready:
        return {"status": "BLOCKED", "reason": "QA_WORKER_NOT_READY"}
    job = _worker("POST", "/watcher/smoke")
    job_id = job.get("job_id") if type(job) is dict else None
    import re
    if type(job_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", job_id):
        return {"status": "BLOCKED", "reason": "INVALID_JOB_ID"}
    return {"status": "QUEUED", "job_id": job_id}


def _reply(id_, result):
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


@app.post("/mcp")
async def mcp(request: Request):
    if not _authorized(request.headers):
        return Response(status_code=403)
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return Response(status_code=415)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 16384:
            return Response(status_code=413)
    try:
        body = json.loads(data)
    except (ValueError, UnicodeError):
        return JSONResponse(_error(None, -32700, "Parse error"))
    if type(body) is not dict or body.get("jsonrpc") != "2.0" or type(body.get("method")) is not str:
        return JSONResponse(_error(None, -32600, "Invalid Request"))
    method = body["method"]
    if method == "notifications/initialized" and "id" not in body:
        return Response(status_code=202)
    if "id" not in body or type(body["id"]) not in (str, int):
        return JSONResponse(_error(None, -32600, "Invalid Request"))
    id_ = body["id"]
    if method == "initialize":
        return JSONResponse(_reply(id_, {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "stroyka-jev-qa", "version": "0.1.0"},
        }))
    if method == "ping":
        return JSONResponse(_reply(id_, {}))
    if method == "tools/list":
        return JSONResponse(_reply(id_, {"tools": TOOLS}))
    if method == "tools/call":
        params = body.get("params")
        if type(params) is not dict or type(params.get("name")) is not str or type(params.get("arguments", {})) is not dict:
            return JSONResponse(_error(id_, -32602, "Invalid params"))
        try:
            value = await run_in_threadpool(_tool, params["name"], params.get("arguments", {}))
        except Exception:
            value = {"status": "BLOCKED", "reason": "QA_WORKER_UNAVAILABLE"}
        return JSONResponse(_reply(id_, {
            "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
            "isError": value.get("status") == "BLOCKED",
        }))
    return JSONResponse(_error(id_, -32601, "Method not found"))


@app.get("/mcp")
async def mcp_get():
    return Response(status_code=405)
