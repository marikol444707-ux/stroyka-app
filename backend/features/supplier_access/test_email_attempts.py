"""Email preparation must never turn an ambiguous delivery into a new send."""
import unittest
from backend.features.supplier_access.email_attempts import (
    EMAIL_QUEUED, EMAIL_UNCONFIRMED, prepare_email_status,
)


class EmailAttemptPolicyTests(unittest.TestCase):
    def test_new_email_is_queued_without_sending(self):
        self.assertEqual(prepare_email_status('', 'supplier@example.com', True, False), EMAIL_QUEUED)

    def test_sent_and_ambiguous_states_survive_repeated_request(self):
        for status in ('Отправлено', EMAIL_UNCONFIRMED, 'Ошибка отправки'):
            with self.subTest(status=status):
                self.assertEqual(prepare_email_status(status, 'changed@example.com', True, False), status)

    def test_preflight_block_can_be_rechecked_after_configuration_changes(self):
        for status in ('', 'Нет email', 'SMTP не настроен', 'Пропущено: тестовый email', EMAIL_QUEUED):
            self.assertEqual(prepare_email_status(status, '', True, False), 'Нет email')
            self.assertEqual(prepare_email_status(status, 'a@example.com', False, False), 'SMTP не настроен')
            self.assertEqual(prepare_email_status(status, 'a@test.local', True, True), 'Пропущено: тестовый email')
            self.assertEqual(prepare_email_status(status, 'a@example.com', True, False), EMAIL_QUEUED)

    def test_unrecognized_historical_status_is_not_automatically_retried(self):
        self.assertEqual(prepare_email_status('legacy custom status', 'a@example.com', True, False), 'legacy custom status')
