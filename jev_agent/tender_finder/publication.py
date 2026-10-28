"""Publish a durable receipt and enqueue a completion event without sending it.

Integration library only. Never adopt an unbound nonempty legacy result folder,
delete queue inputs, overwrite latest.json, start services or send notifications.
A new channel is bound to exactly one protected company/principal Scope.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
import stat

from .state import (RequestLedger, RequestBusy, RequestConflict, Scope, StorageError,
                    _atomic, _directory, _identifier, _json, _read)

CHANNEL = '.jev-channel'
CHANNEL_LOCK = '.jev-channel.lock'


@dataclass(frozen=True)
class Publication:
    disposition: str
    completion_event_id: str
    notification_sent: bool = False
    actual_hermes_read_verified: bool = False


@contextmanager
def _channel(path, scope, result_gid):
    fd = _directory(path,private=False,result_gid=result_gid)
    lock = None
    expected = {'format':1,'scope':scope.key(),'result_gid':result_gid}
    try:
        # Reject the installed legacy folder before writing even our lock.
        entries = set(os.listdir(fd))
        if CHANNEL not in entries and entries - {CHANNEL_LOCK}:
            raise StorageError('legacy_result_channel_requires_review')
        try:
            lock = os.open(CHANNEL_LOCK,os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                           0o600,dir_fd=fd)
            os.fchmod(lock,0o600)
        except FileExistsError:
            lock = os.open(CHANNEL_LOCK,os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK,dir_fd=fd)
        info = os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            raise StorageError('unsafe_channel_lock')
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RequestBusy('result_channel_busy') from None
        raw = _read(fd,CHANNEL,private=True)
        if raw is None:
            if set(os.listdir(fd)) - {CHANNEL_LOCK}:
                raise StorageError('legacy_result_channel_requires_review')
            _atomic(fd,CHANNEL,expected)
        elif raw != _json(expected):
            raise RequestConflict('result_channel_scope_conflict')
        yield fd
    finally:
        if lock is not None:
            os.close(lock)
        os.close(fd)


def _write_event(ledger, event_id, result):
    event = {'format':1,'event_id':event_id,'kind':'jev_result_published',
             'scope':ledger.scope_key,'request_id':result['request_id'],
             'result_sha256':hashlib.sha256(_json(result)).hexdigest(),
             'delivery_status':'pending','notification_sent':False}
    # Private, immutable event. A supported Hermes consumer must supply delivery
    # acknowledgement/idempotency; merely creating this file sends nothing.
    name = 'completion-'+event_id+'.json'
    existing = _read(ledger.fd,name,private=True)
    if existing is not None and existing != _json(event):
        raise RequestConflict('completion_event_conflict')
    _atomic(ledger.fd,name,event)


def publish_committed_result(private_directory, scope, result_directory, request_id,
                             fingerprint, *, result_gid):
    """Existing receipt -> no-clobber result -> durable private completion event.

    Retrying after a publication/event crash never invokes search. No automatic
    retry/delivery promise for Telegram, whose supported mechanism is unbound.
    Paths, scope and group must come from protected configuration/authentication.
    """
    if type(scope) is not Scope:
        raise StorageError('protected_scope_required')
    if type(result_gid) is not int or not 0 <= result_gid < 2**31:
        raise StorageError('protected_result_gid_required')
    request_id = _identifier(request_id)
    with RequestLedger(private_directory,scope) as ledger:
        with ledger.claim(request_id,fingerprint,existing_only=True) as reservation:
            result = reservation.result
            if type(result) is not dict or result.get('request_id') != request_id:
                raise StorageError('committed_result_required')
            with _channel(result_directory,scope,result_gid) as fd:
                created = _atomic(fd,request_id+'.json',result,public_gid=result_gid)
                event_id = hashlib.sha256(_json({'scope':ledger.scope_key,'request_id':request_id,
                                                 'fingerprint':fingerprint})).hexdigest()
                _write_event(ledger,event_id,result)
            return Publication('published' if created else 'already_published',event_id)
