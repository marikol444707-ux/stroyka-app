import datetime as dt
import unittest

from backend.features.client_account.subscription_state import billing_state


class BillingStateTests(unittest.TestCase):
    def setUp(self):
        self.today = dt.date(2026, 9, 2)

    def test_paid_subscription_warns_seven_days_before_expiry(self):
        result = billing_state(
            {"plan": "business", "plan_expires_at": dt.date(2026, 9, 9)},
            today=self.today,
        )

        self.assertEqual(result["status"], "payment_expiring")
        self.assertEqual(result["daysLeft"], 7)

    def test_paid_subscription_is_active_before_warning_window(self):
        result = billing_state(
            {"plan": "business", "plan_expires_at": dt.date(2026, 9, 10)},
            today=self.today,
        )

        self.assertEqual(result["status"], "active")

    def test_demo_subscription_uses_same_seven_day_warning_window(self):
        result = billing_state(
            {"plan": "demo", "trial_until": dt.date(2026, 9, 9)},
            today=self.today,
        )

        self.assertEqual(result["status"], "trial_expiring")
        self.assertEqual(result["daysLeft"], 7)

    def test_expired_subscription_remains_visible_as_urgent(self):
        result = billing_state(
            {"plan": "business", "plan_expires_at": dt.date(2026, 9, 1)},
            today=self.today,
        )

        self.assertEqual(result["status"], "payment_expired")
        self.assertEqual(result["daysLeft"], -1)


if __name__ == "__main__":
    unittest.main()
