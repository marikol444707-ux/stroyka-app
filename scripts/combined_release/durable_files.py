"""Durable, narrowly scoped local file replacements; no DB/services or CLI.

The caller must hold its shared writer lock for prepare/apply/recovery/rollback.
The private evidence directory is trusted control data. This module refuses
symlinks and observed concurrent changes; it is not a sandbox against a hostile
privileged writer racing filesystem calls. Original empty/new directories may
remain. No recursive cleanup or unjournaled target deletion is performed.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat


class Stop(RuntimeError):
    """State is unsafe or ambiguous; preserve evidence and require review."""


def digest(body):
    return hashlib.sha256(body).hexdigest()


def _identity(info):
    # rename changes ctime, so record the attributes that survive OUR rename.
    return [info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode), info.st_uid,
            info.st_gid, info.st_mtime_ns, info.st_size]


def _anchor(path, private=False):
    path = Path(path)
    try:
        if not path.is_absolute() or path.resolve(strict=True) != path:
            raise Stop('UNSAFE_DIRECTORY')
        info = path.lstat()
    except (OSError, RuntimeError) as error:
        raise Stop('UNSAFE_DIRECTORY') from error
    if not stat.S_ISDIR(info.st_mode):
        raise Stop('UNSAFE_DIRECTORY')
    if private and (stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid()):
        raise Stop('EVIDENCE_NOT_PRIVATE')
    return _identity(info)[:5]


def _name(name):
    if not isinstance(name, str) or '\x00' in name or any(
            part in ('', '.', '..') for part in name.split('/')):
        raise Stop('UNSAFE_RELATIVE_PATH')
    return name


def _manifest(manifest):
    if not isinstance(manifest, dict) or not manifest:
        raise Stop('EMPTY_OR_BAD_MANIFEST')
    result = {}
    for name, entry in manifest.items():
        _name(name)
        if not isinstance(entry, dict) or set(entry) != {'before_sha256', 'after_sha256'}:
            raise Stop('BAD_MANIFEST_FIELDS')
        for key, value in entry.items():
            if value is None and key == 'before_sha256':
                continue
            if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
                raise Stop('BAD_MANIFEST_HASH')
        result[name] = dict(entry)
    names = set(result)
    if any('/'.join(name.split('/')[:i]) in names for name in names for i in range(1, len(name.split('/')))):
        raise Stop('MANIFEST_PATH_CONFLICT')
    return result


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Transaction:
    VERSION = 1

    def __init__(self, root, evidence, manifest):
        self.root = Path(root)
        self.evidence = Path(evidence)
        self.root_identity = _anchor(self.root)
        self.evidence_identity = _anchor(self.evidence, private=True)
        if self.root == self.evidence or self.root in self.evidence.parents:
            raise Stop('EVIDENCE_INSIDE_TARGET_ROOT')
        self.directory = self.evidence / 'files'
        self.journal = self.directory / 'journal.json'
        self.manifest = _manifest(manifest)
        self.state = None

    def _check_roots(self):
        if _anchor(self.root) != self.root_identity or _anchor(self.evidence, True) != self.evidence_identity:
            raise Stop('ROOT_OR_EVIDENCE_CHANGED')
        if self.state is not None and _anchor(self.directory, True) != self.state['directory_identity']:
            raise Stop('JOURNAL_DIRECTORY_CHANGED')

    @contextmanager
    def _parent(self, name, create=False):
        self._check_roots()
        parts = _name(name).split('/')
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                try:
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        yield None, parts[-1]
                        return
                    os.mkdir(part, 0o755, dir_fd=fd)
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        os.fchown(next_fd, self.root_identity[3], self.root_identity[4])
                        os.fchmod(next_fd, 0o755)
                        os.fsync(next_fd)
                        os.fsync(fd)
                    except BaseException:
                        os.close(next_fd)
                        raise
                os.close(fd)
                fd = next_fd
            yield fd, parts[-1]
        except OSError as error:
            if error.errno in (20, 40):  # ENOTDIR / ELOOP, including ancestor links.
                raise Stop('SYMLINK_OR_NON_DIRECTORY_COMPONENT') from error
            raise
        finally:
            os.close(fd)

    def _read(self, name):
        with self._parent(name) as (parent, leaf):
            if parent is None:
                return None, None
            try:
                fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            except FileNotFoundError:
                return None, None
            try:
                initial = os.fstat(fd)
                if not stat.S_ISREG(initial.st_mode):
                    raise Stop('NOT_REGULAR_FILE')
                chunks = []
                while True:
                    chunk = os.read(fd, 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                body = b''.join(chunks)
                if _identity(os.fstat(fd)) != _identity(initial):
                    raise Stop('FILE_CHANGED_DURING_READ')
                # The opened inode must still be the inode at this name.
                if _identity(os.stat(leaf, dir_fd=parent, follow_symlinks=False)) != _identity(initial):
                    raise Stop('FILE_REPLACED_DURING_READ')
                return {'identity': _identity(initial), 'sha256': digest(body)}, body
            finally:
                os.close(fd)

    def _save(self):
        self._check_roots()
        if self.journal.exists() or self.journal.is_symlink():
            self._private_read(self.journal)
        temporary = self.directory / ('.journal-' + secrets.token_hex(12))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(json.dumps(self.state, sort_keys=True, separators=(',', ':')).encode() + b'\n')
                stream.flush()
                os.fchmod(stream.fileno(), 0o600)
                os.fsync(stream.fileno())
            os.replace(temporary, self.journal)
            _sync_dir(self.directory)
        finally:
            # This path is an unpredictable private journal temp, not app data.
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _private_read(path):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid():
                raise Stop('UNSAFE_PRIVATE_FILE')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                return stream.read()
        finally:
            os.close(fd)

    def prepare(self):
        if self.state is not None or self.directory.exists() or self.directory.is_symlink():
            raise Stop('TRANSACTION_EVIDENCE_ALREADY_EXISTS')
        self._check_roots()
        originals = {}
        for name, entry in self.manifest.items():
            record, body = self._read(name)
            if (record['sha256'] if record else None) != entry['before_sha256']:
                raise Stop('PREEXISTING_PATH_CHANGED_OR_COLLISION')
            originals[name] = (record, body)
        self.directory.mkdir(mode=0o700)
        os.chmod(self.directory, 0o700)
        backup_dir = self.directory / 'backups'
        backup_dir.mkdir(mode=0o700)
        os.chmod(backup_dir, 0o700)
        entries = {}
        for index, (name, (record, body)) in enumerate(originals.items()):
            backup = f'{index:08d}' if body is not None else None
            if backup is not None:
                fd = os.open(backup_dir / backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(body)
                    stream.flush()
                    os.fchmod(stream.fileno(), 0o600)
                    os.fsync(stream.fileno())
            entries[name] = {'before': record, 'backup': backup, 'apply': None, 'rollback': None}
        _sync_dir(backup_dir)
        _sync_dir(self.directory)
        _sync_dir(self.evidence)
        self.state = {'version': self.VERSION, 'root': str(self.root), 'root_identity': self.root_identity,
                      'evidence_identity': self.evidence_identity, 'directory_identity': _anchor(self.directory, True),
                      'manifest': self.manifest, 'phase': 'prepared', 'entries': entries}
        # Backups, snapshots and before-state must agree before publishing intent.
        self._preflight()
        self._save()
        return self

    @classmethod
    def load(cls, root, evidence):
        evidence = Path(evidence)
        _anchor(evidence, True)
        _anchor(evidence / 'files', True)
        try:
            state = json.loads(cls._private_read(evidence / 'files' / 'journal.json'))
            if state['version'] != cls.VERSION or state['root'] != str(Path(root)):
                raise Stop('JOURNAL_ROOT_OR_VERSION_MISMATCH')
            transaction = cls(root, evidence, state['manifest'])
            if state['root_identity'] != transaction.root_identity or state['evidence_identity'] != transaction.evidence_identity:
                raise Stop('ROOT_OR_EVIDENCE_CHANGED')
            if set(state['entries']) != set(transaction.manifest):
                raise Stop('BAD_JOURNAL_ENTRIES')
            if state['phase'] not in ('prepared', 'applying', 'applied', 'rolling_back', 'rolled_back'):
                raise Stop('BAD_JOURNAL_PHASE')
            transaction.state = state
            transaction._preflight()
            return transaction
        except (KeyError, TypeError, ValueError) as error:
            raise Stop('BAD_JOURNAL') from error

    def _backup(self, name):
        entry = self.state['entries'][name]
        before = entry['before']
        if before is None:
            if entry['backup'] is not None or self.manifest[name]['before_sha256'] is not None:
                raise Stop('BAD_BACKUP_RECORD')
            return None
        if not isinstance(entry['backup'], str) or not re.fullmatch('[0-9]{8}', entry['backup']):
            raise Stop('BAD_BACKUP_NAME')
        _anchor(self.directory / 'backups', True)
        body = self._private_read(self.directory / 'backups' / entry['backup'])
        if digest(body) != self.manifest[name]['before_sha256'] or before['sha256'] != digest(body):
            raise Stop('BACKUP_CONTENT_HASH_MISMATCH')
        return body

    def _classify(self, name):
        entry = self.state['entries'][name]
        current, _ = self._read(name)
        before, applied, rollback = entry['before'], entry['apply'], entry['rollback']
        if rollback is not None:
            expected = rollback['file'] if rollback['kind'] == 'replace' else None
            if current == expected:
                return 'restored'
            if rollback['done']:
                raise Stop('CONCURRENT_EDIT_REQUIRES_MANUAL_REVIEW')
            if applied is not None and current == applied['file']:
                return 'installed'
        elif applied is not None and current == applied['file']:
            return 'installed'
        elif (applied is None or not applied['done']) and current == before:
            return 'untouched'
        raise Stop('CONCURRENT_EDIT_REQUIRES_MANUAL_REVIEW')

    def _validate_records(self):
        def file_record(record, expected_hash, attributes=None):
            if not isinstance(record, dict) or set(record) != {'identity', 'sha256'}:
                raise Stop('BAD_FILE_RECORD')
            identity = record['identity']
            if (record['sha256'] != expected_hash or not isinstance(identity, list)
                    or len(identity) != 7 or any(type(value) is not int or value < 0 for value in identity)
                    or identity[2] > 0o7777):
                raise Stop('BAD_FILE_IDENTITY')
            if attributes is not None and identity[2:5] != attributes:
                raise Stop('JOURNAL_ATTRIBUTES_MISMATCH')

        if set(self.state['entries']) != set(self.manifest):
            raise Stop('BAD_JOURNAL_ENTRIES')
        for name, entry in self.state['entries'].items():
            if not isinstance(entry, dict) or set(entry) != {'before', 'backup', 'apply', 'rollback'}:
                raise Stop('BAD_JOURNAL_ENTRY')
            hashes = self.manifest[name]
            before = entry['before']
            if hashes['before_sha256'] is None:
                if before is not None:
                    raise Stop('BAD_ORIGINAL_RECORD')
                attributes = [0o644, self.root_identity[3], self.root_identity[4]]
            else:
                file_record(before, hashes['before_sha256'])
                attributes = before['identity'][2:5]
            for key in ('apply', 'rollback'):
                action = entry[key]
                if action is None:
                    continue
                fields = {'temp', 'file', 'done'} | ({'kind'} if key == 'rollback' else set())
                if not isinstance(action, dict) or set(action) != fields or type(action['done']) is not bool:
                    raise Stop('BAD_ACTION_RECORD')
                if key == 'rollback':
                    if entry['apply'] is None:
                        raise Stop('ROLLBACK_WITHOUT_APPLY_INTENT')
                    if action['kind'] == 'remove' and before is None:
                        if action['temp'] is not None or action['file'] is not None:
                            raise Stop('BAD_REMOVE_INTENT')
                        continue
                    if action['kind'] != 'replace' or before is None:
                        raise Stop('BAD_ROLLBACK_KIND')
                temporary = _name(action['temp'])
                if (temporary.split('/')[:-1] != name.split('/')[:-1]
                        or not re.fullmatch(r'\.release-[0-9a-f]{32}', temporary.split('/')[-1])):
                    raise Stop('BAD_TEMP_NAME')
                file_record(action['file'], hashes['after_sha256' if key == 'apply' else 'before_sha256'], attributes)

    def _preflight(self):
        if self.state is None:
            raise Stop('NOT_PREPARED')
        self._check_roots()
        self._validate_records()
        result = {}
        for name, entry in self.state['entries'].items():
            self._backup(name)
            for key in ('apply', 'rollback'):
                action = entry[key]
                if action is not None and action.get('temp') is not None:
                    # Never delete/reuse a foreign replacement of our temp name.
                    current, _ = self._read(action['temp'])
                    if current is not None and current != action['file']:
                        raise Stop('FOREIGN_TEMP_REQUIRES_MANUAL_REVIEW')
            result[name] = self._classify(name)
        return result

    def _temporary(self, name, body):
        before = self.state['entries'][name]['before']
        mode, uid, gid = before['identity'][2:5] if before else [0o644, self.root_identity[3], self.root_identity[4]]
        with self._parent(name, create=True) as (parent, leaf):
            temporary = '.release-' + secrets.token_hex(16)
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body)
                stream.flush()
                os.fchown(stream.fileno(), uid, gid)
                os.fchmod(stream.fileno(), mode)
                os.fsync(stream.fileno())
                record = {'identity': _identity(os.fstat(stream.fileno())), 'sha256': digest(body)}
            os.fsync(parent)
        parts = name.split('/')[:-1] + [temporary]
        return {'temp': '/'.join(parts), 'file': record, 'done': False}

    def _replace_file(self, name, action):
        entry = self.state['entries'][name]
        expected = entry['before'] if action is entry['apply'] else entry['apply']['file']
        temporary, _ = self._read(action['temp'])
        if temporary != action['file']:
            raise Stop('OWN_TEMP_CHANGED_OR_MISSING')
        with self._parent(name) as (parent, leaf):
            if parent is None or name.split('/')[:-1] != action['temp'].split('/')[:-1]:
                raise Stop('TEMP_PARENT_MISMATCH')
            if self._read(name)[0] != expected:
                raise Stop('CONCURRENT_EDIT_REQUIRES_MANUAL_REVIEW')
            os.replace(action['temp'].split('/')[-1], leaf, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)

    def apply(self, payload, order=None):
        if self.state is None or self.state['phase'] in ('rolling_back', 'rolled_back'):
            raise Stop('TRANSACTION_NOT_APPLICABLE')
        if set(payload) != set(self.manifest):
            raise Stop('INCOMPLETE_PAYLOAD')
        names = list(self.manifest) if order is None else list(order)
        if len(names) != len(self.manifest) or set(names) != set(self.manifest):
            raise Stop('BAD_APPLY_ORDER')
        bodies = {}
        for name, source in payload.items():
            if isinstance(source, bytes):
                body = source
            elif isinstance(source, (str, os.PathLike)):
                body = Path(source).read_bytes()
            else:
                raise Stop('BAD_PAYLOAD_TYPE')
            if digest(body) != self.manifest[name]['after_sha256']:
                raise Stop('PACKAGE_CONTENT_HASH_MISMATCH')
            bodies[name] = body
        self._preflight()
        self.state['phase'] = 'applying'
        self._save()
        for name in names:
            entry = self.state['entries'][name]
            if self._classify(name) == 'installed':
                entry['apply']['done'] = True
                self._save()
                continue
            action = entry['apply']
            if action is None or self._read(action['temp'])[0] is None:
                action = self._temporary(name, bodies[name])
                entry['apply'] = action
                self._save()  # Durable identity+intent MUST precede rename.
            if self._classify(name) != 'untouched':
                raise Stop('CONCURRENT_EDIT_REQUIRES_MANUAL_REVIEW')
            self._replace_file(name, action)
            action['done'] = True
            self._save()
        self.verify_after()
        self.state['phase'] = 'applied'
        self._save()
        return self

    def verify_after(self):
        states = self._preflight()
        if any(value != 'installed' for value in states.values()):
            raise Stop('TRANSACTION_NOT_FULLY_APPLIED')
        return True

    def _cleanup_temp(self, action):
        if action is None or action.get('temp') is None:
            return
        current, _ = self._read(action['temp'])
        if current is None:
            return
        if current != action['file']:
            raise Stop('FOREIGN_TEMP_REQUIRES_MANUAL_REVIEW')
        with self._parent(action['temp']) as (parent, leaf):
            os.unlink(leaf, dir_fd=parent)
            os.fsync(parent)

    def rollback(self):
        self._preflight()  # Validate ALL paths/backups/temps before ANY target write.
        self.state['phase'] = 'rolling_back'
        self._save()
        for name in reversed(list(self.manifest)):
            entry = self.state['entries'][name]
            status = self._classify(name)
            if status == 'installed':
                action = entry['rollback']
                if action is None:
                    body = self._backup(name)
                    action = ({'kind': 'remove', 'temp': None, 'file': None, 'done': False}
                              if body is None else dict(self._temporary(name, body), kind='replace'))
                    entry['rollback'] = action
                    self._save()  # Durable rollback intent before rename/unlink.
                elif action['kind'] == 'replace' and self._read(action['temp'])[0] is None:
                    action = dict(self._temporary(name, self._backup(name)), kind='replace')
                    entry['rollback'] = action
                    self._save()
                if self._classify(name) != 'installed':
                    raise Stop('CONCURRENT_EDIT_REQUIRES_MANUAL_REVIEW')
                if action['kind'] == 'remove':
                    with self._parent(name) as (parent, leaf):
                        if self._read(name)[0] != entry['apply']['file']:
                            raise Stop('CONCURRENT_EDIT_REQUIRES_MANUAL_REVIEW')
                        os.unlink(leaf, dir_fd=parent)
                        os.fsync(parent)
                else:
                    self._replace_file(name, action)
                action['done'] = True
                self._save()
            elif status == 'restored' and not entry['rollback']['done']:
                entry['rollback']['done'] = True
                self._save()
            self._cleanup_temp(entry['apply'])
            self._cleanup_temp(entry['rollback'])
        states = self._preflight()
        if any(value not in ('untouched', 'restored') for value in states.values()):
            raise Stop('ROLLBACK_INCOMPLETE')
        self.state['phase'] = 'rolled_back'
        self._save()
        return self
