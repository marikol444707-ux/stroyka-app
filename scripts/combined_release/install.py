#!/usr/bin/env python3
"""Exact-baseline release installer. Default is read-only preflight.

No installation can pass without a real successful exact-tree GitHub CI run.
No migrations, git reset/checkout, credentials, DB restore or broad cleanup.
"""
import sys
sys.dont_write_bytecode = True
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile

from ci_gate import verify_ci, CIGateError
from maintenance import BoundaryError
from durable_files import Transaction, Stop as FileStop
from production import (Production, Stop, need, sha, digest, relative_path,
                        private_directory, atomic_json, verify_backups, ROOT)

SOURCE_TREE='3f32f08e3a287953e12777b2b55360d653c5a937'
CI_TREE='3f32f08e3a287953e12777b2b55360d653c5a937'


def package_manifest(package):
    package=Path(package)
    private_directory(package)
    manifest=json.loads((package/'manifest.json').read_text())
    need(manifest['source_tree']==SOURCE_TREE and manifest['ci_tree']==CI_TREE,'WRONG_PACKAGE_LINEAGE')
    for name, expected in manifest['package_files'].items():
        need(sha(relative_path(package,name))==expected,'PACKAGE_INTEGRITY_FAILED')
    required={'install.py','production.py','durable_files.py','ci_gate.py'}
    need(required <= set(manifest['package_files']),'INCOMPLETE_PACKAGE_MANIFEST')
    for name, entry in manifest['source'].items():
        path='payload/source/'+name
        need(manifest['package_files'].get(path)==entry['after_sha256'],'SOURCE_PAYLOAD_NOT_PINNED')
        if name.endswith('.py'):
            compile(relative_path(package,path).read_bytes(),name,'exec')
    for name in manifest['frontend_delta']:
        need(manifest['package_files'].get('payload/frontend/'+name)==manifest['frontend_files'][name],'FRONTEND_PAYLOAD_NOT_PINNED')
    return manifest


@contextmanager
def deployment_lock():
    path=Path('/var/lock/stroyka-deploy.lock')
    need(not path.is_symlink() and path.parent.resolve()==path.parent,'UNSAFE_DEPLOYMENT_LOCK')
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode),'UNSAFE_DEPLOYMENT_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


class Installer:
    def __init__(self, package, manifest, ops=None, ci_check=verify_ci, transaction=Transaction):
        self.package=Path(package); self.manifest=manifest
        self.ops=ops or Production(package,manifest)
        self.ci_check=ci_check; self.transaction=transaction
        self.evidence=None; self.state=None; self.stage='START'

    def save(self, phase):
        self.stage=phase; self.state['phase']=phase
        atomic_json(self.evidence/'release.json',self.state)

    def preflight(self):
        self.stage='READ_ONLY_PREFLIGHT'
        return self.ops.preflight()

    def payload(self, manifest, frontend=False):
        result={}
        for name in manifest:
            relative=name[len('build/'):] if frontend else name
            result[name]=self.package/'payload'/('frontend' if frontend else 'source')/relative
        return result

    def apply(self, run_id, *, evidence_parent=Path('/root')):
        # There is no allow-tests-passed flag and no trust in a hand-written receipt.
        self.stage='VERIFY_LIVE_EXACT_TREE_CI'
        need(run_id is not None,'REAL_CI_RUN_ID_REQUIRED')
        ci=self.ci_check(run_id)
        safety_ci=self.ops.verify_installer_ci()
        self.stage='FRESH_PRODUCTION_PREFLIGHT'
        baseline=self.ops.preflight()
        self.ops.prepare_maintenance(baseline)
        self.stage='VERIFY_EXISTING_STARTUP_REPAIR_NOOP'
        self.ops.require_startup_ready(baseline)
        frontend=self.ops.frontend_plan()
        self.evidence=Path(tempfile.mkdtemp(prefix='stroyka-combined-release-',dir=evidence_parent))
        os.chmod(self.evidence,0o700)
        self.state=dict(format=1,source_tree=SOURCE_TREE,ci_tree=CI_TREE,ci=ci,
                        package_manifest_sha256=sha(self.package/'manifest.json'),
                        baseline=baseline,installer_ci=safety_ci,frontend_manifest=frontend,restart_attempted=False,
                        source_started=False,frontend_started=False)
        self.save('CREATED_PRIVATE_EVIDENCE')
        print('EVIDENCE='+str(self.evidence),flush=True)
        source=front=None;lock=None
        def maintenance_save(phase, states):
            self.state['original_service_states']=states
            self.save(phase)
        try:
            self.save('ENTER_APPROVED_MAINTENANCE')
            self.ops.begin_maintenance(maintenance_save)
            candidate_lock=self.ops.deployment_lock();candidate_lock.__enter__();lock=candidate_lock
            for name in ('source-transaction','frontend-transaction'):
                (self.evidence/name).mkdir(mode=0o700)
            self.save('PREPARE_DURABLE_SOURCE_BACKUP')
            source=self.transaction(self.ops.root,self.evidence/'source-transaction',self.manifest['source'])
            source.prepare()
            self.save('PREPARE_DURABLE_FRONTEND_BACKUP')
            front=self.transaction(self.ops.root,self.evidence/'frontend-transaction',frontend)
            front.prepare()
            self.save('FRESH_DATABASE_CODE_FRONTEND_UPLOADS_BACKUP')
            self.ops.backup(self.evidence,baseline)
            verify_backups(self.evidence)
            self.ops.assert_preserved(baseline)
            self.save('BACKUP_INTEGRITY_VERIFIED_NOT_RESTORE_TESTED')
            # Re-read online CI to refuse rerun/invalidation races before mutations.
            latest_ci=self.ci_check(run_id)
            need({k:v for k,v in latest_ci.items() if k!='verified_at'}=={k:v for k,v in ci.items() if k!='verified_at'},'CI_EVIDENCE_CHANGED_DURING_BACKUP')
            latest_safety_ci=self.ops.verify_installer_ci()
            need({k:v for k,v in latest_safety_ci.items() if k!='verified_at'}=={k:v for k,v in safety_ci.items() if k!='verified_at'},'INSTALLER_CI_CHANGED_DURING_BACKUP')
            self.state['source_started']=True;self.save('APPLY_SOURCE')
            source.apply(self.payload(self.manifest['source']))
            source.verify_after()
            self.ops.assert_preserved(baseline)
            self.state['restart_attempted']=True;self.save('RESTART_BACKEND_EXISTING_INIT_DB_EFFECTS')
            service=self.ops.start_in_maintenance(baseline)
            self.ops.assert_preserved(baseline)
            self.state['new_service']=service;self.save('BACKEND_AND_SECURITY_VERIFIED')
            self.state['frontend_started']=True;self.save('PUBLISH_FRONTEND_INDEX_LAST')
            order=sorted(n for n in frontend if n not in ('build/index.html','build/asset-manifest.json'))
            order += [n for n in ('build/asset-manifest.json','build/index.html') if n in frontend]
            front.apply(self.payload(frontend,frontend=True),order=order)
            front.verify_after(); source.verify_after()
            self.ops.verify_frontend(local_only=True);self.ops.assert_preserved(baseline)
            self.save('RESTORE_PREVIOUS_SERVICE_STATES')
            self.ops.finish_maintenance()
            self.ops.verify_frontend();self.ops.verify_live_after_open(baseline)
            self.save('INSTALLED_HTTP_VERIFIED_BUSINESS_ACCEPTANCE_PENDING')
            return self.evidence
        except BaseException:
            failure=self.stage
            self.state['failure_stage']=failure
            # Closing writers must precede a journal write which could fail on a
            # full disk. Never leave ingress open because diagnostics cannot save.
            if self.state['restart_attempted']:
                self.ops.stop_for_code_recovery()
            self.save('INSTALL_STOP')
            if self.state['source_started']:
                try:
                    # DB/schema/security ambiguity forbids automatic restart or DB rollback.
                    self.rollback_loaded(source,front)
                except BaseException:
                    self.save('MANUAL_REVIEW_REQUIRED_NO_FURTHER_CHANGES')
            raise
        finally:
            if lock is not None:lock.__exit__(None,None,None)

    def rollback_loaded(self, source, front):
        baseline=self.state['baseline']
        verify_backups(self.evidence)
        # Load performs all-path validation in BOTH transactions before either rollback.
        source=self.transaction.load(self.ops.root,self.evidence/'source-transaction')
        front=self.transaction.load(self.ops.root,self.evidence/'frontend-transaction')
        self.ops.owned_temps={action['temp'] for txn in (source,front) for entry in txn.state['entries'].values() for key in ('apply','rollback') if (action:=entry.get(key)) and action.get('temp')}
        if self.state['restart_attempted']:
            self.ops.stop_for_code_recovery()
        self.ops.assert_preserved(baseline)
        self.save('ROLLBACK_ONLY_OWN_CODE_AND_FRONTEND')
        front.rollback();source.rollback()
        self.ops.verify_rollback(baseline)
        self.save('OWN_FILES_RESTORED_APP_STOPPED_MANUAL_START_REQUIRED' if self.state['restart_attempted']
                  else 'OWN_FILES_RESTORED_DATABASE_NOT_RESTORED')

    def recover(self, evidence):
        self.stage='VALIDATE_PRIVATE_RECOVERY_EVIDENCE'
        b=private_directory(evidence)
        need(b.parent==Path('/root') and b.name.startswith('stroyka-combined-release-'),'WRONG_RECOVERY_LOCATION')
        state=json.loads((b/'release.json').read_text())
        need(state.get('format')==1 and state.get('source_tree')==SOURCE_TREE and state.get('ci_tree')==CI_TREE,'WRONG_RECOVERY_LINEAGE')
        need(state.get('package_manifest_sha256')==sha(self.package/'manifest.json'),'RECOVERY_PACKAGE_CHANGED')
        self.evidence=b;self.state=state
        self.ops.load_helpers()
        self.ops.prepare_recovery(state['baseline'])
        self.rollback_loaded(None,None)
        return b


def service_python(ops, recovery):
    service=ops.service(require_active=not recovery)
    if service:
        return service['python']
    b=private_directory(recovery)
    need(b.parent==Path('/root') and b.name.startswith('stroyka-combined-release-'),'WRONG_RECOVERY_LOCATION')
    state=json.loads((b/'release.json').read_text())
    path=Path(state['baseline']['service']['python'])
    need(path.is_absolute() and path.is_file() and path.resolve()==Path('/usr/bin/python3.12').resolve(),'RECOVERY_INTERPRETER_UNVERIFIED')
    return str(path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--preflight',action='store_true')
    actions.add_argument('--apply',action='store_true')
    actions.add_argument('--rollback',type=Path)
    parser.add_argument('--ci-run-id',type=int)
    args=parser.parse_args(argv)
    package=Path(__file__).absolute().parent
    installer=None;stage='PACKAGE_AND_TARGET'
    try:
        manifest=package_manifest(package)
        ops=Production(package,manifest);ops.require_target()
        executable=service_python(ops,args.rollback)
        if Path(sys.executable).absolute()!=Path(executable).absolute():
            os.execv(executable,[executable,'-E','-B',str(Path(__file__).absolute()),*sys.argv[1:]])
        installer=Installer(package,manifest,ops)
        if not args.apply and not args.rollback:
            installer.preflight()
            print('BASELINE_PREFLIGHT_OK; NO_BACKUP_OR_LOCK_CREATED; NO_FILES_OR_DATABASE_WRITTEN; APPLY_BLOCKED_REAL_CI_AND_STARTUP_REPAIR_NOOP_REQUIRED')
            return 0
        os.umask(0o077)
        # Missing run ID is denied before even creating the coordination lock.
        if args.apply: need(args.ci_run_id is not None,'REAL_CI_RUN_ID_REQUIRED')
        if args.rollback:
            with deployment_lock():evidence=installer.recover(args.rollback)
        else:evidence=installer.apply(args.ci_run_id)
        print(('ROLLBACK_OK' if args.rollback else 'INSTALL_OK_BUSINESS_ACCEPTANCE_PENDING')+'; EVIDENCE='+str(evidence))
        return 0
    except BaseException as error:
        stage=(installer.state or {}).get('failure_stage',installer.stage) if installer else stage
        code=str(error) if isinstance(error,(Stop,CIGateError,FileStop,BoundaryError)) else type(error).__name__
        print('STOP_STAGE='+stage+'; CODE='+code+'; NO_AUTOMATIC_DATABASE_RESTORE')
        return 1

if __name__=='__main__':
    raise SystemExit(main())
