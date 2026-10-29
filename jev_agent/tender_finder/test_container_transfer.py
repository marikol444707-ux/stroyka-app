from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from .container_transfer import create_request,validate_source,verify_created,stop_gracefully,DockerFailure,_same_host_config
from .image_pin import BASE_IMAGE,snapshot_pin


def source():
    return {'Id':'a'*64,'Name':'/hermes-telegram','Image':BASE_IMAGE,'State':{'Running':False},
        'Config':{'Env':['TOKEN=synthetic\nprivate=second','HERMES_HOME=/opt/data'],
                  'Cmd':['gateway'],'Entrypoint':['/init'],'User':'root','Hostname':'keep-host',
                  'Labels':{'keep':'unchanged'},'Volumes':{'/opt/data':{}},'WorkingDir':'/opt/hermes'},
        'HostConfig':{'Privileged':False,'CapAdd':None,'PidMode':'','Devices':[],'SecurityOpt':None,
            'NetworkMode':'bridge','PortBindings':{},'AutoRemove':False,'VolumesFrom':None,'Links':None,
            'ReadonlyRootfs':False,'RestartPolicy':{'Name':'unless-stopped','MaximumRetryCount':0},
            'LogConfig':{'Type':'json-file','Config':{'max-size':'10m'}},'Binds':['/root/hermes-data:/opt/data'],
            'Memory':268435456,'Dns':['1.1.1.1']},
        'Mounts':[{'Type':'bind','Source':'/root/hermes-data','Destination':'/opt/data','RW':True}],
        'NetworkSettings':{'Networks':{'bridge':{'IPAMConfig':None,'Links':None}}}}


class ContainerTransferTests(unittest.TestCase):
    def test_private_clone_preserves_opaque_env_all_host_settings_and_only_adds_mounts(self):
        original=source();frozen=deepcopy(original)
        pin=snapshot_pin(original,{'Id':'sha256:'+'b'*64,'Parent':BASE_IMAGE})
        request=create_request(original,pin)
        self.assertNotIn('TOKEN',repr(request));self.assertNotIn('private=second',repr(request))
        self.assertEqual(original,frozen)
        expected=deepcopy(original['Config']);expected['Image']=pin['snapshot_image']
        expected['HostConfig']=deepcopy(original['HostConfig'])
        expected['HostConfig']['Mounts']=request.body['HostConfig']['Mounts']
        self.assertEqual(request.body,expected)
        self.assertEqual(len(request.body['HostConfig']['Mounts']),3)
        self.assertTrue(all(mount['ReadOnly'] for mount in request.body['HostConfig']['Mounts']))
        self.assertEqual(json.loads(json.dumps(request.body))['Env'],original['Config']['Env'])

    def test_source_must_be_stopped_and_supported_topology_not_silently_rewritten(self):
        cases=[]
        running=source();running['State']['Running']=True;cases.append(running)
        for key,value in (('NetworkMode','host'),('Privileged',True),('AutoRemove',True),
                          ('PortBindings',{'80/tcp':[]}),('Links',['other:other'])):
            wrong=source();wrong['HostConfig'][key]=value;cases.append(wrong)
        wrong=source();wrong['Mounts'].append({'Type':'volume','Source':'foreign'});cases.append(wrong)
        for wrong in cases:
            with self.assertRaises(ValueError):validate_source(wrong,stopped=True)

    def test_replacement_is_compared_before_start_and_foreign_changes_block_it(self):
        original=source();pin=snapshot_pin(original,{'Id':'sha256:'+'b'*64,'Parent':BASE_IMAGE})
        body=create_request(original,pin).body
        actual={'Image':pin['snapshot_image'],'State':{'Running':False},
                'Config':{key:value for key,value in body.items() if key!='HostConfig'},'HostConfig':body['HostConfig']}
        verify_created(actual,original,pin)
        actual['Config']['Env']=['TOKEN=changed']
        with self.assertRaises(DockerFailure):verify_created(actual,original,pin)

    def test_only_null_to_false_oom_default_is_equivalent(self):
        self.assertTrue(_same_host_config({'OomKillDisable':False},{'OomKillDisable':None}))
        self.assertFalse(_same_host_config({'OomKillDisable':True},{'OomKillDisable':None}))
        self.assertFalse(_same_host_config({'Memory':0},{'Memory':4096}))

    def test_graceful_stop_never_escalates_to_kill_on_timeout(self):
        state={'Id':'a'*64,'State':{'Running':True}}
        api=Mock();api.request.return_value=state
        with self.assertRaisesRegex(DockerFailure,'graceful_stop_not_confirmed'):
            stop_gracefully(api,'a'*64,timeout=1,_clock=Mock(side_effect=[0,2]),_wait=Mock())
        paths=[call.args[1] for call in api.request.call_args_list]
        self.assertEqual([path for path in paths if '/kill' in path],['/containers/'+'a'*64+'/kill?signal=SIGTERM'])
        self.assertFalse(any('force=' in path or 'SIGKILL' in path for path in paths))


if __name__=='__main__':unittest.main()
