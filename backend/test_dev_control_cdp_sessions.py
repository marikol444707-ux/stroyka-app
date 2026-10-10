"""Offline regressions for #275. No Chrome, external HTTP or model calls.

Tests use the actual NetworkBoundary methods with a fake CDP transport and
execute routing in a minimal synthetic Daemon fixture. Full-file hash checks
use a scoped synthetic trust reference; production pins are checked separately. Existing backend
unittest discovery includes this file without installing worker dependencies.
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from dev_control.browser_worker.network_guard import NetworkBoundary, _TRANSPORT_BLOCK_SCRIPT
from dev_control.browser_worker.patch_harness import (
    EXPECTED_VERSION, EXPECTED_ORIGINAL_SHA256, EXPECTED_PATCHED_SHA256,
    NEW_ROUTE, OLD_ROUTE, patch_file, patched_source,
)
from dev_control.jev_timeweb import JevError


SOURCE = ('class Daemon:\n'
          '    async def handle(self, req):\n'
          '        method = req["method"]\n'
          '        ' + OLD_ROUTE + '\n'
          '        return sid\n')


class HarnessRoutingPatchTest(unittest.TestCase):
    def setUp(self):
        from dev_control.browser_worker import patch_harness
        # Real pins are fixed in production code; tests never take trust from
        # the mutated input under test. Use one static synthetic reference here
        # to keep ordinary backend CI independent of the third-party package.
        self.assertEqual(EXPECTED_ORIGINAL_SHA256,
                         '7f05f904e62af8c07153c34a1fd3d334acf5c5aded8d0ddab974596bb50a8c97')
        self.assertEqual(EXPECTED_PATCHED_SHA256,
                         'c91b78c5bf6bd8858721bc6f834104666f0191965ae2946b01c832af004aca46')
        self.fixture_original_hash = hashlib.sha256(SOURCE.encode()).hexdigest()
        self.fixture_patched_hash = hashlib.sha256(SOURCE.replace(OLD_ROUTE, NEW_ROUTE, 1).encode()).hexdigest()
        for name, value in (('EXPECTED_ORIGINAL_SHA256', self.fixture_original_hash),
                            ('EXPECTED_PATCHED_SHA256', self.fixture_patched_hash)):
            handle = patch.object(patch_harness, name, value)
            handle.start()
            self.addCleanup(handle.stop)

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

    def test_original_and_patched_full_file_digests_on_synthetic_fixture(self):
        self.assertEqual(hashlib.sha256(SOURCE.encode()).hexdigest(), self.fixture_original_hash)
        output = patched_source(SOURCE, EXPECTED_VERSION)
        self.assertEqual(hashlib.sha256(output.encode()).hexdigest(), self.fixture_patched_hash)

    def test_early_return_and_request_rewrite_are_rejected(self):
        for source in (SOURCE, patched_source(SOURCE, EXPECTED_VERSION)):
            route = NEW_ROUTE if NEW_ROUTE in source else OLD_ROUTE
            mutations = (
                source.replace('        ' + route, '        return {"result": {"sid": "foreign-tab"}}\n        ' + route),
                source.replace('        ' + route, '        req["session_id"] = "foreign-tab"\n        ' + route),
                source.replace('        ' + route, '        method = "Target.closeTarget"\n        ' + route),
                source.replace('return sid', 'return "foreign-tab"'),
                source + '\n# unreviewed module change\n',
            )
            for changed in mutations:
                with self.subTest(patched=route == NEW_ROUTE), self.assertRaisesRegex(ValueError, 'SHA256'):
                    patched_source(changed, EXPECTED_VERSION)

    def test_changed_line_endings_bom_or_truncation_rejected_without_write(self):
        original = SOURCE.encode('utf-8')
        for raw in (original.replace(b'\n', b'\r\n'), b'\xef\xbb\xbf' + original,
                    original[:-1], original + b'\n', original + b'\xff'):
            with self.subTest(size=len(raw)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'daemon.py'
                path.write_bytes(raw)
                with self.assertRaises((ValueError, UnicodeDecodeError)):
                    patch_file(path, EXPECTED_VERSION)
                self.assertEqual(path.read_bytes(), raw)

    def test_unrecognized_original_or_patched_file_is_not_written(self):
        for source in (SOURCE, patched_source(SOURCE, EXPECTED_VERSION)):
            changed = source + '\n# downstream code\n'
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'daemon.py'
                path.write_bytes(changed.encode())
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    patch_file(path, EXPECTED_VERSION)
                self.assertEqual(path.read_bytes(), changed.encode())

    def test_bad_transform_output_cannot_be_written(self):
        from dev_control.browser_worker import patch_harness
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'daemon.py'
            path.write_bytes(SOURCE.encode())
            with patch.object(patch_harness, 'NEW_ROUTE', 'sid = req.get("diagnostic-test-route")'):
                with self.assertRaisesRegex(ValueError, 'patched daemon.py SHA256'):
                    patch_file(path, EXPECTED_VERSION)
            self.assertEqual(path.read_bytes(), SOURCE.encode())

    def test_failed_entrypoint_prints_no_readiness_marker(self):
        from dev_control.browser_worker import patch_harness
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'daemon.py'
            raw = (SOURCE + '\n# changed\n').encode()
            path.write_bytes(raw)
            dist = SimpleNamespace(version=EXPECTED_VERSION, files=['browser_harness/daemon.py'],
                                   locate_file=lambda _: path)
            with patch.object(patch_harness, 'distribution', return_value=dist):
                with patch('builtins.print') as output, self.assertRaisesRegex(ValueError, 'SHA256'):
                    patch_harness.main()
                output.assert_not_called()
            self.assertEqual(path.read_bytes(), raw)

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
        guard._read_only = False
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

    def test_new_targets_install_fetch_and_transport_block_before_resume(self):
        for kind in ('page', 'iframe', 'worker', 'shared_worker', 'service_worker'):
            with self.subTest(kind=kind):
                guard = self.guard()
                guard._handle_attached_target(self.event('new-child', kind))
                calls = guard._cdp.call_args_list
                expected_methods = (
                    ['Fetch.enable', 'Target.setAutoAttach', 'Page.enable',
                     'Page.addScriptToEvaluateOnNewDocument',
                     'Runtime.evaluate', 'Runtime.runIfWaitingForDebugger']
                    if kind in {'page', 'iframe'}
                    else ['Fetch.enable', 'Target.setAutoAttach',
                          'Runtime.evaluate', 'Runtime.runIfWaitingForDebugger']
                )
                self.assertEqual([item.args[0] for item in calls], expected_methods)
                self.assertTrue(all(item.kwargs['session_id'] == 'new-child' for item in calls))
                self.assertTrue(calls[1].kwargs['waitForDebuggerOnStart'])
                self.assertIn('new-child', guard._guarded_sessions)

    def test_transport_block_is_worker_safe_and_covers_required_non_fetch_apis(self):
        self.assertIn('globalThis', _TRANSPORT_BLOCK_SCRIPT)
        self.assertNotIn('window', _TRANSPORT_BLOCK_SCRIPT)
        self.assertIn('STROYKA_TRANSPORT_BLOCK_FAILED', _TRANSPORT_BLOCK_SCRIPT)
        self.assertIn('if (!installed)', _TRANSPORT_BLOCK_SCRIPT)
        for api in ('WebSocket', 'WebTransport', 'RTCPeerConnection', 'webkitRTCPeerConnection'):
            self.assertIn(api, _TRANSPORT_BLOCK_SCRIPT)

    def test_registration_is_local_to_each_job_not_global(self):
        first, second = self.guard('company-a'), self.guard('company-b')
        event = self.event('child')
        first._handle_attached_target(event)
        self.assertNotIn('child', second._guarded_sessions)
        second._handle_attached_target(event)
        self.assertEqual(second._cdp.call_count, 6)

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
        cases = (
            ('page', 'Fetch.enable'),
            ('page', 'Target.setAutoAttach'),
            ('page', 'Page.enable'),
            ('page', 'Page.addScriptToEvaluateOnNewDocument'),
            ('page', 'Runtime.evaluate'),
            ('worker', 'Runtime.evaluate'),
            ('shared_worker', 'Runtime.evaluate'),
            ('service_worker', 'Runtime.evaluate'),
        )
        for kind, failed_method in cases:
            with self.subTest(kind=kind, method=failed_method):
                guard = self.guard()
                def fail(method, **params):
                    if method == failed_method:
                        raise RuntimeError('guard setup failed')
                    return {}
                guard._cdp.side_effect = fail
                guard._drain_events = lambda: [{'method': 'Target.attachedToTarget',
                                                'params': self.event('new-child', kind)}]
                guard._loop()
                self.assertNotIn('new-child', guard._guarded_sessions)
                self.assertNotIn('Runtime.runIfWaitingForDebugger',
                                 [item.args[0] for item in guard._cdp.call_args_list])
                with self.assertRaises(JevError):
                    guard.raise_if_failed()

    def test_close_is_safe_when_root_protection_failed_before_thread_start(self):
        guard = self.guard()
        guard._thread = threading.Thread(target=lambda: None)
        guard._thread_started = False
        guard.close()
        guard._cdp.assert_called_once_with('Fetch.disable', session_id='root-session')

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
