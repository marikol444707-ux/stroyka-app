"""Offline regressions for #275. No Chrome, external HTTP or model calls.

Tests use the actual NetworkBoundary methods with a fake CDP transport and
execute the patched dispatcher in a minimal Daemon fixture. Existing backend
unittest discovery includes this file without installing worker dependencies.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dev_control.browser_worker.network_guard import NetworkBoundary
from dev_control.browser_worker.patch_harness import (
    EXPECTED_VERSION, NEW_ROUTE, OLD_ROUTE, patch_file, patched_source,
)
from dev_control.jev_timeweb import JevError


SOURCE = ('class Daemon:\n'
          '    async def handle(self, req):\n'
          '        method = req["method"]\n'
          '        ' + OLD_ROUTE + '\n'
          '        return sid\n')


class HarnessRoutingPatchTest(unittest.TestCase):
    def routed(self, source, method, session):
        namespace = {}
        exec(compile(source, '<daemon-fixture>', 'exec'), namespace)
        daemon = namespace['Daemon']()
        daemon.session = 'default-tab'
        return asyncio.run(daemon.handle({'method': method, 'session_id': session}))

    def test_old_source_loses_autoattach_session(self):
        self.assertIsNone(self.routed(SOURCE, 'Target.setAutoAttach', 'job-tab'))

    def test_autoattach_preserves_explicit_session_without_default_fallback(self):
        source = patched_source(SOURCE, EXPECTED_VERSION)
        for supplied in ('job-tab', 'other-company-tab', None):
            with self.subTest(session=supplied):
                self.assertEqual(self.routed(source, 'Target.setAutoAttach', supplied), supplied)

    def test_browser_level_methods_stay_browser_level(self):
        source = patched_source(SOURCE, EXPECTED_VERSION)
        for method in ('Target.createTarget', 'Target.createBrowserContext',
                       'Target.disposeBrowserContext', 'Target.attachToTarget',
                       'Target.closeTarget', 'Target.getBrowserContexts'):
            with self.subTest(method=method):
                self.assertIsNone(self.routed(source, method, 'job-tab'))

    def test_page_runtime_and_fetch_keep_existing_session_routing(self):
        source = patched_source(SOURCE, EXPECTED_VERSION)
        for method in ('Page.navigate', 'Runtime.runIfWaitingForDebugger',
                       'Fetch.enable', 'Fetch.continueRequest', 'Fetch.failRequest'):
            with self.subTest(method=method):
                self.assertEqual(self.routed(source, method, 'job-tab'), 'job-tab')
                self.assertEqual(self.routed(source, method, None), 'default-tab')

    def test_patch_is_idempotent(self):
        once = patched_source(SOURCE, EXPECTED_VERSION)
        self.assertEqual(patched_source(once, EXPECTED_VERSION), once)
        self.assertIn(NEW_ROUTE, once)

    def test_unsupported_version_rejected(self):
        with self.assertRaises(ValueError):
            patched_source(SOURCE, '0.1.14')

    def test_unknown_duplicate_or_comment_only_source_rejected(self):
        for source in ('', SOURCE + SOURCE, '# ' + OLD_ROUTE,
                       SOURCE.replace(OLD_ROUTE, 'sid = self.session'),
                       SOURCE + '\n# ' + OLD_ROUTE):
            with self.subTest(source=source), self.assertRaises(ValueError):
                patched_source(source, EXPECTED_VERSION)

    def test_rejection_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'daemon.py'
            path.write_text(SOURCE, encoding='utf-8')
            with self.assertRaises(ValueError):
                patch_file(path, 'unknown')
            self.assertEqual(path.read_text(), SOURCE)
            patch_file(path, EXPECTED_VERSION)
            self.assertEqual(path.read_text(), patched_source(SOURCE, EXPECTED_VERSION))

    def test_build_pins_dependency_and_applies_patch_before_nonroot_runtime(self):
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / 'dev_control/Dockerfile').read_text()
        requirements = (root / 'dev_control/browser_worker/requirements.txt').read_text()
        self.assertIn('browser-harness==0.1.13', requirements)
        apply = 'RUN python /app/dev_control/browser_worker/patch_harness.py'
        self.assertLess(dockerfile.index('COPY . /app/dev_control'), dockerfile.index(apply))
        self.assertLess(dockerfile.index(apply), dockerfile.index('USER worker'))

    def test_installed_distribution_entrypoint_without_importing_daemon(self):
        from dev_control.browser_worker import patch_harness
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'daemon.py'
            path.write_text(SOURCE, encoding='utf-8')
            dist = SimpleNamespace(version=EXPECTED_VERSION,
                                   files=['browser_harness/daemon.py'],
                                   locate_file=lambda _: path)
            with patch.object(patch_harness, 'distribution', return_value=dist):
                with patch('builtins.print'):
                    patch_harness.main()
            self.assertIn(NEW_ROUTE, path.read_text())


class RegisteredSessionRegressionTest(unittest.TestCase):
    def guard(self, root='root-session'):
        # Constructor's dependency import is intentionally avoided in ordinary CI.
        guard = NetworkBoundary.__new__(NetworkBoundary)
        guard._cdp = Mock(return_value={})
        guard._session_id = root
        guard._guarded_sessions = {root}
        guard._child_targets = set()
        guard._base_url = 'https://qa.example.test/app'
        guard._error = None
        guard._stop = threading.Event()
        return guard

    def event(self, sid, kind='page', url='https://qa.example.test/app'):
        return {'sessionId': sid, 'targetInfo': {
            'targetId': 'target-' + sid, 'type': kind, 'url': url}}

    def test_root_announcement_does_not_reconfigure_resume_or_track_root(self):
        guard = self.guard()
        guard._handle_attached_target(self.event('root-session'))
        guard._cdp.assert_not_called()
        self.assertEqual(guard._child_targets, set())

    def test_registered_child_is_not_processed_twice(self):
        guard = self.guard()
        event = self.event('child')
        guard._handle_attached_target(event)
        guard._cdp.reset_mock()
        guard._handle_attached_target(event)
        guard._cdp.assert_not_called()
        self.assertEqual(guard._child_targets, {'target-child'})

    def test_new_targets_keep_fetch_and_autoattach_before_resume(self):
        for kind in ('page', 'iframe', 'worker', 'shared_worker', 'service_worker'):
            with self.subTest(kind=kind):
                guard = self.guard()
                guard._handle_attached_target(self.event('new-child', kind))
                calls = guard._cdp.call_args_list
                self.assertEqual([item.args[0] for item in calls],
                                 ['Fetch.enable', 'Target.setAutoAttach',
                                  'Runtime.runIfWaitingForDebugger'])
                self.assertTrue(all(item.kwargs['session_id'] == 'new-child' for item in calls))
                self.assertTrue(calls[1].kwargs['waitForDebuggerOnStart'])
                self.assertIn('new-child', guard._guarded_sessions)

    def test_registration_is_local_to_each_job_not_global(self):
        first, second = self.guard('company-a'), self.guard('company-b')
        event = self.event('child')
        first._handle_attached_target(event)
        self.assertNotIn('child', second._guarded_sessions)
        second._handle_attached_target(event)
        self.assertEqual(second._cdp.call_count, 3)

    def test_unapproved_page_or_iframe_closed_without_resume(self):
        for kind in ('page', 'iframe'):
            for url in ('https://other.example.test/app', 'https://qa.example.test/admin'):
                with self.subTest(kind=kind, url=url):
                    guard = self.guard()
                    guard._handle_attached_target(self.event('bad', kind, url))
                    guard._cdp.assert_called_once_with('Target.closeTarget', targetId='target-bad')
                    self.assertNotIn('bad', guard._guarded_sessions)
                    with self.assertRaises(JevError):
                        guard.raise_if_failed()

    def test_failed_protection_never_registers_or_resumes_new_session(self):
        for failed_method in ('Fetch.enable', 'Target.setAutoAttach'):
            with self.subTest(method=failed_method):
                guard = self.guard()
                def fail(method, **params):
                    if method == failed_method:
                        raise RuntimeError('guard setup failed')
                    return {}
                guard._cdp.side_effect = fail
                guard._drain_events = lambda: [{'method': 'Target.attachedToTarget',
                                                'params': self.event('new-child')}]
                guard._loop()
                self.assertNotIn('new-child', guard._guarded_sessions)
                self.assertNotIn('Runtime.runIfWaitingForDebugger',
                                 [item.args[0] for item in guard._cdp.call_args_list])
                with self.assertRaises(JevError):
                    guard.raise_if_failed()

    def test_paused_request_still_blocked_after_ignored_root_event(self):
        guard = self.guard()
        def events():
            guard._stop.set()
            return [{'method': 'Target.attachedToTarget', 'params': self.event('root-session')},
                    {'method': 'Fetch.requestPaused', 'session_id': 'root-session',
                     'params': {'requestId': 'blocked-request', 'resourceType': 'XHR',
                                'request': {'url': 'https://outside.example.test'}}}]
        guard._drain_events = events
        guard._loop()
        guard._cdp.assert_called_once_with('Fetch.failRequest', session_id='root-session',
                                          requestId='blocked-request', errorReason='BlockedByClient')
        with self.assertRaises(JevError):
            guard.raise_if_failed()

    def test_allowed_request_still_continues_on_exact_child_session(self):
        guard = self.guard()
        guard._handle_attached_target(self.event('child'))
        guard._cdp.reset_mock()
        def events():
            guard._stop.set()
            return [{'method': 'Fetch.requestPaused', 'session_id': 'child',
                     'params': {'requestId': 'allowed-request', 'resourceType': 'XHR',
                                'request': {'url': 'https://qa.example.test/api'}}}]
        guard._drain_events = events
        guard._loop()
        guard._cdp.assert_called_once_with('Fetch.continueRequest', session_id='child',
                                          requestId='allowed-request')
        guard.raise_if_failed()


if __name__ == '__main__':
    unittest.main()
