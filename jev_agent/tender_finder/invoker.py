"""Bounded fixed CLI invoker. Importing this module never launches a process.

Only explicitly called by an authorized worker binding, never a generic model
tool. There is no shell, sudo, CRM import, Docker operation or arbitrary URL API.
"""
import errno
import json
import os
import selectors
import signal
import subprocess
import tempfile
import time

from jev_agent.server_runtime.scripts.jev_commercial_search import normalize_company_profile

from .cli_plan import DiscoveryCall, EXECUTABLE
from .cli_result import MAX_RESULT_BYTES, _pairs, _nonfinite
from .discovery import verify_installed_runtime
from .state import Scope, StorageError


def _stop(process):
    # SIGINT lets the reviewed Python CLI run its Docker cleanup finally block.
    # If cleanup is stuck, bound our wait; actual container removal still needs
    # live acceptance and must never be inferred from this process exit alone.
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def _run_bounded(argv, stdin, timeout):
    """Internal transport; only invoke_cli supplies production argv.

    stdin is a temporary descriptor, not a pipe that can deadlock on a child
    ignoring its input. stdout is drained with a hard memory/byte limit; stderr
    is discarded so credentials/error text cannot become report fields.
    """
    with tempfile.TemporaryFile() as input_file:
        if stdin is not None:
            input_file.write(stdin)
        input_file.seek(0)
        process = subprocess.Popen(argv, stdin=input_file, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, shell=False, start_new_session=True, cwd='/',
            env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8'})
        complete = False
        try:
            deadline = time.monotonic() + timeout
            chunks, total = [], 0
            with selectors.DefaultSelector() as selector:
                os.set_blocking(process.stdout.fileno(),False)
                selector.register(process.stdout,selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(argv,timeout)
                    for key, _ in selector.select(remaining):
                        chunk = os.read(key.fd,65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        total += len(chunk)
                        if total > MAX_RESULT_BYTES:
                            raise OSError(errno.EFBIG,'cli_output_limit')
                        chunks.append(chunk)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(argv,timeout)
                returncode = process.wait(timeout=remaining)
            complete = True
            return b''.join(chunks),returncode
        finally:
            if not complete:
                _stop(process)
            process.stdout.close()


def invoke_cli(call, timeout_seconds, *, scope):
    """scope must be bound by protected server configuration/authentication."""
    if type(scope) is not Scope:
        raise StorageError('protected_scope_required')
    scope.key()
    if type(call) is not DiscoveryCall or type(timeout_seconds) is not int:
        raise ValueError('fixed_discovery_call_required')
    if call.source == 'commercial':
        if (call.argv != (EXECUTABLE,'commercial-search','--profile-stdin')
                or timeout_seconds != 330 or type(call.stdin) is not bytes or len(call.stdin)>32768):
            raise ValueError('invalid_commercial_call')
        try:
            profile = json.loads(call.stdin.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=_nonfinite)
            if type(profile) is not dict or set(profile) != {'companyId','region','searchTerms','sourceProviders'}:
                raise ValueError('invalid_profile')
            normalized = normalize_company_profile(profile)
            if normalized != profile or profile['companyId'] != scope.company_id or not profile['searchTerms']:
                raise ValueError('invalid_profile')
        except (UnicodeError,ValueError,TypeError,RecursionError):
            raise ValueError('protected_company_profile_required') from None
    elif call.source == 'eis':
        if (not isinstance(call.query,str) or not 1 <= len(call.query) <= 80
                or any(ord(char)<32 for char in call.query) or call.stdin is not None
                or call.argv != (EXECUTABLE,'eis-search','--query',call.query,'--stavropol-open')
                or timeout_seconds != 100):
            raise ValueError('invalid_eis_call')
    else:
        raise ValueError('unsupported_discovery_call')
    verify_installed_runtime()
    return _run_bounded(call.argv,call.stdin,timeout_seconds)
