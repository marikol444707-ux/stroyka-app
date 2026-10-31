"""Read explicit protected bridge settings; no defaults, secrets or server writes.

The configuration's owner/parent permissions are checked before parsing. Paths
for host worker and container gateway are separate because mount views differ.
This loader is not installation, authorization of a deployment, or readiness.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat

from .cli_result import _pairs, _nonfinite
from .ingress import OwnerBinding
from .pipeline import PipelineConfig
from .queue import QueueConfig
from .state import Scope, StorageError

FIELDS={'schema_version','company_id','principal_subject','telegram_user_id','reply_chat_id',
        'hermes_profile','writer_uid','result_gid','worker','gateway'}


def _path(value):
    if (not isinstance(value,str) or not value.startswith('/') or value=='/' or len(value)>1024
            or '..' in Path(value).parts or any(ord(char)<33 for char in value)):
        raise ValueError('explicit_absolute_bridge_path_required')
    return Path(value)


@dataclass(frozen=True,repr=False)
class BridgeSettings:
    owner: OwnerBinding
    queue: QueueConfig
    worker_admissions: Path
    gateway_inbox: Path
    gateway_admissions: Path
    gateway_uid: int | None = None

    def __repr__(self):return 'BridgeSettings(<protected bindings>)'


def parse_settings(value):
    if type(value) is not dict or type(value.get('schema_version')) is not int:
        raise ValueError('explicit_bridge_settings_required')
    version=value['schema_version']
    required=FIELDS if version==1 else FIELDS|{'gateway_uid'} if version==2 else set()
    if not required or set(value)!=required:raise ValueError('explicit_bridge_settings_required')
    scope=Scope(value['company_id'],value['principal_subject']);scope.key()
    owner=OwnerBinding(scope,value['telegram_user_id'],value['reply_chat_id'],value['hermes_profile'])
    owner.validate()
    if (type(value['writer_uid']) is not int
            or (not 0<value['writer_uid']<2**31 if version==1 else value['writer_uid']!=0)
            or type(value['result_gid']) is not int or not 0<value['result_gid']<2**31):
        raise ValueError('unprivileged_gateway_identity_required')
    gateway_uid=value['writer_uid'] if version==1 else value['gateway_uid']
    if type(gateway_uid) is not int or not 0<gateway_uid<2**31:
        raise ValueError('unprivileged_gateway_identity_required')
    worker=value['worker'];gateway=value['gateway']
    if (type(worker) is not dict or set(worker)!={'inbox','private','results','admissions'}
            or type(gateway) is not dict or set(gateway)!={'inbox','admissions'}):
        raise ValueError('explicit_host_and_container_paths_required')
    worker={name:_path(path) for name,path in worker.items()}
    gateway={name:_path(path) for name,path in gateway.items()}
    for paths in (tuple(worker.values()),tuple(gateway.values())):
        if len(set(paths))!=len(paths) or any(left in right.parents for left in paths for right in paths if left!=right):
            raise ValueError('bridge_paths_must_be_separate')
    pipeline=PipelineConfig(scope,worker['private'],worker['results'],value['result_gid'])
    return BridgeSettings(owner,QueueConfig(pipeline,worker['inbox'],value['writer_uid']),
                          worker['admissions'],gateway['inbox'],gateway['admissions'],gateway_uid)


def _load_settings_json(path,*,trusted_root=Path('/etc/stroyka-jev'),expected_uid=0):
    """trusted_root/expected_uid are bootstrap parameters, never model inputs.

    pyproject/app env/home-channel values are never configuration fallbacks.
    The default policy is root-owned; test fixtures may specify a different UID.
    """
    path=Path(path).absolute();root=Path(trusted_root).absolute()
    if path==root or not path.is_relative_to(root) or path.resolve(strict=True)!=path or root.resolve(strict=True)!=root:
        raise StorageError('untrusted_settings_path')
    for directory in (path.parent,*path.parent.parents):
        info=directory.stat()
        if info.st_uid!=expected_uid or info.st_mode & 0o022:
            raise StorageError('untrusted_settings_parent')
        if directory==root:break
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid!=expected_uid or info.st_nlink!=1
                or stat.S_IMODE(info.st_mode) not in (0o600,0o640) or info.st_size>8192):
            raise StorageError('unsafe_settings_file')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(8193)
        if len(raw)>8192:raise StorageError('settings_size_limit')
    finally:os.close(fd)
    try:value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_nonfinite)
    except (ValueError,UnicodeError,RecursionError):raise StorageError('invalid_settings_json') from None
    return value


def load_settings(path,*,trusted_root=Path('/etc/stroyka-jev'),expected_uid=0):
    return parse_settings(_load_settings_json(path,trusted_root=trusted_root,expected_uid=expected_uid))
