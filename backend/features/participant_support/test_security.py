import unittest
from unittest.mock import Mock, patch

from .security import record_denial, validate_storage_configuration


class SupportStorageConfigurationTests(unittest.TestCase):
    def test_public_storage_cannot_coexist_with_scoped_support(self):
        with patch.dict('os.environ', PARTICIPANT_SUPPORT_ACCESS_ENABLED='1'):
            for args in ((True,'local',''), (False,'s3','public-read'), (False,'s3','public-read-write')):
                with self.subTest(args=args), self.assertRaises(RuntimeError):
                    validate_storage_configuration(*args)
            for args in ((False,'local','public-read'), (False,'s3','private'), (False,'s3','bucket-owner-full-control')):
                validate_storage_configuration(*args)

    def test_existing_mode_configuration_is_preserved(self):
        with patch.dict('os.environ', PARTICIPANT_SUPPORT_ACCESS_ENABLED='0'):
            validate_storage_configuration(True,'s3','public-read')

    def test_broken_audit_connection_cannot_replace_denial_with_server_error(self):
        conn = Mock()
        conn.cursor.side_effect = RuntimeError('sensitive connection detail')
        conn.rollback.side_effect = RuntimeError('rollback failed')
        conn.close.side_effect = RuntimeError('close failed')
        with patch.dict('os.environ', PARTICIPANT_SUPPORT_ACCESS_ENABLED='1'), self.assertLogs('backend.features.participant_support.security', level='ERROR') as logs:
            record_denial(lambda:conn, {'id':7,'role':'platform_support'}, surface='business')
        self.assertNotIn('sensitive connection detail', str(logs.output))
