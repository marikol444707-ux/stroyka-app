from pathlib import Path
import unittest


class BrowserWorkerContainerContractTest(unittest.TestCase):
    def test_worker_container_is_isolated_and_app_platform_ready(self):
        dockerfile = Path("dev_control/Dockerfile").read_text(encoding="utf-8")
        requirements = Path("dev_control/browser_worker/requirements.txt").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.12", dockerfile)
        self.assertIn("USER worker", dockerfile)
        self.assertIn("EXPOSE 8080", dockerfile)
        self.assertIn("COPY . /app/dev_control", dockerfile)
        self.assertNotIn("COPY backend", dockerfile)
        self.assertIn(
            "1231850a0bf1a0c0341fe408ef1668dbbfdfac46",
            requirements,
        )



    def test_worker_has_hard_timeout_and_authenticated_evidence_contract(self):
        service = Path("dev_control/browser_worker/service.py").read_text(encoding="utf-8")
        network_guard = Path("dev_control/browser_worker/network_guard.py").read_text(encoding="utf-8")

        self.assertIn("result_queue.get(timeout=remaining)", service)
        self.assertIn("deadline = time.monotonic() + request.max_seconds", service)
        self.assertIn("process.terminate()", service)
        self.assertGreaterEqual(service.count("_cleanup_qa_browser_contexts()"), 3)
        self.assertIn('/jobs/{job_id}/evidence/{filename}', service)
        self.assertIn("_authorize(authorization)", service)
        self.assertIn("Fetch.enable", network_guard)
        self.assertIn("Fetch.failRequest", network_guard)
        self.assertIn("PreAuthBodyLimitMiddleware", service)
        self.assertIn("_MAX_JOB_BODY_BYTES = 32 * 1024", service)
        self.assertIn("status_code=413", service)
        self.assertIn("Target.setAutoAttach", network_guard)
        self.assertIn("waitForDebuggerOnStart=True", network_guard)
        self.assertIn("Runtime.runIfWaitingForDebugger", network_guard)
        self.assertIn("Target.createBrowserContext", network_guard)
        self.assertIn("Target.disposeBrowserContext", network_guard)
        self.assertIn("QA navigation did not commit within 15s", network_guard)
        self.assertIn("self._cleanup_allocations()", network_guard)
        self.assertIn('"type": "worker"', network_guard)
        self.assertIn('"type": "iframe"', network_guard)

if __name__ == "__main__":
    unittest.main()
