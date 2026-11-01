import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from .server_preflight import policy_metadata,collect,metadata
from .test_runtime_config import policies


class PreflightTests(unittest.TestCase):
    def test_only_whitelisted_identity_metadata_is_returned(self):
        old,_=policies();old['principal_subject']='PRIVATE_PRINCIPAL'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bridge.json';path.write_text(json.dumps(old));path.chmod(0o600)
            result=policy_metadata(path,expected_uid=os.geteuid(),system_uid=Path('/').stat().st_uid)
            self.assertEqual(result['company_id'],37)
            self.assertNotIn('PRIVATE_PRINCIPAL',json.dumps(result))
            path.write_text(json.dumps({**old,'secret':'PRIVATE_TOKEN'}));path.chmod(0o600)
            result=policy_metadata(path,expected_uid=os.geteuid(),system_uid=Path('/').stat().st_uid)
            self.assertFalse(result['recognized_v2_policy']);self.assertNotIn('PRIVATE_TOKEN',json.dumps(result))

    def test_unsafe_policy_and_key_metadata_do_not_read_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'admission.key';path.write_text('PRIVATE_TOKEN');path.chmod(0o600)
            with patch.object(Path,'read_bytes',side_effect=AssertionError('do not read')):
                result=metadata(path)
            self.assertTrue(result['exists']);self.assertNotIn('PRIVATE_TOKEN',str(result))
            path.chmod(0o666)
            self.assertEqual(policy_metadata(path,expected_uid=os.geteuid())['read_error_type'],'ValueError')

    def test_nonroot_diagnostic_never_runs_commands_or_reads_policy(self):
        run=Mock()
        with patch('os.geteuid',return_value=12345),patch('jev_agent.tender_finder.commercial.server_preflight.policy_metadata') as read:
            result=collect(_run=run)
        run.assert_not_called();read.assert_not_called();self.assertFalse(result['installation_ready'])

    def test_only_fixed_readonly_command_families_are_used(self):
        calls=[]
        def run(args):
            calls.append(args)
            if 'inspect' in args:return '{"running":true,"image":"sha256:fixture","privileged":false}'
            if 'top' in args:return 'PID UID GID COMMAND\n321 10000 10000 hermes\n'
            return 'LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\n'
        with patch('os.geteuid',return_value=0),patch('jev_agent.tender_finder.commercial.server_preflight.policy_metadata',return_value={}):
            result=collect(_run=run)
        self.assertEqual(result['hermes_actors'],[{'pid':321,'uid':10000,'gid':10000}])
        for args in calls:self.assertTrue('show' in args or 'inspect' in args or 'top' in args)
        self.assertFalse(result['signing_key_read']);self.assertFalse(result['services_changed'])
