"""Strict URL and network boundary for the isolated QA Chrome."""

from __future__ import annotations

import posixpath
import threading
import time
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlsplit, urlunsplit

from dev_control.jev_timeweb import JevError


_SENSITIVE_MARKERS = (
    "token", "code", "invite", "password", "secret", "key", "auth", "signature", "sig", "session",
)
_SENSITIVE_PATH_MARKERS = frozenset({
    "reset", "password-reset", "magic", "magic-link", "verify", "verification",
    "invite", "invitation", "callback", "oauth", "token",
})


def redact_boundary_url(url: str) -> str:
    parts = urlsplit(str(url))
    path_segments = parts.path.split("/")
    output = []
    redact_next = False
    for segment in path_segments:
        lowered = segment.lower()
        if redact_next and segment:
            output.append("[REDACTED]")
            redact_next = False
            continue
        output.append(segment)
        if lowered in _SENSITIVE_PATH_MARKERS:
            redact_next = True

    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        query.append(
            (key, "[REDACTED]")
            if any(marker in lowered for marker in _SENSITIVE_MARKERS)
            else (key, value)
        )
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port is not None else ""
    authority = f"{host}{port}"
    return urlunsplit((parts.scheme, authority, "/".join(output), urlencode(query), ""))


def _fully_unquote(value: str) -> str:
    current = value
    for _ in range(12):
        decoded = unquote(current)
        if decoded == current:
            return decoded
        current = decoded
    raise ValueError("URL path is excessively encoded")


def canonical_origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80 if scheme == "http" else None
    return scheme, host, port


def normalized_path(url: str) -> str:
    parsed = urlparse(url)
    raw = _fully_unquote(parsed.path or "/").replace("\\", "/")
    parts = raw.split("/")
    if any(part in {".", ".."} for part in parts):
        raise ValueError("QA URL contains dot path segments")
    normalized = posixpath.normpath(raw)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    if raw.endswith("/") and normalized != "/":
        normalized += "/"
    return normalized


def assert_allowed_document_url(url: str, base_url: str) -> None:
    target = urlparse(url)
    base = urlparse(base_url)
    if target.scheme not in {"http", "https"}:
        raise ValueError("QA URL must use http or https")
    if base.scheme not in {"http", "https"} or not base.netloc:
        raise ValueError("QA_BASE_URL must be an absolute http(s) URL")
    if canonical_origin(url) != canonical_origin(base_url):
        raise ValueError("QA URL is outside QA_BASE_URL origin")

    target_path = normalized_path(url)
    base_path = normalized_path(base_url).rstrip("/")
    if base_path and base_path != "/" and not (
        target_path == base_path or target_path.startswith(base_path + "/")
    ):
        raise ValueError("QA URL is outside QA_BASE_URL path")


def request_allowed(url: str, base_url: str, resource_type: str | None) -> bool:
    """Allow same-origin resources; document navigations must also stay in base path."""

    target = urlparse(url)
    base = urlparse(base_url)
    if target.scheme in {"data", "blob"}:
        return True
    if target.scheme not in {"http", "https"}:
        return False
    if canonical_origin(url) != canonical_origin(base_url):
        return False
    if resource_type == "Document":
        try:
            assert_allowed_document_url(url, base_url)
        except ValueError:
            return False
    return True


class NetworkBoundary:
    """CDP Fetch guard that fails disallowed requests before Chrome sends them."""

    def __init__(self, session_id: str, base_url: str):
        from browser_harness.helpers import cdp, drain_events

        self._cdp = cdp
        self._drain_events = drain_events
        self._session_id = session_id
        self._base_url = base_url
        self._stop = threading.Event()
        self._error: str | None = None
        self._thread = threading.Thread(target=self._loop, name="qa-network-boundary", daemon=True)
        self._guarded_sessions = {session_id}
        self._child_targets: set[str] = set()

    def start(self) -> None:
        self._enable_session(self._session_id)
        self._thread.start()

    def _enable_session(self, session_id: str) -> None:
        self._cdp(
            "Fetch.enable",
            session_id=session_id,
            patterns=[{"urlPattern": "*", "requestStage": "Request"}],
        )
        self._cdp(
            "Target.setAutoAttach",
            session_id=session_id,
            autoAttach=True,
            waitForDebuggerOnStart=True,
            flatten=True,
            filter=[
                {"type": "page", "exclude": False},
                {"type": "iframe", "exclude": False},
                {"type": "worker", "exclude": False},
                {"type": "shared_worker", "exclude": False},
                {"type": "service_worker", "exclude": False},
                {"exclude": True},
            ],
        )
        self._guarded_sessions.add(session_id)

    def _handle_attached_target(self, params: dict) -> None:
        child_session = params.get("sessionId")
        target_info = params.get("targetInfo") or {}
        target_id = target_info.get("targetId")
        target_type = target_info.get("type")
        initial_url = str(target_info.get("url") or "about:blank")

        if target_id:
            self._child_targets.add(target_id)
        if not child_session:
            return
        if target_type in {"page", "iframe"} and initial_url not in {"", "about:blank"}:
            if not request_allowed(initial_url, self._base_url, "Document"):
                if target_id:
                    self._cdp("Target.closeTarget", targetId=target_id)
                self._error = f"blocked out-of-scope popup target: {redact_boundary_url(initial_url)}"
                return

        self._enable_session(child_session)
        self._cdp("Runtime.runIfWaitingForDebugger", session_id=child_session)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                events = self._drain_events()
            except Exception as exc:
                self._error = f"network boundary event loop failed: {exc}"
                return
            for event in events:
                method = event.get("method")
                params = event.get("params") or {}
                if method == "Target.attachedToTarget":
                    try:
                        self._handle_attached_target(params)
                    except Exception as exc:
                        self._error = f"popup boundary enforcement failed: {exc}"
                        return
                    continue
                if method != "Fetch.requestPaused":
                    continue
                request_id = params.get("requestId")
                url = str((params.get("request") or {}).get("url") or "")
                resource_type = params.get("resourceType")
                event_session = event.get("session_id") or self._session_id
                if not request_id:
                    continue
                try:
                    if request_allowed(url, self._base_url, resource_type):
                        self._cdp(
                            "Fetch.continueRequest",
                            session_id=event_session,
                            requestId=request_id,
                        )
                    else:
                        self._cdp(
                            "Fetch.failRequest",
                            session_id=event_session,
                            requestId=request_id,
                            errorReason="BlockedByClient",
                        )
                        self._error = f"blocked out-of-scope browser request: {redact_boundary_url(url)}"
                except Exception as exc:
                    self._error = f"network boundary enforcement failed: {exc}"
                    return
            time.sleep(0.005)

    def raise_if_failed(self) -> None:
        if self._error:
            raise JevError(self._error)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        for target_id in tuple(self._child_targets):
            try:
                self._cdp("Target.closeTarget", targetId=target_id)
            except Exception:
                pass
        try:
            self._cdp("Fetch.disable", session_id=self._session_id)
        except Exception:
            pass


def install_safe_browser(base_url: str):
    """Patch Jev Agent to use a Browser with Fetch interception before navigation."""

    import jev_ultrafast.agent as agent_module
    import jev_ultrafast.browser as browser_module
    from browser_harness.admin import ensure_daemon
    from browser_harness.helpers import cdp

    upstream_browser = browser_module.Browser

    transport_block_script = r"""
(() => {
  const blocked = () => { throw new Error('Blocked by Stroyka QA network policy'); };
  try { Object.defineProperty(window, 'WebSocket', {value: function(){ blocked(); }, configurable: false}); } catch (_) {}
  try { Object.defineProperty(window, 'WebTransport', {value: function(){ blocked(); }, configurable: false}); } catch (_) {}
  try { Object.defineProperty(window, 'RTCPeerConnection', {value: function(){ blocked(); }, configurable: false}); } catch (_) {}
  try { Object.defineProperty(window, 'webkitRTCPeerConnection', {value: function(){ blocked(); }, configurable: false}); } catch (_) {}
})();
"""

    class SafeBrowser(upstream_browser):
        def __init__(self, url):
            assert_allowed_document_url(url, base_url)
            self.browser_context_id = None
            self.target = None
            self.session = None
            self._qa_boundary = None
            try:
                ensure_daemon()
                self.browser_context_id = cdp(
                    "Target.createBrowserContext",
                    disposeOnDetach=True,
                )["browserContextId"]
                self.target = cdp(
                    "Target.createTarget",
                    url="about:blank",
                    background=True,
                    browserContextId=self.browser_context_id,
                )["targetId"]
                self.session = cdp(
                    "Target.attachToTarget",
                    targetId=self.target,
                    flatten=True,
                )["sessionId"]
                self.call(
                    "Emulation.setDeviceMetricsOverride",
                    width=1120,
                    height=780,
                    deviceScaleFactor=1,
                    mobile=False,
                )
                self.call("Emulation.setFocusEmulationEnabled", enabled=True)
                self.call(
                    "Page.addScriptToEvaluateOnNewDocument",
                    source=transport_block_script,
                    runImmediately=True,
                )
                cdp(
                    "Browser.setDownloadBehavior",
                    behavior="deny",
                    browserContextId=self.browser_context_id,
                )
                self._qa_boundary = NetworkBoundary(self.session, base_url)
                self._qa_boundary.start()

                nav = self.call("Page.navigate", url=url)
                expected_loader = nav.get("loaderId")
                deadline = time.monotonic() + 15
                committed = False
                while time.monotonic() < deadline:
                    self._qa_boundary.raise_if_failed()
                    current_url = str(self.evaluate("location.href") or "")
                    if current_url not in {"", "about:blank"}:
                        try:
                            assert_allowed_document_url(current_url, base_url)
                            committed = True
                        except ValueError:
                            committed = False
                    if committed and self.evaluate("document.readyState") == "complete":
                        break
                    time.sleep(0.02)
                else:
                    raise RuntimeError(
                        f"QA navigation did not commit within 15s (loader={expected_loader or 'unknown'})"
                    )
                self._qa_boundary.raise_if_failed()
            except Exception:
                self._cleanup_allocations()
                raise

        def _cleanup_allocations(self):
            if self._qa_boundary is not None:
                self._qa_boundary.close()
                self._qa_boundary = None
            if self.target:
                try:
                    cdp("Target.closeTarget", targetId=self.target)
                except Exception:
                    pass
                self.target = None
            if self.browser_context_id:
                try:
                    cdp("Target.disposeBrowserContext", browserContextId=self.browser_context_id)
                except Exception:
                    pass
                self.browser_context_id = None

        def observe(self, screenshot=True):
            self._qa_boundary.raise_if_failed()
            result = super().observe(screenshot=screenshot)
            self._qa_boundary.raise_if_failed()
            return result

        def act(self, action, page, text=None):
            self._qa_boundary.raise_if_failed()
            result = super().act(action, page, text=text)
            self._qa_boundary.raise_if_failed()
            return result

        def close(self):
            self._cleanup_allocations()

    agent_module.Browser = SafeBrowser
    return SafeBrowser
