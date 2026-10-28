"""One v2 job through discovery, evidence, durable receipt and result publication.

For a protected worker binding, not a deployment command. Legacy namespaces are
never adopted. This module does not remove inbox files or send notifications.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import stat

from .contract import validate_v2_request
from .discovery import verify_installed_runtime
from .jobs import process_request
from .publication import CHANNEL, CHANNEL_LOCK, _channel, publish_committed_result
from .state import (RequestLedger, Scope, StorageError, RequestBusy, RequestConflict,
                    _atomic, _directory, _json, _read)

NAMESPACE = '.jev-private-namespace'
NAMESPACE_LOCK = NAMESPACE+'.lock'


@dataclass(frozen=True)
class PipelineConfig:
    scope: Scope
    private_directory: Path
    result_directory: Path
    result_gid: int


def _bind_private(config):
    fd=_directory(config.private_directory,private=True)
    lock=None
    try:
        expected={'format':1,'scope':config.scope.key(),
                  'result_directory':str(Path(config.result_directory).resolve(strict=True)),
                  'result_gid':config.result_gid}
        if NAMESPACE not in os.listdir(fd) and set(os.listdir(fd))-{NAMESPACE_LOCK}:
            raise StorageError('legacy_private_namespace_requires_review')
        try:
            lock=os.open(NAMESPACE_LOCK,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=fd)
            os.fchmod(lock,0o600)
        except FileExistsError:
            lock=os.open(NAMESPACE_LOCK,os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        info=os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600:
            raise StorageError('unsafe_namespace_lock')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RequestBusy('namespace_busy') from None
        raw=_read(fd,NAMESPACE,private=True)
        if raw is None:
            if set(os.listdir(fd))-{NAMESPACE_LOCK}:raise StorageError('legacy_private_namespace_requires_review')
            _atomic(fd,NAMESPACE,expected)
        elif raw!=_json(expected):raise RequestConflict('private_namespace_scope_conflict')
    finally:
        if lock is not None:os.close(lock)
        os.close(fd)


def run_request(payload, config, *, invoke, verify_runtime=verify_installed_runtime,
                clock=lambda:datetime.now(timezone.utc)):
    """No second search when replaying after a result/event publication failure.

    config and callbacks must be protected worker bindings, not model JSON.
    v1 must remain with its reviewed existing handler until migration is agreed.
    """
    if type(config) is not PipelineConfig or type(config.scope) is not Scope:
        raise StorageError('protected_pipeline_config_required')
    config.scope.key()
    if type(config.result_gid) is not int or not 0<=config.result_gid<2**31:
        raise StorageError('protected_result_gid_required')
    request=validate_v2_request(payload)
    fingerprint=request.fingerprint(config.scope.company_id)
    # Validate public channel before any search, including a lost private receipt.
    # A foreign or legacy result must never cause a new paid search first.
    with _channel(config.result_directory,config.scope,config.result_gid) as public:
        _bind_private(config)
        existing=_read(public,request.request_id+'.json',private=False,public_gid=config.result_gid)
        if existing is not None:
            with RequestLedger(config.private_directory,config.scope) as ledger:
                with ledger.claim(request.request_id,fingerprint,existing_only=True) as receipt:
                    if _json(receipt.result)!=existing:
                        raise RequestConflict('published_receipt_conflict')
    job=process_request(payload,config.scope,config.private_directory,invoke=invoke,
                        verify_runtime=verify_runtime,clock=clock)
    publication=publish_committed_result(config.private_directory,config.scope,config.result_directory,
                                         request.request_id,fingerprint,result_gid=config.result_gid)
    return {'request_id':request.request_id,'job_disposition':job.disposition,
            'publication_disposition':publication.disposition,'result':job.result,
            'completion_event_id':publication.completion_event_id,
            'notification_sent':False,'actual_hermes_read_verified':False}
