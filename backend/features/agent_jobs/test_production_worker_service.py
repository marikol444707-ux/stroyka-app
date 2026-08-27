import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
UNIT = ROOT / "ops" / "systemd" / "stroyka-agent-job-worker.service"


class AgentJobProductionWorkerServiceTests(unittest.TestCase):
    def test_unit_is_single_process_hardened_and_disabled_by_deploy(self):
        source = UNIT.read_text(encoding="utf-8")
        deploy = (ROOT / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("ExecStart=/usr/bin/python3 -m backend.features.agent_jobs.runner", source)
        self.assertNotIn("--once", source)
        self.assertIn("Restart=on-failure", source)
        self.assertIn("RestartSec=10s", source)
        self.assertIn("TimeoutStopSec=10min", source)
        self.assertIn("NoNewPrivileges=true", source)
        self.assertIn("PrivateTmp=true", source)
        self.assertIn("ProtectSystem=full", source)
        self.assertIn("UMask=0077", source)
        self.assertNotIn("stroyka-agent-job-worker.service", deploy)

    def test_package_exposes_read_only_status_command(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(
            package["scripts"]["status:agent-job-worker"],
            "python3 -m backend.features.agent_jobs.operational_report",
        )


if __name__ == "__main__":
    unittest.main()
