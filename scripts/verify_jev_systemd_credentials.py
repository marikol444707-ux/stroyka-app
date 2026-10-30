"""Required CI-only native systemd credential regression; no application units.

Uses unique fixture units under /run and an explicitly synthetic credential.
Never deploys JEV, runs a search, accesses Hermes or calls Telegram. A missing
native systemd manager is a failure, not a skipped acceptance check.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import uuid

from jev_agent.tender_finder.standalone_release import _gateway_group_plan


PROBE='''import json,os,socket,stat
from pathlib import Path
assert os.geteuid()==0 and os.getegid()==0
assert os.environ.get("LISTEN_PID")==str(os.getpid())
assert os.environ.get("LISTEN_FDS")=="1"
assert os.environ.get("LISTEN_FDNAMES")=="admission"
root=Path(__file__).parent
with socket.socket(fileno=3) as listener:
    assert listener.getsockopt(socket.SOL_SOCKET,socket.SO_ACCEPTCONN)==1
    assert listener.getsockname()==str(root/"admission.sock")
metadata=(root/"admission.sock").stat()
assert metadata.st_uid==0 and metadata.st_gid==10000
assert stat.S_IMODE(metadata.st_mode)==0o660
credential=Path(os.environ["CREDENTIALS_DIRECTORY"])/"admission.key"
assert credential.stat().st_uid==0
assert stat.S_IMODE(credential.stat().st_mode) in (0o400,0o600)
assert stat.S_IMODE(credential.parent.stat().st_mode) in (0o500,0o700)
assert credential.read_bytes()==b"native-systemd-fixture-key-123456"
with (root/"proof.json").open("x") as stream:
    json.dump({"uid":0,"gid":0,"socket_gid":10000,"socket_mode":"0660","listener_fd":"admission","credential_read":True},stream)
'''


def run(*args):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
    if result.returncode:
        raise RuntimeError('native_fixture_operation_failed_'+str(result.returncode))
    return result.stdout


def main():
    if os.geteuid()!=0 or not Path('/run/systemd/system').is_dir():
        raise RuntimeError('native_root_systemd_required')
    group=_gateway_group_plan()
    if not group['existing']:
        run('/usr/sbin/groupadd','--gid','10000','stroyka-jev-gateway')
        assert _gateway_group_plan()=={**group,'existing':True}
    # Leave an existing group unchanged; a newly provisioned empty fixture
    # group disappears with the ephemeral runner and is never groupdel'ed.
    folder=Path(tempfile.mkdtemp(prefix='jev-systemd-fixture-',dir='/run'))
    os.chown(folder,0,10000);folder.chmod(0o710)
    name='jev-credentials-test-'+uuid.uuid4().hex
    owned={};registered=False
    try:
        key=folder/'synthetic.key';key.write_bytes(b'native-systemd-fixture-key-123456');key.chmod(0o600)
        probe=folder/'probe.py';probe.write_text(PROBE);probe.chmod(0o644)
        service=f'''[Unit]
Requires={name}.socket
After={name}.socket
[Service]
Type=oneshot
User=root
Group=root
UMask=0077
LoadCredential=admission.key:{key}
ExecStart=/usr/bin/python3 -I -B {probe}
'''
        socket_unit=f'''[Socket]
ListenStream={folder}/admission.sock
FileDescriptorName=admission
SocketUser=root
SocketGroup=10000
SocketMode=0660
DirectoryMode=0710
Service={name}.service
RemoveOnStop=no
'''
        for suffix,content in (('service',service),('socket',socket_unit)):
            path=Path('/run/systemd/system')/(name+'.'+suffix)
            with path.open('x') as stream:stream.write(content)
            path.chmod(0o644);owned[path]=hashlib.sha256(content.encode()).hexdigest()
        run('/usr/bin/systemctl','daemon-reload');registered=True
        run('/usr/bin/systemctl','start',name+'.socket')
        run('/usr/bin/systemctl','start',name+'.service')
        proof=json.loads((folder/'proof.json').read_text())
        assert proof=={'uid':0,'gid':0,'socket_gid':10000,'socket_mode':'0660',
                       'listener_fd':'admission','credential_read':True}
        assert stat.S_IMODE((folder/'proof.json').stat().st_mode)==0o600
        run('/usr/bin/systemctl','stop',name+'.service',name+'.socket')
        assert stat.S_ISSOCK((folder/'admission.sock').stat().st_mode)
        (folder/'proof.json').rename(folder/'first-proof.json')
        # Production rollback deliberately retains the socket inode. Verify a
        # real manager can rebind it and supply the same FD/credential contract.
        run('/usr/bin/systemctl','start',name+'.socket')
        run('/usr/bin/systemctl','start',name+'.service')
        assert json.loads((folder/'proof.json').read_text())==proof
        print(json.dumps({'native_systemd_credentials':'PASS','restart_with_retained_socket':True,**proof}))
        return 0
    finally:
        if registered:
            # Stop only these captured, uniquely named fixture units.
            run('/usr/bin/systemctl','stop',name+'.service',name+'.socket')
        for path,digest in owned.items():
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise RuntimeError('fixture_unit_changed_cleanup_refused')
            path.unlink()
        if registered:run('/usr/bin/systemctl','daemon-reload')
        shutil.rmtree(folder)


if __name__=='__main__':raise SystemExit(main())
