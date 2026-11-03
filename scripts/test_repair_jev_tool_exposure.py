"""Scoped live-repair filesystem tests, no real server, keys or messages."""
import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from scripts import activate_jev_commercial as operator
from scripts import test_activate_jev_commercial as fixture
from scripts import repair_jev_tool_exposure as repair_module


class EditorTests(unittest.TestCase):
    def test_inline_block_and_indentless_lists_preserve_every_other_byte(self):
        examples=[
            (b'model: PRIVATE_FIXTURE\nplatform_toolsets:\n  telegram: [hermes-telegram] # keep\n  cli: [terminal]\n',
             b'model: PRIVATE_FIXTURE\nplatform_toolsets:\n  telegram: ["hermes-telegram", "jev"] # keep\n  cli: [terminal]\n'),
            (b'platform_toolsets:\n  telegram:\n    - hermes-telegram # original\n  cli: [terminal]\nmodel: PRIVATE_FIXTURE\n',
             b'platform_toolsets:\n  telegram:\n    - hermes-telegram # original\n    - jev\n  cli: [terminal]\nmodel: PRIVATE_FIXTURE\n'),
            (b'platform_toolsets:\n  telegram:\n  - "hermes-telegram"\n  cli: [terminal]\n',
             b'platform_toolsets:\n  telegram:\n  - "hermes-telegram"\n  - jev\n  cli: [terminal]\n'),
            (b'model: PRIVATE_FIXTURE\r\nplatform_toolsets:\r\n  telegram: ["hermes-telegram"]\r\n',
             b'model: PRIVATE_FIXTURE\r\nplatform_toolsets:\r\n  telegram: ["hermes-telegram", "jev"]\r\n'),
            (b'model: PRIVATE_FIXTURE',b'model: PRIVATE_FIXTURE\nplatform_toolsets:\n  telegram: ["hermes-telegram", "jev"]\n')]
        for before,after in examples:
            with self.subTest(before=before):self.assertEqual(repair_module.config_patch(before),after)

    def test_missing_telegram_entry_gets_a_separate_line_without_rewriting_other_platforms(self):
        raw=b'platform_toolsets:\n  cli: [terminal]'
        self.assertEqual(repair_module.config_patch(raw),raw+b'\n  telegram: ["hermes-telegram", "jev"]\n')

    def test_alias_duplicate_flow_and_unreviewed_selections_are_rejected(self):
        for raw in (b'platform_toolsets: &x\n  telegram: [hermes-telegram]\n',
            b'platform_toolsets: {telegram: [hermes-telegram]}\n',
            b'platform_toolsets:\n  telegram: *alias\n',
            b'platform_toolsets:\n  telegram: []\n',
            b'platform_toolsets:\n  telegram:\n  - browser\n',
            b'platform_toolsets:\n  telegram: [hermes-telegram]\n  telegram: [terminal]\n',
            b'platform_toolsets:\n  telegram: [hermes-telegram]\nplatform_toolsets: {}\n',
            b'<<: *defaults\nmodel: fixture\n'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):repair_module.config_patch(raw)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.ActivationTests('test_activation_preserves_plugin_inode_container_old_key_and_owner')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.activation.apply()
        self.bundle=dict(self.fixture.bundle)
        self.bundle['candidate']=dict(self.fixture.bundle['candidate'])
        for name in repair_module.PATCHES:
            raw=b'"""existing adapter fixture"""\n'
            self.fixture.put('/opt/stroyka-jev/app/'+name,raw)
            self.bundle['candidate'][name]=operator.sha(raw)
        from jev_agent.tender_finder import docker_delivery
        delivery='jev_agent/tender_finder/docker_delivery.py'
        original=Path(docker_delivery.__file__).read_bytes()
        self.fixture.put('/opt/stroyka-jev/app/'+delivery,original)
        self.bundle['candidate'][delivery]=operator.sha(original)
        self.raw=b'model: PRIVATE_FIXTURE\nplatform_toolsets:\n  telegram: [hermes-telegram]\n  cli: [terminal]\nagent:\n  disabled_toolsets: []\n'
        self.fixture.put(repair_module.CONFIG,self.raw,0o600)
        self.patch={name:b'"""repaired adapter fixture"""\n' for name in repair_module.PATCHES}
        self.readback_wrong=False;self.extra_platform_change=False
        self.repair=repair_module.Repair(operator,self.bundle,self.patch,_root=self.fixture.root,
            _uid=self.fixture.activation.uid,_run=self.run_command,_sleep=lambda _:None,_probe=Mock(return_value={"runtime_sender_ready":True}))
        self.bundle['probe'].reset_mock();self.fixture.calls.clear()

    def run_command(self,*args,**kwargs):
        if 'config' in args and 'exec' in args:
            suffix=args[args.index('config')+1:]
            if suffix==('path',):return b'/opt/data/config.yaml\n'
            if suffix==('get','agent.disabled_toolsets','--json'):return b'[]\n'
            if suffix==('get','platform_toolsets','--json'):
                raw=self.fixture.path(repair_module.CONFIG).read_bytes()
                selected=['hermes-telegram','jev'] if b'"jev"' in raw and not self.readback_wrong else ['hermes-telegram']
                cli=['browser'] if self.extra_platform_change and b'"jev"' in raw else ['terminal']
                return json.dumps({'telegram':selected,'cli':cli}).encode()
            raise AssertionError(suffix)
        return self.fixture.run_command(*args,**kwargs)

    def test_repair_changes_pinned_sources_and_telegram_only_preserving_keys_and_container(self):
        inode=self.fixture.path('/opt/stroyka-jev/app/'+operator.PLUGIN).stat().st_ino
        delivery=self.fixture.path('/opt/stroyka-jev/app/jev_agent/tender_finder/docker_delivery.py')
        delivery_before=(delivery.stat().st_ino,delivery.read_bytes())
        key=self.fixture.path('/etc/stroyka-jev-commercial/private/admission.key');old_key=key.read_bytes()
        result=self.repair.apply();self.assertTrue(result['repaired']);self.assertFalse(result['real_telegram_acceptance'])
        self.assertEqual(key.read_bytes(),old_key)
        self.assertEqual(self.fixture.path('/opt/stroyka-jev/app/'+operator.PLUGIN).stat().st_ino,inode)
        self.assertEqual((delivery.stat().st_ino,delivery.read_bytes()),delivery_before)
        self.assertEqual(result['source_files_updated'],4)
        self.assertEqual(self.fixture.path(repair_module.CONFIG).read_bytes(),self.raw.replace(b'[hermes-telegram]',b'["hermes-telegram", "jev"]'))
        self.repair.snapshot(self.repair.bundle['candidate'])
        for name in operator.OLD+operator.NEW:self.assertEqual(self.fixture.units[name]['ActiveState'],'active')

    def test_sender_probe_uses_native_venv_and_only_loads_original_guarded_sender(self):
        from jev_agent.tender_finder.docker_delivery import REMOTE_PROGRAM
        self.repair.base.run=Mock(return_value=b'{"runtime_sender_ready": true, "notifications_sent": false}\n')
        self.assertTrue(self.repair.delivery_probe()['runtime_sender_ready'])
        argv=self.repair.base.run.call_args.args
        self.assertEqual(argv[-5:-1],('/opt/hermes/.venv/bin/python','-I','-B','-c'))
        self.assertIn('10000:10000',argv);self.assertIn('HERMES_HOME=/opt/data',argv)
        self.assertNotIn('--print-runtime-command',argv)
        # The fixed program loads the original gate. Invoking its returned
        # sender here would fail this test; no real send/config is used.
        guarded_fixture="def _load_sender():\n    def sender(*args): raise RuntimeError('probe_must_not_send')\n    return sender\n"
        program=argv[-1].replace(repr(REMOTE_PROGRAM),repr(guarded_fixture))
        output=io.StringIO()
        with contextlib.redirect_stdout(output):exec(compile(program,'native-venv-probe','exec'),{})
        self.assertEqual(json.loads(output.getvalue()),{'runtime_sender_ready':True,'notifications_sent':False})

    def test_sender_probe_rejects_extra_logs_or_unconfirmed_load(self):
        for raw in (b'',b'{}',b'BOOTSTRAP_ERROR\n{"runtime_sender_ready":true}'):
            self.repair.base.run=Mock(return_value=raw)
            with self.assertRaisesRegex(ValueError,'sender_runtime_not_confirmed'):self.repair.delivery_probe()
        self.assertFalse(self.repair.journal.exists())

    def test_bad_config_readback_restores_raw_file_before_old_code_is_changed(self):
        self.readback_wrong=True
        with self.assertRaisesRegex(ValueError,'telegram_only'):self.repair.apply()
        self.assertEqual(self.repair.state()['source_intents'],[])
        self.assertTrue(self.repair.rollback()['restored'])
        self.assertEqual(self.fixture.path(repair_module.CONFIG).read_bytes(),self.raw)
        self.repair.snapshot(self.repair.bundle['previous'])

    def test_sender_dependency_failure_stops_before_maintenance_or_config_write(self):
        self.repair.probe=Mock(side_effect=ValueError('hermes_sender_runtime_not_confirmed'))
        with self.assertRaisesRegex(ValueError,'sender_runtime_not_confirmed'):self.repair.apply()
        self.assertFalse(self.repair.journal.exists())
        self.assertEqual(self.fixture.path(repair_module.CONFIG).read_bytes(),self.raw)
        self.repair.snapshot(self.repair.bundle['previous'])
        self.assertFalse(any('stop' in call for call in self.fixture.calls))

    def test_repeated_rollback_refuses_foreign_config_change(self):
        self.repair.apply();self.repair.rollback()
        self.assertTrue(self.repair.rollback()['restored'])
        self.fixture.path(repair_module.CONFIG).write_bytes(self.raw+b'# operator change\n')
        with self.assertRaisesRegex(ValueError,'configuration_or_container_changed'):self.repair.rollback()

    def test_unrelated_platform_change_is_detected(self):
        self.extra_platform_change=True
        with self.assertRaisesRegex(ValueError,'telegram_only'):self.repair.apply()
        self.assertTrue(self.repair.rollback()['restored'])
        self.assertEqual(self.fixture.path(repair_module.CONFIG).read_bytes(),self.raw)

    def test_failure_after_source_patch_restores_pinned_sources_and_config_keeps_receipts(self):
        original=self.repair.base.healthy
        self.repair.base.healthy=lambda _:(_ for _ in ()).throw(ValueError('synthetic_failed_health'))
        with self.assertRaisesRegex(ValueError,'failed_health'):self.repair.apply()
        receipt=self.fixture.path('/var/lib/stroyka-jev-commercial/private/receipt');receipt.write_text('unknown: preserve')
        self.repair.base.healthy=original
        result=self.repair.rollback();self.assertTrue(result['restored']);self.assertFalse(result['data_restored'])
        self.assertEqual(receipt.read_text(),'unknown: preserve')
        self.assertEqual(self.fixture.path(repair_module.CONFIG).read_bytes(),self.raw)
        self.repair.snapshot(self.repair.bundle['previous'])

    def test_foreign_config_blocks_rollback_before_any_stop(self):
        self.repair.apply();self.fixture.path(repair_module.CONFIG).write_bytes(b'manual PRIVATE_FIXTURE edit')
        count=len(self.fixture.calls)
        with self.assertRaisesRegex(ValueError,'foreign_config'):self.repair.rollback()
        self.assertEqual(len(self.fixture.calls),count)

    def test_repeat_apply_preserves_previous_success(self):
        self.repair.apply();count=len(self.fixture.calls)
        with self.assertRaisesRegex(ValueError,'existing_repair'):self.repair.apply()
        self.assertEqual(len(self.fixture.calls),count)
        self.assertEqual(self.repair.state()['phase'],'repaired_unverified')

    def test_verified_exec_namespace_preserves_operator_function_binding(self):
        namespace={'__name__':'test_verified_operator'}
        exec(compile(Path(operator.__file__).read_bytes(),'verified-operator','exec'),namespace)
        verified=type('VerifiedOperator',(),namespace)
        candidate=repair_module.Repair(verified,self.bundle,self.patch,_root=self.fixture.root,
            _uid=self.fixture.activation.uid,_run=self.run_command,_sleep=lambda _:None,_probe=Mock(return_value={"runtime_sender_ready":True}))
        self.assertTrue(candidate.apply()['repaired'])
