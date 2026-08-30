import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
UNIT = ROOT / "ops" / "systemd" / "stroyka-hidden-works-local-model.service"


class HiddenWorksLocalModelServiceTests(unittest.TestCase):
    def test_unit_is_loopback_only_authenticated_and_resource_bounded(self):
        source = UNIT.read_text(encoding="utf-8")

        self.assertIn("User=stroyka-hidden-works", source)
        self.assertIn("Group=stroyka-hidden-works", source)
        self.assertIn("--host 127.0.0.1", source)
        self.assertIn("--port 18080", source)
        self.assertIn("--api-key-file /etc/stroyka/hidden-works-local-model.key", source)
        self.assertIn("--offline", source)
        self.assertIn("--no-ui", source)
        self.assertIn("--metrics", source)
        self.assertIn("--threads 4", source)
        self.assertIn("--parallel 1", source)
        self.assertIn("Nice=10", source)
        self.assertIn("CPUWeight=10", source)
        self.assertIn("MemoryHigh=4G", source)
        self.assertIn("MemoryMax=5G", source)

    def test_unit_is_hardened_and_not_activated_by_deploy(self):
        source = UNIT.read_text(encoding="utf-8")
        deploy = (ROOT / "deploy.sh").read_text(encoding="utf-8")

        self.assertIn("NoNewPrivileges=true", source)
        self.assertIn("PrivateTmp=true", source)
        self.assertIn("PrivateDevices=true", source)
        self.assertIn("ProtectHome=true", source)
        self.assertIn("ProtectSystem=strict", source)
        self.assertIn("ProtectKernelTunables=true", source)
        self.assertIn("ProtectKernelModules=true", source)
        self.assertIn("ProtectControlGroups=true", source)
        self.assertIn("RestrictSUIDSGID=true", source)
        self.assertIn("LockPersonality=true", source)
        self.assertIn("CapabilityBoundingSet=", source)
        self.assertIn("RestrictAddressFamilies=AF_UNIX AF_INET", source)
        self.assertIn("IPAddressDeny=any", source)
        self.assertIn("IPAddressAllow=localhost", source)
        self.assertIn("UMask=0077", source)
        self.assertNotIn("stroyka-hidden-works-local-model.service", deploy)


if __name__ == "__main__":
    unittest.main()
