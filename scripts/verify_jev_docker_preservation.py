"""Real isolated Docker regression; synthetic data only, no production access."""
import copy, http.client, io, json, socket, tarfile, time, uuid
from jev_agent.tender_finder.container_transfer import DockerAPI, _private_clone, _same_host_config, stop_gracefully
from jev_agent.tender_finder.image_pin import snapshot_pin

class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout);self.sock.connect('/var/run/docker.sock')

def request(method,path,value=None):
    connection=UnixHTTP('localhost',timeout=40)
    data=None if value is None else json.dumps(value).encode()
    try:
        connection.request(method,path,body=data,headers={'Content-Type':'application/json'})
        response=connection.getresponse();raw=response.read()
        if response.status>=300:raise RuntimeError('docker_http_'+str(response.status))
        return raw
    finally:connection.close()

def obj(method,path,value=None):
    raw=request(method,path,value)
    return json.loads(raw) if raw else None

prefix='/v'+obj('GET','/version')['ApiVersion']
created=[];snapshot=None;volume=None;readonly_volume=None
api=DockerAPI()
try:
    base=obj('GET',prefix+'/images/postgres:16/json')['Id']
    nonce=uuid.uuid4().hex[:12]
    volume='jev-fixture-'+nonce
    obj('POST',prefix+'/volumes/create',{'Name':volume,'Labels':{'jev-fixture':nonce}})
    readonly_volume='jev-ro-fixture-'+nonce
    obj('POST',prefix+'/volumes/create',{'Name':readonly_volume,'Labels':{'jev-fixture':nonce}})
    body={'Image':base,'Entrypoint':['/bin/sh','-c'],
          'Cmd':['trap "exit 0" TERM; printf cow-preserved >/tmp/jev-cow-marker; printf data-preserved >/var/lib/postgresql/data/jev-fixture; while :; do sleep 1 & wait $!; done'],
          'Env':['SYNTHETIC_PRIVATE=first\nsecond'],
          'Labels':{'jev-fixture':nonce},'HostConfig':{'NetworkMode':'none','RestartPolicy':{'Name':'unless-stopped'},
          'Mounts':[{'Type':'volume','Source':volume,'Target':'/var/lib/postgresql/data'}]}}
    old=obj('POST',prefix+'/containers/create?name=jev-old-'+nonce,body)['Id'];created.append(old)
    request('POST',prefix+'/containers/'+old+'/start')
    for _ in range(20):
        try:
            request('GET',prefix+'/containers/'+old+'/archive?path=/tmp/jev-cow-marker');break
        except RuntimeError:time.sleep(.1)
    original=obj('GET',prefix+'/containers/'+old+'/json')
    stop_gracefully(api,old,timeout=10)
    stopped=obj('GET',prefix+'/containers/'+old+'/json')
    snapshot=obj('POST',prefix+'/commit?container='+old+'&pause=false',original['Config'])['Id']
    image=obj('GET',prefix+'/images/'+snapshot+'/json')
    pin=snapshot_pin(stopped,image,_base=base)
    assert pin['snapshot_image']==snapshot
    extra=[{'Type':'volume','Source':readonly_volume,'Target':'/opt/stroyka-jev','ReadOnly':True}]
    replacement=_private_clone(stopped,snapshot,extra,release_token=uuid.uuid4().hex).body
    new=obj('POST',prefix+'/containers/create?name=jev-new-'+nonce,replacement)['Id'];created.append(new)
    actual=obj('GET',prefix+'/containers/'+new+'/json')
    assert actual['Config']['Env']==original['Config']['Env']
    assert actual['Config']['Entrypoint']==original['Config']['Entrypoint']
    assert actual['Config']['Cmd']==original['Config']['Cmd']
    assert _same_host_config(actual['HostConfig'],replacement['HostConfig']), 'unexpected daemon HostConfig rewrite'
    assert any(m['Destination']=='/opt/stroyka-jev' and m['RW'] is False for m in actual['Mounts'])
    for path,expected in (('/tmp/jev-cow-marker',b'cow-preserved'),('/var/lib/postgresql/data/jev-fixture',b'data-preserved')):
        archive=request('GET',prefix+'/containers/'+new+'/archive?path='+path)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            member=next(item for item in tar if item.isfile())
            assert tar.extractfile(member).read()==expected
    request('POST',prefix+'/containers/'+new+'/start')
    stop_gracefully(api,new,timeout=10)
    request('POST',prefix+'/containers/'+old+'/start')
    assert obj('GET',prefix+'/containers/'+old+'/json')['State']['Running']
    print('PASS: real managed Docker; stopped snapshot retains writable-layer file; opaque multiline env, entrypoint, command, complete HostConfig and mounted data preserved; added mount is read-only; original container restart verified; no production access')
finally:
    for identifier in reversed(created):
        try:request('DELETE',prefix+'/containers/'+identifier+'?force=true&v=true')
        except Exception:pass
    if snapshot:
        try:request('DELETE',prefix+'/images/'+snapshot)
        except Exception:pass
    if volume:
        try:request('DELETE',prefix+'/volumes/'+volume)
        except Exception:pass

    if readonly_volume:
        try:request('DELETE',prefix+'/volumes/'+readonly_volume)
        except Exception:pass
