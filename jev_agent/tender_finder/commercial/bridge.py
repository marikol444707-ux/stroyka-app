"""Opt-in v3 bridge assembly using existing signed queue/publication primitives.

No startup hook, production config migration, key creation, network transport,
timer or send. Operator must bind independent protocol-3 queue/results/registry
directories and reviewed source adapters. Default v2 admission stays v2-only.
"""
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from .contract import validate_request
from .model import Profile
from .preview import render_preview
from .runner import run
from .sources import source_registry
from ..admission_files import publish_admission, read_receipt
from ..bootstrap_key import AdmissionSecret
from ..ingress import issue_admission, make_authenticator
from ..jobs import JobOutcome, _result
from ..queue import consume_file, resume_claim
from ..settings import BridgeSettings
from ..state import RequestLedger, StorageError, _directory


class CommercialBridge:
    def __init__(self,settings,secret,registry_directory,*,profile=Profile(),sources=None,adapters=None):
        if (type(settings) is not BridgeSettings or type(secret) is not AdmissionSecret
                or settings.queue.pipeline.protocol!=3):
            raise ValueError('explicit_protocol3_bridge_required')
        profile.validate()
        settings.owner.validate()
        if settings.owner.scope!=settings.queue.pipeline.scope:
            raise ValueError('commercial_owner_scope_mismatch')
        registry_directory=Path(registry_directory).absolute()
        paths=[Path(path).absolute() for path in (settings.queue.pipeline.private_directory,
               settings.queue.pipeline.result_directory,settings.queue.inbox,settings.worker_admissions,
               registry_directory)]
        if any(a==b or a in b.parents or b in a.parents for i,a in enumerate(paths) for b in paths[i+1:]):
            raise ValueError('independent_commercial_directories_required')
        import os
        fd=_directory(registry_directory,private=True);os.close(fd)
        self.settings,self.secret,self.directory=settings,secret,registry_directory
        self.profile=profile
        self.sources=dict(source_registry() if sources is None else sources)
        self.adapters=dict(adapters or {})
        if set(self.adapters)-set(self.sources):raise ValueError('registered_commercial_adapters_required')
        self.validate=partial(validate_request,sources=self.sources)

    def broker(self,peer,*,epoch):
        """Host-only Unix broker, preserving SO_PEERCRED/PID/start-time checks."""
        from ..admission_broker import AdmissionBroker
        return AdmissionBroker(self.settings,self.secret,peer,clock=epoch,request_validator=self.validate)

    def gateway(self,socket_path,*,current_source,authorize_source):
        """Key-free adapter; production callbacks must come from live Hermes."""
        from ..admission_broker import BrokerClient, BrokerGatewayRuntime
        return BrokerGatewayRuntime(self.settings.owner,BrokerClient(socket_path),
            current_source=current_source,authorize_source=authorize_source,request_validator=self.validate)

    def submit(self,raw,source,*,authorize_source,clock):
        receipt=issue_admission(raw,source,authorize_source=authorize_source,
            bindings=(self.settings.owner,),signing_key=self.secret.material,clock=clock,
            request_validator=self.validate)
        return publish_admission(raw,receipt,self.settings,self.secret,clock=clock)

    def _execute(self,payload,scope,private_directory,*,clock,**_protected):
        if scope!=self.settings.owner.scope or Path(private_directory)!=Path(self.settings.queue.pipeline.private_directory):
            raise StorageError('commercial_executor_scope_mismatch')
        request=self.validate(payload)
        fingerprint=request.fingerprint(scope.company_id)
        with RequestLedger(private_directory,scope) as ledger:
            with ledger.claim(request.request_id,fingerprint) as reservation:
                if reservation.action=='execute':
                    try:
                        selected={key:self.sources[key] for key in request.source_ids}
                        result=run(request.request_id,scope,self.directory,profile=request.profile(self.profile),
                            sources=selected,adapters={key:value for key,value in self.adapters.items() if key in selected},
                            clock=clock)
                        if result.get('status')=='interrupted':raise ValueError('interrupted_registry_run')
                        result.update(schema_version=3,company_id=scope.company_id,protected_scope=scope.key())
                        result['completion_preview']=render_preview(result,scope)
                        result=_result(result,request.request_id,scope)
                    except Exception:
                        result={'ok':False,'status':'failed','request_id':request.request_id,'reason':'execution_failed'}
                    reservation.complete(result)
                return JobOutcome(reservation.action,reservation.result)

    def _bindings(self,epoch,clock):
        return {'authenticate':make_authenticator(bindings=(self.settings.owner,),
                    verification_key=self.secret.material,clock=epoch,
                    receipt_loader=partial(read_receipt,self.settings.worker_admissions,
                                           writer_uid=self.settings.queue.writer_uid)),
                'request_validator':self.validate,'job_executor':self._execute,
                'invoke':None,'clock':clock}

    def consume(self,filename,*,epoch,clock=lambda:datetime.now(timezone.utc)):
        return consume_file(self.settings.queue,filename,**self._bindings(epoch,clock))

    def pending(self):
        from ..queue import pending_claims
        return pending_claims(self.settings.queue)

    def resume(self,handle,*,epoch,clock=lambda:datetime.now(timezone.utc)):
        return resume_claim(self.settings.queue,handle,**self._bindings(epoch,clock))
