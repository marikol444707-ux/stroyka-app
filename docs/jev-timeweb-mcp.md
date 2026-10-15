# Jev QA — Timeweb AI MCP adapter (draft, not deployed)

Timeweb AI's standard external chat supports remote Streamable HTTP MCP tools.
This adapter is not the Timeweb SystemOne model endpoint. It is an optional,
separate bridge to the existing HMAC-scoped QA worker.

Source: dev_control/jev_mcp_gateway.py
Tests: python -m unittest dev_control.test_jev_mcp_gateway -v

Tools:
- jev_qa_capabilities: static allowlist, no worker access
- jev_qa_status: authenticated QA-only worker health (sanitized)
- jev_qa_start_smoke: one fixed read-only smoke; OFF by default

Configuration (only after independent QA/security acceptance):
- JEV_MCP_ENABLED=1
- JEV_MCP_ALLOWED_ORIGIN=https://<dedicated-qa-mcp-host>
- JEV_MCP_BEARER_TOKEN=<separate random secret, minimum 32 chars>
- JEV_WATCHER_TOKEN=<HMAC scoped watcher secret>
- JEV_WATCH_PORT=18084
- JEV_MCP_SMOKE_ENABLED=0
- JEV_MCP_OWNER_APPROVED=0

No automatic deployment, activation or production access. Serve only behind
an authenticated HTTPS ingress with network restrictions; do not expose Uvicorn
or the worker loopback API directly to the Internet. Never put tokens in Issues.
The MCP response never returns screenshots, raw errors, cookies or DOM.

Timeweb configuration, after a reviewed QA-only deployment: AI services →
MCP servers → add remote HTTP server at the dedicated HTTPS /mcp URL using
Bearer auth → attach allowlisted tools to the agent → use ai.timeweb.cloud.
The public URL is NOT provisioned by this code. This is not a live connection.

MCP transport: stateless JSON POST /mcp, initialize, ping, tools/list,
tools/call. GET SSE returns 405. Check provider compatibility in an isolated
QA environment before enabling any action. This adapter does not remove the
existing #344/#345/#346 security blockers or count as E2E evidence.
