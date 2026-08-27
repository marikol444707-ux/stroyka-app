import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
UNIT = ROOT / "ops" / "systemd" / "stroyka-agent-job-worker.service"


class AgentJobProductionWorkerServiceTests(unittest.TestCase):
    def test_unit_is_single_process_hardened_and_not_activated_by_deploy(self):
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
        self.assertNotIn("systemctl enable", deploy)
        self.assertNotIn("systemctl start", deploy)

    def test_deploy_restarts_only_an_already_active_worker(self):
        deploy = (ROOT / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn(
            'AGENT_JOB_WORKER_UNIT="stroyka-agent-job-worker.service"',
            deploy,
        )
        active_gate = 'if systemctl is-active --quiet "$AGENT_JOB_WORKER_UNIT"; then'
        worker_restart = 'systemctl restart "$AGENT_JOB_WORKER_UNIT"'
        worker_health = 'systemctl is-active --quiet "$AGENT_JOB_WORKER_UNIT"'
        self.assertIn(active_gate, deploy)
        self.assertIn(worker_restart, deploy)
        self.assertIn(worker_health, deploy)
        self.assertLess(deploy.index(active_gate), deploy.index(worker_restart))
        self.assertLess(deploy.index(worker_restart), deploy.rindex(worker_health))

    def test_package_exposes_read_only_status_command(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(
            package["scripts"]["status:agent-job-worker"],
            "python3 -m backend.features.agent_jobs.operational_report",
        )


if __name__ == "__main__":
    unittest.main()
