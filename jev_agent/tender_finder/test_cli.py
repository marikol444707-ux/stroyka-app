import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from .__main__ import main


class ValidationCLITests(unittest.TestCase):
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
