from copy import deepcopy
import json
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from urllib.parse import unquote

from .standalone_release import Release,backup_data,verify_ci,source_files,_operator_lock,_gateway_group_plan,BRANCH,OLD_UNITS,NEW_UNITS
from .source_package import REQUIRED
from .container_transfer import DockerFailure
from .prepare_install import TMPFILES
from .test_container_transfer import source


class EngineFixture:
    def __init__(self):
        self.old=source();self.old['State']['Running']=True
        self.containers={self.old['Id']:self.old};self.calls=[];self.fail_create=False;self.created=0
        self.snapshot='sha256:'+'b'*64
    def request(self,method,path,body=None):
        self.calls.append((method,path))
        if path=='/info':return {'Driver':'overlay2','DockerRootDir':'/var/lib/docker'}
        if path=='/images/'+self.old['Image']+'/json':return {'Id':self.old['Image'],'Size':1024}
        if path=='/containers/json?all=1':return [dict(Id=row['Id'],State='running' if row['State']['Running'] else 'exited',Mounts=row['Mounts']) for row in self.containers.values()]
        if method=='GET' and path.startswith('/images/'):
            return {'Id':self.snapshot,'Parent':self.old['Image']}
        if method=='GET' and path.startswith('/containers/') and path.endswith('/json'):
            key=path[len('/containers/'):-len('/json')]
            if key in self.containers:return deepcopy(self.containers[key])
            match=next((row for row in self.containers.values() if row['Name']=='/'+key),None)
            if match is None:raise DockerFailure('docker_operation_unconfirmed',status=404)
            return deepcopy(match)
        if path.startswith('/commit?'):
            assert not self.old['State']['Running']
            assert body==self.old['Config']
            return {'Id':self.snapshot}
        if path.startswith('/containers/create?'):
            if self.fail_create:raise RuntimeError('synthetic create failure')
            name=path.split('name=',1)[1]
            identifier=hex(12+self.created)[2:]*64;self.created+=1
            row={'Id':identifier,'Name':'/'+name,'Image':body['Image'],'State':{'Running':False},
                'Config':{key:deepcopy(value) for key,value in body.items() if key!='HostConfig'},
                'HostConfig':deepcopy(body['HostConfig']),'Mounts':deepcopy(self.old['Mounts'])}
            self.containers[row['Id']]=row;return {'Id':row['Id']}
        if method=='POST' and path.startswith('/containers/'):
            tail=path[len('/containers/'):];identifier,operation=tail.split('/',1)
            row=self.containers[identifier]
            if operation=='kill?signal=SIGTERM':row['State']['Running']=False
            elif operation=='start':row['State']['Running']=True
            elif operation.startswith('rename?name='):row['Name']='/'+operation.split('=',1)[1]
            else:raise AssertionError(operation)
            return None
        raise AssertionError((method,path))


class StandaloneReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.stage=self.folder/'stage';self.stage.mkdir(mode=0o700)
        self.root=self.folder/'root'
        for path in ('opt','etc/systemd/system','etc/tmpfiles.d','root/hermes-data','var/lib/docker'):
            (self.root/path).mkdir(parents=True,exist_ok=True)
        self.data=self.root/'root/hermes-data/session.sqlite';self.data.write_bytes(b'original history')
        repository=self.stage/'repository';repository.mkdir()
        def git(*args):return subprocess.check_output(['git','-C',str(repository),*args],stderr=subprocess.DEVNULL)
        git('init','--quiet')
        for name in REQUIRED:
            for base in (repository,self.stage/'source'):
                path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('pass\n')
        git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@invalid','commit','--quiet','-m','release fixture')
        self.commit=git('rev-parse','HEAD').decode().strip()
        self.api=EngineFixture();self.commands=[]
        self.units={name:{'LoadState':'not-found','ActiveState':'inactive','UnitFileState':''} for name in NEW_UNITS+OLD_UNITS}
        self.units[OLD_UNITS[0]]={'LoadState':'loaded','ActiveState':'active','UnitFileState':'enabled'}
        self.units['hermes-jev-search.service']={'LoadState':'loaded','ActiveState':'inactive','UnitFileState':'static'}
        self.old_states=deepcopy(self.units)
        self.probe=Mock();self.group_exists=False
        self.release=Release(self.stage,_api=self.api,_unit=lambda name:deepcopy(self.units[name]),
            _run=self.run_command,_ci=lambda commit:'https://github.com/example/fixture-success',
            _root=self.root,_uid=os.geteuid(),_verify=Mock(),_probe=self.probe,_group_plan=self.group_plan)

    def group_plan(self):
        return {'gid':10000,'name':'stroyka-jev-gateway','existing':self.group_exists,
                'members_sha256':hashlib.sha256(b'[]').hexdigest()}

    def run_command(self,*args):
        self.commands.append(args)
        if args[0]=='/usr/sbin/groupadd':
            self.assertEqual(args,('/usr/sbin/groupadd','--gid','10000','stroyka-jev-gateway'))
            self.group_exists=True
        if args[0]=='/usr/bin/systemd-tmpfiles':
            for row in TMPFILES.splitlines():
                _,name,mode,*_=row.split();path=self.root/name.lstrip('/')
                path.mkdir(parents=True,exist_ok=True);path.chmod(int(mode,8))
        if args[0]=='/usr/bin/systemctl':
            operation=args[1]
            if operation=='daemon-reload':
                for name in NEW_UNITS:
                    if not (self.root/'etc/systemd/system'/name).exists():
                        self.units[name].update(LoadState='not-found',UnitFileState='')
            if operation in ('stop','start','enable','disable'):
                for name in args[2:]:
                    if name.startswith('--'):continue
                    if operation=='stop':self.units[name]['ActiveState']='inactive'
                    if operation=='start':self.units[name]['ActiveState']='active'
                    if operation=='enable':self.units[name]={'LoadState':'loaded','ActiveState':'active','UnitFileState':'enabled'}
                    if operation=='disable':self.units[name]['UnitFileState']='disabled'
        return b''

    def prepare(self):return self.release.prepare(self.commit,37,'123456789')

    def test_operator_mutex_prevents_two_stages_from_overlapping_without_overwriting_contents(self):
        path=self.folder/'host-release.lock';path.write_bytes(b'keep existing private bytes');path.chmod(0o600)
        first=_operator_lock(path,os.geteuid())
        try:
            with self.assertRaises(BlockingIOError):_operator_lock(path,os.geteuid())
            self.assertEqual(path.read_bytes(),b'keep existing private bytes')
        finally:os.close(first)
        os.close(_operator_lock(path,os.geteuid()))

    def test_operator_mutex_rejects_symlink_fifo_and_readable_foreign_file(self):
        path=self.folder/'host-release.lock'
        path.write_bytes(b'foreign bytes');path.chmod(0o644)
        with self.assertRaises(ValueError):_operator_lock(path,os.geteuid())
        self.assertEqual(path.read_bytes(),b'foreign bytes');path.unlink()
        path.symlink_to(self.data)
        with self.assertRaises(OSError):_operator_lock(path,os.geteuid())
        self.assertEqual(self.data.read_bytes(),b'original history');path.unlink()
        os.mkfifo(path,mode=0o600)
        with self.assertRaises(ValueError):_operator_lock(path,os.geteuid())

    def failed_start_and_retry_fixture(self):
        self.prepare();state=self.release.state()
        # Reproduce the previous pinned release's invalid host group while
        # keeping its protected binding and ownership journal intact.
        state['policy']['units/stroyka-jev.service']=state['policy']['units/stroyka-jev.service'].replace('\nGroup=root\n','\nGroup=10000\n')
        self.release.checkpoint(state)
        self.probe.side_effect=ValueError('synthetic_startup_failure')
        with patch('jev_agent.tender_finder.standalone_release.time.monotonic',side_effect=[0,100]):
            with self.assertRaisesRegex(ValueError,'initialized_jev_broker_not_confirmed'):self.release.apply()
        self.assertTrue(self.release.rollback()['restored'])
        stage=self.folder/'retry';stage.mkdir(mode=0o700)
        for name in ('repository','source'):shutil.copytree(self.stage/name,stage/name)
        retry=Release(stage,_api=self.api,_unit=lambda name:deepcopy(self.units[name]),
            _run=self.run_command,_ci=lambda commit:'https://github.com/example/retry-success',
            _root=self.root,_uid=os.geteuid(),_verify=Mock(),_probe=Mock(),_group_plan=self.group_plan)
        return retry

    def test_prepare_does_not_stop_or_mutate_containers_or_install_files(self):
        result=self.prepare()
        self.assertTrue(result['prepared']);self.assertFalse(result['installation_started'])
        self.assertFalse(any(method!='GET' for method,path in self.api.calls))
        self.assertEqual(self.commands,[])
        self.assertFalse((self.root/'opt/stroyka-jev').exists())

    def test_git_archive_explicit_private_modes_pass_source_protection(self):
        # Regression for root tar extraction preserving Git's default group-write
        # archive modes despite the calling shell's restrictive umask.
        output=self.stage/'archive-source';output.mkdir(mode=0o700)
        raw=subprocess.check_output(['git','-C',str(self.stage/'repository'),
            '-c','tar.umask=0077','archive',self.commit])
        subprocess.run(['tar','-x','-C',str(output)],input=raw,check=True)
        for path in output.rglob('*'):
            self.assertEqual(path.stat().st_mode & 0o077,0)
        verified=source_files(self.stage/'repository',output,self.commit,os.geteuid())
        self.assertEqual(set(verified),REQUIRED)

    def test_apply_then_rollback_preserves_current_data_key_and_original_configuration(self):
        self.prepare();result=self.release.apply()
        self.assertTrue(result['activated']);self.assertFalse(result['real_telegram_acceptance'])
        self.assertEqual(self.units[OLD_UNITS[0]],self.old_states[OLD_UNITS[0]])
        state=self.release.state();self.assertTrue(state['data_backup_verified'])
        self.assertTrue((self.stage/'hermes-data.tar.gz').is_file())
        self.assertFalse(self.api.old['State']['Running'])
        self.probe.assert_called_once()
        new=self.api.containers[state['new_id']]
        self.assertEqual(new['Config']['Env'],self.api.old['Config']['Env'])
        self.data.write_bytes(b'new session written after activation')
        key=self.root/'etc/stroyka-jev/private/admission.key';key_bytes=key.read_bytes()
        restored=self.release.rollback()
        self.assertTrue(restored['restored']);self.assertFalse(restored['data_restored'])
        self.assertEqual(self.data.read_bytes(),b'new session written after activation')
        self.assertEqual(key.read_bytes(),key_bytes)
        self.assertTrue(self.api.old['State']['Running']);self.assertEqual(self.api.old['Name'],'/hermes-telegram')
        self.assertFalse(new['State']['Running'])
        self.assertEqual(self.units[OLD_UNITS[0]],self.old_states[OLD_UNITS[0]])
        self.assertTrue(self.release.rollback()['restored'])

    def test_failed_create_can_restore_original_without_data_restore(self):
        self.prepare();self.api.fail_create=True
        with self.assertRaises(RuntimeError):self.release.apply()
        self.assertFalse(self.api.old['State']['Running'])
        self.assertTrue(self.release.rollback()['restored'])
        self.assertTrue(self.api.old['State']['Running'])
        self.assertEqual(self.data.read_bytes(),b'original history')

    def test_foreign_code_or_container_change_blocks_rollback_before_stop(self):
        self.prepare();self.release.apply()
        target=self.root/'opt/stroyka-jev/app/jev_agent/__init__.py';target.write_text('foreign edit')
        before=len(self.commands)
        with self.assertRaisesRegex(ValueError,'foreign_file_change'):self.release.rollback()
        self.assertEqual(len(self.commands),before)
        self.assertTrue(self.api.containers['c'*64]['State']['Running'])

    def test_other_rw_data_writer_or_active_legacy_job_blocks_prepare(self):
        other=deepcopy(self.api.old);other['Id']='e'*64;other['Name']='/other'
        other['Mounts'][0]['Source']=str(self.root/'root/hermes-data')
        self.api.containers[other['Id']]=other
        with self.assertRaisesRegex(ValueError,'other_active_data_writer'):self.prepare()
        self.assertFalse(self.release.state_path.exists())
        self.api.containers.pop(other['Id']);self.units['hermes-jev-search.service']['ActiveState']='active'
        with self.assertRaisesRegex(ValueError,'legacy_search_must_finish'):self.prepare()

    def test_ci_or_source_change_blocks_apply_before_any_service_stop(self):
        self.prepare()
        self.release.ci=Mock(side_effect=ValueError('CI not confirmed'))
        with self.assertRaises(ValueError):self.release.apply()
        self.assertEqual(self.commands,[]);self.assertTrue(self.api.old['State']['Running'])

    def test_lost_create_reply_recovers_only_owned_stopped_candidate(self):
        self.prepare()
        original_request=self.api.request
        def lose_reply(method,path,body=None):
            result=original_request(method,path,body)
            if path.startswith('/containers/create?'):raise DockerFailure('synthetic_lost_reply')
            return result
        self.api.request=lose_reply
        with self.assertRaises(DockerFailure):self.release.apply()
        self.assertIsNone(self.release.state()['new_id'])
        self.assertTrue(self.release.rollback()['restored'])
        self.assertTrue(self.api.old['State']['Running'])
        self.assertFalse(self.api.containers['c'*64]['State']['Running'])

    def test_foreign_container_settings_block_rollback_before_stop(self):
        self.prepare();self.release.apply()
        self.api.containers['c'*64]['HostConfig']['Memory']=999
        before=len(self.commands)
        with self.assertRaisesRegex(DockerFailure,'replacement_host_configuration_conflict'):
            self.release.rollback()
        self.assertEqual(len(self.commands),before)
        self.assertTrue(self.api.containers['c'*64]['State']['Running'])

    def test_unfinished_shutdown_requires_recovery_without_restarting_old_timer(self):
        self.prepare();state=self.release.state()
        state.update(phase='failed',stop_intent=True,stop_confirmed=False)
        self.release.checkpoint(state)
        with self.assertRaisesRegex(ValueError,'shutdown_inflight'):
            self.release.rollback()
        self.assertEqual(self.commands,[])

    def test_foreign_runtime_directory_blocks_before_stop(self):
        self.prepare();(self.root/'run/stroyka-jev').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'existing_target_requires_review'):self.release.apply()
        self.assertEqual(self.commands,[]);self.assertTrue(self.api.old['State']['Running'])

    def test_existing_private_qa_directory_and_files_survive_apply_and_rollback(self):
        directory=self.root/'etc/stroyka-jev';directory.mkdir(mode=0o700)
        directory.chmod(0o700)
        secret=directory/'qa.env';secret.write_bytes(b'SYNTHETIC_ONLY=opaque\n')
        secret.chmod(0o600)
        script=directory/'model-click-probe.py';script.write_bytes(b'# unrelated QA probe\n')
        script.chmod(0o644)
        def signatures():
            return {p.name:(p.read_bytes(),p.stat()) for p in (secret,script)}
        before=signatures();parent=directory.stat()
        self.assertTrue(self.prepare()['prepared'])
        self.assertTrue(self.release.apply()['activated'])
        self.assertEqual(signatures(),before)
        self.assertTrue(self.release.rollback()['restored'])
        self.assertEqual(signatures(),before)
        after=directory.stat()
        self.assertEqual((after.st_ino,after.st_mode,after.st_uid,after.st_gid),
                         (parent.st_ino,parent.st_mode,parent.st_uid,parent.st_gid))

    def test_retry_preserves_key_receipts_old_backups_and_copies_fresh_current_data(self):
        retry=self.failed_start_and_retry_fixture()
        key=self.root/'etc/stroyka-jev/private/admission.key';key_bytes=key.read_bytes()
        old_backup=(self.stage/'hermes-data.tar.gz').read_bytes()
        receipt=self.root/'var/lib/stroyka-jev/v2/private/durable-receipt.json'
        receipt.write_bytes(b'opaque existing receipt');receipt.chmod(0o600)
        self.data.write_bytes(b'current history after rollback')
        before=len(self.commands);calls=len(self.api.calls)
        plan=retry.prepare_retry(self.commit,self.stage)
        self.assertTrue(plan['prepared']);self.assertFalse(plan['installation_started'])
        self.assertEqual(len(self.commands),before)
        self.assertFalse(any(method!='GET' for method,path in self.api.calls[calls:]))
        self.assertEqual(retry.state()['policy']['policy/host-bridge.json'],self.release.state()['policy']['policy/host-bridge.json'])
        self.assertIn('\nGroup=root\n',retry.state()['policy']['units/stroyka-jev.service'])
        self.assertTrue(retry.apply()['activated'])
        self.assertEqual(key.read_bytes(),key_bytes)
        self.assertEqual(receipt.read_bytes(),b'opaque existing receipt')
        self.assertEqual((self.stage/'hermes-data.tar.gz').read_bytes(),old_backup)
        with tarfile.open(retry.stage/'hermes-data.tar.gz') as archive:
            self.assertEqual(archive.extractfile('hermes-data/session.sqlite').read(),b'current history after rollback')
        self.assertEqual(len(self.api.containers),3)
        self.assertFalse(self.api.containers['c'*64]['State']['Running'])
        self.data.write_bytes(b'new history after retry activation')
        self.assertTrue(retry.rollback()['restored'])
        self.assertEqual(self.data.read_bytes(),b'new history after retry activation')
        self.assertEqual(key.read_bytes(),key_bytes)
        self.assertEqual(receipt.read_bytes(),b'opaque existing receipt')
        self.assertTrue(self.api.old['State']['Running'])

    def test_retry_requires_completed_rollback_and_unchanged_retained_key(self):
        retry=self.failed_start_and_retry_fixture()
        old=self.release.state();old['phase']='failed';self.release.checkpoint(old)
        with self.assertRaisesRegex(ValueError,'completed_owned_rollback_required'):
            retry.prepare_retry(self.commit,self.stage)
        old['phase']='rolled_back';self.release.checkpoint(old)
        key=self.root/'etc/stroyka-jev/private/admission.key';key.write_bytes(b'foreign changed private key')
        with self.assertRaisesRegex(ValueError,'retained_private_file_changed'):
            retry.prepare_retry(self.commit,self.stage)
        self.assertTrue(self.api.old['State']['Running']);self.assertFalse(retry.state_path.exists())

    def test_retry_rejects_foreign_code_or_changed_previous_journal_before_stop(self):
        retry=self.failed_start_and_retry_fixture()
        foreign=self.root/'opt/stroyka-jev/app/foreign.py';foreign.write_bytes(b'foreign code')
        with self.assertRaisesRegex(ValueError,'foreign_retry_code_directory_preserved'):
            retry.prepare_retry(self.commit,self.stage)
        self.assertEqual(foreign.read_bytes(),b'foreign code');foreign.unlink()
        retry.prepare_retry(self.commit,self.stage)
        old=self.release.state();old['accepted']=True;self.release.checkpoint(old)
        before=len(self.commands)
        with self.assertRaisesRegex(ValueError,'previous_release_journal_changed'):retry.apply()
        self.assertEqual(len(self.commands),before);self.assertTrue(self.api.old['State']['Running'])

    def test_retry_refuses_foreign_running_retained_container_and_owner_change(self):
        retry=self.failed_start_and_retry_fixture()
        failed=self.api.containers['c'*64];failed['State']['Running']=True
        with self.assertRaisesRegex(DockerFailure,'stopped_replacement_required'):
            retry.prepare_retry(self.commit,self.stage)
        failed['State']['Running']=False
        with self.assertRaisesRegex(ValueError,'retry_owner_policy_must_match'):
            retry.prepare(self.commit,999,'987654321',previous_stage=self.stage)
        self.assertFalse(retry.state_path.exists());self.assertTrue(self.api.old['State']['Running'])

    def test_retry_refuses_changed_backup_before_stopping_anything(self):
        retry=self.failed_start_and_retry_fixture()
        archive=self.stage/'hermes-data.tar.gz';archive.write_bytes(b'changed archive')
        before=len(self.commands)
        with self.assertRaisesRegex(ValueError,'retained_data_backup_changed'):
            retry.prepare_retry(self.commit,self.stage)
        self.assertEqual(len(self.commands),before);self.assertTrue(self.api.old['State']['Running'])
        self.assertEqual(archive.read_bytes(),b'changed archive')

    def test_missing_host_root_group_blocks_prepare_without_gateway_group_fallback(self):
        with patch('jev_agent.tender_finder.standalone_release.grp.getgrnam',side_effect=KeyError('root')) as group:
            with self.assertRaises(KeyError):self.prepare()
        group.assert_called_once_with('root')
        self.assertEqual(self.commands,[]);self.assertFalse(self.release.state_path.exists())
        self.assertTrue(self.api.old['State']['Running'])

    def test_socket_group_is_provisioned_before_stop_and_retained_on_rollback(self):
        self.prepare();self.release.apply()
        create=('/usr/sbin/groupadd','--gid','10000','stroyka-jev-gateway')
        stop=('/usr/bin/systemctl','stop','hermes-jev-search.timer')
        self.assertLess(self.commands.index(create),self.commands.index(stop))
        self.assertTrue(self.release.state()['gateway_group_created'])
        self.assertTrue(self.release.rollback()['restored'])
        self.assertTrue(self.group_exists)
        self.assertEqual(self.commands.count(create),1)

    def test_existing_gateway_group_is_preserved_without_membership_changes(self):
        self.group_exists=True;self.prepare();self.release.apply()
        self.assertFalse(any(args[0]=='/usr/sbin/groupadd' for args in self.commands))
        self.assertFalse(self.release.state()['gateway_group_created'])

    def test_group_nss_plan_handles_missing_reuses_existing_and_rejects_name_conflict(self):
        with patch('grp.getgrgid',side_effect=KeyError),patch('grp.getgrnam',side_effect=KeyError):
            plan=_gateway_group_plan()
            self.assertFalse(plan['existing']);self.assertEqual(plan['gid'],10000)
        with patch('grp.getgrgid',return_value=SimpleNamespace(gr_gid=10000,gr_name='existing-hermes',gr_mem=['synthetic-member'])):
            plan=_gateway_group_plan()
            self.assertTrue(plan['existing']);self.assertEqual(plan['name'],'existing-hermes')
        with patch('grp.getgrgid',side_effect=KeyError),patch('grp.getgrnam',return_value=SimpleNamespace(gr_gid=999)):
            with self.assertRaisesRegex(ValueError,'gateway_group_name_conflict'):_gateway_group_plan()

    def test_group_change_since_prepare_blocks_before_stop(self):
        self.prepare();self.group_exists=True
        with self.assertRaisesRegex(ValueError,'gateway_group_changed_since_review'):self.release.apply()
        self.assertEqual(self.commands,[]);self.assertTrue(self.api.old['State']['Running'])

    def test_group_provision_failure_does_not_stop_running_hermes(self):
        self.prepare();real_run=self.release.run
        def fail(*args):
            if args[0]=='/usr/sbin/groupadd':raise ValueError('synthetic_groupadd_failure')
            return real_run(*args)
        self.release.run=fail
        with self.assertRaisesRegex(ValueError,'synthetic_groupadd_failure'):self.release.apply()
        self.assertTrue(self.release.rollback()['restored'])
        self.assertFalse(any(method!='GET' for method,path in self.api.calls))
        self.assertTrue(self.api.old['State']['Running'])

    def test_shared_parent_does_not_allow_existing_owned_leaf_or_symlink(self):
        directory=self.root/'etc/stroyka-jev';directory.mkdir(mode=0o700)
        for name in ('bridge.json','container-image.json','private'):
            with self.subTest(name=name):
                target=directory/name;target.write_bytes(b'foreign contents')
                with self.assertRaisesRegex(ValueError,'existing_target_requires_review'):self.prepare()
                self.assertEqual(target.read_bytes(),b'foreign contents')
                target.unlink()
        link=directory/'bridge.json';link.symlink_to('missing-target')
        with self.assertRaisesRegex(ValueError,'existing_target_requires_review'):self.prepare()
        self.assertTrue(link.is_symlink())
        self.assertFalse(self.release.state_path.exists());self.assertEqual(self.commands,[])

    def test_shared_parent_owner_mode_and_type_are_checked_without_chmod(self):
        directory=self.root/'etc/stroyka-jev';directory.mkdir(mode=0o700)
        directory.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private_release_directory_required'):self.prepare()
        self.assertEqual(directory.stat().st_mode & 0o777,0o755)
        directory.rmdir();other=self.root/'other-qa';other.mkdir(mode=0o700)
        directory.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'private_release_path_required'):self.prepare()
        self.assertTrue(directory.is_symlink());directory.unlink()
        directory.write_bytes(b'foreign plain file')
        with self.assertRaisesRegex(ValueError,'private_release_directory_required'):self.prepare()
        self.assertEqual(directory.read_bytes(),b'foreign plain file')
        self.assertEqual(self.commands,[])

    def test_owned_leaf_created_after_prepare_blocks_before_service_stop(self):
        directory=self.root/'etc/stroyka-jev';directory.mkdir(mode=0o700)
        self.prepare();target=directory/'bridge.json';target.write_bytes(b'later foreign settings')
        with self.assertRaisesRegex(ValueError,'existing_target_requires_review'):self.release.apply()
        self.assertEqual(target.read_bytes(),b'later foreign settings')
        self.assertEqual(self.commands,[]);self.assertTrue(self.api.old['State']['Running'])

    def test_rollback_resumes_after_crash_between_own_file_unlink_and_journal(self):
        self.prepare();self.release.apply()
        real_run=self.release.run
        def crash(*args):
            if args==('/usr/bin/systemctl','daemon-reload'):raise RuntimeError('synthetic interruption')
            return real_run(*args)
        self.release.run=crash
        with self.assertRaises(RuntimeError):self.release.rollback()
        self.release.run=real_run
        self.assertTrue(self.release.rollback()['restored'])
        self.assertTrue(self.api.old['State']['Running'])
        self.assertEqual(self.data.read_bytes(),b'original history')

    def test_ci_checks_exact_commit_workflow_and_success(self):
        commit='a'*40
        url='https://github.com/marikol444707-ux/stroyka-app/actions?query=branch%3A'+BRANCH
        row={'description':{'linkUrl':'/marikol444707-ux/stroyka-app/commit/'+commit},
            'workflowFilePath':'.github/workflows/ci.yml','runUrl':'https://github.com/marikol444707-ux/stroyka-app/actions/runs/123',
            'state':{'status':'WORKFLOW_RUN_STATUS_COMPLETED','conclusion':'WORKFLOW_RUN_CONCLUSION_SUCCESS'}}
        def response():
            value=Mock();value.url=url
            value.read.return_value=('<script type="application/json">'+json.dumps({'payload':{
                'allWorkflowRunsRoute':{'workflowRuns':[row]}}})+'</script>').encode()
            context=Mock();context.__enter__=Mock(return_value=value);context.__exit__=Mock(return_value=False)
            return context
        with patch('urllib.request.urlopen',side_effect=lambda *a,**kw:response()):
            self.assertEqual(verify_ci(commit),row['runUrl'])
            with self.assertRaisesRegex(ValueError,'unconfirmed'):verify_ci('b'*40)
            row['state']['conclusion']='WORKFLOW_RUN_CONCLUSION_FAILURE'
            with self.assertRaisesRegex(ValueError,'not_successful'):verify_ci(commit)
            row['workflowFilePath']='other.yml'
            with self.assertRaisesRegex(ValueError,'unconfirmed'):verify_ci(commit)

    def test_actual_tar_backup_validates_bytes_and_symlinks_without_restoring(self):
        directory=self.root/'root/hermes-data';(directory/'link').symlink_to('session.sqlite')
        archive=self.stage/'test-backup.tar.gz'
        proof=backup_data(directory,archive)
        self.assertEqual(proof['regular_files'],1)
        with tarfile.open(archive) as tar:
            self.assertEqual(tar.extractfile('hermes-data/session.sqlite').read(),b'original history')
            self.assertEqual(tar.getmember('hermes-data/link').linkname,'session.sqlite')
        self.assertEqual(self.data.read_bytes(),b'original history')

    def test_backup_supports_hardlinks_and_rejects_fifo(self):
        directory=self.data.parent;os.link(self.data,directory/'hardlink')
        self.assertEqual(backup_data(directory,self.stage/'links.tar.gz')['regular_files'],2)
        os.mkfifo(directory/'fifo')
        with self.assertRaisesRegex(ValueError,'special_data_file'):
            backup_data(directory,self.stage/'fifo.tar.gz')


if __name__=='__main__':unittest.main()
