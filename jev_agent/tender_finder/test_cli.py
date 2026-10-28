import io
import json
import unittest
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import Mock
from unittest.mock import patch

from .__main__ import main


class ValidationCLITests(unittest.TestCase):
    def test_settings_check_never_initializes_worker_or_prints_private_values(self):
        with patch('jev_agent.tender_finder.__main__.load_settings',return_value=object()) as loader,patch('jev_agent.tender_finder.__main__.initialize_worker') as worker,redirect_stdout(io.StringIO()) as output:
            status=main(['check-settings','--config','/fixture/settings.json'])
        self.assertEqual(status,0);loader.assert_called_once();worker.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())['installation_ready'])

    def test_explicit_worker_command_returns_only_lifecycle_metadata(self):
        worker=Mock();worker.consume.return_value={'request_id':'synthetic-1','status':'processed',
            'notification_sent':False,'result':{'private':'PRIVATE'},'signing_key':'PRIVATE'}
        with patch('jev_agent.tender_finder.__main__.initialize_worker',return_value=worker) as initialize,redirect_stdout(io.StringIO()) as output:
            status=main(['worker-once','--config','/fixture/settings.json','--key-fd','9','--request','synthetic-1.json'])
        self.assertEqual(status,0);initialize.assert_called_once_with('/fixture/settings.json',9)
        worker.consume.assert_called_once_with('synthetic-1.json');self.assertNotIn('PRIVATE',output.getvalue())

    def test_no_secret_argument_echo_and_no_worker_without_key_descriptor(self):
        for argv in (['worker-once','--config','/fixture','--request','a.json'],
                     ['worker-once','--key','PRIVATE_VALUE']):
            with self.subTest(argv=argv),patch('jev_agent.tender_finder.__main__.initialize_worker') as initialize,redirect_stderr(io.StringIO()) as error:
                with self.assertRaises(SystemExit):main(argv)
                initialize.assert_not_called();self.assertNotIn('PRIVATE_VALUE',error.getvalue())

    def test_worker_failure_does_not_echo_exception_text(self):
        with patch('jev_agent.tender_finder.__main__.initialize_worker',side_effect=RuntimeError('PRIVATE_VALUE')),redirect_stdout(io.StringIO()) as output:
            status=main(['worker-resume','--config','/fixture/settings.json','--key-fd','9','--claim','synthetic-handle'])
        self.assertEqual(status,1);self.assertNotIn('PRIVATE_VALUE',output.getvalue())

    def test_valid_request_is_normalized_without_search_or_notification(self):
        raw = json.dumps({'version': 2, 'request_id': 'synthetic-1', 'region': 'Ставропольский край',
                          'sources': ['eis'], 'topics': ['капремонт']}).encode()
        with patch('sys.stdin', io.TextIOWrapper(io.BytesIO(raw))), redirect_stdout(io.StringIO()) as output:
            status = main(['validate-v2'])
        value = json.loads(output.getvalue())
        self.assertEqual(status, 0)
        self.assertFalse(value['search_executed'])
        self.assertEqual(value['source_coverage'], 'not_tested')
        self.assertEqual(value['legacy_v1_compatibility'], 'not_verified')

    def test_invalid_fields_return_specific_reason_without_echoing_values(self):
        raw = b'{"version":2,"companyId":12345,"token":"PRIVATE_DO_NOT_LOG"}'
        with patch('sys.stdin', io.TextIOWrapper(io.BytesIO(raw))), redirect_stdout(io.StringIO()) as output:
            status = main(['validate-v2'])
        self.assertEqual(status, 2)
        self.assertNotIn('PRIVATE_DO_NOT_LOG', output.getvalue())
        self.assertEqual({row['field'] for row in json.loads(output.getvalue())['errors']}, {'companyId', 'token'})


if __name__ == '__main__':
    unittest.main()
