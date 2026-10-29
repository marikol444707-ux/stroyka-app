from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import systemd_bootstrap as bootstrap
from .bootstrap_key import read_bootstrap_key
from .prepare_install import review_files
from .settings import parse_settings
from . import test_docker_delivery as delivery_fixtures


def config():
    return parse_settings(json.loads(review_files(37,'123456789')['policy/host-bridge.json']))


def mounted_metadata():
    from .prepare_install import MOUNTS
    mounts=json.loads(delivery_fixtures.metadata())['mounts']
    mounts.extend({'Type':'bind','Source':row['source'],'Destination':row['destination'],
                   'RW':not row['read_only']} for row in MOUNTS)
    return delivery_fixtures.metadata(mounts=mounts)


class SystemdBootstrapTests(unittest.TestCase):
    def test_real_credential_becomes_private_pipe_and_is_closed_after_consumption(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'admission.key';path.write_bytes(b'synthetic-local-credential-12345678')
            path.chmod(0o400)
            fd=bootstrap.credential_pipe(_path=path,_uid=os.geteuid(),_trusted_root=root)
            self.assertFalse(os.get_inheritable(fd))
            secret=read_bootstrap_key(fd,expected_uid=os.geteuid())
            self.assertEqual(secret.material,path.read_bytes())
            self.assertNotIn('synthetic',repr(secret))
            with self.assertRaises(OSError):os.fstat(fd)

    def test_credential_rejects_weak_oversized_readable_linked_and_special_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'admission.key'
            check=lambda:bootstrap.credential_pipe(_path=path,_uid=os.geteuid(),_trusted_root=root)
            for raw,mode in ((b'weak',0o600),(b'x'*65,0o600),(b'x'*32,0o640)):
                path.write_bytes(raw);path.chmod(mode)
                with self.subTest(size=len(raw),mode=mode),self.assertRaises(ValueError):check()
            path.chmod(0o600);alias=root/'alias';os.link(path,alias)
            with self.assertRaises(ValueError):check()
            alias.unlink();path.unlink();path.symlink_to(root/'missing')
            with self.assertRaises((ValueError,FileNotFoundError)):check()
            path.unlink();os.mkfifo(path,mode=0o600)
            with self.assertRaises(ValueError):check()

    def test_credential_parent_must_be_private_and_trusted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);private=root/'credentials';private.mkdir(mode=0o700)
            path=private/'admission.key';path.write_bytes(b'x'*32);path.chmod(0o600)
            private.chmod(0o750)
            with self.assertRaises(ValueError):bootstrap.credential_pipe(_path=path,_uid=os.geteuid(),_trusted_root=root)
            private.chmod(0o700)
            with self.assertRaises(ValueError):bootstrap.credential_pipe(_path=path,_uid=os.geteuid()+1,_trusted_root=root)

    def test_only_exact_named_systemd_socket_for_this_process_is_used(self):
        env={'LISTEN_PID':'123','LISTEN_FDS':'1','LISTEN_FDNAMES':'admission'}
        factory=Mock();listener=factory.return_value
        with patch.object(bootstrap,'validate_listener') as validate:
            self.assertIs(bootstrap.inherited_listener(env,_pid=123,_factory=factory),listener)
            factory.assert_called_once_with(fileno=3);validate.assert_called_once_with(listener,10000)
            for key,value in (('LISTEN_PID','124'),('LISTEN_FDS','2'),('LISTEN_FDNAMES','other')):
                with self.subTest(key=key),self.assertRaises(ValueError):
                    bootstrap.inherited_listener({**env,key:value},_pid=123,_factory=factory)

    def test_listener_is_closed_when_permissions_fail(self):
        factory=Mock()
        with patch.object(bootstrap,'validate_listener',side_effect=ValueError()):
            with self.assertRaises(ValueError):bootstrap.inherited_listener(
                {'LISTEN_PID':'123','LISTEN_FDS':'1','LISTEN_FDNAMES':'admission'},_pid=123,_factory=factory)
        factory.return_value.close.assert_called_once()

    def test_discovery_checks_complete_mounts_unique_actor_and_attests_source(self):
        run=Mock(side_effect=[(mounted_metadata(),0),(b'PID UID GID COMMAND\n789 10000 10000 hermes\n',0)])
        with patch.object(bootstrap,'process_start_ticks',return_value=12),patch.object(bootstrap,'validate_gateway_peer') as validate:
            peer=bootstrap.discover_gateway_peer(_run=run)
        self.assertEqual((peer.pid,peer.uid,peer.gid,peer.start_ticks),(789,10000,10000,12))
        validate.assert_called_once_with(peer,_run=run)

    def test_discovery_rejects_missing_mounts_ambiguity_and_privileged_actor(self):
        cases=[[(delivery_fixtures.metadata(),0)],
               [(mounted_metadata(),0),(b'PID UID GID COMMAND\n789 10000 10000 hermes\n790 10000 10000 hermes\n',0)],
               [(mounted_metadata(),0),(b'PID UID GID COMMAND\n789 0 0 hermes\n',0)]]
        for values in cases:
            with self.subTest(values=len(values)),patch.object(bootstrap,'validate_gateway_peer') as validate:
                with self.assertRaises(ValueError):bootstrap.discover_gateway_peer(_run=Mock(side_effect=values))
                validate.assert_not_called()

    def test_host_and_gateway_policy_must_match_and_use_host_only_namespace(self):
        value=config()
        with patch.object(bootstrap,'load_settings',side_effect=[value,value]):
            self.assertEqual(bootstrap.runtime_settings(),value)
        for other in (replace(value,gateway_uid=10001),replace(value,queue=replace(value.queue,inbox=Path('/opt/data/old')))):
            with patch.object(bootstrap,'load_settings',side_effect=[value,other]):
                with self.assertRaises(ValueError):bootstrap.runtime_settings()

    def test_all_preflight_failures_happen_before_credential_read_and_no_service_activation(self):
        stages=('runtime_settings','validate_state_directories','verify_installed_runtime',
                'inherited_listener','discover_gateway_peer')
        from contextlib import ExitStack
        for failed in stages:
            with self.subTest(stage=failed),ExitStack() as stack,redirect_stdout(io.StringIO()) as output:
                stack.enter_context(patch.object(bootstrap.os,'geteuid',return_value=0))
                for stage in stages:
                    stack.enter_context(patch.object(bootstrap,stage,side_effect=ValueError('PRIVATE') if stage==failed else None,
                                                     return_value=Mock()))
                credential=stack.enter_context(patch.object(bootstrap,'credential_pipe'))
                host=stack.enter_context(patch.object(bootstrap,'ConnectedHost'))
                self.assertEqual(bootstrap.main([]),1)
                credential.assert_not_called();host.assert_not_called()
                self.assertNotIn('PRIVATE',output.getvalue())

    def test_root_gate_rejects_before_any_settings_or_credential_read(self):
        with patch.object(bootstrap.os,'geteuid',return_value=10000),patch.object(bootstrap,'runtime_settings') as settings,patch.object(
                bootstrap,'credential_pipe') as credential,redirect_stdout(io.StringIO()):
            self.assertEqual(bootstrap.main([]),1)
        settings.assert_not_called();credential.assert_not_called()

    def test_bootstrap_transfers_real_pipe_key_only_after_attestation_and_closes_listener(self):
        from contextlib import ExitStack
        uid=os.geteuid();events=[];descriptors=[]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'admission.key';key=b'fixture-service-private-key-12345678'
            path.write_bytes(key);path.chmod(0o600)
            original=bootstrap.credential_pipe
            def credential():
                events.append('credential')
                fd=original(_path=path,_uid=uid,_trusted_root=root);descriptors.append(fd);return fd
            listener=Mock();host=Mock();value=config();peer=Mock()
            with ExitStack() as stack,redirect_stdout(io.StringIO()) as output:
                stack.enter_context(patch.object(bootstrap.os,'geteuid',return_value=0))
                stack.enter_context(patch.object(bootstrap,'runtime_settings',return_value=value))
                for name in ('validate_state_directories','verify_installed_runtime'):
                    stack.enter_context(patch.object(bootstrap,name))
                stack.enter_context(patch.object(bootstrap,'inherited_listener',return_value=listener))
                stack.enter_context(patch.object(bootstrap,'discover_gateway_peer',side_effect=lambda:(events.append('attested') or peer)))
                stack.enter_context(patch.object(bootstrap,'credential_pipe',side_effect=credential))
                stack.enter_context(patch.object(bootstrap,'read_bootstrap_key',side_effect=lambda fd:read_bootstrap_key(fd,expected_uid=uid)))
                factory=stack.enter_context(patch.object(bootstrap,'ConnectedHost',return_value=host))
                self.assertEqual(bootstrap.main([]),0)
            self.assertEqual(events,['attested','credential'])
            self.assertEqual(factory.call_args.args[1].material,key)
            host.serve.assert_called_once();listener.close.assert_called_once()
            self.assertNotIn(key.decode(),output.getvalue())
            for fd in descriptors:
                with self.assertRaises(OSError):os.fstat(fd)

    def test_unknown_runtime_arguments_are_not_ignored_or_echoed(self):
        with patch.object(bootstrap,'runtime_settings') as settings,patch.object(bootstrap.sys,'argv',
                ['bootstrap','PRIVATE_TOKEN']),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(bootstrap.main(),1)
        settings.assert_not_called();self.assertNotIn('PRIVATE_TOKEN',output.getvalue())


if __name__=='__main__':unittest.main()
