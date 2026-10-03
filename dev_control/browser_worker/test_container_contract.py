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

        self.assertIn("process.join(timeout=request.max_seconds)", service)
        self.assertIn("process.terminate()", service)
        self.assertIn('/jobs/{job_id}/evidence/{filename}', service)
        self.assertIn("_authorize(authorization)", service)
        self.assertIn("Fetch.enable", network_guard)
        self.assertIn("Fetch.failRequest", network_guard)

if __name__ == "__main__":
    unittest.main()
