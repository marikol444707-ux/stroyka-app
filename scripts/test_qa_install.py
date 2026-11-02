"""No host/database/container/app calls: only mocked driver and source assertions."""
import ast
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from scripts import qa_install as qa


def manifest():
    return dict(qa_only=True, database='stroyka_qa', container='stroyka-qa-db',
                source_sha='a'*40, target_sha='b'*40, candidate_root=str(qa.ROOT),
                frontend_root=qa.FRONTEND_VOLUME, discard_test_data=True,
                maintenance_database='postgres')


class QAInstallTests(unittest.TestCase):
    def test_routing_change_preserves_other_routes(self):
        from scripts.test_qa_routing import GATEWAY, STATIC, MAIN, CANDIDATE
        a,b=qa.routing_update(STATIC,GATEWAY,{'8001/tcp':[{'HostPort':'8002'}]})
        self.assertEqual(a,STATIC)
        self.assertEqual(b,GATEWAY.replace(MAIN,CANDIDATE))
        old=STATIC.replace('/srv/app/build','/srv/app')
        a,b=qa.routing_update(old,GATEWAY,{'8001/tcp':[{'HostPort':'8002'}]})
        self.assertEqual(a,STATIC)

    def test_unknown_route_or_ports_rejected(self):
        for ports,gateway in [({},'reverse_proxy stroyka-qa-backend:8000\n'),
                              ({'8000/tcp':[{'HostPort':'8002'}]},'reverse_proxy other:80\n')]:
            with self.assertRaises(ValueError):
                qa.routing_update('root * /srv/app\n',gateway,ports)

    def test_database_preparation_is_one_bound_child(self):
        d=qa.LocalDriver()
        d.environment={'synthetic':'only'}
        d.maintenance_stage=Path('/synthetic')
        with tempfile.TemporaryDirectory() as folder, patch.object(qa.tempfile,'mkdtemp',return_value=folder), patch.object(d,'run') as run:
            d.prepare_database(manifest())
        self.assertEqual(run.call_count, 1)
        args=run.call_args.args[0]
        self.assertEqual(args[0],qa.PYTHON_PATH)
        ast.parse(args[-1])
        payload=json.loads(run.call_args.kwargs['stdin'])
        self.assertEqual(payload['maintenance_database'],'postgres')
        self.assertEqual(payload['confirmed_scope'],'qa_connection_gate_and_session_termination')

    def test_plan_has_no_execution(self):
        self.assertFalse(qa.plan(manifest())['execution'])

    def test_scope_or_extra_fields_rejected(self):
        for key, value in [('database','production'), ('container','other'),
                           ('qa_only',False), ('candidate_root','/var/www/stroyka-app'),
                           ('target_sha','short'), ('extra','anything')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                qa.plan(dict(manifest(), **{key:value}))

    def test_explicit_confirmation_before_writes(self):
        d = MagicMock()
        d.preflight.return_value = {'same': True}
        out = qa.execute(manifest(), d, lambda _: qa.confirmation(manifest()))
        self.assertFalse(out['audit_complete'])
        self.assertEqual([c[0] for c in d.mock_calls],
            ['deliver_target','preflight','prepare_frontend','preflight','verify_frontend',
             'preflight','verify_frontend','record_maintenance_intent','accept_preparation',
             'stop','prepare_database','switch','frontend','start_and_check'])

    def test_missing_confirmation_has_no_writes(self):
        d = MagicMock()
        with self.assertRaises(ValueError):
            qa.execute(manifest(), d, lambda _: '')
        d.stop.assert_not_called()
        d.prepare_database.assert_not_called()

    def test_expired_confirmation_has_no_writes(self):
        d = MagicMock()
        with self.assertRaises(ValueError):
            qa.execute(manifest(), d, lambda _: qa.confirmation(manifest()),
                       clock=MagicMock(side_effect=[0,301]))
        d.stop.assert_not_called()

    def test_changed_preflight_has_no_writes(self):
        d = MagicMock()
        d.preflight.side_effect = [{'version':1},{'version':2}]
        with self.assertRaises(ValueError):
            qa.execute(manifest(), d, lambda _: qa.confirmation(manifest()))
        d.stop.assert_not_called()

    def test_each_failed_phase_stops_without_rollback(self):
        phases = ['stop','prepare_database','switch','frontend','start_and_check']
        for i, phase in enumerate(phases):
            d = MagicMock()
            d.preflight.return_value = {}
            getattr(d,phase).side_effect = RuntimeError('mock failure')
            with self.subTest(phase=phase), self.assertRaises(RuntimeError):
                qa.execute(manifest(),d,lambda _:qa.confirmation(manifest()))
            for later in phases[i+1:]:
                getattr(d,later).assert_not_called()

    def test_dry_run_command_never_constructs_driver(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'manifest.json'
            p.write_text(json.dumps(manifest()))
            with patch.object(qa,'LocalDriver') as driver, patch('builtins.print'):
                qa.command(SimpleNamespace(manifest=p,execute=False))
                driver.assert_not_called()

    def test_noninteractive_execution_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'manifest.json'
            p.write_text(json.dumps(manifest()))
            with patch.object(qa,'LocalDriver') as driver, patch('sys.stdin.isatty',return_value=False):
                with self.assertRaises(ValueError):
                    qa.command(SimpleNamespace(manifest=p,execute=True))
                driver.assert_not_called()

    def test_sql_and_command_scope_source(self):
        tree=ast.parse(Path(qa.__file__).read_text())
        text='\n'.join(n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str))
        self.assertNotIn('DROP SCHEMA public CASCADE',text)
        self.assertNotIn('DROP DATABASE',text.replace('No DROP DATABASE',''))
        self.assertNotIn('docker run',text)
        self.assertIn('qa_connection_gate_and_session_termination',text)
        self.assertIn('stroyka_qa',text)

    def test_intent_failure_prevents_stops_and_switch(self):
        d=MagicMock()
        d.preflight.return_value={}
        d.record_maintenance_intent.side_effect=OSError('synthetic journal failure')
        with self.assertRaises(OSError):
            qa.execute(manifest(),d,lambda _:qa.confirmation(manifest()))
        d.stop.assert_not_called()
        d.switch.assert_not_called()

    def test_confirmation_names_access_change_and_termination(self):
        phrase=qa.confirmation(manifest())
        self.assertIn('CLOSE QA CONNECTIONS VIA postgres',phrase)
        self.assertIn('TERMINATE OTHER stroyka_qa SESSIONS',phrase)
        self.assertIn(manifest()['target_sha'],phrase)

    def test_every_preparation_failure_precedes_live_changes(self):
        for phase in ('deliver_target','preflight','prepare_frontend','verify_frontend','record_maintenance_intent'):
            with self.subTest(phase=phase):
                d=MagicMock()
                d.preflight.return_value={}
                getattr(d,phase).side_effect=RuntimeError('synthetic preparation failure')
                with self.assertRaises(RuntimeError):
                    qa.execute(manifest(),d,lambda _:qa.confirmation(manifest()))
                for later in ('stop','switch','prepare_database','frontend','start_and_check'):
                    getattr(d,later).assert_not_called()

    def test_denied_confirmation_discards_only_preparation(self):
        d=MagicMock()
        d.preflight.return_value={}
        with self.assertRaises(ValueError):
            qa.execute(manifest(),d,lambda _: '')
        d.discard_preparation.assert_called_once()
        d.stop.assert_not_called()
        d.accept_preparation.assert_not_called()

    def test_database_child_runs_target_tooling_before_switch(self):
        d=qa.LocalDriver()
        d.environment={}
        d.maintenance_stage=Path('/synthetic')
        d.database_evidence={'synthetic':True}
        with patch.object(d,'run') as run:
            d.prepare_database(manifest())
        payload=json.loads(run.call_args.kwargs['stdin'])
        self.assertEqual(payload['expected_database'],{'synthetic':True})
        self.assertEqual(payload['target_root'],str(Path(qa.__file__).resolve().parents[1]))

    def test_runtime_version_precedence(self):
        target='b'*40
        qa.check_version_environment({},target)
        qa.check_version_environment({'APP_VERSION':target,'GIT_COMMIT':'old'},target)
        qa.check_version_environment({'GIT_COMMIT':target[:12]},target)
        with self.assertRaises(ValueError):
            qa.check_version_environment({'APP_VERSION':'old','GIT_COMMIT':target},target)

    def test_dry_run_imports_do_not_load_maintenance_or_frontend_stager(self):
        tree=ast.parse(Path(qa.__file__).read_text())
        names=[n.module for n in tree.body if isinstance(n,ast.ImportFrom)]
        self.assertNotIn('scripts.qa_maintenance',names)
        self.assertNotIn('scripts.qa_frontend_stage',names)
        self.assertFalse(any((n or '').startswith('backend') for n in names))

    def test_delivery_rejects_wrong_target_without_checkout(self):
        d=qa.LocalDriver()
        m=manifest()
        def git(*args):
            if args==('config','--name-only','--list'): return ''
            if args==('rev-parse','HEAD'): return m['source_sha']
            if args==('status','--porcelain'): return ''
            if args==('rev-parse','--is-shallow-repository'): return 'true'
            if args==('rev-parse','FETCH_HEAD^{commit}'): return 'c'*40
            if 'fetch' in args: return ''
            raise AssertionError(args)
        with patch.object(qa.socket,'gethostname',return_value='stroyka-dev-agent'), patch.object(d,'git',side_effect=git) as git_call, patch.object(d,'run',return_value=m['target_sha']):
            with self.assertRaises(ValueError): d.deliver_target(m)
        fetch=[c.args for c in git_call.call_args_list if 'fetch' in c.args]
        self.assertEqual(len(fetch),1)
        self.assertIn('--unshallow',fetch[0])
        self.assertIn('https://github.com/marikol444707-ux/stroyka-app.git',fetch[0])
        self.assertFalse(any('checkout' in c.args or '--force' in c.args for c in git_call.call_args_list))

    def test_dryrun_and_confirmation_disclose_general_api_switch(self):
        view=qa.plan(manifest())
        self.assertFalse(view['execution'])
        self.assertEqual(view['routing_change']['general_api'],'/api/*')
        self.assertEqual(view['routing_change']['preserve_exact_canary'],'/api/users/qa-readonly-context/identity')
        self.assertIn('SWITCH GENERAL /api/* FROM MAIN TO CANDIDATE',qa.confirmation(manifest()))
        self.assertIn('PRESERVE EXACT IDENTITY CANARY',qa.confirmation(manifest()))

    def test_config_reader_and_adapter_preserve_crlf_bytes(self):
        from scripts.test_qa_routing import GATEWAY, STATIC, MAIN, CANDIDATE
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'Caddyfile'
            original=GATEWAY.replace('\n','\r\n').encode()
            p.write_bytes(original)
            read=qa.read_config_text(p)
            self.assertEqual(read.encode(),original)
            static=STATIC.replace('\n','\r\n')
            a,b=qa.routing_update(static,read,{'8001/tcp':[{'HostPort':'8002'}]})
            self.assertEqual(a,static)
            self.assertEqual(b.encode(),original.replace(MAIN.encode(),CANDIDATE.encode()))

    def test_routing_preflight_accepts_observed_global_gateway_and_plain_static(self):
        from scripts.test_qa_routing import KNOWN_LINE_GLOBAL_GATEWAY, STATIC, MAIN, CANDIDATE
        a,b=qa.routing_update(STATIC,KNOWN_LINE_GLOBAL_GATEWAY,{'8001/tcp':[{'HostPort':'8002'}]})
        self.assertEqual(a,STATIC)
        self.assertEqual(b,KNOWN_LINE_GLOBAL_GATEWAY.replace(MAIN,CANDIDATE))
