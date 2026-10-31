"""Explicit connected host service; not installed or enabled by importing it.

The privileged socket/key/PID bootstrap is identical to broker_service. A single
worker thread wakes on startup recovery and committed admissions only. It never
polls providers, schedules searches, retries uncertain sends, or runs work in the
gateway response path. Shutdown finishes the current durable pass, then stops.
"""
import json
import os
import socket
import threading
import time
from datetime import datetime,timezone

from .admission_broker import AdmissionBroker,process_start_ticks
from .bootstrap_key import read_bootstrap_key
from .broker_service import _main
from .host_worker import run_host_pass
from .settings import load_settings


def _emit(summary):
    print(json.dumps({'host_pass':summary,'installation_ready':False}),flush=True)


class ConnectedHost:
    """Root host component; private callbacks are offline fixture seams only."""
    def __init__(self,settings,secret,peer,*,commercial_bridge=None,epoch=lambda:int(time.time()),
                 clock=lambda:datetime.now(timezone.utc),_run_pass=None,_emit_summary=_emit):
        if commercial_bridge is None:
            if settings.queue.pipeline.protocol!=2:raise ValueError('explicit_commercial_service_binding_required')
            self.broker=AdmissionBroker(settings,secret,peer,clock=epoch)
        else:
            from .commercial.bridge import CommercialBridge
            if (type(commercial_bridge) is not CommercialBridge or commercial_bridge.settings is not settings
                    or commercial_bridge.secret is not secret or settings.queue.pipeline.protocol!=3):
                raise ValueError('exact_commercial_service_binding_required')
            self.broker=commercial_bridge.broker(peer,epoch=epoch)
        self._peer=peer
        self._run_pass=_run_pass or (lambda:run_host_pass(settings,secret,gateway_gid=peer.gid,
                                                       should_stop=self._stop.is_set,commercial_bridge=commercial_bridge,
                                                       epoch=epoch,clock=clock))
        self._emit=_emit_summary
        self._wake=threading.Event();self._stop=threading.Event()
        self._thread=None

    def _work(self):
        while True:
            self._wake.wait();self._wake.clear()
            if self._stop.is_set():return
            while not self._stop.is_set():
                try:
                    summary=self._run_pass()
                    self._emit(summary)
                    # Drain bounded batches after progress, including a backlog
                    # larger than 32. Pending auth, v1, faults and uncertainty do
                    # not become a busy retry loop. A fresh wake/restart is needed
                    # after a fault; original receipts remain authoritative.
                    if summary['errors'] or not sum(summary[name] for name in (
                            'processed','acknowledged','unknown')):break
                except Exception:
                    self._emit({'failed':True,'code':'host_pass_failed'})
                    break

    def serve(self,listener,stop):
        if self._thread is not None:raise ValueError('host_service_already_started')
        self._thread=threading.Thread(target=self._work,name='jev-host-worker',daemon=False)
        self._wake.set()  # Frozen claims and committed completions after restart.
        self._thread.start()
        try:
            listener.settimeout(1)
            while not stop.is_set():
                if (process_start_ticks(self._peer.pid)!=self._peer.start_ticks
                        or not self._thread.is_alive()):
                    raise ValueError('host_service_rebind_required')
                try:connection,_=listener.accept()
                except socket.timeout:continue
                with connection:
                    if self.broker.serve_connection(connection):self._wake.set()
        finally:
            self._stop.set();self._wake.set()
            # Do not abandon a paid subprocess or a send in progress and then
            # automatically replay it. Existing bounded invoker/receipt rules
            # determine the result, including an explicit unknown outcome.
            self._thread.join()


def initialize_root_service(settings_path,key_fd,peer):
    if os.geteuid()!=0:
        if type(key_fd) is int and key_fd>=3:
            try:os.close(key_fd)
            except OSError:pass
        raise ValueError('root_host_service_required')
    secret=read_bootstrap_key(key_fd)
    settings=load_settings(settings_path)
    if settings.queue.writer_uid!=0 or settings.gateway_uid is None:
        raise ValueError('root_host_service_settings_v2_required')
    return ConnectedHost(settings,secret,peer)


def main(argv=None):
    return _main(argv,initialize_root_service,lambda listener,host,stop:host.serve(listener,stop))


if __name__=='__main__':raise SystemExit(main())
