import unittest
import tempfile
import fcntl
import subprocess
import io
import json
from contextlib import redirect_stdout
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from scripts.jev_control import recovery_decision, ssh_command, browser_task, server, main
from scripts.install_jev_control import control_environment
from dev_control.browser_worker.control_task import task_spec, demo_passed, _probe_browser


class JevControlTest(unittest.TestCase):
    def test_client_preserves_a_valid_busy_result_on_nonzero_remote_exit(self):
        response = subprocess.CompletedProcess([], 1, '{"ok":false,"status":"busy"}', '')
        output = io.StringIO()
        with patch('sys.argv', ['jev_control.py', 'status']), \
             patch('scripts.jev_control.subprocess.run', return_value=response), redirect_stdout(output):
            self.assertEqual(main(), 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'busy')

    def test_install_does_not_copy_qa_cookie_database_or_general_worker_credentials(self):
        source = {'TIMEWEB_AI_API_KEY': 'test-key', 'QA_SESSION_COOKIE_VALUE': 'private',
                  'DATABASE_URL': 'private', 'DEV_CONTROL_API_TOKEN': 'old-token',
                  'CHROME_NO_SANDBOX': '1'}
        env = control_environment(source, {'TIMEWEB_AI_API_KEY': 'test-key', 'TIMEWEB_TEXT_MODEL': 'example'})
        self.assertNotIn('QA_SESSION_COOKIE_VALUE', env)
        self.assertNotIn('DATABASE_URL', env)
        self.assertEqual(len(env['DEV_CONTROL_API_TOKEN']), 64)
        self.assertNotEqual(env['DEV_CONTROL_API_TOKEN'], 'old-token')
        self.assertEqual(env['QA_BASE_URL'], 'http://127.0.0.1:8080')
        with self.assertRaises(ValueError):
            control_environment(source, {'TIMEWEB_AI_API_KEY': 'other', 'TIMEWEB_TEXT_MODEL': 'example'})

    def test_transport_timeout_is_a_failed_health_result_for_recovery(self):
        with patch('scripts.jev_control.subprocess.run', side_effect=subprocess.TimeoutExpired('docker', 110)):
            self.assertEqual(browser_task({'operation': 'health'})['status'], 'runner_timeout')

    def test_watchdog_cannot_restart_or_probe_an_active_task(self):
        with tempfile.TemporaryDirectory() as directory:
            lock_path = str(Path(directory) / 'operation.lock')
            with open(lock_path, 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch('scripts.jev_control.os.geteuid', return_value=0), \
                     patch('scripts.jev_control.STATE_DIR', Path(directory)), \
                     patch('scripts.jev_control.LOCK', lock_path), \
                     patch('scripts.jev_control.browser_task') as task:
                    self.assertEqual(server({'operation': 'watchdog'})['status'], 'busy')
                    task.assert_not_called()

    def test_external_task_cannot_select_an_arbitrary_site_or_supply_credentials(self):
        for request in ({'operation': 'browse', 'url': 'https://stroyka26.pro'},
                        {'operation': 'avito', 'query': 'brick', 'cookie': 'secret'},
                        {'operation': 'avito', 'query': 'x' * 501}):
            with self.assertRaises(ValueError):
                task_spec(request)

    def test_avito_search_keeps_region_and_encodes_query_as_data(self):
        from urllib.parse import urlparse, parse_qs
        spec = task_spec({'operation': 'avito', 'query': 'кирпич б/у & пароль'})
        parsed = urlparse(spec['url'])
        self.assertEqual(parsed.netloc, 'www.avito.ru')
        self.assertEqual(parsed.path, '/stavropolskiy_kray')
        self.assertEqual(parse_qs(parsed.query), {'q': ['кирпич б/у & пароль']})

    def test_demo_success_requires_independent_facts_and_actual_agent_completion(self):
        facts = {'marker': 'JEV_BROWSER_OK', 'disabled': True}
        self.assertTrue(demo_passed({'status': 'done', 'history': [{'kind': 'click'}]}, facts))
        self.assertFalse(demo_passed({'status': 'done', 'history': []}, facts))
        self.assertFalse(demo_passed({'status': 'blocked', 'history': [{'kind': 'click'}]}, facts))
        self.assertFalse(demo_passed({'status': 'done', 'history': [{'kind': 'click'}]},
                                     {'marker': 'JEV_BROWSER_OK', 'disabled': False}))

    def test_watchdog_requires_three_failures_and_caps_restarts_per_hour(self):
        state = {'failures': 1, 'restarts': []}
        state, restart = recovery_decision(state, healthy=False, now=5000)
        self.assertFalse(restart)
        state, restart = recovery_decision(state, healthy=False, now=5030)
        self.assertTrue(restart)
        self.assertEqual(state['restarts'], [5030])
        state, restart = recovery_decision({'failures': 2, 'restarts': [4000, 4100, 4200]},
                                           healthy=False, now=5050)
        self.assertFalse(restart)
        self.assertEqual(state['status'], 'recovery_limit_reached')

    def test_healthy_check_clears_failures_and_old_restarts_expire(self):
        state, restart = recovery_decision({'failures': 5, 'restarts': [1, 4999]},
                                           healthy=True, now=5000)
        self.assertFalse(restart)
        self.assertEqual(state['failures'], 0)
        self.assertEqual(state['restarts'], [4999])

    def test_goal_and_query_are_never_interpolated_into_ssh_command(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(ssh_command(), ['ssh', '-o', 'BatchMode=yes', '-o',
                'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=yes',
                'stroyka-dev-agent', 'sudo -n python3 /usr/local/libexec/stroyka-jev-control/jev_control.py --server'])


class BrowserProbeTest(unittest.IsolatedAsyncioTestCase):
    async def test_renderer_probe_checks_execution_and_disposes_its_context(self):
        class Socket:
            def __init__(self):
                self.sent = []
            async def __aenter__(self): return self
            async def __aexit__(self, *_): pass
            async def send(self, text): self.sent.append(json.loads(text))
            async def recv(self):
                request = self.sent[-1]
                result = {'Target.createBrowserContext': {'browserContextId': 'ctx'},
                          'Target.createTarget': {'targetId': 'tab'},
                          'Target.attachToTarget': {'sessionId': 'session'},
                          'Runtime.evaluate': {'result': {'value': 2}}}.get(request['method'], {})
                return json.dumps({'id': request['id'], 'result': result})
        socket = Socket()
        endpoint = 'ws://127.0.0.1:9222/devtools/browser/test'
        with patch.dict('sys.modules', {'websockets': SimpleNamespace(connect=lambda *a, **kw: socket)}), \
             patch('urllib.request.urlopen', return_value=io.StringIO(json.dumps({'webSocketDebuggerUrl': endpoint}))):
            await _probe_browser()
        self.assertEqual(socket.sent[-1]['method'], 'Target.disposeBrowserContext')
        self.assertEqual(socket.sent[-1]['params'], {'browserContextId': 'ctx'})
        self.assertIn('Runtime.evaluate', [x['method'] for x in socket.sent])

    async def test_probe_rejects_redirected_websocket_before_connecting(self):
        from unittest.mock import Mock
        connect = Mock()
        with patch.dict('sys.modules', {'websockets': SimpleNamespace(connect=connect)}), \
             patch('urllib.request.urlopen', return_value=io.StringIO(json.dumps({
                 'webSocketDebuggerUrl': 'ws://foreign.example/devtools/browser/test'}))):
            with self.assertRaises(ValueError):
                await _probe_browser()
        connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
