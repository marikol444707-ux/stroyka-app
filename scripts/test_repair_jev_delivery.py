"""Filesystem/operator regression fixtures; no live tokens, Docker or sends."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from scripts import repair_jev_delivery as delivery
from scripts import test_repair_jev_tool_exposure as visibility_fixture
from jev_agent.tender_finder import docker_delivery


def original_source():
    raw = Path(docker_delivery.__file__).read_bytes()
    start = raw.index(b'\ndef _profile_sender(sender):')
    end = raw.index(b'\ndef main():', start)
    return (raw[:start] + raw[end:]).replace(
        b'return _profile_sender(module.send_message_tool)', b'return module.send_message_tool')


class DeliveryRepairTests(unittest.TestCase):
    def setUp(self):
        self.visibility = visibility_fixture.RepairTests()
        self.visibility.setUp(); self.addCleanup(self.visibility.doCleanups)
        self.h = self.visibility.repair
        self.f = self.visibility.fixture
        self.f.put('/opt/stroyka-jev/app/' + delivery.TARGET, original_source())
        self.h.bundle['previous'][delivery.TARGET] = delivery.OLD_SHA
        self.h.bundle['candidate'][delivery.TARGET] = delivery.OLD_SHA
        self.h.apply()
        self.probe = Mock()
        self.repair = delivery.DeliveryRepair(self.h, _probe=self.probe)
        self.f.calls.clear()
        self.receipt = self.f.put('/var/lib/stroyka-jev-commercial/private/unknown-fixture.json',
                                 b'{"delivery_status":"unknown","notification_sent":null}', 0o600)

    def test_one_source_change_keeps_container_keys_config_and_unknown_receipt(self):
        watched = [self.f.path('/etc/stroyka-jev-commercial/private/admission.key'),
                   self.f.path('/root/hermes-data/config.yaml'),
                   self.f.path('/opt/stroyka-jev/app/' + self.h.op.PLUGIN),
                   self.f.path('/var/lib/stroyka-jev-commercial/private/unknown-fixture.json')]
        before = [(p.stat().st_ino, p.read_bytes()) for p in watched]
        result = self.repair.apply()
        self.assertTrue(result['repaired']); self.assertFalse(result['notifications_sent'])
        self.assertFalse(result['unknown_delivery_retried'])
        self.assertEqual(self.repair.path.read_bytes(), Path(docker_delivery.__file__).read_bytes())
        self.assertEqual(before, [(p.stat().st_ino, p.read_bytes()) for p in watched])
        self.assertFalse(any('docker' in call[0] and ('stop' in call or 'start' in call) for call in self.f.calls))
        self.assertEqual(self.probe.call_count, 2)
        self.assertEqual(self.repair.status()['phase'], 'ready_unverified')

    def test_missing_profile_credentials_stops_before_backup_or_service_change(self):
        self.probe.side_effect = ValueError('native_profile_credentials_not_confirmed')
        with self.assertRaisesRegex(ValueError, 'native_profile_credentials'):
            self.repair.apply()
        self.assertFalse(self.repair.journal.exists()); self.assertFalse(self.repair.backup.exists())
        self.assertFalse(any('stop' in call for call in self.f.calls))

    def test_foreign_source_change_is_rejected_without_maintenance(self):
        self.repair.path.write_bytes(b'foreign source')
        with self.assertRaises(ValueError): self.repair.apply()
        self.assertFalse(self.repair.journal.exists())
        self.assertFalse(any('stop' in call for call in self.f.calls))

    def test_repeated_apply_does_not_restart_or_resend(self):
        self.repair.apply(); self.f.calls.clear()
        with self.assertRaisesRegex(ValueError, 'existing_delivery_repair_requires_review'):
            self.repair.apply()
        self.assertEqual(self.f.calls, [])

    def test_failed_post_patch_probe_can_restore_source_and_preserve_receipts(self):
        self.probe.side_effect = [None, ValueError('native_profile_credentials_not_confirmed')]
        with self.assertRaises(ValueError): self.repair.apply()
        self.assertTrue(self.repair.rollback()['restored'])
        self.assertEqual(self.repair.path.read_bytes(), original_source())
        self.assertEqual(self.repair.status()['phase'], 'rolled_back')
        self.assertEqual(self.f.path('/var/lib/stroyka-jev-commercial/private/unknown-fixture.json').read_bytes(),
                         b'{"delivery_status":"unknown","notification_sent":null}')

    def test_foreign_change_after_patch_blocks_rollback(self):
        self.repair.apply(); self.repair.path.write_bytes(b'foreign source')
        with self.assertRaisesRegex(ValueError, 'foreign_delivery_change_blocks_rollback'):
            self.repair.rollback()
        self.assertEqual(self.repair.path.read_bytes(), b'foreign source')

    def test_probe_uses_scoped_sdk_but_never_calls_returned_sender(self):
        self.repair.base.run = Mock(return_value=b'{"profile_credentials_ready": true, "notifications_sent": false}\n')
        self.repair.credentials_probe(Path(docker_delivery.__file__).read_bytes())
        argv = self.repair.base.run.call_args.args
        self.assertEqual(argv[-5:-1], ('/opt/hermes/.venv/bin/python', '-I', '-B', '-c'))
        program = argv[-1]
        fixture = ("def _load_sender():\n    return lambda _: (_ for _ in ()).throw(Exception('must_not_send'))\n"
                   "def _profile_sender(fn):\n    return fn\n")
        program = program.replace(repr(docker_delivery.REMOTE_PROGRAM), repr(fixture))
        # Replace only native config import with an in-memory fixture.
        program = program.replace('from gateway.config import load_gateway_config, Platform',
                                 'load_gateway_config=lambda: type("C",(),{"platforms":{None:type("P",(),{"token":"fixture"})()}})(); Platform=type("E",(),{"TELEGRAM":None})')
        output = io.StringIO()
        with contextlib.redirect_stdout(output): exec(compile(program, 'configuration-only-probe', 'exec'), {})
        self.assertEqual(json.loads(output.getvalue()), {'profile_credentials_ready': True, 'notifications_sent': False})

    def test_patch_reconstructs_exact_current_source_and_refuses_other_input(self):
        self.assertEqual(delivery.patched(original_source(), self.h.op.sha), Path(docker_delivery.__file__).read_bytes())
        with self.assertRaisesRegex(ValueError, 'exact_original_delivery_required'):
            delivery.patched(b'unknown source', self.h.op.sha)


if __name__ == '__main__':
    unittest.main()
