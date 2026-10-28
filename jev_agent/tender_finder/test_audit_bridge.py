import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .audit_bridge import (collect, collect_integration_requirements, inspect_worker, validation_contract,
                           result_permissions, runtime_source, public_image_metadata, REVIEWED_RUNTIME,
                           _read_relative_source, hermes_source_inventory, collect_hermes_interface,
                           startup_environment,startup_source_metadata,collect_startup,process_startup_sources,
                           public_install_metadata,process_runtime_metadata,PUBLIC_DOCKER_LAUNCHERS)


class BridgeAuditTests(unittest.TestCase):
    def test_process_startup_probe_reads_public_files_not_env_or_command_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            root=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
            def source(fd,path,maximum,*,with_metadata=False):
                raw=None
                if path=='opt/venv/bin/hermes':raw=b'#!/opt/venv/bin/python3\nPRIVATE_TOKEN="not emitted"\n'
                if path=='etc/s6-overlay/s6-rc.d/main-hermes/run':raw=b'exec /opt/venv/bin/hermes gateway\n'
                if path=='opt/hermes/gateway/authz_mixin.py':raw=b'TOKEN="PRIVATE_TOKEN"\n'
                if raw is not None:return (raw,{'uid':0,'gid':0,'mode':'0o644'}) if with_metadata else raw
            with patch('jev_agent.tender_finder.audit_bridge.os.readlink',return_value='/usr/local/bin/python3.12'),patch('jev_agent.tender_finder.audit_bridge.os.open',return_value=root),patch('jev_agent.tender_finder.audit_bridge._read_relative_source',side_effect=source) as read,patch('subprocess.run') as run:
                value=process_startup_sources(123)
            run.assert_not_called()
            self.assertNotIn('PRIVATE_TOKEN',json.dumps(value))
            self.assertEqual(value['entrypoint_candidates'][0]['python_shebang'],'/opt/venv/bin/python3')
            self.assertFalse(value['process_env_read']);self.assertFalse(value['process_cmdline_read'])
            self.assertTrue(all(not call.args[1].endswith(('.env','environ','cmdline')) for call in read.call_args_list))

    def test_startup_environment_only_emits_paths_and_hashed_owner(self):
        value=startup_environment('HOME=/opt/data\nVIRTUAL_ENV=/opt/venv\nTELEGRAM_ALLOWED_USERS=123456789\nTELEGRAM_TOKEN=PRIVATE_TOKEN\nHERMES_PROFILE=PRIVATE_PROFILE\nHERMES_PYTHON=/opt/hermes/.venv/bin/python')
        self.assertEqual(value['paths']['HOME'],'/opt/data')
        self.assertEqual(value['paths']['HERMES_PYTHON'],'/opt/hermes/.venv/bin/python')
        self.assertEqual(value['numeric_allowed_owner_count'],1)
        self.assertFalse(value['owner_selection_required'])
        self.assertNotIn('123456789',json.dumps(value))
        self.assertNotIn('PRIVATE',json.dumps(value))
        self.assertFalse(value['effective_gateway_policy_verified'])
        dynamic=startup_source_metadata(b'export HERMES_PROFILE="$HERMES_PROFILE"\n')
        self.assertEqual(dynamic['dynamic_public_keys'],['HERMES_PROFILE'])
        self.assertNotIn('profile_sha256',dynamic['declared_runtime'])

    def test_ambiguous_duplicate_or_wildcard_owner_is_not_auto_selected(self):
        for source in ('TELEGRAM_ALLOWED_USERS=123,456','TELEGRAM_ALLOWED_USERS=*',
                       'TELEGRAM_ALLOWED_USERS=123\nTELEGRAM_ALLOWED_USERS=456'):
            value=startup_environment(source)
            self.assertTrue(value['owner_selection_required'])
            self.assertNotIn('single_owner_id_sha256',value)

    def test_startup_shell_literals_never_expose_tokens_or_execute_code(self):
        raw=b'#!/bin/sh\nexport HOME=/opt/data\nexport BOT_TOKEN=PRIVATE_TOKEN\nexec s6-setuidgid hermes /opt/venv/bin/hermes gateway --token PRIVATE_TOKEN\n'
        with patch('subprocess.run') as run:
            value=startup_source_metadata(raw)
        run.assert_not_called()
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(value))
        self.assertIn('/opt/venv/bin/hermes',value['exec_shapes'][0])
        self.assertEqual(value['declared_runtime']['paths']['HOME'],'/opt/data')

    def test_startup_probe_only_inspects_container_and_hermes_process(self):
        from types import SimpleNamespace
        containers={'containers':[{'name':'hermes-telegram','image_metadata':{},'process_credentials':[
            {'executable_name':'hermes','host_pid':123},{'executable_name':'python','host_pid':456}]}]}
        observed=SimpleNamespace(returncode=0,stdout='{"entrypoint":["/init","PRIVATE_TOKEN"],"readonly_rootfs":false}\nHOME=/opt/data\nTELEGRAM_ALLOWED_USERS=123456789\n')
        with patch('jev_agent.tender_finder.audit_bridge.container_inventory',return_value=containers),patch('jev_agent.tender_finder.audit_bridge.shutil.which',return_value='/usr/bin/docker'),patch('subprocess.run',return_value=observed) as run,patch('jev_agent.tender_finder.audit_bridge.process_startup_sources',return_value={}) as process:
            value=collect_startup()
        process.assert_called_once_with(123)
        self.assertEqual(run.call_args.args[0][:2],['/usr/bin/docker','inspect'])
        self.assertNotIn('PRIVATE_TOKEN',json.dumps(value));self.assertNotIn('123456789',json.dumps(value))
        self.assertFalse(value['services_changed']);self.assertFalse(value['notifications_sent'])
        self.assertFalse(value['startup'][0]['container_rootfs_readonly'])
    def test_install_markers_project_revision_without_tokens_or_private_fields(self):
        value=public_install_metadata(json.dumps({'revision':'a'*40,'commit':'0'*40,
            'version':'1.2.3','manager':'docker','deployment_kind':'image','token':'PRIVATE_TOKEN',
            'pmRuntime':'/opt/hermes/pm-runtime','private':{'owner':123456789}}).encode())
        self.assertEqual(value['revision'],'a'*40)
        self.assertNotIn('commit',value)
        self.assertEqual(value['pmRuntime'],'/opt/hermes/pm-runtime')
        self.assertFalse(value['active_runtime_verified'])
        self.assertNotIn('PRIVATE',json.dumps(value));self.assertNotIn('123456789',json.dumps(value))
        self.assertNotIn('version',public_install_metadata(b'{"version":"PRIVATE_TOKEN"}'))
        self.assertEqual(public_install_metadata(b'[]')['code'],'PUBLIC_INSTALL_METADATA_INVALID')

    def test_python_process_metadata_reads_only_exe_and_cwd(self):
        paths=[]
        def link(path):
            paths.append(path)
            return '/usr/local/bin/python3.12' if path.endswith('/exe') else '/opt/data/installs/release/code'
        with patch('jev_agent.tender_finder.audit_bridge.os.readlink',side_effect=link),patch('subprocess.run') as run:
            value=process_runtime_metadata(456)
        run.assert_not_called()
        self.assertEqual(paths,['/proc/456/exe','/proc/456/cwd'])
        self.assertEqual(value['observed_source_directory'],'/opt/data/installs/release/code')
        self.assertFalse(value['process_env_read']);self.assertFalse(value['process_cmdline_read'])

    def test_startup_probe_includes_python_metadata_without_reading_python_sources(self):
        from types import SimpleNamespace
        containers={'containers':[{'name':'hermes-telegram','process_credentials':[
            {'executable_name':'python3.12','host_pid':456}]}]}
        observed=SimpleNamespace(returncode=0,stdout='{"entrypoint":["/opt/hermes/docker/entrypoint-dispatch.sh"],"readonly_rootfs":false}\n')
        with patch('jev_agent.tender_finder.audit_bridge.container_inventory',return_value=containers),patch('jev_agent.tender_finder.audit_bridge.shutil.which',return_value='/usr/bin/docker'),patch('subprocess.run',return_value=observed),patch('jev_agent.tender_finder.audit_bridge.process_runtime_metadata',return_value={'process_id':456}) as metadata,patch('jev_agent.tender_finder.audit_bridge.process_startup_sources') as sources:
            value=collect_startup()
        metadata.assert_called_once_with(456);sources.assert_not_called()
        self.assertEqual(value['startup'][0]['container_entrypoint_program'],'entrypoint-dispatch.sh')
        self.assertEqual(value['startup'][0]['python_process_metadata'],[{'process_id':456}])

    def test_fixed_docker_sources_include_launcher_and_do_not_follow_runtime_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'opt/hermes').mkdir(parents=True)
            (root/'private').mkdir();(root/'private/install-stamp.json').write_text('{"token":"PRIVATE"}')
            (root/'opt/hermes/install-stamp.json').symlink_to(root/'private/install-stamp.json')
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:self.assertIsNone(_read_relative_source(fd,'opt/hermes/install-stamp.json',16384))
            finally:os.close(fd)
        self.assertIn('opt/hermes/docker/entrypoint-dispatch.sh',PUBLIC_DOCKER_LAUNCHERS)
        self.assertIn('opt/hermes/docker/main-wrapper.sh',PUBLIC_DOCKER_LAUNCHERS)
        self.assertIn('etc/s6-overlay/s6-rc.d/main-hermes/run',PUBLIC_DOCKER_LAUNCHERS)

    def test_relative_source_reader_cannot_escape_or_follow_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'public').mkdir();(root/'public/source.py').write_bytes(b'public source')
            (root/'private').write_bytes(b'PRIVATE')
            (root/'public/link.py').symlink_to(root/'private')
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:
                self.assertEqual(_read_relative_source(fd,'public/source.py',100),b'public source')
                for path in ('../private','/private','public/link.py'):
                    self.assertIsNone(_read_relative_source(fd,path,100))
                self.assertIsNone(_read_relative_source(fd,'public/source.py',2))
            finally:os.close(fd)

    def test_hermes_source_inventory_emits_signatures_not_private_literals_or_config(self):
        root_fd=os.open('/tmp',os.O_RDONLY|os.O_DIRECTORY)
        def source(root,relative,maximum):
            if relative=='opt/hermes/pyproject.toml':
                return b'[project]\nname="hermes-agent"\nversion="1.2.3"\n[private]\ntoken="PRIVATE"\n'
            if relative=='opt/hermes/.git/HEAD':return b'a'*40
            if relative=='opt/hermes/tools/send_message_tool.py':
                return b'TOKEN="PRIVATE"\ndef send_message(text, chat_id="PRIVATE"):\n return "PRIVATE"\n'
        with patch('jev_agent.tender_finder.audit_bridge.os.readlink',return_value='/opt/hermes'),patch('jev_agent.tender_finder.audit_bridge.os.open',return_value=root_fd),patch('jev_agent.tender_finder.audit_bridge._read_relative_source',side_effect=source),patch('subprocess.run') as run:
            value=hermes_source_inventory(123)
        run.assert_not_called()
        self.assertNotIn('PRIVATE',json.dumps(value))
        self.assertEqual(value['projects'][0]['version'],'1.2.3')
        self.assertEqual(value['source_modules'][0]['entrypoints'][0]['parameters'],['text','chat_id'])
        self.assertFalse(value['notification_binding_verified'])

    def test_focused_hermes_probe_targets_hermes_process_not_arbitrary_python(self):
        containers={'containers':[{'process_credentials':[{'host_pid':123,'executable_name':'hermes'},
                                                          {'host_pid':456,'executable_name':'python'}]}]}
        with patch('jev_agent.tender_finder.audit_bridge.container_inventory',return_value=containers),patch('jev_agent.tender_finder.audit_bridge.hermes_source_inventory',return_value={}) as reader:
            value=collect_hermes_interface()
        reader.assert_called_once_with(123)
        self.assertFalse(value['notifications_sent'])
        self.assertFalse(value['model_called'])

    def test_integration_audit_does_not_execute_worker_or_inspect_requests(self):
        with patch('jev_agent.tender_finder.audit_bridge.runtime_cli_inventory',return_value={}),patch('jev_agent.tender_finder.audit_bridge.container_inventory',return_value={}),patch('jev_agent.tender_finder.audit_bridge.inspect_worker') as worker,patch('jev_agent.tender_finder.audit_bridge.result_permissions') as results:
            value=collect_integration_requirements()
        worker.assert_not_called();results.assert_not_called()
        self.assertFalse(value['search_executed']);self.assertFalse(value['model_called'])
        self.assertFalse(value['notifications_sent']);self.assertFalse(value['notification_binding_verified'])
        self.assertTrue(value['reviewed_eis_review_operation']['invokes_model'])
        # Optional review tools must not accidentally become mandatory search dependencies.
        self.assertEqual(set(REVIEWED_RUNTIME),{'jev_server_tools.py','jev_commercial_search.py','jev_eis_probe.py'})

    def test_image_metadata_never_emits_private_labels_or_urls(self):
        value=public_image_metadata({'image_id':'sha256:'+'a'*64,'revision':'b'*40,'version':'v1.2.3',
                    'source':'https://github.com/synthetic/hermes-agent','Env':['PRIVATE'],
                    'token':'PRIVATE','arbitrary_label':'PRIVATE'})
        self.assertEqual(value['version'],'v1.2.3')
        self.assertEqual(value['revision'],'b'*40)
        self.assertNotIn('PRIVATE',json.dumps(value))
        for source in ('https://user:PRIVATE@github.com/org/repo','https://github.com/org/repo?token=PRIVATE'):
            result=public_image_metadata({'source':source,'version':'PRIVATE_TOKEN'})
            self.assertNotIn('source',result);self.assertNotIn('version',result)

    def test_release_symlink_inventory_reads_only_protected_source_without_executing_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            release=root/'release';release.mkdir()
            source=release/'jev_server_tools.py'
            source.write_text('raise RuntimeError("MUST_NOT_EXECUTE")\nparser.add_argument("--profile-stdin")\n')
            (root/'current').symlink_to(release, target_is_directory=True)
            with patch('subprocess.run') as run:
                result=runtime_source(root/'current'/'jev_server_tools.py',(root,),trusted_uid=os.geteuid())
            run.assert_not_called()
            self.assertEqual(result['parser_flags'],['--profile-stdin'])
            self.assertEqual(result['resolved_path'],str(source))
            source.chmod(0o666)
            denied=runtime_source(root/'current'/'jev_server_tools.py',(root,),trusted_uid=os.geteuid())
            self.assertEqual(denied['code'],'UNTRUSTED_SOURCE_PERMISSIONS')
            self.assertNotIn('sha256',denied)

    def test_release_symlink_cannot_escape_allowed_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);allowed=root/'allowed';allowed.mkdir()
            source=root/'outside.py';source.write_text('secret="PRIVATE"')
            (allowed/'jev_server_tools.py').symlink_to(source)
            value=runtime_source(allowed/'jev_server_tools.py',(allowed,),trusted_uid=os.geteuid())
            self.assertEqual(value['code'],'UNTRUSTED_SOURCE_PATH')
            self.assertNotIn('sha256',value)

    def test_command_assigned_before_runner_reveals_only_allowlisted_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'worker.py'
            source.write_text('EXECUTABLE="/usr/local/bin/stroyka-jev"\ndef execute(req):\n command=[EXECUTABLE,"eis-search","--query","PRIVATE"]\n return runner(command, 100)\n')
            value=inspect_worker(source)
        self.assertEqual(value['literal_cli_shapes'][0]['arguments'],
                         [{'variable':'EXECUTABLE'},'eis-search','--query','<REDACTED_ARGUMENT>'])
        self.assertNotIn('PRIVATE',json.dumps(value))

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
