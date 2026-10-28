"""Consume an admission key from a bootstrap-owned anonymous pipe, then close it.

No generation, disk/env storage, argv key, subprocess launch or default secret.
The caller must initialize this before enabling model tools. This only protects
descriptor lifetime: it does not prove model isolation of the entire gateway or
replace review of actual startup, plugins, tools, dumps and process permissions.
"""
from dataclasses import dataclass, field
import os
import select
import stat
import time


@dataclass(frozen=True)
class AdmissionSecret:
    material: bytes=field(repr=False)

    def __repr__(self):return 'AdmissionSecret(<redacted>)'


def read_bootstrap_key(fd,*,expected_uid=0,timeout_seconds=3):
    """Takes ownership of fd >=3 and closes it on success or failure.

    Only an anonymous pipe from the privileged bootstrap is accepted. A normal
    key file, stdin, inherited env, and weak/oversized keys are rejected.
    """
    if type(fd) is not int or fd<3:raise ValueError('dedicated_bootstrap_descriptor_required')
    try:
        os.set_inheritable(fd,False)
        info=os.fstat(fd)
        if (info.st_uid!=expected_uid or not stat.S_ISFIFO(info.st_mode)
                or stat.S_IMODE(info.st_mode)!=0o600
                or not os.readlink(f'/proc/self/fd/{fd}').startswith('pipe:[')):
            raise ValueError('trusted_anonymous_key_pipe_required')
        if type(timeout_seconds) is not int or not 1<=timeout_seconds<=3:
            raise ValueError('bounded_bootstrap_timeout_required')
        os.set_blocking(fd,False)
        chunks=[];length=0;deadline=time.monotonic()+timeout_seconds
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([fd],[],[],remaining)[0]:
                raise ValueError('bootstrap_key_timeout')
            chunk=os.read(fd,65-length)
            if not chunk:break
            chunks.append(chunk);length+=len(chunk)
            if length>64:raise ValueError('bootstrap_key_size_limit')
        key=b''.join(chunks)
        if not 32<=len(key)<=64:raise ValueError('strong_admission_key_required')
        return AdmissionSecret(key)
    finally:os.close(fd)
