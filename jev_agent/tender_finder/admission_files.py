"""Detached admission files: publish signed provenance before exposing request.

Only called by an authenticated gateway binding. Directories must exist. There
is no key file, background task, model call, overwrite of a different request, or
claim of a cross-directory transaction; the consumer verifies the signed digest.
"""
import hashlib
import os
from pathlib import Path
import secrets
import stat
import fcntl
import json

from .ingress import make_authenticator
from .queue import _filename
from .state import RequestBusy, RequestConflict, StorageError, _json


def _directory(path,uid):
    path=Path(path).absolute()
    if path.resolve(strict=True)!=path:raise StorageError('admission_directory_symlink')
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    info=os.fstat(fd)
    if info.st_uid!=uid or stat.S_IMODE(info.st_mode)!=0o700:
        os.close(fd);raise StorageError('unsafe_admission_directory')
    return fd


def _read(fd,name,uid,maximum):
    try:file=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
    except FileNotFoundError:return None
    try:
        info=os.fstat(file)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=uid or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>maximum):
            raise StorageError('unsafe_admission_file')
        with os.fdopen(file,'rb',closefd=False) as stream:data=stream.read(maximum+1)
        if len(data)>maximum:raise StorageError('admission_file_size_limit')
        return data
    finally:os.close(file)


def _write(fd,name,data,uid,*,replace=False):
    temporary='.admission-'+secrets.token_hex(16)
    file=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
    try:
        os.fchmod(file,0o600)
        with os.fdopen(file,'wb') as stream:
            file=None;stream.write(data);stream.flush();os.fsync(stream.fileno())
        if replace:os.replace(temporary,name,src_dir_fd=fd,dst_dir_fd=fd)
        else:
            try:os.link(temporary,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
            except FileExistsError:
                if _read(fd,name,uid,len(data))!=data:raise RequestConflict('admission_publication_conflict')
                return False
        os.fsync(fd);return True
    finally:
        if file is not None:os.close(file)
        try:os.unlink(temporary,dir_fd=fd);os.fsync(fd)
        except FileNotFoundError:pass


def read_receipt(directory,filename,*,writer_uid):
    identifier=_filename(filename)
    fd=_directory(directory,writer_uid)
    try:return _read(fd,identifier+'.auth.json',writer_uid,4096)
    finally:os.close(fd)


def publish_admission(raw,receipt,settings,secret,*,clock):
    """Validate current admission before any file writes; no request overwrite.

    A byte-identical retry reuses a still-valid receipt. Renewal requires a new
    authenticated admission with exactly the same owner and wire identity.
    """
    if os.geteuid()!=settings.queue.writer_uid:raise StorageError('gateway_runtime_uid_mismatch')
    body=receipt['body'];name=body['request_id']+'.json'
    identifier=_filename(name);digest=hashlib.sha256(raw).hexdigest()
    policies=(settings.owner,);scope=settings.owner.scope
    encoded=_json(receipt)
    if len(encoded)>4096 or len(raw)>32768:raise StorageError('admission_size_limit')
    def verifier(data,when):
        return make_authenticator(receipt_loader=lambda filename:data,bindings=policies,
            verification_key=secret.material,clock=when)(name,digest,scope)
    if not verifier(encoded,clock):raise StorageError('valid_current_admission_required')
    inbox=_directory(settings.gateway_inbox,settings.queue.writer_uid)
    admissions=None;lock=None
    try:
        admissions=_directory(settings.gateway_admissions,settings.queue.writer_uid)
        try:
            lock=os.open('.admissions.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=admissions)
            os.fchmod(lock,0o600)
        except FileExistsError:lock=os.open('.admissions.lock',os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=admissions)
        info=os.fstat(lock)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=settings.queue.writer_uid
                or info.st_nlink!=1 or stat.S_IMODE(info.st_mode)!=0o600):raise StorageError('unsafe_admission_lock')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RequestBusy('admission_publisher_busy') from None
        pending=_read(inbox,name,settings.queue.writer_uid,32768)
        if pending is not None and pending!=raw:raise RequestConflict('queued_request_wire_conflict')
        old=_read(admissions,identifier+'.auth.json',settings.queue.writer_uid,4096)
        renew=False
        if old is not None:
            if verifier(old,clock):encoded=old
            else:
                try:issued=json.loads(old)['body']['issued_at']
                except (ValueError,KeyError,TypeError):raise RequestConflict('prior_admission_conflict') from None
                if not verifier(old,lambda:issued):raise RequestConflict('prior_admission_identity_conflict')
                renew=True
        _write(admissions,identifier+'.auth.json',encoded,settings.queue.writer_uid,replace=renew)
        created=_write(inbox,name,raw,settings.queue.writer_uid)
        return {'request_id':identifier,'queued':True,'request_file_created':created,
                'admission_renewed':renew,'search_executed':False,'notification_sent':False}
    finally:
        if lock is not None:os.close(lock)
        if admissions is not None:os.close(admissions)
        os.close(inbox)
