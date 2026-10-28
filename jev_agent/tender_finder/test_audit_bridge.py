import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .audit_bridge import collect, inspect_worker, validation_contract, result_permissions


class BridgeAuditTests(unittest.TestCase):
    def test_operational_source_and_cli_shape_never_disclose_query_or_token_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'worker.py'
            path.write_text('''
def run_job(request):
    token = "PRIVATE_TOKEN"
    return subprocess.run(["stroyka-jev", "commercial-search", "--query", "PRIVATE_QUERY"], input=token)
''')
            value=inspect_worker(path)
        self.assertEqual(value['literal_cli_shapes'][0]['arguments'],
                         ['stroyka-jev','commercial-search','--query','<REDACTED_ARGUMENT>'])
        self.assertTrue(value['source_stable_during_audit'])
        self.assertEqual(value['operational_functions'][0]['name'],'run_job')
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(value))
        self.assertNotIn('PRIVATE_QUERY',json.dumps(value))

    def test_actual_execute_and_file_helpers_are_included_for_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'worker.py'
            path.write_text('def execute(req):\n    return "PRIVATE"\ndef put_json(fd, name, data):\n    return None\ndef read_req(fd, name):\n    return None\n')
            value=inspect_worker(path)
        self.assertEqual({item['name'] for item in value['operational_functions']}, {'execute','put_json','read_req'})
        self.assertNotIn('PRIVATE',json.dumps(value))

    def test_inline_raw_validator_reveals_public_schema_without_private_values(self):
        import ast
        source = r'''
TOKEN = "PRIVATE_TOKEN"
REGION = "Ставропольский край"
REQUEST_RE = re.compile(r"search-[A-Za-z0-9_-]{1,40}")
TOPICS = {"roof": "PRIVATE_QUERY_VALUE", "electric": "other value"}
def validate(raw):
    if not isinstance(raw, dict) or set(raw) != {"version", "request_id", "region", "sources", "topics"}:
        raise BadRequest("invalid_fields")
    if type(raw["version"]) is not int or raw["version"] != 1:
        raise BadRequest("invalid_version")
    sources = raw["sources"]
    if any(x not in ("eis", "commercial") for x in sources):
        raise BadRequest("invalid_sources")
    topics = raw["topics"]
    if not 1 <= len(topics) <= 4:
        raise BadRequest("invalid_topics")
    if topics == ["all"]:
        topics = ALL_TOPICS
    return topics
'''
        value=validation_contract(ast.parse(source))
        self.assertEqual(value['exact_field_sets'][0]['fields'], ['region','request_id','sources','topics','version'])
        self.assertEqual(value['version_checks'], [{'operator':'NotEq','value':1}])
        self.assertEqual(value['source_choices'][0]['values'], ['eis','commercial'])
        self.assertEqual(value['topic_keys'], ['electric','roof'])
        self.assertEqual(value['topic_selectors'][0]['values'], ['all'])
        self.assertEqual(value['topic_length_checks'][0]['numbers'], [1,4])
        self.assertTrue(value['region_is_stavropol'])
        self.assertEqual(value['request_id_pattern'], 'search-[A-Za-z0-9_-]{1,40}')
        self.assertFalse(value['complete'])
        self.assertNotIn('PRIVATE', json.dumps(value))

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

    def test_unit_queries_never_disclose_environment_commands_or_change_services(self):
        from types import SimpleNamespace
        with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='ActiveState=active\nEnvironment=PRIVATE\nExecStart=PRIVATE\n')) as run, patch('jev_agent.tender_finder.audit_bridge.WORKER',Path('/missing-worker')), patch('jev_agent.tender_finder.audit_bridge.shutil.which',return_value=None), patch('jev_agent.tender_finder.audit_bridge.result_permissions',return_value={'exists':False}):
            value=collect()
        self.assertNotIn('PRIVATE', json.dumps(value))
        for call in run.call_args_list:
            command=call.args[0]
            self.assertEqual(command[:2], ['/usr/bin/systemctl','show'])
            self.assertNotIn('Environment',command)
            # Captured only for a hash/path-presence check; never printed raw.
            self.assertIn('ExecStart',command)

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
                        'Env':['PRIVATE'], 'mounts':[{'Source':'/root/hermes-data','Destination':'/opt/data','RW':True}]})),
                   SimpleNamespace(returncode=0,stdout='PID EUID EGID COMMAND\n123 10000 10000 python3\n')]
        with patch('jev_agent.tender_finder.audit_bridge.shutil.which',return_value='/usr/bin/docker'), patch('subprocess.run',side_effect=responses) as run:
            value=container_inventory()
        self.assertNotIn('PRIVATE', json.dumps(value))
        self.assertEqual(value['containers'][0]['configured_user'],'1000:1000')
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['ps','inspect','top'])
        self.assertEqual(value['containers'][0]['process_credentials'][0]['euid'],10000)

    def test_result_permission_report_does_not_read_contents_or_disclose_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'private-job-id.json').write_text('PRIVATE_RESULT_CONTENT')
            (root/'private-job-id.json').chmod(0o640)
            (root/'link.json').symlink_to(root/'private-job-id.json')
            with patch.object(Path,'read_text',side_effect=AssertionError('Do not read result content')):
                value=result_permissions(root)
        encoded=json.dumps(value)
        self.assertNotIn('private-job-id',encoded)
        self.assertNotIn('PRIVATE_RESULT_CONTENT',encoded)
        self.assertEqual(sum(value['mode_counts'].values()),1)
        self.assertEqual(value['symlinks_skipped'],1)
        self.assertEqual(value['real_hermes_result_read_access'],'NOT_TESTED')


if __name__ == '__main__':
    unittest.main()
