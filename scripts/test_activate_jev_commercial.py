"""Offline filesystem activation/rollback; no Docker daemon, keys or network."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import Mock,patch

from scripts import activate_jev_commercial as operator
from jev_agent.tender_finder.commercial.upgrade_review import installed_manifest
from jev_agent.tender_finder.commercial.prepare_install import review_files
from jev_agent.tender_finder.commercial.test_runtime_config import policies
from jev_agent.tender_finder.settings import parse_settings
from jev_agent.tender_finder.standalone_release import _save


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name);self.root=self.base/'root';self.stage=self.base/'stage'
        self.root.mkdir();self.stage.mkdir(mode=0o700)
        for name in ('opt/stroyka-jev/app','opt/stroyka-jev/config','etc/stroyka-jev/private',
                     'etc/systemd/system','etc/tmpfiles.d','var/lib','run/stroyka-jev'):
            (self.root/name).mkdir(mode=0o755,parents=True,exist_ok=True)
        self.path('/run/stroyka-jev').chmod(0o710)
        self.previous={operator.PLUGIN:b'"""bound plugin fixture"""\n',
            'jev_agent/tender_finder/host_service.py':b'"""old source"""\n',
            'jev_agent/__init__.py':b'pass\n'}
        self.candidate={**self.previous,'jev_agent/tender_finder/host_service.py':b'"""new source"""\n',
            'jev_agent/tender_finder/commercial/fixture_new.py':b'pass\n'}
        for name,raw in self.previous.items():self.put('/opt/stroyka-jev/app/'+name,raw)
        for name,raw in self.candidate.items():
            path=self.stage/'source'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(0o600)
        self.put('/etc/stroyka-jev/bridge.json',b'legacy owner fixture',0o600)
        self.put('/opt/stroyka-jev/config/bridge.json',b'public owner fixture',0o640)
        self.put('/etc/stroyka-jev/private/admission.key',b'PRIVATE_OLD_KEY_KEPT_WITHOUT_READ',0o600)
        self.old_units={operator.OLD[0]:b'old socket fixture',operator.OLD[1]:b'old service fixture'}
        for name,raw in self.old_units.items():self.put('/etc/systemd/system/'+name,raw)
        legacy,_=policies();prepared={k:v.encode() for k,v in review_files(parse_settings(legacy)).items()}
        self.identifier='c'*64;self.running=True;self.calls=[];self.fail_enable=False;self.hang_stop=False
        self.units={name:{'ActiveState':'active','UnitFileState':'enabled'} for name in operator.OLD}
        self.bundle={'stage':self.stage,'previous':{k:operator.sha(v) for k,v in self.previous.items()},
            'candidate':{k:operator.sha(v) for k,v in self.candidate.items()},'prepared':prepared,
            'old_units':self.old_units,'legacy_hash':operator.sha(b'legacy owner fixture'),
            'public_hash':operator.sha(b'public owner fixture'),
            'installed':installed_manifest,'save':_save,'probe':Mock(),'peer':Mock(),
            'container':Mock(side_effect=lambda:self.identifier)}
        self.activation=operator.Activation(self.bundle,_root=self.root,_uid=os.geteuid(),
            _run=self.run_command,_provision=self.provision,_sleep=lambda seconds:None)

    def path(self,name):return self.root/name.lstrip('/')
    def put(self,name,raw,mode=0o644):
        path=self.path(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);path.chmod(mode)
    def provision(self,state):
        self.path('/opt/stroyka-jev-commercial/venv').mkdir(mode=0o700)
    def run_command(self,*args,**kwargs):
        self.calls.append(args)
        if args[0]=='/usr/bin/systemctl':
            operation=args[1]
            if operation=='show':
                name=args[2];state=self.units.get(name,{'ActiveState':'inactive','UnitFileState':''})
                present=self.path('/etc/systemd/system/'+name).exists()
                return ('LoadState='+('loaded' if present else 'not-found')+'\nDropInPaths=\nTimeoutStopUSec=infinity\nKillSignal=15\n'+
                        '\n'.join(k+'='+v for k,v in state.items())).encode()
            if operation in ('stop','start','enable','disable'):
                for name in args[2:]:
                    if name=='--now':continue
                    row=self.units.setdefault(name,{'ActiveState':'inactive','UnitFileState':'disabled'})
                    if operation in ('stop','start'):row['ActiveState']='active' if operation=='start' else 'inactive'
                    if operation in ('enable','disable'):
                        row['UnitFileState']='enabled' if operation=='enable' else 'disabled'
                        if operation=='enable':row['ActiveState']='active'
                if operation=='enable' and self.fail_enable:raise ValueError('synthetic_partial_enable_failure')
                return b''
            if operation=='daemon-reload':return b''
        if args[0]=='/usr/bin/docker':
            if 'inspect' in args:
                if args[-2]=='{{json .Config.StopSignal}}':return b'"SIGTERM"'
                return json.dumps(self.running).encode()
            if 'stop' in args:
                self.assertIn('--timeout=-1',args)
                if self.hang_stop:raise ValueError('synthetic_shutdown_still_inflight')
                self.running=False;return b''
            if 'start' in args:self.running=True;return b''
        raise AssertionError(args)

    def test_activation_preserves_plugin_inode_container_old_key_and_owner(self):
        plugin=self.path('/opt/stroyka-jev/app/'+operator.PLUGIN);inode=plugin.stat().st_ino
        old_key=self.path('/etc/stroyka-jev/private/admission.key');old_bytes=old_key.read_bytes()
        original_read=operator.read_file
        def read(path,**kwargs):
            self.assertNotEqual(Path(path),old_key)
            return original_read(path,**kwargs)
        with patch.object(operator,'read_file',side_effect=read):result=self.activation.apply()
        self.assertTrue(result['activated']);self.assertFalse(result['real_telegram_acceptance'])
        self.assertFalse(result['container_recreated']);self.assertFalse(result['installation_ready'])
        self.assertEqual(plugin.stat().st_ino,inode);self.assertEqual(old_key.read_bytes(),old_bytes)
        self.assertEqual(self.path('/etc/stroyka-jev/bridge.json').read_bytes(),b'legacy owner fixture')
        new_key=self.path('/etc/stroyka-jev-commercial/private/admission.key')
        self.assertEqual(new_key.stat().st_size,32);self.assertEqual(stat.S_IMODE(new_key.stat().st_mode),0o600)
        installed_manifest(self.path('/opt/stroyka-jev/app'),self.bundle['candidate'],uid=os.geteuid(),trusted_root=self.root)
        runtime=json.loads(self.path('/etc/stroyka-jev-commercial/runtime.json').read_text())
        self.assertEqual(runtime['bridge']['company_id'],37)
        self.assertEqual(runtime['enabled_sources'],['step','federation','rtender'])
        stop_index=next(i for i,args in enumerate(self.calls) if args[:2]==('/usr/bin/systemctl','stop'))
        self.assertLess(stop_index,next(i for i,args in enumerate(self.calls) if 'stop' in args and args[0]=='/usr/bin/docker'))
        for args in self.calls:
            self.assertNotIn('kill',args);self.assertNotIn('rm',args);self.assertNotIn('create',args)

    def test_partial_activation_rollback_restores_code_retains_receipts_and_key(self):
        self.fail_enable=True
        with self.assertRaisesRegex(ValueError,'synthetic_partial_enable'):self.activation.apply()
        receipt=self.path('/var/lib/stroyka-jev-commercial/private/fixture-receipt.json')
        receipt.write_text('uncertain delivery: retain');receipt.chmod(0o600)
        key=self.path('/etc/stroyka-jev-commercial/private/admission.key');key_hash=operator.sha(key.read_bytes())
        self.fail_enable=False;result=self.activation.rollback()
        self.assertTrue(result['restored']);self.assertFalse(result['data_restored'])
        self.assertEqual(receipt.read_text(),'uncertain delivery: retain');self.assertEqual(operator.sha(key.read_bytes()),key_hash)
        installed_manifest(self.path('/opt/stroyka-jev/app'),self.bundle['previous'],uid=os.geteuid(),trusted_root=self.root)
        self.assertTrue(self.running)
        self.assertFalse(self.path('/opt/stroyka-jev/config/commercial.json').exists())
        for name in operator.OLD:self.assertEqual(self.units[name],{'ActiveState':'active','UnitFileState':'enabled'})
        self.assertTrue(self.activation.backup.exists())

    def test_foreign_source_or_policy_blocks_rollback_before_any_stop(self):
        self.activation.apply()
        for name in ('/opt/stroyka-jev/app/jev_agent/tender_finder/host_service.py','/opt/stroyka-jev/config/commercial.json'):
            path=self.path(name);original=path.read_bytes();path.write_bytes(b'manual operator change')
            calls=len(self.calls)
            with self.assertRaisesRegex(ValueError,'foreign_change'):self.activation.rollback()
            self.assertEqual(len(self.calls),calls);self.assertEqual(path.read_bytes(),b'manual operator change')
            path.write_bytes(original)

    def test_shutdown_inflight_never_overwrites_sources_or_claims_restoration(self):
        self.hang_stop=True
        with self.assertRaisesRegex(ValueError,'shutdown_still_inflight'):self.activation.apply()
        self.assertEqual(self.activation.state()['intents'],[])
        with self.assertRaisesRegex(ValueError,'shutdown_still_inflight'):self.activation.rollback()
        installed_manifest(self.path('/opt/stroyka-jev/app'),self.bundle['previous'],uid=os.geteuid(),trusted_root=self.root)
        self.assertTrue(self.running)
        self.hang_stop=False;self.assertTrue(self.activation.rollback()['restored'])

    def test_dependency_failure_never_stops_legacy_services(self):
        self.activation.provision=Mock(side_effect=ValueError('synthetic_dependency_failure'))
        with self.assertRaisesRegex(ValueError,'dependency_failure'):self.activation.apply()
        result=self.activation.rollback();self.assertTrue(result['restored'])
        self.assertFalse(any(args[:2]==('/usr/bin/systemctl','stop') for args in self.calls))
        self.assertTrue(self.running)

    def test_existing_target_is_preserved_before_provisioning(self):
        self.put('/opt/stroyka-jev/config/commercial.json',b'foreign settings',0o640)
        self.activation.provision=Mock()
        with self.assertRaisesRegex(ValueError,'existing_commercial_target'):self.activation.apply()
        self.activation.provision.assert_not_called();self.assertFalse(self.activation.journal.exists())
        self.assertEqual(self.path('/opt/stroyka-jev/config/commercial.json').read_bytes(),b'foreign settings')

    def test_repeated_rollback_verifies_old_services_without_stopping_them(self):
        self.activation.apply();self.activation.rollback();calls=len(self.calls)
        self.assertTrue(self.activation.rollback()['restored'])
        self.assertFalse(any(args[:2]==('/usr/bin/systemctl','stop') for args in self.calls[calls:]))
        self.running=False;self.bundle['container'].side_effect=ValueError('not_running')
        with self.assertRaisesRegex(ValueError,'not_running'):self.activation.rollback()

    def test_changed_backup_or_foreign_journal_path_blocks_recovery(self):
        self.activation.apply()
        state=self.activation.state();backup=next(iter(state['backups']))
        (self.activation.backup/backup).write_bytes(b'manual changed backup')
        calls=len(self.calls)
        with self.assertRaisesRegex(ValueError,'backup_changed'):self.activation.rollback()
        self.assertEqual(len(self.calls),calls)
        state['intents'].append('/etc/passwd');self.activation.save(state)
        with self.assertRaisesRegex(ValueError,'owned_activation_journal'):self.activation.rollback()

    def test_owner_change_during_provisioning_blocks_maintenance(self):
        def provision(state):self.path('/etc/stroyka-jev/bridge.json').write_bytes(b'changed owner')
        self.activation.provision=provision
        with self.assertRaisesRegex(ValueError,'existing_owner_policy_changed'):self.activation.apply()
        self.assertFalse(self.activation.state()['maintenance'])
        self.assertFalse(any(args[:2]==('/usr/bin/systemctl','stop') for args in self.calls))


class MainTests(unittest.TestCase):
    def test_repeated_apply_never_rolls_back_a_previous_activation(self):
        activation=Mock();activation.journal.exists.return_value=True
        activation.state.return_value={'failed_step':None}
        activation.apply.side_effect=ValueError('existing_activation_requires_rollback_review')
        metadata=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=0,st_nlink=1)
        with patch.object(operator,'bootstrap',return_value={}),patch.object(operator,'Activation',return_value=activation),\
                patch.object(os,'geteuid',return_value=0),patch.object(operator.sys,'flags',SimpleNamespace(isolated=True)),\
                patch.object(os,'open',return_value=99),patch.object(os,'fstat',return_value=metadata),\
                patch.object(os,'close'),patch.object(operator.fcntl,'flock'),redirect_stdout(io.StringIO()):
            self.assertEqual(operator.main(['--stage','fixture','--operation','apply']),1)
        activation.rollback.assert_not_called()

    def test_nonroot_or_nonisolated_does_not_bootstrap(self):
        for uid,isolated in ((12345,True),(0,False)):
            with patch.object(os,'geteuid',return_value=uid),patch.object(operator.sys,'flags',SimpleNamespace(isolated=isolated)),\
                    patch.object(operator,'bootstrap') as bootstrap,redirect_stdout(io.StringIO()):
                self.assertEqual(operator.main(['--stage','fixture','--operation','apply']),1)
            bootstrap.assert_not_called()

    def test_new_failed_attempt_reports_original_step_and_runs_rollback_once(self):
        activation=Mock();activation.journal.exists.side_effect=[False,True,True]
        activation.apply.side_effect=ValueError('operator_command_failed')
        activation.state.return_value={'failed_step':'commercial_services_start'}
        activation.rollback.return_value={'restored':True,'data_restored':False}
        metadata=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=0,st_nlink=1)
        output=io.StringIO()
        with patch.object(operator,'bootstrap',return_value={}),patch.object(operator,'Activation',return_value=activation),\
                patch.object(os,'geteuid',return_value=0),patch.object(operator.sys,'flags',SimpleNamespace(isolated=True)),\
                patch.object(os,'open',return_value=99),patch.object(os,'fstat',return_value=metadata),\
                patch.object(os,'close'),patch.object(operator.fcntl,'flock'),redirect_stdout(output):
            self.assertEqual(operator.main(['--stage','fixture','--operation','apply']),1)
        activation.rollback.assert_called_once()
        result=json.loads(output.getvalue());self.assertEqual(result['failed_step'],'commercial_services_start')
        self.assertTrue(result['rollback']['restored'])


class StagedSourceTests(unittest.TestCase):
    def test_changed_unknown_and_symlink_sources_never_execute_or_get_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory);source=stage/'source';source.mkdir()
            path=source/'jev_agent/__init__.py';path.parent.mkdir();raw=b'raise AssertionError("NEVER_EXECUTE")\n'
            path.write_bytes(raw);expected={'jev_agent/__init__.py':operator.sha(raw)}
            operator.verify_staged_sources(stage,expected,uid=os.geteuid())
            path.write_bytes(b'manual edit')
            with self.assertRaisesRegex(ValueError,'staged_payload_changed'):
                operator.verify_staged_sources(stage,expected,uid=os.geteuid())
            path.write_bytes(raw);foreign=source/'private.key';foreign.write_bytes(b'PRIVATE_TOKEN')
            original=operator.read_file
            def read(path,**kwargs):
                self.assertNotEqual(Path(path),foreign);return original(path,**kwargs)
            with patch.object(operator,'read_file',side_effect=read),self.assertRaisesRegex(ValueError,'unknown_staged_file'):
                operator.verify_staged_sources(stage,expected,uid=os.geteuid())
            self.assertEqual(foreign.read_bytes(),b'PRIVATE_TOKEN');foreign.unlink()
            path.unlink();path.symlink_to(stage/'outside')
            (stage/'outside').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'protected_staged_sources'):
                operator.verify_staged_sources(stage,expected,uid=os.geteuid())


class WheelTests(unittest.TestCase):
    def wheel(self,extra=()):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,raw in [('pypdf/__init__.py',b'fixture = True\n'),
                    ('pypdf-6.18.1.dist-info/WHEEL',b'Root-Is-Purelib: true\n'),
                    ('pypdf-6.18.1.dist-info/METADATA',b'Name: pypdf\nVersion: 6.18.1\n'),*extra]:
                archive.writestr(name,raw)
        return stream.getvalue()

    def test_only_new_package_files_are_written_and_existing_files_are_preserved(self):
        raw=self.wheel()
        with tempfile.TemporaryDirectory() as directory,patch.object(operator,'WHEEL_SHA',operator.sha(raw)):
            site=Path(directory)
            operator.install_wheel(site,raw,uid=os.geteuid())
            path=site/'pypdf/__init__.py';self.assertEqual(path.read_bytes(),b'fixture = True\n')
            path.write_text('manual change')
            with self.assertRaisesRegex(ValueError,'existing_dependency_preserved'):operator.install_wheel(site,raw,uid=os.geteuid())
            self.assertEqual(path.read_text(),'manual change')

    def test_hash_mismatch_and_unsafe_members_never_write(self):
        for name in ('pypdf/../../outside','/pypdf/outside','pypdf\\outside','pypdf/run.pth','another_package/run.py'):
            raw=self.wheel([(name,b'fixture')])
            with tempfile.TemporaryDirectory() as directory,patch.object(operator,'WHEEL_SHA',operator.sha(raw)):
                with self.assertRaisesRegex(ValueError,'unsafe_wheel_member'):
                    operator.install_wheel(Path(directory),raw,uid=os.geteuid())
                self.assertEqual(list(Path(directory).iterdir()),[])
        with self.assertRaisesRegex(ValueError,'pinned_wheel_hash_mismatch'):operator.wheel_contents(b'wrong archive')

    def test_symlink_and_existing_alias_are_refused(self):
        raw=self.wheel()
        with tempfile.TemporaryDirectory() as directory,patch.object(operator,'WHEEL_SHA',operator.sha(raw)):
            site=Path(directory);outside=site/'outside';outside.mkdir();(site/'pypdf').symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'protected_dependency_parent'):
                operator.install_wheel(site,raw,uid=os.geteuid())
            self.assertEqual(list(outside.iterdir()),[])

    def test_copied_venv_internal_lib64_alias_is_allowed_but_external_alias_is_not(self):
        with tempfile.TemporaryDirectory() as directory:
            venv=Path(directory);(venv/'lib').mkdir();(venv/'lib64').symlink_to('lib')
            operator.validate_venv_tree(venv,uid=os.geteuid())
            (venv/'bin').symlink_to('/usr/bin')
            with self.assertRaisesRegex(ValueError,'external_venv_alias'):operator.validate_venv_tree(venv,uid=os.geteuid())
