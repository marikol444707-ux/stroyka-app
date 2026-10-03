"""Strict URL and network boundary for the isolated QA Chrome."""

from __future__ import annotations

import posixpath
import threading
import time
from urllib.parse import unquote, urlparse

from dev_control.jev_timeweb import JevError


def _fully_unquote(value: str) -> str:
    current = value
    for _ in range(12):
        decoded = unquote(current)
        if decoded == current:
            return decoded
        current = decoded
    raise ValueError("URL path is excessively encoded")


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
    if (target.scheme.lower(), target.netloc.lower()) != (base.scheme.lower(), base.netloc.lower()):
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
    if (target.scheme.lower(), target.netloc.lower()) != (base.scheme.lower(), base.netloc.lower()):
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
        )
        self._guarded_sessions.add(session_id)

    def _handle_attached_target(self, params: dict) -> None:
        child_session = params.get("sessionId")
        target_info = params.get("targetInfo") or {}
        target_id = target_info.get("targetId")
        target_type = target_info.get("type")
        initial_url = str(target_info.get("url") or "about:blank")

        if not child_session:
            return
        if target_type == "page" and initial_url not in {"", "about:blank"}:
            if not request_allowed(initial_url, self._base_url, "Document"):
                if target_id:
                    self._cdp("Target.closeTarget", targetId=target_id)
                self._error = f"blocked out-of-scope popup target: {initial_url}"
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
                        self._error = f"blocked out-of-scope browser request: {url}"
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

    class SafeBrowser(upstream_browser):
        def __init__(self, url):
            assert_allowed_document_url(url, base_url)
            ensure_daemon()
            self.target = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
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
            self._qa_boundary = None
            try:
                self._qa_boundary = NetworkBoundary(self.session, base_url)
                self._qa_boundary.start()
                self.call("Page.navigate", url=url)
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    self._qa_boundary.raise_if_failed()
                    if self.evaluate("document.readyState") == "complete":
                        break
                    time.sleep(0.02)
                self._qa_boundary.raise_if_failed()
            except Exception:
                if self._qa_boundary is not None:
                    self._qa_boundary.close()
                if self.target:
                    try:
                        cdp("Target.closeTarget", targetId=self.target)
                    finally:
                        self.target = None
                raise

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
            boundary = getattr(self, "_qa_boundary", None)
            if boundary is not None:
                boundary.close()
            super().close()

    agent_module.Browser = SafeBrowser
    return SafeBrowser
