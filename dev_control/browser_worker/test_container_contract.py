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


if __name__ == "__main__":
    unittest.main()
