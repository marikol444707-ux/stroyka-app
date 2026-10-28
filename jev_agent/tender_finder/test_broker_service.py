from contextlib import redirect_stdout,redirect_stderr
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from .broker_service import main,validate_listener,serve,validate_gateway_peer
from .admission_broker import GatewayPeer
from .hermes_binding import REVIEWED_MODULES
from .admission_broker import initialize_root_broker


class BrokerServiceTests(unittest.TestCase):
    def test_gateway_attestation_checks_unique_kernel_process_and_source_permissions(self):
        peer=GatewayPeer(123,10000,10000,12345)
        rows=[{'module':name.replace('.','/')+'.py','sha256':digest,'uid':0,'mode':'0o644',
               'directory_permissions':[{'uid':0,'mode':'0o755'}]} for name,digest in REVIEWED_MODULES.items()]
        run=Mock(return_value=(b'PID UID GID COMMAND\n123 10000 10000 hermes\n',0))
        with patch('jev_agent.tender_finder.broker_service.check_hermes_container',return_value='a'*64),patch(
                'jev_agent.tender_finder.broker_service.process_startup_sources',return_value={'gateway_modules':rows}),patch(
                'jev_agent.tender_finder.broker_service.process_start_ticks',return_value=12345):
            validate_gateway_peer(peer,_run=run)
            run.return_value=(b'PID UID GID COMMAND\n123 10000 10000 hermes\n124 10000 10000 hermes\n',0)
            with self.assertRaises(ValueError):validate_gateway_peer(peer,_run=run)
            run.return_value=(b'PID UID GID COMMAND\n123 10000 10000 hermes\n',0)
            rows[0]['mode']='0o666'
            with self.assertRaises(ValueError):validate_gateway_peer(peer,_run=run)
            rows[0]['mode']='0o644';rows[0]['sha256']='0'*64
            with self.assertRaises(ValueError):validate_gateway_peer(peer,_run=run)

    def test_real_listener_requires_socket_and_traversable_protected_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o710);path=root/'broker.sock'
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
                listener.bind(str(path));path.chmod(0o660)
                policy={'_path':path,'_uid':os.geteuid(),'_trusted_directory':root}
                with self.assertRaises(ValueError):validate_listener(listener,os.getegid(),**policy)
                listener.listen(1)
                validate_listener(listener,os.getegid(),**policy)
                path.chmod(0o666)
                with self.assertRaises(ValueError):validate_listener(listener,os.getegid(),**policy)
                path.chmod(0o660);root.chmod(0o777)
                with self.assertRaises(ValueError):validate_listener(listener,os.getegid(),**policy)

    def test_nonroot_service_rejects_before_key_or_configuration_read_and_closes_key(self):
        reader,writer=os.pipe()
        try:
            os.write(writer,b'x'*32)
            with patch('jev_agent.tender_finder.broker_service.os',SimpleNamespace(geteuid=lambda:10000,close=os.close)),patch(
                    'jev_agent.tender_finder.broker_service.initialize_root_broker') as initialize,patch(
                    'jev_agent.tender_finder.broker_service.load_settings') as load,redirect_stdout(io.StringIO()) as out:
                status=main(['--config','/fixture','--key-fd',str(reader),'--listener-fd','100000',
                             '--gateway-pid','100','--gateway-start-ticks','100','--gateway-gid','10000'])
            self.assertEqual(status,1);initialize.assert_not_called();load.assert_not_called()
            self.assertFalse(json.loads(out.getvalue())['installation_ready'])
            with self.assertRaises(OSError):os.fstat(reader)
        finally:os.close(writer)

    def test_nonroot_initializer_closes_pipe_without_consuming_key(self):
        reader,writer=os.pipe()
        try:
            with patch('jev_agent.tender_finder.admission_broker.os',SimpleNamespace(geteuid=lambda:10000,close=os.close)),patch(
                    'jev_agent.tender_finder.admission_broker.read_bootstrap_key') as read:
                with self.assertRaises(ValueError):initialize_root_broker('/fixture',reader,None)
            read.assert_not_called()
            with self.assertRaises(OSError):os.fstat(reader)
        finally:os.close(writer)

    def test_broker_parser_does_not_echo_unknown_secret_arguments(self):
        with redirect_stderr(io.StringIO()) as error:
            with self.assertRaises(SystemExit):main(['--secret','PRIVATE_TOKEN'])
        self.assertNotIn('PRIVATE_TOKEN',error.getvalue())

    def test_stopped_accept_loop_never_starts_search_or_reads_requests(self):
        listener=Mock();broker=Mock();stop=threading.Event();stop.set()
        serve(listener,broker,stop)
        listener.accept.assert_not_called();broker.serve_connection.assert_not_called()
