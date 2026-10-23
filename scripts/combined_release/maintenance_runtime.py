"""Native systemd binding. Only installer --apply may call mutating methods."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time

import maintenance as m
from production import ROOT, SERVICE, Stop, need, sha, run, atomic_json

# Reviewed metadata only; no environment, commands, customer rows or credentials.
APPROVED_UNIT_FILES = {'nginx.service': {'/usr/lib/systemd/system/nginx.service': '6c759c229d4dacf65c1f98c1733646f8b979d3e75e13a98bfbcfe26f8a2f793c'}, 'postgresql.service': {'/usr/lib/systemd/system/postgresql.service': '3670a6eba171d9402075bb0a56a0a52cf2f5be652b43486db744defa7cdb0be3'}, 'postgresql@16-main.service': {'/usr/lib/systemd/system/postgresql@.service': '4c44931bba34e0754b7c0762852a5c1b615a1e307df9c458d231232d55e4c907'}, 'stroyka-agent-job-worker.service': {'/etc/systemd/system/stroyka-agent-job-worker.service': '06839311cfa110833dc49aa01bbcf3fcf60a3ef131fcfe1df34d8976897cf4e0'}, 'stroyka-deploy-backup.service': {'/etc/systemd/system/stroyka-deploy-backup.service': '8fcfc832acb4701bce602e89e4aea882084ed1199c75f653a28c0bb88929dec5'}, 'stroyka-deploy-backup.timer': {'/etc/systemd/system/stroyka-deploy-backup.timer': '0412de4f5ea9b4881dc6865d695f560e90dd94e14b8108b0077fb37824cb276f'}, 'stroyka-director-daily-brief.service': {'/etc/systemd/system/stroyka-director-daily-brief.service': 'c53a06e1e4eb82701b9713261ebaf12c951af3589980ce0c3710f0271f8c4e7c'}, 'stroyka-director-daily-brief.timer': {'/etc/systemd/system/stroyka-director-daily-brief.timer': '251e1947ec683287c2d082ce6b1877041f464245c1f86654038d51228d7acc8f'}, 'stroyka-documents-backup.service': {'/etc/systemd/system/stroyka-documents-backup.service': 'f395eab04ea1cc28f338bf2fe03c4a55030465faf5767db67c92fe9155b9c1fa'}, 'stroyka-documents-backup.timer': {'/etc/systemd/system/stroyka-documents-backup.timer': '2a2e0e6a6722dcf26a000323ae9564beaf4876d0a32c66e6abc4b7d95f453fa3'}, 'stroyka-hidden-works-local-model.service': {'/etc/systemd/system/stroyka-hidden-works-local-model.service': '3a468da8f2cfcfc281491a164d7511e849bed01cd35da31ae42e4216c42f251e'}, 'stroyka-max-dispatch.service': {'/etc/systemd/system/stroyka-max-dispatch.service': 'cb08067ee2998980a2571a5abe4bcee5f0900e2461e24ba7893a4cc35378d25c'}, 'stroyka-max-dispatch.timer': {'/etc/systemd/system/stroyka-max-dispatch.timer': '1cdeccfde7702e32716764ee2d5caac8160a320c349655738adee39179486629'}, 'stroyka-release-cleanup.service': {'/etc/systemd/system/stroyka-release-cleanup.service': '1a2718dbc566921730df1b94849c6deef266c1d770c14e9878c03f6a472cf153'}, 'stroyka-release-cleanup.timer': {'/etc/systemd/system/stroyka-release-cleanup.timer': '0100a17ae3d11258650986f1ebc363c5333b5be79eb3d9ab682ef5be5984f1fc'}, 'stroyka-supplier-email.service': {'/etc/systemd/system/stroyka-supplier-email.service': 'f09689ca06706cb5b4bcb44cfb3e77b9ca9338005cb43148c487233271ab0ff1'}, 'stroyka-supplier-email.timer': {'/etc/systemd/system/stroyka-supplier-email.timer': '813ef762acbebb5b85f70c72cf266b5c0d9df23d56deaf950df90aa7119ac491'}, 'stroyka.service': {'/etc/systemd/system/stroyka.service': '49be8f2dfe9ef9f60e6e797e4254290efc4b8ff6441f685f907405108bea00ab', '/etc/systemd/system/stroyka.service.d/10-csrf.conf': '678d863179f40e2d0ed5d79c675250a9dfdfd6c360f04e0ecd91b04dbb3c5d95', '/etc/systemd/system/stroyka.service.d/20-jev-opportunity.conf': '0826f0f3f8b91303ec36c97dcc17d7b3c7620be64d454edda89cc9ecece8ede1', '/etc/systemd/system/stroyka.service.d/20-public-site-uploads.conf': 'b7434f3e2ddcb75549bebe5a0f86bbb1d9d6a6348e925e7f09ad72ca02322782', '/etc/systemd/system/stroyka.service.d/30-python-package.conf': '5ff4ca10aff425bd3a4e9769a3028514b9a0d43b98d3b036dfb070b12ab217f8', '/etc/systemd/system/stroyka.service.d/40-backend-loopback.conf': '693900140af255f302346572ecdb18b8906d4eb072696efcbb4188c270ef2870', '/etc/systemd/system/stroyka.service.d/50-warehouse-anomaly-preview-canary.conf': 'fd3f4945df7eff6f1980f26263691f4852c882d903cfd8d0ad3b2775d2205852', '/etc/systemd/system/stroyka.service.d/70-accounting-exception-checks-canary.conf': 'c41d22896caeebb7870db5a09567b8fa95dc94cda9c9a01fff6051e1863925b0', '/etc/systemd/system/stroyka.service.d/80-assignment-daily-draft-canary.conf': '374e691c89500e82c4f18333e2ef5e0755fbeef182a809878e72f7715390b38d', '/etc/systemd/system/stroyka.service.d/90-hidden-works-local-model-canary.conf': 'f1d37b8c45dd40dc80b42aff8437f34f4542beeeade4dd6d9cbb3e617636414a', '/etc/systemd/system/stroyka.service.d/95-platform-client-card-model-gateway-canary.conf': '95f3ecf491545cc5d5be4ca02e111deceb85858f47ab7730688380bddab201a7', '/etc/systemd/system/stroyka.service.d/95-s3-private-uploads.conf': '07bcc6910f0db95acbb9074730910922ed9bd6ffe36c16c687a7e377b7d7cafd', '/etc/systemd/system/stroyka.service.d/96-supply-technical-comparison.conf': '6ff85a5bee55acf7db1b035f8ddc4a01829a317e56c2c9bc242074048667624a', '/etc/systemd/system/stroyka.service.d/99-participant-connections.conf': '43812e90bb7c46072ddd9a497e65ca40d89430be0dc17e2750e6d90a2f868e6f', '/etc/systemd/system/stroyka.service.d/99-participant-history-merge.conf': '92021d78bd776da9972497c7f4d7cbb6414b1dbd7afbb1d3015972df4ef32dfc', '/etc/systemd/system/stroyka.service.d/99-participant-support.conf': 'ed003ee859d4b6c42dd0bbb9fa2d1ef77ca42ac004a2ea06be9d57764698fcc7'}}
APPROVED_CRON = {
    '/var/spool/cron/crontabs/root':'f46b8a2f67410b8ec3e827bd47e1c49b67f9ca725d2379faac04b2d09e28beef',
    '/root/backup-stroyka.sh':'a282cb30cdb753b880e019b828238566c8bdbdd14cf47ea7ce71cc0d27f85318',
    '/root/stroyka-ai-control-nightly.sh':'05d08a5e3ad21ffafd615fa1d3ca875d0430dc9aa1d39963547ef3ed7f3c2d05',
}
RETRY_DROPIN = Path('/run/systemd/system/stroyka.service.d/zzzz-combined-release-single-start.conf')
RETRY_BYTES = b'[Service]\nRestart=no\n'

class Operations:
    def __init__(self, production, baseline):
        self.production=production;self.baseline=baseline;self.retry_owned=False
        spec=importlib.util.spec_from_file_location('_combined_probe',production.package/'server-readonly-check.py')
        self.probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.probe)
        self.groups={u:self.probe.unit_report(u).get('ControlGroup','') for u in m.UNITS}
    def state(self,unit):
        data=self.probe.unit_report(unit)
        groups={self.groups.get(unit,''),data.get('ControlGroup','')}-{''}
        empty=data.get('CGroupProcessCount')==0
        for group in groups:
            need(group.startswith('/') and '..' not in Path(group).parts,'UNSAFE_CGROUP_PATH')
            directory=Path('/sys/fs/cgroup')/group.lstrip('/')
            empty=empty and not any(p.read_text().split() for p in directory.rglob('cgroup.procs'))
        return {'active':data.get('ActiveState'),'enabled':data.get('UnitFileState'),
                'cgroup_empty':empty,'result':data.get('Result','success')}
    def verify_configuration(self):
        for unit,expected in APPROVED_UNIT_FILES.items():
            actual=self.probe.unit_report(unit)
            expected=dict(expected)
            if unit==m.MAIN and self.retry_owned:
                need(RETRY_DROPIN.read_bytes()==RETRY_BYTES,'OWN_RETRY_POLICY_CHANGED')
                expected[str(RETRY_DROPIN)]=hashlib.sha256(RETRY_BYTES).hexdigest()
            need(actual.get('UnitFileSHA256')==expected,'SERVICE_CONFIGURATION_CHANGED')
        for path,expected in APPROVED_CRON.items():
            need(not Path(path).is_symlink() and sha(path)==expected,'CRON_OR_SCRIPT_CHANGED')
    def verify_inventory(self,state):
        self.verify_configuration()
        cron=self.probe.unit_report(m.CRON)
        need(cron.get('KillMode')=='process','CRON_SHUTDOWN_POLICY_CHANGED')
        for path,expected in APPROVED_CRON.items():
            p=Path(path)
            need(not p.is_symlink() and sha(p)==expected,'CRON_OR_SCRIPT_CHANGED')
        rows=self.probe.systemd_rows('units')
        approved=set(APPROVED_UNIT_FILES)-{'nginx.service','postgresql.service','postgresql@16-main.service'}
        need({x['unit'] for x in rows}==approved,'STROYKA_UNIT_SET_CHANGED')
        need(not self.probe.systemd_rows('jobs'),'QUEUED_SYSTEMD_JOBS')
        listeners=self.probe.listeners(self.baseline['service']['pid'])
        need(bool(listeners) and all(x['loopback_only'] and x['port']==8001 for x in listeners),'BACKEND_LISTENER_CHANGED')
        routing=self.probe.routing_facts(self.probe.output(['nginx','-T']))
        need(bool(routing) and all(not x['dynamic_proxy_targets'] and all(
            target['host']=='127.0.0.1' and target['port']==8001 and target['scheme']=='http'
            for target in x['proxy_targets']) for x in routing),'NGINX_ROUTING_CHANGED')
        units={u:self.probe.unit_report(u) for u in APPROVED_UNIT_FILES}
        need(not self.probe.launch_inventory(units)['unclassified_processes'],'UNCLASSIFIED_APP_PROCESSES')
    def stop(self,unit):
        need(unit in m.UNITS,'UNAPPROVED_UNIT')
        # systemctl stop with KillMode=process leaves cron children to drain.
        run(['systemctl','stop',unit],timeout=700)
    def start(self,unit):
        need(unit in m.UNITS and unit not in m.SERVICES,'UNAPPROVED_SERVICE_REPLAY')
        run(['systemctl','start',unit],timeout=120)
    def queued_starts(self,units):
        return [j for j in self.probe.systemd_rows('jobs') if j['unit'] in units and j['type'] in ('start','restart','reload-or-start')]
    def verify_ingress_excluded(self):
        nginx=self.state(m.INGRESS)
        need(nginx['active']=='inactive' and nginx['cgroup_empty'],'NGINX_NOT_DRAINED')
        # No other command using the app, SQL client, dump or known cron script.
        known={u:self.probe.unit_report(u) for u in APPROVED_UNIT_FILES}
        extras=self.probe.launch_inventory(known)['unclassified_processes']
        need(not extras,'UNCLASSIFIED_APP_PROCESSES')
        for process in Path('/proc').iterdir():
            if not process.name.isdigit() or int(process.name)==os.getpid():continue
            try:command=(process/'cmdline').read_bytes()
            except (FileNotFoundError,ProcessLookupError):continue
            need(not any(path.encode() in command for path in APPROVED_CRON if path.endswith('.sh')),
                 'CRON_JOB_STILL_RUNNING')
    def hold_for_recovery(self):
        # This also handles a failure after ingress/timers were restored.
        for unit in (m.CRON,*m.TIMERS,m.INGRESS,m.WORKER,m.MAIN):
            state=self.state(unit)
            if state['active']=='active':self.stop(unit)
            deadline=time.monotonic()+2700
            while not self.state(unit)['cgroup_empty']:
                need(time.monotonic()<deadline,'RECOVERY_WRITER_DRAIN_TIMEOUT')
                time.sleep(1)
        for unit in m.SERVICES:
            deadline=time.monotonic()+2700
            while self.state(unit)['active']=='active' or not self.state(unit)['cgroup_empty']:
                need(time.monotonic()<deadline,'RECOVERY_JOB_DRAIN_TIMEOUT')
                time.sleep(1)
        self.verify_ingress_excluded()

    def require_single_start_policy(self):
        need(not self.retry_owned and not RETRY_DROPIN.exists(),'RETRY_POLICY_ALREADY_PRESENT')
        parent=RETRY_DROPIN.parent
        need(not parent.is_symlink() and parent.parent.resolve()==parent.parent,'UNSAFE_RUNTIME_UNIT_DIRECTORY')
        parent.mkdir(mode=0o755,exist_ok=True)
        need(parent.resolve()==parent,'UNSAFE_RUNTIME_UNIT_DIRECTORY')
        fd=os.open(RETRY_DROPIN,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o644)
        try:
            need(os.write(fd,RETRY_BYTES)==len(RETRY_BYTES),'RETRY_POLICY_WRITE_FAILED');os.fsync(fd)
        finally:os.close(fd)
        self.retry_owned=True
        run(['systemctl','daemon-reload'])
        need(run(['systemctl','show',SERVICE,'-p','Restart','--value'])=='no','AUTOMATIC_STARTUP_RETRIES_NOT_EXCLUDED')
    def restore_retry_policy(self):
        need(self.retry_owned and RETRY_DROPIN.read_bytes()==RETRY_BYTES,'OWN_RETRY_POLICY_CHANGED')
        RETRY_DROPIN.unlink();run(['systemctl','daemon-reload'])
        need(run(['systemctl','show',SERVICE,'-p','Restart','--value'])=='always','ORIGINAL_RESTART_POLICY_NOT_RESTORED')
        self.retry_owned=False
    def verify_health_and_business(self):
        deadline=time.monotonic()+75
        while True:
            try:
                service=self.production.service()
                need(service['python']==self.baseline['service']['python'],'SERVICE_INTERPRETER_CHANGED')
                need((service['pid'],service['started'])!=(self.baseline['service']['pid'],self.baseline['service']['started']),
                     'SERVICE_DID_NOT_START_NEW_PROCESS')
                need(self.production.health(service)==self.baseline['version'],'RUNTIME_VERSION_CHANGED')
                self.production.assert_preserved(self.baseline)
                m.require_clean_snapshot(self.production.startup_snapshot())
                return
            except Exception:
                if time.monotonic()>=deadline:raise
                time.sleep(1)

class Session:
    def __init__(self, production, baseline, save):
        self.operations=Operations(production,baseline)
        self.boundary=m.Boundary(self.operations,save)
    def preview(self):self.operations.verify_inventory(None)
    def freeze(self):self.boundary.capture();self.boundary.freeze()
    def start(self,snapshot):self.boundary.start_once(snapshot)
    def restore(self):
        self.boundary.restore()
        self.operations.restore_retry_policy()
