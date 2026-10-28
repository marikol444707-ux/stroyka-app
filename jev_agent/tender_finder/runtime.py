"""Explicit bootstrap assembly. No daemon, timer, automatic import hook or deploy.

Gateway model-facing submit accepts request bytes only. Runtime source and
authorization come from mandatory protected callbacks supplied by actual Hermes
startup integration; environment/session text is never an identity fallback.
"""
from functools import partial
import time

from .admission_files import publish_admission, read_receipt
from .bootstrap_key import AdmissionSecret, read_bootstrap_key
from .ingress import issue_admission, make_authenticator
from .invoker import invoke_cli
from .queue import consume_file, resume_claim, pending_claims
from .settings import BridgeSettings, load_settings


def _epoch():return int(time.time())


class GatewayRuntime:
    def __init__(self,settings,secret,*,authorize_source,current_source,clock=_epoch):
        if (type(settings) is not BridgeSettings or type(secret) is not AdmissionSecret
                or not callable(authorize_source) or not callable(current_source)):
            raise ValueError('protected_gateway_bootstrap_required')
        self._settings=settings;self._secret=secret
        self._authorize=authorize_source;self._source=current_source;self._clock=clock

    def submit(self,raw):
        receipt=issue_admission(raw,self._source(),authorize_source=self._authorize,
            bindings=(self._settings.owner,),signing_key=self._secret.material,clock=self._clock)
        return publish_admission(raw,receipt,self._settings,self._secret,clock=self._clock)


class WorkerRuntime:
    def __init__(self,settings,secret,*,invoke=None,verify_runtime=None,clock=_epoch):
        if type(settings) is not BridgeSettings or type(secret) is not AdmissionSecret:
            raise ValueError('protected_worker_bootstrap_required')
        self._settings=settings
        self._authenticate=make_authenticator(bindings=(settings.owner,),verification_key=secret.material,
            receipt_loader=partial(read_receipt,settings.worker_admissions,writer_uid=settings.queue.writer_uid),clock=clock)
        self._pipeline={'invoke':invoke if invoke is not None else partial(invoke_cli,scope=settings.owner.scope)}
        if verify_runtime is not None:self._pipeline['verify_runtime']=verify_runtime

    def consume(self,filename):
        return consume_file(self._settings.queue,filename,authenticate=self._authenticate,**self._pipeline)

    def resume(self,handle):
        return resume_claim(self._settings.queue,handle,authenticate=self._authenticate,**self._pipeline)

    def pending(self):return pending_claims(self._settings.queue)


def initialize_gateway(settings_path,key_fd,*,authorize_source,current_source):
    # Consume/close inherited secret descriptor even if later settings fail.
    secret=read_bootstrap_key(key_fd)
    settings=load_settings(settings_path)
    return GatewayRuntime(settings,secret,authorize_source=authorize_source,current_source=current_source)


def initialize_worker(settings_path,key_fd):
    secret=read_bootstrap_key(key_fd)
    return WorkerRuntime(load_settings(settings_path),secret)
