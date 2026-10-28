import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .audit_bridge import collect, inspect_worker


class BridgeAuditTests(unittest.TestCase):
    def test_fields_and_validator_are_read_without_executing_source_or_printing_secrets(self):
        source = ('import os\nraise RuntimeError("EXECUTED")\n'
                  'TOKEN = "PRIVATE_TOKEN"\nOWNER = 918273645\n'
                  'ALLOWED_FIELDS = {"version", "request_id", "query"}\n'
                  'def validate(data):\n'
                  '    owner = 918273645\n'
                  '    token = "PRIVATE_EMBEDDED_TOKEN"\n'
                  '    if data.get("version") != 1:\n'
                  '        return {"reason":"invalid_fields"}\n')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'worker.py';path.write_text(source)
            with patch('subprocess.run') as run:
                value = inspect_worker(path)
            run.assert_not_called()
            self.assertEqual(path.read_text(), source)
        rendered = json.dumps(value)
        self.assertNotIn('PRIVATE_TOKEN', rendered)
        self.assertNotIn('PRIVATE_EMBEDDED_TOKEN', rendered)
        self.assertNotIn('918273645', rendered)
        self.assertIn('version', value['request_functions'][0]['redacted_source'])
        self.assertEqual(value['declared_field_sets']['ALLOWED_FIELDS'], ['query','request_id','version'])
        self.assertFalse(value['schema_compatibility_verified'])

    def test_dictionary_schema_values_are_never_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'worker.py'
            path.write_text('FIELDS = {"request_id":"PRIVATE_VALUE"}\n')
            value=inspect_worker(path)
        self.assertEqual(value['declared_field_sets'], {'FIELDS':['request_id']})
        self.assertNotIn('PRIVATE_VALUE', json.dumps(value))

    def test_missing_worker_is_explicit_and_symlink_is_not_followed_for_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertFalse(inspect_worker(root/'missing.py')['exists'])
            (root/'private').write_text('PRIVATE')
            (root/'worker.py').symlink_to(root/'private')
            value=inspect_worker(root/'worker.py')
        self.assertEqual(value['code'], 'SOURCE_LINK_OR_NONREGULAR_FILE')
        self.assertNotIn('PRIVATE', json.dumps(value))

    def test_unit_queries_never_request_environment_commands_or_service_changes(self):
        from types import SimpleNamespace
        with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='ActiveState=active\nEnvironment=PRIVATE\nExecStart=PRIVATE\n')) as run, patch('jev_agent.tender_finder.audit_bridge.WORKER',Path('/missing-worker')), patch('jev_agent.tender_finder.audit_bridge.shutil.which',return_value=None):
            value=collect()
        self.assertNotIn('PRIVATE', json.dumps(value))
        for call in run.call_args_list:
            command=call.args[0]
            self.assertEqual(command[:2], ['/usr/bin/systemctl','show'])
            self.assertNotIn('Environment',command)
            self.assertNotIn('ExecStart',command)

    def test_class_validator_is_inventoried_without_loading_the_class(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'worker.py'
            path.write_text('class Bridge:\n    def validate(self, data):\n        return "invalid_fields", data.get("query")\n')
            value=inspect_worker(path)
        self.assertEqual(value['observed_request_field_accesses'], ['query'])
        self.assertEqual(value['request_functions'][0]['name'], 'validate')

    def test_docker_inspection_never_executes_container_or_discloses_environment(self):
        from types import SimpleNamespace
        from .audit_bridge import container_inventory
        responses=[SimpleNamespace(returncode=0,stdout='hermes\nother-container\n'),
                   SimpleNamespace(returncode=0,stdout=json.dumps({'user':'1000:1000','status':'running','pid':111,
                        'Env':['PRIVATE'], 'mounts':[{'Source':'/root/hermes-data','Destination':'/opt/data','RW':True}]}))]
        with patch('jev_agent.tender_finder.audit_bridge.shutil.which',return_value='/usr/bin/docker'), patch('subprocess.run',side_effect=responses) as run:
            value=container_inventory()
        self.assertNotIn('PRIVATE', json.dumps(value))
        self.assertEqual(value['containers'][0]['configured_user'],'1000:1000')
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['ps','inspect'])


if __name__ == '__main__':
    unittest.main()
