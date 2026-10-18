import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts.jev_local_browser import demo, observed_page, remote_choose, verified_done, validate_choice


class LocalJevTest(unittest.TestCase):
    def test_only_observed_test_button_is_executable(self):
        page = observed_page('- button "Проверить связь" [ref=e7]\n- button "Delete" [ref=e8]')
        self.assertEqual([a['id'] for a in page['actions']], ['e7'])
        with self.assertRaises(ValueError):
            validate_choice({'choice': 'e8'}, page)

    def test_model_done_without_result_is_not_success(self):
        self.assertFalse(verified_done('DONE', '- paragraph: Waiting', ['e7']))
        self.assertFalse(verified_done('DONE', '- paragraph: JEV_LOCAL_OK', []))
        self.assertTrue(verified_done('DONE', '- paragraph: JEV_LOCAL_OK', ['e7']))

    def test_marker_in_button_or_instructions_does_not_count(self):
        self.assertFalse(verified_done('DONE', '- button "JEV_LOCAL_OK"', ['e7']))
        self.assertFalse(verified_done('e7', '- paragraph: JEV_LOCAL_OK', ['e7']))

    def test_missing_or_ambiguous_button_stops_without_guessing(self):
        self.assertEqual(observed_page('waiting')['actions'], [])
        with self.assertRaises(ValueError):
            observed_page('- button "Проверить связь" [ref=e7]\n- button "Проверить связь" [ref=e8]')

    def test_disabled_button_is_not_offered(self):
        self.assertEqual(observed_page('- button "Проверить связь" [ref=e7] [disabled]')['actions'], [])

    def test_provider_failure_closes_browser(self):
        with patch('scripts.jev_local_browser.LocalBrowser') as browser, \
                patch('scripts.jev_local_browser.remote_choose', side_effect=RuntimeError('provider')):
            browser.return_value.__enter__.return_value.snapshot.return_value = '- paragraph: Waiting'
            with self.assertRaises(RuntimeError):
                demo()
            browser.return_value.__exit__.assert_called_once()

    def test_repeated_model_click_is_stopped(self):
        with patch('scripts.jev_local_browser.LocalBrowser') as browser, \
                patch('scripts.jev_local_browser.remote_choose', return_value={'choice': 'e7'}):
            handle = browser.return_value.__enter__.return_value
            handle.snapshot.return_value = '- button "Проверить связь" [ref=e7]'
            with self.assertRaisesRegex(ValueError, 'Repeated click'):
                demo()
            self.assertEqual(sum(call.args[0] == 'browser_click' for call in handle.call.call_args_list), 1)
            browser.return_value.__exit__.assert_called_once()

    def test_remote_error_cannot_print_provider_secrets(self):
        with patch('scripts.jev_local_browser.subprocess.run',
                   return_value=SimpleNamespace(returncode=1, stderr='private-provider-key')):
            with self.assertRaises(RuntimeError) as caught:
                remote_choose(observed_page('Waiting'), [])
            self.assertNotIn('private-provider-key', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
