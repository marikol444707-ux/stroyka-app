import copy
import unittest
import maintenance as m


def clean_report():
    return {'postgres_major':16,'business_guards_satisfied':True,
        'counts':{str(i):0 for i in range(31)},'estimate_json':{'would_update':0,'startup_error':0},
        'prepared_transactions':0,'other_db_sessions':[],
        'catalog':{'inheritance_edges':0,'rules':[],'event_triggers':[],'unclassified_seed_defaults':[],'triggers':[]},
        'bookkeeping':{'explicit_setval':[{'table':t,'setval_logical_noop':True,'increment':1,'cache':1,'cycle':False,'target_within_bounds':True} for t in ['platform_accounts','companies']]}}

class Ops:
    def __init__(self):
        self.units={u:{'active':'inactive','enabled':'disabled','cgroup_empty':True,'result':'success'} for u in m.UNITS}
        for u in [m.MAIN,m.INGRESS,m.WORKER,m.TIMERS[0]]:
            self.units[u].update(active='active',enabled='enabled',cgroup_empty=False)
        self.actions=[];self.jobs=[];self.fail_health=False;self.inventory_ok=True
    def state(self,u):return copy.deepcopy(self.units[u])
    def verify_inventory(self,state):m.require(self.inventory_ok,'INVENTORY_CHANGED')
    def verify_configuration(self):m.require(self.inventory_ok,'CONFIGURATION_CHANGED')
    def stop(self,u):
        self.actions.append(('stop',u));self.units[u].update(active='inactive',cgroup_empty=True)
    def start(self,u):
        self.actions.append(('start',u));self.units[u].update(active='active',cgroup_empty=False)
    def require_single_start_policy(self):pass
    def queued_starts(self,units):return self.jobs
    def verify_ingress_excluded(self):m.require(self.units[m.INGRESS]['active']=='inactive','INGRESS_NOT_EXCLUDED')
    def verify_health_and_business(self):m.require(not self.fail_health,'BUSINESS_CHANGED')

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.ops=Ops();self.events=[];self.boundary=m.Boundary(self.ops,lambda phase,state:self.events.append(phase),pause=lambda _:None)
    def freeze(self):self.boundary.capture();self.boundary.freeze()
    def test_cron_scheduler_stops_before_any_writers_and_returns_to_original_state(self):
        self.ops.units[m.CRON].update(active='active',enabled='enabled',cgroup_empty=False)
        self.freeze()
        self.assertEqual(self.ops.actions[0],('stop',m.CRON))
        self.boundary.start_once(clean_report());self.boundary.restore()
        self.assertEqual(self.ops.actions[-1],('start',m.CRON))
    def test_cron_children_drain_without_kill_or_replay(self):
        self.ops.units[m.CRON].update(active='active',cgroup_empty=False)
        stop=self.ops.stop
        def stop_scheduler(unit):
            stop(unit)
            if unit==m.CRON:self.ops.units[unit]['cgroup_empty']=False
        self.ops.stop=stop_scheduler
        def finish(_):self.ops.units[m.CRON]['cgroup_empty']=True
        self.boundary.pause=finish
        self.freeze()
        self.assertEqual(self.ops.actions.count(('stop',m.CRON)),1)
    def test_cron_children_timeout_prevents_main_stop(self):
        self.ops.units[m.CRON].update(active='active',cgroup_empty=False)
        def stop_scheduler(unit):
            self.ops.actions.append(('stop',unit));self.ops.units[unit]['active']='inactive'
        self.ops.stop=stop_scheduler
        values=iter([0,9999]);self.boundary.clock=lambda:next(values)
        with self.assertRaisesRegex(m.BoundaryError,'TIMEOUT'):self.freeze()
        self.assertNotIn(('stop',m.MAIN),self.ops.actions)
    def test_restart_always_policy_cannot_silently_retry_startup(self):
        self.freeze()
        def refuse():raise m.BoundaryError('AUTOMATIC_STARTUP_RETRIES_NOT_EXCLUDED')
        self.ops.require_single_start_policy=refuse
        with self.assertRaisesRegex(m.BoundaryError,'RETRIES'):self.boundary.start_once(clean_report())
        self.assertNotIn(('start',m.MAIN),self.ops.actions)
    def test_zero_snapshot_passes(self):m.require_clean_snapshot(clean_report())
    def test_bad_snapshots_never_pass(self):
        for field,value in [('postgres_major',15),('business_guards_satisfied',False),('prepared_transactions',1),('counts',{})]:
            with self.subTest(field=field):
                report=clean_report();report[field]=value
                with self.assertRaises(m.BoundaryError):m.require_clean_snapshot(report)
    def test_trigger_requires_review(self):
        report=clean_report();report['catalog']['triggers']=[{'review_required_if_guards_zero':True}]
        with self.assertRaisesRegex(m.BoundaryError,'TRIGGER'):m.require_clean_snapshot(report)
    def test_only_exact_reviewed_trigger_fingerprint_is_accepted(self):
        report=clean_report()
        trigger={'table':'users','name':'supplier_team_epoch_change','enabled':'O',
                 'definition_sha256':'9d0453060a7d107addbde23cffe202a164dfa0b7296d103adb75557960dad9b2',
                 'review_required_if_guards_zero':True}
        report['catalog']['triggers']=[trigger]
        m.require_clean_snapshot(report)
        for field in ('table','name','enabled','definition_sha256'):
            with self.subTest(field=field):
                changed=copy.deepcopy(report);changed['catalog']['triggers'][0][field]='changed'
                with self.assertRaisesRegex(m.BoundaryError,'TRIGGER'):m.require_clean_snapshot(changed)
        report['counts']['0']=1
        with self.assertRaises(m.BoundaryError):m.require_clean_snapshot(report)
    def test_missing_cgroup_evidence_is_rejected(self):
        self.freeze();del self.ops.units[m.WORKER]['cgroup_empty']
        with self.assertRaisesRegex(m.BoundaryError,'CGROUP'):self.boundary.assert_frozen()
    def test_sequence_rewind_requires_review(self):
        report=clean_report();report['bookkeeping']['explicit_setval'][0]['setval_logical_noop']=False
        with self.assertRaisesRegex(m.BoundaryError,'SEQUENCE'):m.require_clean_snapshot(report)
    def test_external_client_refuses_startup(self):
        report=clean_report();report['other_db_sessions']=[{'backend_type':'client backend','count':1}]
        with self.assertRaisesRegex(m.BoundaryError,'CLIENTS'):m.require_clean_snapshot(report)
    def test_only_active_units_are_stopped_and_enabled_states_preserved(self):
        self.freeze()
        self.assertEqual(self.ops.actions,[('stop',m.TIMERS[0]),('stop',m.INGRESS),('stop',m.WORKER),('stop',m.MAIN)])
        self.assertEqual(self.ops.units[m.TIMERS[1]]['enabled'],'disabled')
    def test_restore_preserves_disabled_timers_and_never_replays_backups(self):
        self.freeze();self.boundary.start_once(clean_report());self.boundary.restore()
        self.assertNotIn(('start',m.TIMERS[1]),self.ops.actions)
        self.assertFalse(any(action=='start' and unit in m.SERVICES for action,unit in self.ops.actions))
        self.assertEqual(self.ops.units[m.WORKER]['active'],'active')
    def test_running_backup_is_drained_naturally_never_stopped(self):
        unit=m.SERVICES[3];self.ops.units[unit]['active']='active'
        def finish(_):self.ops.units[unit].update(active='inactive',cgroup_empty=True)
        self.boundary.pause=finish
        self.freeze();self.assertNotIn(('stop',unit),self.ops.actions)
    def test_failed_backup_drain_never_kills_or_replays_it(self):
        unit=m.SERVICES[3];self.ops.units[unit]['active']='active'
        values=iter([0,9999]);self.boundary.clock=lambda:next(values)
        with self.assertRaisesRegex(m.BoundaryError,'TIMEOUT'):self.freeze()
        self.assertNotIn(('stop',unit),self.ops.actions)
        self.assertNotIn(('start',unit),self.ops.actions)
    def test_no_second_startup(self):
        self.freeze();self.boundary.start_once(clean_report())
        with self.assertRaises(m.BoundaryError):self.boundary.start_once(clean_report())
        self.assertEqual(self.ops.actions.count(('start',m.MAIN)),1)
    def test_failed_startup_does_not_reopen_ingress_or_retry(self):
        self.freeze();self.ops.fail_health=True
        with self.assertRaisesRegex(m.BoundaryError,'BUSINESS_CHANGED'):self.boundary.start_once(clean_report())
        with self.assertRaisesRegex(m.BoundaryError,'NO_VERIFIED_STARTUP'):self.boundary.restore()
        self.assertEqual(self.ops.units[m.INGRESS]['active'],'inactive')
        self.assertEqual(self.ops.actions.count(('start',m.MAIN)),1)
    def test_reactivation_or_enablement_drift_is_rejected(self):
        self.freeze();self.ops.units[m.TIMERS[1]]['enabled']='enabled'
        with self.assertRaisesRegex(m.BoundaryError,'ENABLEMENT'):self.boundary.assert_frozen()
    def test_queued_starts_are_not_ignored(self):
        self.freeze();self.ops.jobs=['unexpected']
        with self.assertRaisesRegex(m.BoundaryError,'QUEUED'):self.boundary.assert_frozen()
    def test_inventory_change_stops_before_any_service_action(self):
        self.ops.inventory_ok=False
        with self.assertRaisesRegex(m.BoundaryError,'INVENTORY'):self.boundary.capture()
        self.assertEqual(self.ops.actions,[])
    def test_configuration_change_after_drain_prevents_start(self):
        self.freeze();self.ops.inventory_ok=False
        with self.assertRaisesRegex(m.BoundaryError,'CONFIGURATION'):self.boundary.start_once(clean_report())
        self.assertNotIn(('start',m.MAIN),self.ops.actions)
    def test_cgroup_is_checked_after_stop(self):
        self.freeze();self.ops.units[m.WORKER]['cgroup_empty']=False
        with self.assertRaisesRegex(m.BoundaryError,'CGROUP'):self.boundary.assert_frozen()
    def test_original_state_is_saved_before_service_actions(self):
        def fail(phase,state):raise RuntimeError('disk unavailable')
        self.boundary.save=fail
        with self.assertRaises(RuntimeError):self.boundary.capture()
        self.assertEqual(self.ops.actions,[])

if __name__=='__main__':unittest.main(verbosity=2)
