import ast
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SPEC=importlib.util.spec_from_file_location('single_server_probe',Path(__file__).with_name('server_readonly_check.py'))
probe=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(probe)
routing_facts=probe.routing_facts

class ReadOnlyProbeTests(unittest.TestCase):
    def test_pinned_embedded_guards_and_source_do_not_import_application(self):
        before=set(sys.modules)
        runner=probe.startup_module();plan=runner.load_plan()
        self.assertEqual(len(plan['guards']),31)
        self.assertFalse(any(name.startswith('backend') for name in set(sys.modules)-before))
    def test_wrong_host_stops_before_commands_or_database(self):
        with patch.object(probe.sys,'argv',['server-readonly-check.py']),patch.object(probe.os,'geteuid',return_value=0),patch.object(probe.socket,'gethostname',return_value='not-production'),patch.object(probe.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main(),1)
        run.assert_not_called();self.assertIn('WRONG_PRODUCTION_HOST_OR_USER',out.getvalue())
    def test_systemd_output_does_not_include_environment_or_command_values(self):
        secret='PRIVATE_VALUE_NEVER_EMIT'
        text='LoadState=loaded\nActiveState=inactive\nExecStart={ path=/usr/bin/python3 ; argv[]=/usr/bin/python3 --token '+secret+' ; }\nControlGroup=\n'
        with patch.object(probe,'output',return_value=text):report=probe.unit_report('stroyka.service')
        self.assertNotIn(secret,str(report));self.assertNotIn('ExecStart',report)
        self.assertEqual(report['Executable'],'/usr/bin/python3')
    def test_nginx_credentials_headers_and_urls_are_not_disclosed(self):
        text='http { server { server_name stroyka26.pro; listen 443 ssl; location / { proxy_pass http://user:PRIVATE_TOKEN@127.0.0.1:8001/private?token=PRIVATE_QUERY; proxy_set_header Authorization PRIVATE_HEADER; } } }'
        result=routing_facts(text)
        self.assertEqual(result[0]['proxy_targets'],[{'scheme':'http','host':'127.0.0.1','port':8001}])
        self.assertNotIn('PRIVATE',str(result))
    def test_unrelated_virtual_host_is_not_reported(self):
        self.assertEqual(routing_facts('http { server { server_name private.example; location / { proxy_pass http://private.example; } } }'),[])
    def test_dynamic_upstream_does_not_become_fake_verified_address(self):
        result=routing_facts('server { server_name stroyka26.pro; location / { proxy_pass http://$private_upstream; } }')[0]
        self.assertEqual(result['dynamic_proxy_targets'],1);self.assertEqual(result['proxy_targets'],[])
    def test_probe_has_no_service_control_commands(self):
        source=Path(probe.__file__).read_text();tree=ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node,ast.List) and node.elts and isinstance(node.elts[0],ast.Constant) and node.elts[0].value=='systemctl':
                values=[n.value for n in node.elts if isinstance(n,ast.Constant)]
                self.assertTrue(set(values).isdisjoint({'start','stop','restart','reload','enable','disable','mask','unmask'}))

class SystemdTextInventoryTests(unittest.TestCase):
    def test_no_jobs_human_message_is_explicitly_recognized(self):
        with patch.object(probe,'output',return_value='No jobs running.\n') as output:
            self.assertEqual(probe.systemd_rows('jobs'),[])
        self.assertEqual(output.call_args.args[0],['systemctl','list-jobs','--no-pager','--plain','--no-legend'])
    def test_empty_jobs_output_is_recognized(self):
        with patch.object(probe,'output',return_value='   \n'):
            self.assertEqual(probe.systemd_rows('jobs'),[])
    def test_actual_queued_job_is_never_hidden(self):
        with patch.object(probe,'output',return_value='42 stroyka.service start waiting\n43 nginx.service stop running\n'):
            self.assertEqual(probe.systemd_rows('jobs'),[
                {'unit':'stroyka.service','type':'start','state':'waiting'},
                {'unit':'nginx.service','type':'stop','state':'running'}])
    def test_unrecognized_response_is_not_treated_as_empty(self):
        for raw in ('not JSON', 'Error connecting to bus', 'not-a-job stroyka.service start waiting'):
            with self.subTest(raw=raw),patch.object(probe,'output',return_value=raw):
                with self.assertRaises(probe.Stop):probe.systemd_rows('jobs')
    def test_unit_metadata_drops_all_description_values(self):
        with patch.object(probe,'output',return_value='stroyka.service loaded active running PRIVATE_DESCRIPTION\nstroyka-backup.timer loaded inactive dead PRIVATE_EXTRA\n'):
            rows=probe.systemd_rows('units')
        self.assertEqual(len(rows),2);self.assertEqual(rows[1]['active'],'inactive')
        self.assertNotIn('PRIVATE',str(rows))
    def test_no_units_message_and_unknown_response_are_distinct(self):
        with patch.object(probe,'output',return_value='No units found.\n'):
            self.assertEqual(probe.systemd_rows('units'),[])
        with patch.object(probe,'output',return_value='unsupported output'):
            with self.assertRaises(probe.Stop):probe.systemd_rows('units')
    def test_error_stage_is_reported_without_raw_response_or_traceback(self):
        def fail():
            probe.STAGE='QUEUED_JOBS'
            raise ValueError('PRIVATE_RESPONSE')
        with patch.object(probe,'collect',side_effect=fail),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main(),1)
        self.assertIn('QUEUED_JOBS',out.getvalue());self.assertNotIn('PRIVATE',out.getvalue())

class ErrorCountTests(unittest.TestCase):
    def test_budget_error_exposes_only_aggregate_sizes_and_remains_failed(self):
        runner=probe.startup_module()
        error=runner.CheckError('JSON_SCAN_BUDGET_EXCEEDED',{
            'json_rows':40,'json_total_bytes':50000000,'json_max_value_bytes':2000000,
            'business_row':'PRIVATE_DATA','password':'PRIVATE_SECRET'})
        with patch.object(probe,'collect',side_effect=error),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(probe.main(),1)
        import json
        result=json.loads(out.getvalue())
        self.assertFalse(result['report_complete']);self.assertFalse(result['installation_ready'])
        self.assertEqual(result['code'],'JSON_SCAN_BUDGET_EXCEEDED')
        self.assertEqual(result['counts'],dict(json_rows=40,json_total_bytes=50000000,json_max_value_bytes=2000000))
        self.assertNotIn('PRIVATE',out.getvalue())
    def test_invalid_count_values_are_never_printed(self):
        error=ValueError('PRIVATE')
        error.counts={'json_rows':True,'json_total_bytes':'PRIVATE','json_max_value_bytes':-1,'unexpected':42}
        self.assertEqual(probe.safe_error_counts(error),{})
        error.counts=['PRIVATE'];self.assertEqual(probe.safe_error_counts(error),{})
    def test_missing_counts_are_safe(self):
        self.assertEqual(probe.safe_error_counts(ValueError('PRIVATE')),{})
    def test_production_budget_limits_are_preserved(self):
        runner=probe.startup_module()
        self.assertEqual((runner.MAX_JSON_ROWS,runner.MAX_JSON_VALUE_BYTES,runner.MAX_JSON_TOTAL_BYTES),
                         (50000,1024*1024,32*1024*1024))

if __name__=='__main__':unittest.main(verbosity=2)
