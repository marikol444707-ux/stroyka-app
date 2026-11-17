import unittest

from .email_notifications import LeadEmailNotifier


class LeadEmailNotifierReadinessTests(unittest.TestCase):
    def test_uses_smtp_user_when_sender_is_not_explicit(self):
        notifier = LeadEmailNotifier({
            "PUBLIC_SITE_LEAD_EMAIL_ENABLED": "true",
            "PUBLIC_SITE_LEAD_EMAIL_TO": "leads@example.test",
            "SMTP_HOST": "smtp.example.test",
            "SMTP_PORT": "465",
            "SMTP_USER": "sender@example.test",
            "SMTP_PASSWORD": "present",
        })

        status = notifier.readiness()

        self.assertTrue(status["configured"])
        self.assertNotIn("smtp_sender_missing_or_invalid", status["issues"])


if __name__ == "__main__":
    unittest.main()
