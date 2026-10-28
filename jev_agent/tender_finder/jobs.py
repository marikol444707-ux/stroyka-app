"""Durable job core for integration into the existing bridge, not a new worker.

Authorization/scope and callbacks must be bound by protected server code. This
module does not consume queue files, adopt legacy .seen files, publish results,
notify Hermes, or install services. A returned receipt is not delivery evidence.
"""
from dataclasses import dataclass
import hashlib
import json

from .compat import LegacyRequest, normalize_request
from .discovery import discover, RuntimeMismatch, verify_installed_runtime
from .state import MAX_RESULT_BYTES, RequestLedger, Scope, StorageError


@dataclass(frozen=True)
class JobOutcome:
    disposition: str
    result: dict
    delivery_verified: bool = False


def _fingerprint(request, scope):
    if not isinstance(request, LegacyRequest):
        return request.fingerprint(scope.company_id)
    raw = json.dumps({'scope':scope.key(),'v1':request.legacy_payload()},ensure_ascii=False,
                     sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _result(value, request_id, scope):
    if type(value) is not dict or value.get('request_id') != request_id:
        raise ValueError('invalid_executor_result')
    if 'company_id' in value and (type(value['company_id']) is not int or value['company_id'] != scope.company_id):
        raise ValueError('executor_company_mismatch')
    raw = json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()
    if len(raw) > MAX_RESULT_BYTES:
        raise ValueError('executor_result_size_limit')
    return json.loads(raw)


def process_request(payload, scope, private_directory, *, legacy_validator=None,
                    legacy_executor=None, invoke=None, verify_runtime=verify_installed_runtime):
    """Validate -> durable claim -> v1 callback or v2 discovery -> durable result.

    Same scoped ID/fingerprint replays a saved result. Changed contents conflict;
    an interrupted reservation becomes an explicit failure, never another search.
    Only the installed legacy validator/executor may define the v1 semantics.
    """
    if type(scope) is not Scope:
        raise StorageError('protected_scope_required')
    scope.key()
    request = normalize_request(payload, legacy_validator=legacy_validator)
    legacy = isinstance(request, LegacyRequest)
    if (legacy and not callable(legacy_executor)) or (not legacy and
            (not callable(invoke) or not callable(verify_runtime))):
        raise ValueError('protected_executor_binding_required')
    with RequestLedger(private_directory,scope) as ledger:
        with ledger.claim(request.request_id,_fingerprint(request,scope)) as reservation:
            disposition = reservation.action
            if disposition == 'execute':
                try:
                    value = (legacy_executor(request.legacy_payload()) if legacy else
                             discover(request,scope,invoke=invoke,verify_runtime=verify_runtime))
                    result = _result(value,request.request_id,scope)
                except Exception as exc:
                    # No stdout/stderr/exception text in a failure receipt. Disk
                    # commits remain outside this catch: storage faults must surface.
                    result = {'ok':False,'status':'failed','request_id':request.request_id,
                              'reason':'runtime_changed' if isinstance(exc,RuntimeMismatch) else 'execution_failed'}
                reservation.complete(result)
            return JobOutcome(disposition,reservation.result)
