import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent


class SmokeStaffLinkCleanupTests(unittest.TestCase):
    def test_auth_session_removes_membership_before_staff(self):
        source = (SCRIPTS_DIR / "smoke-auth-session.py").read_text(encoding="utf-8")

        self.assertLess(
            source.index("DELETE FROM user_company_roles"),
            source.index("DELETE FROM staff"),
        )

    def test_platform_crm_removes_membership_before_staff(self):
        source = (SCRIPTS_DIR / "smoke-platform-crm.py").read_text(encoding="utf-8")

        self.assertLess(
            source.index("DELETE FROM user_company_roles"),
            source.index("DELETE FROM staff"),
        )


if __name__ == "__main__":
    unittest.main()
