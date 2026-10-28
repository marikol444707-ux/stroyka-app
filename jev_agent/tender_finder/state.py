"""POSIX durable request receipts and no-clobber result publication.

Integration component, not a new queue/worker. Paths, principal and company must
come from protected server configuration. Existing v1 `.seen` files/results are
never adopted, reset, or migrated. A crashed running reservation becomes an
explicit interrupted failure; it is never silently replayed as another search.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_RESULT_BYTES = 1024 * 1024


class StorageError(ValueError):
    pass


class RequestBusy(StorageError):
    pass


class RequestConflict(StorageError):
    pass


def _json(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError):
        raise StorageError('invalid_json_result') from None
    if len(raw) > MAX_STATE_BYTES:
        raise StorageError('state_size_limit')
    return raw


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise StorageError('invalid_request_id')
    return value


def _directory(path, *, private, result_gid=None):
    path = Path(path).absolute()
    if path.resolve(strict=True) != path:
        raise StorageError('directory_symlink')
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    expected_mode = 0o700 if private else 0o750
    bad = info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o777 != expected_mode
    if not private:
        bad = bad or info.st_gid != result_gid
    if bad:
        os.close(fd)
        raise StorageError('untrusted_storage_directory')
    return fd


def _read(directory, name, *, private, public_gid=None):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None
    except OSError:
        raise StorageError('unsafe_storage_file') from None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_size > MAX_STATE_BYTES
                or private and (stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1)):
            raise StorageError('unsafe_storage_file')
        if public_gid is not None and (info.st_gid != public_gid or stat.S_IMODE(info.st_mode) != 0o640):
            raise StorageError('unsafe_result_permissions')
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, min(65536, MAX_STATE_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_STATE_BYTES:
                raise StorageError('state_size_limit')
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        os.close(fd)


def _atomic(directory, name, value, *, public_gid=None, replace=False):
    raw = _json(value)
    temporary = '.jev-receipt-' + secrets.token_hex(16) + '.tmp'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        os.fchmod(fd, 0o600)
        if public_gid is not None:
            os.fchown(fd, os.geteuid(), public_gid)
            os.fchmod(fd, 0o640)
        with os.fdopen(fd, 'wb') as output:
            fd = None
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        if replace:
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
            return True
        try:
            # Atomic, portable POSIX no-replace publication. A consumer sees the
            # final filename only after the entire validated JSON is fsynced.
            os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            os.fsync(directory)
            return True
        except FileExistsError:
            existing = _read(directory, name, private=False, public_gid=public_gid)
            if existing is None or _digest(existing) != _digest(raw):
                raise RequestConflict('existing_result_conflict')
            return False
    finally:
        if fd is not None:
            os.close(fd)
        try:
            os.unlink(temporary, dir_fd=directory)
            os.fsync(directory)
        except FileNotFoundError:
            pass


@dataclass(frozen=True)
class Scope:
    company_id: int
    principal_subject: str

    def key(self):
        if type(self.company_id) is not int or self.company_id <= 0 or not isinstance(self.principal_subject, str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_:.@-]{0,127}', self.principal_subject):
            raise StorageError('protected_scope_required')
        return _digest(_json({'company':self.company_id, 'principal':self.principal_subject}))


class Reservation:
    def __init__(self, ledger, name, record, action):
        self._ledger = ledger
        self._name = name
        self._record = record
        self.action = action
        self._finished = action != 'execute'
        self._commit_started = False

    @property
    def result(self):
        return deepcopy(self._record.get('result'))

    def complete(self, result):
        if self._finished or self._commit_started or self.action != 'execute':
            raise StorageError('reservation_not_executable')
        if type(result) is not dict:
            raise StorageError('result_object_required')
        if 'request_id' in result and result['request_id'] != self._record['request_id']:
            raise StorageError('result_request_mismatch')
        if 'company_id' in result and (type(result['company_id']) is not int or result['company_id'] != self._ledger.scope.company_id):
            raise StorageError('result_company_mismatch')
        raw = _json(result)
        if len(raw) > MAX_RESULT_BYTES:
            raise StorageError('result_size_limit')
        next_record = {**self._record, 'state':'completed', 'result':json.loads(raw), 'result_sha256':_digest(raw)}
        self._commit_started = True
        _atomic(self._ledger.fd, self._name, next_record, replace=True)
        self._record = next_record
        self._finished = True


class RequestLedger:
    def __init__(self, private_directory, scope, *, namespace='ledger'):
        if namespace not in ('ledger','delivery'):
            raise StorageError('invalid_receipt_namespace')
        self.namespace=namespace
        self.scope = scope
        self.scope_key = scope.key()
        self.fd = _directory(private_directory, private=True)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        os.close(self.fd)

    @contextmanager
    def claim(self, request_id, fingerprint, *, existing_only=False):
        if type(existing_only) is not bool:
            raise StorageError('invalid_receipt_mode')
        request_id = _identifier(request_id)
        if not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint):
            raise StorageError('invalid_fingerprint')
        name = self.namespace + '-' + self.scope_key + '-' + request_id + '.json'
        try:
            lock = os.open(name + '.lock', os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK,
                           0o600, dir_fd=self.fd)
            try:
                os.fchmod(lock, 0o600)
            except BaseException:
                os.close(lock)
                raise
        except FileExistsError:
            lock = os.open(name + '.lock', os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        reservation = None
        try:
            info = os.fstat(lock)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
                raise StorageError('unsafe_lock_file')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RequestBusy('request_in_progress') from None
            raw = _read(self.fd, name, private=True)
            record = None
            if raw is not None:
                try:
                    def pairs(values):
                        result = {}
                        for key, value in values:
                            if key in result:
                                raise ValueError('duplicate_field')
                            result[key] = value
                        return result
                    record = json.loads(raw, object_pairs_hook=pairs)
                except (ValueError, UnicodeError, RecursionError):
                    raise StorageError('corrupt_receipt') from None
                if (type(record) is not dict or type(record.get('format')) is not int or record.get('format') != 1 or record.get('scope') != self.scope_key
                        or type(record.get('company_id')) is not int or record['company_id'] != self.scope.company_id
                        or record.get('principal_subject') != self.scope.principal_subject
                        or record.get('request_id') != request_id or record.get('state') not in ('running','completed','interrupted')):
                    raise StorageError('invalid_receipt_identity')
                if record.get('fingerprint') != fingerprint:
                    raise RequestConflict('request_id_conflict')
            if record is None:
                if existing_only:
                    raise StorageError('receipt_missing')
                record = {'format':1,'scope':self.scope_key,'company_id':self.scope.company_id,
                          'principal_subject':self.scope.principal_subject,
                          'request_id':request_id,'fingerprint':fingerprint,'state':'running'}
                _atomic(self.fd, name, record, replace=True)
                reservation = Reservation(self, name, record, 'execute')
            elif record['state'] == 'running':
                failure = {'ok':False,'status':'failed','reason':'execution_interrupted','request_id':request_id}
                record = {**record,'state':'interrupted','result':failure,'result_sha256':_digest(_json(failure))}
                _atomic(self.fd, name, record, replace=True)
                reservation = Reservation(self, name, record, 'interrupted')
            else:
                if type(record.get('result')) is not dict or record.get('result_sha256') != _digest(_json(record['result'])):
                    raise StorageError('corrupt_cached_result')
                if ('request_id' in record['result'] and record['result']['request_id'] != request_id
                        or 'company_id' in record['result'] and (type(record['result']['company_id']) is not int
                            or record['result']['company_id'] != self.scope.company_id)):
                    raise StorageError('cached_result_scope_mismatch')
                reservation = Reservation(self, name, record, 'cached')
            try:
                yield reservation
            except BaseException:
                if not reservation._finished and not reservation._commit_started:
                    reservation.complete({'ok':False,'status':'failed','reason':'execution_failed','request_id':request_id})
                raise
            finally:
                if not reservation._finished and not reservation._commit_started:
                    reservation.complete({'ok':False,'status':'failed','reason':'execution_not_completed','request_id':request_id})
        finally:
            os.close(lock)


def publish_result_once(result_directory, request_id, result, *, result_gid):
    """Caller selects an authorized result directory; never overwrite another result.

    A process crash can leave a hidden temporary hardlink. Retrying the same
    committed result is safe and does not require deleting/rewriting its target.
    Readability by the actual Hermes UID must still be tested at integration.
    """
    request_id = _identifier(request_id)
    if type(result) is not dict or 'request_id' in result and result['request_id'] != request_id:
        raise StorageError('result_request_mismatch')
    if len(_json(result)) > MAX_RESULT_BYTES:
        raise StorageError('result_size_limit')
    if type(result_gid) is not int or not 0 <= result_gid < 2**31:
        raise StorageError('protected_result_gid_required')
    directory = _directory(result_directory, private=False, result_gid=result_gid)
    try:
        return _atomic(directory, request_id + '.json', result, public_gid=result_gid)
    finally:
        os.close(directory)
