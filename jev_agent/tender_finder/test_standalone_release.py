from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import Mock,patch
from urllib.parse import unquote

from .standalone_release import Release,backup_data,verify_ci,BRANCH,OLD_UNITS,NEW_UNITS
from .source_package import REQUIRED
from .container_transfer import DockerFailure
from .test_container_transfer import source


class EngineFixture:
    def __init__(self):
        self.old=source();self.old['State']['Running']=True
        self.containers={self.old['Id']:self.old};self.calls=[];self.fail_create=False
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
            row={'Id':'c'*64,'Name':'/'+name,'Image':body['Image'],'State':{'Running':False},
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
        self.probe=Mock()
        self.release=Release(self.stage,_api=self.api,_unit=lambda name:deepcopy(self.units[name]),
            _run=self.run_command,_ci=lambda commit:'https://github.com/example/fixture-success',
            _root=self.root,_uid=os.geteuid(),_verify=Mock(),_probe=self.probe)

    def run_command(self,*args):
        self.commands.append(args)
        if args[0]=='/usr/bin/systemctl':
            operation=args[1]
            if operation in ('stop','start','enable','disable'):
                for name in args[2:]:
                    if name.startswith('--'):continue
                    if operation=='stop':self.units[name]['ActiveState']='inactive'
                    if operation=='start':self.units[name]['ActiveState']='active'
                    if operation=='enable':self.units[name]={'LoadState':'loaded','ActiveState':'active','UnitFileState':'enabled'}
                    if operation=='disable':self.units[name]['UnitFileState']='disabled'
        return b''

    def prepare(self):return self.release.prepare(self.commit,37,'123456789')

    def test_prepare_does_not_stop_or_mutate_containers_or_install_files(self):
        result=self.prepare()
        self.assertTrue(result['prepared']);self.assertFalse(result['installation_started'])
        self.assertFalse(any(method!='GET' for method,path in self.api.calls))
        self.assertEqual(self.commands,[])
        self.assertFalse((self.root/'opt/stroyka-jev').exists())

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
