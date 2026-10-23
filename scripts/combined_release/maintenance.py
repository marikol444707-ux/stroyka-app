"""Finite service boundary. Never invoked by the read-only evidence collector.

Production binding needs the operator's sanitized inventory before it is enabled
in install.py. State restoration never enables/disables units and never restores DB.
"""
import time

TIMERS = tuple('stroyka-'+name+'.timer' for name in (
    'max-dispatch','supplier-email','director-daily-brief',
    'deploy-backup','documents-backup','release-cleanup'))
SERVICES = tuple(name.replace('.timer','.service') for name in TIMERS)
WORKER = 'stroyka-agent-job-worker.service'
MAIN = 'stroyka.service'
INGRESS = 'nginx.service'
CRON = 'cron.service'
UNITS = (*TIMERS,*SERVICES,WORKER,MAIN,INGRESS,CRON)

class BoundaryError(RuntimeError):pass

def require(value, code):
    if not value:raise BoundaryError(code)

def require_clean_snapshot(report):
    require(report.get('postgres_major')==16,'POSTGRES16_REQUIRED')
    require(report.get('business_guards_satisfied') is True,'BUSINESS_REPAIR_CANDIDATES')
    counts=report.get('counts',{})
    require(len(counts)==31 and all(type(x) is int and x==0 for x in counts.values()),'EXACT_ZERO_GUARDS_REQUIRED')
    require(report.get('estimate_json',{}).get('would_update')==0
            and report.get('estimate_json',{}).get('startup_error')==0,'ESTIMATE_REPAIR_OR_PARSE_ERROR')
    require(report.get('prepared_transactions')==0,'PREPARED_TRANSACTIONS_PRESENT')
    require(not any(x.get('count',0) for x in report.get('other_db_sessions',[])
                    if x.get('backend_type')=='client backend'),'OTHER_DATABASE_CLIENTS_PRESENT')
    catalog=report.get('catalog',{})
    require(catalog.get('inheritance_edges')==0,'INHERITANCE_REVIEW_REQUIRED')
    require(not catalog.get('rules') and not catalog.get('event_triggers'),'RULE_OR_EVENT_TRIGGER_REVIEW_REQUIRED')
    require(not catalog.get('unclassified_seed_defaults'),'SEED_DEFAULT_REVIEW_REQUIRED')
    for trigger in catalog.get('triggers',[]):
        if trigger.get('review_required_if_guards_zero'):
            # Exact definition+function fingerprint reproduced on PG16. This is
            # BEFORE UPDATE OF active,role, whereas the only unconditional users
            # UPDATE sets two_factor_required. All guarded repair rows are zero.
            require(trigger.get('table')=='users'
                    and trigger.get('name')=='supplier_team_epoch_change'
                    and trigger.get('enabled')=='O'
                    and trigger.get('definition_sha256')=='9d0453060a7d107addbde23cffe202a164dfa0b7296d103adb75557960dad9b2',
                    'STARTUP_TRIGGER_REVIEW_REQUIRED')
    sequences=report.get('bookkeeping',{}).get('explicit_setval',[])
    require({x.get('table') for x in sequences}=={'platform_accounts','companies'} and len(sequences)==2,'SEQUENCE_METADATA_MISSING')
    require(all(x.get('setval_logical_noop') is True and x.get('increment')==1
                and x.get('cache')==1 and x.get('cycle') is False
                and x.get('target_within_bounds') is True for x in sequences),'EXPLICIT_SEQUENCE_CHANGE_REVIEW_REQUIRED')

class Boundary:
    def __init__(self, operations, save, *, monotonic=time.monotonic, pause=time.sleep):
        self.ops=operations;self.save=save;self.clock=monotonic;self.pause=pause
        self.original=None;self.started=False;self.verified=False
    def capture(self):
        state={unit:self.ops.state(unit) for unit in UNITS}
        for name,value in state.items():
            require(value['active'] in ('active','inactive','failed','not-found'),'TRANSITIONAL_UNIT_STATE')
        require(state[MAIN]['active']=='active' and state[INGRESS]['active']=='active','ACTIVE_BASELINE_REQUIRED')
        # The actual binding must compare approved ExecStart/drop-in hashes and
        # require loopback-only app listeners and no unclassified writer launchers.
        self.ops.verify_inventory(state)
        self.original=state
        self.save('CAPTURED_ORIGINAL_SERVICE_STATES',state)
        return state
    def wait_inactive(self,unit,timeout=660):
        deadline=self.clock()+timeout
        while True:
            state=self.ops.state(unit)
            if state['active'] in ('inactive','not-found') and state.get('cgroup_empty') is True:
                return
            require(state['active']!='failed','SERVICE_DRAIN_FAILED')
            require(self.clock()<deadline,'SERVICE_DRAIN_TIMEOUT')
            self.pause(1)
    def freeze(self):
        require(self.original is not None,'ORIGINAL_STATES_NOT_CAPTURED')
        self.ops.verify_inventory(self.original)
        # Production cron uses KillMode=process. Stop the scheduler first, then
        # let every existing child finish; never kill or replay cron jobs.
        if self.original[CRON]['active']=='active':
            self.ops.stop(CRON)
            self.wait_inactive(CRON,timeout=2700)
        for unit in TIMERS:
            if self.original[unit]['active']=='active':self.ops.stop(unit)
        # Backups and dispatches finish naturally. Never stop/kill these services.
        for unit in SERVICES:
            if self.ops.state(unit)['active']=='active' or self.ops.state(unit).get('cgroup_empty') is not True:
                self.wait_inactive(unit)
        for unit in (INGRESS,WORKER,MAIN):
            if self.original[unit]['active']=='active':
                self.ops.stop(unit);self.wait_inactive(unit)
                require(self.ops.state(unit).get('result','success')=='success','UNCLEAN_SERVICE_STOP')
        self.assert_frozen()
        self.save('WRITERS_DRAINED_BEFORE_DEPLOY_LOCK',self.original)
    def assert_frozen(self, *, main_started=False):
        require(self.original is not None,'ORIGINAL_STATES_NOT_CAPTURED')
        for unit in UNITS:
            current=self.ops.state(unit)
            require(current['enabled']==self.original[unit]['enabled'],'UNIT_ENABLEMENT_CHANGED')
            if unit==MAIN and main_started:
                require(current['active']=='active','MAIN_NOT_HEALTHY')
            else:
                require(current['active'] in ('inactive','failed','not-found'),'UNEXPECTED_UNIT_ACTIVATION')
                require(current.get('cgroup_empty') is True,'SERVICE_CGROUP_NOT_EMPTY')
        require(not self.ops.queued_starts(UNITS),'QUEUED_SERVICE_STARTS')
        self.ops.verify_ingress_excluded()
    def start_once(self, snapshot):
        self.assert_frozen();require_clean_snapshot(snapshot)
        require(not self.started,'REPEATED_STARTUP_REFUSED')
        # Persist intent before the only allowed startup. Failure keeps ingress closed.
        self.started=True;self.save('STARTUP_ONCE_INTENT',self.original)
        # Restart=always on production would silently repeat init_db after a
        # failed process. Binding must prove automatic retries are suppressed.
        self.ops.require_single_start_policy()
        self.ops.start(MAIN)
        self.ops.verify_health_and_business()
        self.assert_frozen(main_started=True)
        self.verified=True
        self.save('STARTUP_BUSINESS_CHECKED_INGRESS_STILL_CLOSED',self.original)
    def restore(self):
        require(self.verified,'NO_VERIFIED_STARTUP')
        self.assert_frozen(main_started=True)
        self.ops.verify_health_and_business()
        # Timer services that ran once before maintenance have completed naturally;
        # never replay them. Restore persistent worker/ingress and original timers only.
        for unit in (WORKER,INGRESS,*TIMERS,CRON):
            if self.original[unit]['active']=='active':self.ops.start(unit)
        for unit in UNITS:
            current=self.ops.state(unit)
            require(current['enabled']==self.original[unit]['enabled'],'UNIT_ENABLEMENT_NOT_RESTORED')
            if unit not in SERVICES:
                require(current['active']==self.original[unit]['active'],'UNIT_ACTIVITY_NOT_RESTORED')
        self.save('PRIOR_PERSISTENT_SERVICE_STATES_RESTORED',self.original)
