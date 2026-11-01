import unittest
from unittest.mock import MagicMock
from scripts.qa_host_runtime import PYTHON_PATH, USER_REPORTED, require_current_runtime


class HostRuntimeTests(unittest.TestCase):
    def test_report_does_not_claim_database_or_restore(self):
        self.assertTrue(USER_REPORTED['pip_check'])
        for key in ('database_connection', 'migrations', 'restore'):
            self.assertFalse(USER_REPORTED[key])

    def test_different_path_rejected_before_verifier(self):
        runtime = MagicMock(python_path='/some/other/python')
        with self.assertRaises(ValueError):
            require_current_runtime(runtime)
        runtime.verify_current_installation.assert_not_called()

    def test_stale_or_non_boolean_attestation_rejected(self):
        for value in (False, None, 'true', 1):
            runtime = MagicMock(python_path=PYTHON_PATH)
            runtime.verify_current_installation.return_value = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                require_current_runtime(runtime)

    def test_current_verifier_required_even_for_recorded_path(self):
        runtime = MagicMock(python_path=PYTHON_PATH)
        runtime.verify_current_installation.return_value = True
        require_current_runtime(runtime)
        runtime.verify_current_installation.assert_called_once()
