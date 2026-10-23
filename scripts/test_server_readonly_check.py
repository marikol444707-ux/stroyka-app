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

if __name__=='__main__':unittest.main(verbosity=2)
