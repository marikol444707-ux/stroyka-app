"""No systemd/production calls: exercise native binding's dangerous failure paths."""
import contextlib
import tempfile
from pathlib import Path
import types
import unittest
from unittest.mock import patch
import maintenance as m
import maintenance_runtime as runtime
from production import Stop

class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.ops=object.__new__(runtime.Operations)
        self.ops.retry_owned=False;self.ops.groups={}
    def test_runtime_policy_is_exclusive_and_original_restart_policy_restored(self):
        dropin=self.root/'unit.d'/'guard.conf';calls=[]
        def run(args,**kwargs):
            calls.append(args)
            if 'Restart' in args:return 'no' if dropin.exists() else 'always'
            return ''
        with patch.object(runtime,'RETRY_DROPIN',dropin),patch.object(runtime,'run',side_effect=run):
            self.ops.require_single_start_policy()
            self.assertEqual(dropin.read_bytes(),b'[Service]\nRestart=no\n')
            with self.assertRaises(Stop):self.ops.require_single_start_policy()
            self.ops.restore_retry_policy()
            self.assertFalse(dropin.exists())
        self.assertEqual(sum(c==['systemctl','daemon-reload'] for c in calls),2)
    def test_foreign_runtime_policy_is_never_overwritten_or_deleted(self):
        dropin=self.root/'guard.conf';dropin.write_bytes(b'foreign')
        with patch.object(runtime,'RETRY_DROPIN',dropin),patch.object(runtime,'run') as run:
            with self.assertRaises(Stop):self.ops.require_single_start_policy()
            with self.assertRaises(Stop):self.ops.restore_retry_policy()
        run.assert_not_called();self.assertEqual(dropin.read_bytes(),b'foreign')
    def test_failed_daemon_reload_leaves_owned_policy_for_manual_recovery(self):
        dropin=self.root/'unit.d'/'guard.conf'
        with patch.object(runtime,'RETRY_DROPIN',dropin),patch.object(runtime,'run',side_effect=Stop('FAILED')):
            with self.assertRaises(Stop):self.ops.require_single_start_policy()
        self.assertTrue(dropin.exists());self.assertTrue(self.ops.retry_owned)
    def test_missing_or_wrong_restart_property_refuses_start_policy(self):
        for value in ('always','on-failure',''):
            dropin=self.root/('unit'+str(len(value)))/'guard.conf';self.ops.retry_owned=False
            with self.subTest(value=value),patch.object(runtime,'RETRY_DROPIN',dropin),patch.object(runtime,'run',return_value=value):
                with self.assertRaisesRegex(Stop,'RETRIES'):self.ops.require_single_start_policy()
    def test_one_shot_services_cannot_be_replayed_by_binding(self):
        with patch.object(runtime,'run') as run:
            for unit in m.SERVICES:
                with self.assertRaisesRegex(Stop,'REPLAY'):self.ops.start(unit)
        run.assert_not_called()
    def test_recovery_closes_cron_and_ingress_before_main_and_never_starts(self):
        state={u:{'active':'active','cgroup_empty':False} for u in m.UNITS}
        actions=[]
        def stop(u):actions.append(u);state[u]={'active':'inactive','cgroup_empty':True}
        for u in m.SERVICES:state[u]={'active':'inactive','cgroup_empty':True}
        self.ops.state=lambda u:state[u];self.ops.stop=stop
        self.ops.verify_ingress_excluded=lambda:None
        self.ops.hold_for_recovery()
        self.assertEqual(actions[0],m.CRON)
        self.assertLess(actions.index(m.INGRESS),actions.index(m.MAIN))
    def test_cgroup_path_traversal_is_refused(self):
        self.ops.groups={m.CRON:'/../../tmp'}
        self.ops.probe=types.SimpleNamespace(unit_report=lambda _:{'ActiveState':'inactive','CGroupProcessCount':0})
        with self.assertRaisesRegex(Stop,'CGROUP'):self.ops.state(m.CRON)
    def test_drain_detects_children_when_systemd_clears_controlgroup_property(self):
        group='/system.slice/cron.service';self.ops.groups={m.CRON:group}
        self.ops.probe=types.SimpleNamespace(unit_report=lambda _:{'ActiveState':'inactive','ControlGroup':'','CGroupProcessCount':0})
        fake=types.SimpleNamespace(read_text=lambda:'1234\n')
        with patch.object(Path,'rglob',return_value=iter([fake])):
            self.assertFalse(self.ops.state(m.CRON)['cgroup_empty'])

if __name__=='__main__':unittest.main(verbosity=2)
