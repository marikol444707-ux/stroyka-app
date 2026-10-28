"""Explicit one-file v2 handoff for the existing worker integration.

No daemon, timer, LLM, inbox creation, v1 execution, migration or notification.
authenticate must verify protected ingress provenance; inode UID alone is NOT
Telegram-owner authentication. No permissive default authenticator is provided.
"""
import base64
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

from .contract import MAX_REQUEST_BYTES, _pairs, validate_v2_request
from .pipeline import PipelineConfig, prepare_pipeline, run_request
from .state import RequestBusy, StorageError, _atomic, _directory, _read

INCOMING='.queue-incoming-'
FROZEN='queue-request-'


@dataclass(frozen=True)
class QueueConfig:
    pipeline: PipelineConfig
    inbox: Path
    writer_uid: int


def _decode(raw):
    def constant(_):raise ValueError('nonfinite_request')
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_float=Decimal,parse_constant=constant)
    except (ValueError,UnicodeError,RecursionError):raise ValueError('invalid_request_json') from None
    if type(value) is not dict:raise ValueError('request_object_required')
    return value


def _filename(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.json',name):
        raise ValueError('invalid_queue_filename')
    return name[:-5]


def _handle(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.[a-f0-9]{32}',value):
        raise ValueError('invalid_claim_handle')
    return value.split('.')[0]


def _read_incoming(directory,name,uid,*,strict_mode=True):
    fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
    try:
        before=os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid!=uid or before.st_nlink!=1
                or (strict_mode and stat.S_IMODE(before.st_mode)!=0o600) or before.st_size>MAX_REQUEST_BYTES):
            raise StorageError('unsafe_queue_request')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(MAX_REQUEST_BYTES+1)
        after=os.fstat(fd)
        if (len(raw)>MAX_REQUEST_BYTES or (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=
                (after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise StorageError('queue_request_changed')
        return raw
    finally:os.close(fd)


def _validate(raw,identifier):
    value=_decode(raw)
    if type(value.get('version')) is int and value['version']==1:return None
    request=validate_v2_request(value)
    if request.request_id!=identifier:raise ValueError('queue_request_identity_conflict')
    return value


def _inbox(config):
    if (type(config) is not QueueConfig or type(config.pipeline) is not PipelineConfig
            or type(config.writer_uid) is not int or config.writer_uid<0):
        raise ValueError('protected_queue_config_required')
    path=Path(config.inbox).absolute()
    if path.resolve(strict=True)!=path:raise StorageError('inbox_symlink')
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    info=os.fstat(fd)
    if info.st_uid!=config.writer_uid or stat.S_IMODE(info.st_mode)!=0o700:
        os.close(fd);raise StorageError('unsafe_inbox')
    return fd


@contextmanager
def _private_lock(config):
    prepare_pipeline(config.pipeline)
    fd=_directory(config.pipeline.private_directory,private=True)
    lock=None
    try:
        try:
            lock=os.open('.queue.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=fd)
            os.fchmod(lock,0o600)
        except FileExistsError:
            lock=os.open('.queue.lock',os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        info=os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid()
                or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600):raise StorageError('unsafe_queue_lock')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RequestBusy('queue_busy') from None
        yield fd
    finally:
        if lock is not None:os.close(lock)
        os.close(fd)


def _finish(config,private,handle,authenticate,pipeline_bindings):
    identifier=_handle(handle)
    original=INCOMING+handle
    frozen=FROZEN+handle+'.json'
    stored=_read(private,frozen,private=True)
    if stored is None:
        raw=_read_incoming(private,original,config.writer_uid)
        value=_validate(raw,identifier)
        if value is None:
            return {'status':'needs_review','reason':'claimed_protocol_changed','claim_handle':handle}
        record={'format':1,'scope':config.pipeline.scope.key(),'handle':handle,
                'sha256':hashlib.sha256(raw).hexdigest(),'wire':base64.b64encode(raw).decode('ascii')}
        _atomic(private,frozen,record)
    else:
        record=json.loads(stored)
        if (type(record) is not dict or type(record.get('format')) is not int or record['format']!=1
                or record.get('scope')!=config.pipeline.scope.key() or record.get('handle')!=handle):
            raise StorageError('invalid_frozen_request_identity')
        raw=base64.b64decode(record['wire'],validate=True)
        if len(raw)>MAX_REQUEST_BYTES or hashlib.sha256(raw).hexdigest()!=record.get('sha256'):
            raise StorageError('invalid_frozen_request_digest')
        value=_validate(raw,identifier)
        if value is None:raise StorageError('invalid_frozen_request_protocol')
    digest=hashlib.sha256(raw).hexdigest()
    if authenticate(identifier+'.json',digest,config.pipeline.scope) is not True:
        return {'status':'authorization_pending','claim_handle':handle,'request_id':identifier}
    outcome=run_request(value,config.pipeline,**pipeline_bindings)
    # Only our claimed entry is removed. A newly created inbox file of the same
    # name belongs to another handoff and is never unlinked here.
    try:os.unlink(original,dir_fd=private)
    except FileNotFoundError:pass
    os.fsync(private)
    os.unlink(frozen,dir_fd=private);os.fsync(private)
    return {'status':'processed','claim_handle':handle,**outcome}


def consume_file(config,name,*,authenticate,**pipeline_bindings):
    identifier=_filename(name)
    if not callable(authenticate):raise ValueError('protected_ingress_authenticator_required')
    inbox=_inbox(config)
    try:
        raw=_read_incoming(inbox,name,config.writer_uid,strict_mode=False)
        if _validate(raw,identifier) is None:return {'status':'legacy_v1','handled':False}
        _read_incoming(inbox,name,config.writer_uid)
        with _private_lock(config) as private:
            # Re-read after acquiring the consumer lock; producer may have changed it.
            raw=_read_incoming(inbox,name,config.writer_uid)
            if _validate(raw,identifier) is None:return {'status':'legacy_v1','handled':False}
            if sum(name.startswith(INCOMING) for name in os.listdir(private))>=32:
                raise StorageError('pending_claim_limit')
            handle=identifier+'.'+secrets.token_hex(16)
            os.rename(name,INCOMING+handle,src_dir_fd=inbox,dst_dir_fd=private)
            os.fsync(inbox);os.fsync(private)
            return _finish(config,private,handle,authenticate,pipeline_bindings)
    finally:os.close(inbox)


def resume_claim(config,handle,*,authenticate,**pipeline_bindings):
    _handle(handle)
    if not callable(authenticate):raise ValueError('protected_ingress_authenticator_required')
    with _private_lock(config) as private:
        return _finish(config,private,handle,authenticate,pipeline_bindings)


def pending_claims(config):
    """Bounded recovery handles only; never return request data or credentials."""
    with _private_lock(config) as private:
        result=[]
        for name in os.listdir(private):
            handle=(name[len(INCOMING):] if name.startswith(INCOMING) else
                    name[len(FROZEN):-5] if name.startswith(FROZEN) and name.endswith('.json') else None)
            if handle is not None:
                _handle(handle)
                if handle not in result:result.append(handle)
                if len(result)>32:raise StorageError('pending_claim_limit')
        return sorted(result)
