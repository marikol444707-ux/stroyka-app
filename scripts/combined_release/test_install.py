"""Fixture-only orchestration tests. No systemctl, PostgreSQL, GitHub or production calls."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install
import production
from durable_files import Transaction


def h(body): return hashlib.sha256(body).hexdigest()


class FakeProduction:
    def __init__(self, root, manifest):
        self.root=root;self.manifest=manifest;self.events=[];self.owned_temps=set()
        self.security='unchanged';self.restarts=0;self.fail_restart=False;self.foreign=False
        self.startup_allowed=True;self.bad_backup=False
    def require_target(self): self.events.append('target')
    def load_helpers(self): self.events.append('helpers')
    def inventory(self):
        excluded=set(self.manifest['source']) | self.owned_temps
        return {str(p.relative_to(self.root)):[production.sha(p),p.stat().st_mode]
                for p in self.root.rglob('*') if p.is_file()
                and not str(p.relative_to(self.root)).startswith('build/')
                and str(p.relative_to(self.root)) not in excluded}
    def preflight(self):
        self.events.append('preflight')
        return {'untouched':self.inventory(),'security':self.security,'service':{'python':'fixture'}}
    def verify_installer_ci(self):return {'fixture':'safety_ci'}
    def prepare_maintenance(self, baseline):self.events.append('prepare_maintenance')
    def begin_maintenance(self, save):
        self.events.append('freeze');save('FIXTURE_WRITERS_DRAINED',{})
    def deployment_lock(self):return contextlib.nullcontext()
    def start_in_maintenance(self, baseline):return self.restart(baseline)
    def finish_maintenance(self):self.events.append('restore_states')
    def require_startup_ready(self, baseline):
        self.events.append('startup_gate')
        if not self.startup_allowed:raise production.Stop('STARTUP_CLOSED')
    def frontend_plan(self):
        return {'build/'+n:{'before_sha256':self.manifest['frontend_before'].get(n),
                           'after_sha256':v} for n,v in self.manifest['frontend_files'].items()}
    def assert_preserved(self, baseline, **kwargs):
        production.need(self.inventory()==baseline['untouched'],'UNTOUCHED_CHANGED')
        production.need(self.security==baseline['security'],'SECURITY_CHANGED')
    def backup(self, b, baseline):
        self.events.append('backup')
        (b/'database-before.dump').write_bytes(b'FIXTURE_ONLY_NOT_A_DATABASE')
        hashes={str(p.relative_to(b)):production.sha(p) for p in b.rglob('*') if p.is_file()
                and p.name not in ('release.json','journal.json')}
        if self.bad_backup:hashes['database-before.dump']='0'*64
        production.fsync_backup_tree(b)
        production.atomic_json(b/'backup-hashes.json',hashes)
    def stop_for_code_recovery(self):self.events.append('stopped_for_recovery')
    def restart(self, baseline):
        self.events.append('restart');self.restarts+=1
        if self.fail_restart and self.restarts==1:raise production.Stop('FIXTURE_HEALTH_FAILURE')
        return {'fixture_process':self.restarts}
    def verify_frontend(self, local_only=False):
        self.events.append('frontend_verified')
        if self.foreign:
            (self.root/'a.py').write_bytes(b'FOREIGN EDIT')
            raise production.Stop('FIXTURE_CONCURRENT_CHANGE')
        for n,v in self.manifest['frontend_files'].items():
            production.need(production.sha(self.root/'build'/n)==v,'FRONTEND_WRONG')
    def verify_rollback(self, baseline):
        self.events.append('rollback_verified');self.assert_preserved(baseline)
        for n,e in self.manifest['source'].items():
            p=self.root/n
            production.need((production.sha(p) if p.exists() else None)==e['before_sha256'],'BAD_ROLLBACK')


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        def fixture_private(path):
            path=Path(path);st=path.stat()
            production.need(path.resolve()==path and (st.st_mode&0o777)==0o700 and st.st_uid==os.geteuid(),'FIXTURE_PRIVATE_REQUIRED')
            return path
        guard=patch('production.private_directory',side_effect=fixture_private);guard.start();self.addCleanup(guard.stop)
        self.base=Path(self.temp.name);self.root=self.base/'app';self.root.mkdir()
        self.pkg=self.base/'package';self.pkg.mkdir(mode=0o700)
        (self.root/'build/static').mkdir(parents=True)
        (self.root/'a.py').write_bytes(b'OLD=1\n');(self.root/'a.py').chmod(0o640)
        (self.root/'untouched').write_bytes(b'unchanged')
        (self.root/'build/index.html').write_bytes(b'old index')
        (self.root/'build/asset-manifest.json').write_bytes(b'old manifest')
        source={'a.py':b'NEW=2\n','new.py':b'VALUE=3\n'}
        front={'index.html':b'new index','asset-manifest.json':b'new manifest','static/new.js':b'new chunk'}
        self.manifest={'source':{n:{'before_sha256':production.sha(self.root/n) if (self.root/n).exists() else None,
                                  'after_sha256':h(v)} for n,v in source.items()},
                       'frontend_files':{n:h(v) for n,v in front.items()},
                       'frontend_before':{n:production.sha(self.root/'build'/n) for n in ('index.html','asset-manifest.json')}}
        for kind,files in [('source',source),('frontend',front)]:
            for n,b in files.items():
                p=self.pkg/'payload'/kind/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        (self.pkg/'manifest.json').write_text(json.dumps(self.manifest))
        self.ops=FakeProduction(self.root,self.manifest);self.ci_calls=0
        self.installer=install.Installer(self.pkg,self.manifest,self.ops,self.ci)
    def ci(self, run):
        self.ci_calls+=1
        return {'run_id':run,'tree':install.CI_TREE,'verified_at':str(self.ci_calls)}
    def apply(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.installer.apply(12,evidence_parent=self.base)
    def test_fixture_success_and_new_process_rollback(self):
        b=self.apply();self.assertEqual(self.ci_calls,2)
        self.assertEqual(self.installer.stage,'INSTALLED_HTTP_VERIFIED_BUSINESS_ACCEPTANCE_PENDING')
        self.assertEqual((self.root/'a.py').stat().st_mode&0o777,0o640)
        fresh=install.Installer(self.pkg,self.manifest,self.ops,self.ci)
        fresh.evidence=b;fresh.state=json.loads((b/'release.json').read_text())
        fresh.rollback_loaded(None,None)
        self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n')
        self.assertFalse((self.root/'new.py').exists());self.assertFalse((self.root/'build/static/new.js').exists())
        self.assertEqual(self.ops.restarts,1)
    def test_wildcard_backend_bindings_are_never_misreported_as_loopback(self):
        self.assertEqual(production.loopback_listener_host('tcp','0100007F'),'127.0.0.1')
        self.assertEqual(production.loopback_listener_host('tcp6','0'*24+'01000000'),'[::1]')
        for family,address in [('tcp','00000000'),('tcp6','0'*32),('tcp','0100000A')]:
            with self.subTest(family=family,address=address):
                with self.assertRaisesRegex(production.Stop,'BACKEND_LISTENER'):
                    production.loopback_listener_host(family,address)
    def test_installer_ci_binding_cannot_be_replaced_by_application_ci(self):
        real=production.Production(self.pkg,self.manifest)
        with self.assertRaisesRegex(production.Stop,'INSTALLER_CI_BINDING_REQUIRED'):
            real.verify_installer_ci()
    def test_safety_ci_invalidation_after_backup_prevents_source_changes(self):
        results=iter([{'run':'first'},{'run':'changed'}])
        self.ops.verify_installer_ci=lambda:next(results)
        with self.assertRaisesRegex(production.Stop,'INSTALLER_CI_CHANGED_DURING_BACKUP'):self.apply()
        self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n')
        self.assertEqual(self.ops.restarts,0)
    def test_missing_ci_before_any_evidence_or_backup(self):
        with self.assertRaisesRegex(production.Stop,'REAL_CI_RUN_ID_REQUIRED'):
            self.installer.apply(None,evidence_parent=self.base)
        self.assertIsNone(self.installer.evidence);self.assertEqual(self.ops.events,[])
    def test_failed_ci_before_preflight_or_evidence(self):
        self.installer.ci_check=lambda _:(_ for _ in ()).throw(production.Stop('NO_REAL_CI'))
        with self.assertRaisesRegex(production.Stop,'NO_REAL_CI'):self.apply()
        self.assertIsNone(self.installer.evidence);self.assertEqual(self.ops.events,[])
    def test_closed_startup_gate_before_backup_evidence_mutation(self):
        self.ops.startup_allowed=False
        with self.assertRaisesRegex(production.Stop,'STARTUP_CLOSED'):self.apply()
        self.assertIsNone(self.installer.evidence);self.assertNotIn('backup',self.ops.events)
        self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n')
    def test_production_startup_gate_cannot_be_satisfied_by_ci(self):
        real=production.Production(self.pkg,self.manifest)
        with self.assertRaisesRegex(production.Stop,'VERIFIED_MAINTENANCE_BINDING_REQUIRED'):
            real.require_startup_ready({'ci':{'conclusion':'success'},'startup_approved':True})
    def test_bad_backup_refuses_source_mutation(self):
        self.ops.bad_backup=True
        with self.assertRaisesRegex(production.Stop,'BACKUP_INTEGRITY_FAILED'):self.apply()
        self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n');self.assertEqual(self.ops.restarts,0)
    def test_ci_rerun_after_backup_refuses_mutation(self):
        def changed(run):
            value=self.ci(run);value['attempt']=self.ci_calls;return value
        self.installer.ci_check=changed
        with self.assertRaisesRegex(production.Stop,'CI_EVIDENCE_CHANGED'):self.apply()
        self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n');self.assertEqual(self.ops.restarts,0)
    def test_failed_health_stops_app_and_restores_own_files_without_startup_retry(self):
        self.ops.fail_restart=True
        with self.assertRaisesRegex(production.Stop,'FIXTURE_HEALTH_FAILURE'):self.apply()
        self.assertEqual(self.installer.stage,'OWN_FILES_RESTORED_APP_STOPPED_MANUAL_START_REQUIRED')
        self.assertIn('stopped_for_recovery',self.ops.events)
        self.assertEqual(self.ops.restarts,1);self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n')
    def test_concurrent_foreign_change_prevents_rollback(self):
        self.ops.foreign=True
        with self.assertRaisesRegex(production.Stop,'FIXTURE_CONCURRENT_CHANGE'):self.apply()
        self.assertEqual((self.root/'a.py').read_bytes(),b'FOREIGN EDIT')
        self.assertEqual(self.installer.stage,'MANUAL_REVIEW_REQUIRED_NO_FURTHER_CHANGES')
        self.assertEqual(self.ops.restarts,1)
    def test_journal_owned_temp_is_excluded_only_after_identity_validation(self):
        original=os.replace
        def fail_before(src,dst,**kwargs):
            if dst=='a.py' and kwargs.get('dst_dir_fd') is not None:raise OSError('fixture before rename')
            return original(src,dst,**kwargs)
        with patch('durable_files.os.replace',side_effect=fail_before):
            with self.assertRaises(OSError):self.apply()
        self.assertEqual(self.installer.stage,'OWN_FILES_RESTORED_DATABASE_NOT_RESTORED')
        self.assertFalse(list(self.root.rglob('.release-*')))
        self.assertEqual((self.root/'a.py').read_bytes(),b'OLD=1\n');self.assertEqual(self.ops.restarts,0)
    def test_read_only_preflight_never_calls_lock_ci_or_backup(self):
        with patch.object(install,'package_manifest',return_value=self.manifest),patch.object(install,'Production',return_value=self.ops),patch.object(install,'service_python',return_value=install.sys.executable),patch.object(install,'deployment_lock') as lock,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(install.main([]),0)
        lock.assert_not_called();self.assertEqual(self.ci_calls,0)
        self.assertNotIn('backup',self.ops.events);self.assertIn('APPLY_BLOCKED',output.getvalue())
    def test_backup_fsync_regular_files_and_directories(self):
        b=self.base/'private';b.mkdir(mode=0o700);(b/'nested').mkdir();(b/'nested/dump').write_bytes(b'fixture')
        original=os.fsync;seen=[]
        def record(fd):seen.append(os.fstat(fd).st_mode);return original(fd)
        with patch('production.os.fsync',side_effect=record):production.fsync_backup_tree(b)
        import stat
        self.assertEqual(sum(stat.S_ISREG(mode) for mode in seen),1)
        self.assertEqual(sum(stat.S_ISDIR(mode) for mode in seen),3)
    def test_backup_fsync_rejects_symlink(self):
        b=self.base/'private';b.mkdir(mode=0o700);(b/'foreign').symlink_to(self.root/'a.py')
        with self.assertRaisesRegex(production.Stop,'BACKUP_SYMLINK_REFUSED'):production.fsync_backup_tree(b)

if __name__=='__main__':unittest.main()
