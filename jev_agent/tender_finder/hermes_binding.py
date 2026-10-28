"""Explicit bootstrap adapter for the observed Hermes revision.

No installation, monkeypatch, registry mutation, key provisioning or sends. The
bootstrap must supply the actual running GatewayRunner and a protected signer.
An in-process signer alone does not isolate a key from arbitrary Python/terminal
tools running as that same identity; that deployment requirement remains open.
"""
import dataclasses
import hashlib
import os
from pathlib import Path
import stat
import sys
from types import MappingProxyType

from .audit_bridge import _read_relative_source
from .discovery import RuntimeMismatch
from .runtime import GatewayRuntime
from .contract import MAX_REQUEST_BYTES

HERMES_REVISION = 'bf0203a794a07aac3ff764972ab9087baa4e4f4e'
# Matched both the public revision and the owner's read-only server reports.
REVIEWED_MODULES = MappingProxyType({
    'gateway.run': '0c440eb8b361d28a2f02f3f30c2e7dd738b5ca3249caf267fb90ef087af83d35',
    'gateway.session': 'ed560fb1b416e1bc111ed9c1e20945238fc2632c60121852a428b4ec02b60d5c',
    'gateway.authz_mixin': '16178cdab78dd0fa32432bbf65bc1259e3b3da3eab1030c920b3b5a3cf33244d',
    'gateway.session_context': '3b74485dc394c44739f923142e8eaf9a1e87dbc98763c88c9d2ec21657a89b8b',
})


def verified_loaded_modules(root=Path('/opt/hermes'), *, expected_uid=0):
    """Check source bytes/permissions and origins of ALREADY loaded modules.

    Called by a trusted startup binding, never from a model tool. This checks the
    reviewed source contract, not memory attestation or the whole import graph.
    No import or execution of an unknown module is attempted on mismatch.
    """
    root = Path(root).absolute()
    try:
        if root.resolve(strict=True) != root:
            raise RuntimeMismatch('reviewed_hermes_root_required')
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            if info.st_uid != expected_uid or info.st_mode & 0o022:
                raise RuntimeMismatch('protected_hermes_source_required')
            modules = {}
            for name, digest in REVIEWED_MODULES.items():
                relative = name.replace('.', '/') + '.py'
                observed = _read_relative_source(descriptor, relative, 1536*1024, with_metadata=True)
                if observed is None:
                    raise RuntimeMismatch('reviewed_hermes_source_required')
                raw, permissions = observed
                entries = [permissions, *permissions['directory_permissions']]
                if (any(row['uid'] != expected_uid or int(row['mode'], 8) & 0o022 for row in entries)
                        or hashlib.sha256(raw).hexdigest() != digest):
                    raise RuntimeMismatch('reviewed_hermes_source_required')
                module = sys.modules.get(name)
                if module is None or getattr(module, '__file__', None) != str(root / relative):
                    raise RuntimeMismatch('reviewed_loaded_hermes_module_required')
                modules[name] = module
            return modules
        finally:
            os.close(descriptor)
    except OSError:
        raise RuntimeMismatch('reviewed_hermes_source_unavailable') from None


class HermesSessionBinding:
    """Callbacks for GatewayRuntime using actual SessionSource, not model IDs.

    Constructor arguments belong to the protected bootstrap. The source lookup
    uses a task-local key and direct ContextVars, never get_session_env (which has
    a legacy environment fallback). Every call rechecks current gateway access.
    """
    def __init__(self, runner, context, source_type):
        self._runner = runner
        self._context = context
        self._source_type = source_type

    def current_source(self):
        context = self._context
        key = context.bound_session_key()
        if not isinstance(key, str) or not key or context._CRON_SESSION.get() != '':
            raise ValueError('live_noncron_hermes_session_required')
        source = self._runner._get_cached_session_source(key)
        if type(source) is not self._source_type or not dataclasses.is_dataclass(source):
            raise ValueError('live_hermes_source_required')
        source = dataclasses.replace(source)
        platform = getattr(source.platform, 'value', source.platform)
        expected = (
            (context._SESSION_PLATFORM.get(), platform),
            (context._SESSION_CHAT_ID.get(), source.chat_id),
            (context._SESSION_USER_ID.get(), source.user_id),
            (context._SESSION_CHAT_TYPE.get(), source.chat_type),
            (context._SESSION_THREAD_ID.get(), source.thread_id or ''),
            (context._SESSION_PROFILE.get(), source.profile or ''),
        )
        if (any(type(actual) is not str or actual != wanted for actual, wanted in expected)
                or platform != 'telegram' or source.chat_type != 'dm'
                or source.thread_id not in (None, '') or source.is_bot is not False
                or source.profile_route_rejected is not False):
            raise ValueError('matching_live_private_telegram_source_required')
        return source

    def authorize_source(self, source):
        if type(source) is not self._source_type or source != self.current_source():
            return False
        # Includes live profile-aware policy. No upstream adapter delegation.
        return self._runner._is_user_authorized_for_source(
            source, allow_adapter_delegation=False) is True


def bind_gateway(runner, settings, secret):
    """Explicit startup entrypoint; settings/key are not model-supplied inputs."""
    modules = verified_loaded_modules()
    if type(runner) is not modules['gateway.run'].GatewayRunner:
        raise RuntimeMismatch('actual_reviewed_gateway_runner_required')
    source = HermesSessionBinding(runner, modules['gateway.session_context'],
                                 modules['gateway.session'].SessionSource)
    return GatewayRuntime(settings, secret, current_source=source.current_source,
                          authorize_source=source.authorize_source)


def submit_handler(runtime):
    """Return a narrow registry-compatible handler; registration stays explicit.

    The only model parameter is the bounded v2 request JSON. Registry kwargs such
    as session_id are deliberately ignored; they cannot supply an identity.
    """
    if type(runtime) is not GatewayRuntime:
        raise ValueError('protected_gateway_runtime_required')

    def handle(args, **_context_kwargs):
        if (type(args) is not dict or set(args) != {'request_json'}
                or type(args['request_json']) is not str
                or len(args['request_json']) > MAX_REQUEST_BYTES):
            return {'queued':False, 'reason':'bounded_request_json_required'}
        try:
            raw = args['request_json'].encode('utf-8')
            if len(raw) > MAX_REQUEST_BYTES:
                return {'queued':False, 'reason':'bounded_request_json_required'}
            return runtime.submit(raw)
        except Exception:
            # No gateway/configuration exception (possibly secret-bearing) is
            # returned to the model. A failure never reports search completion.
            return {'queued':False, 'reason':'jev_admission_failed'}
    return handle
