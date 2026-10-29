"""Explicit bounded host pass: authenticated queue -> result -> completion.

No schedule or daemon is installed. A service/path activation must invoke this
only for the new protected namespace. Cached completion recovery never launches
a search; unknown external delivery is never retried automatically.
"""
import hashlib
import json
import os
import re

from .bootstrap_key import AdmissionSecret
from .docker_delivery import deliver_via_hermes
from .queue import _inbox
from .runtime import WorkerRuntime
from .settings import BridgeSettings
from .state import RequestLedger, StorageError, _identifier, _json, _read


def pending_completions(settings,limit=32):
    if type(settings) is not BridgeSettings or type(limit) is not int or not 1<=limit<=32:
        raise ValueError('bounded_protected_completion_scan_required')
    scope=settings.owner.scope;handles=[]
    with RequestLedger(settings.queue.pipeline.private_directory,scope) as ledger:
        with os.scandir(ledger.fd) as entries:
            for entry in entries:
                match=re.fullmatch(r'completion-([a-f0-9]{64})\.json',entry.name)
                if not match:continue
                event_id=match[1]
                delivery=_read(ledger.fd,'delivery-'+scope.key()+'-'+event_id+'.json',private=True)
                if delivery is not None:
                    value=json.loads(delivery)
                    if (type(value) is not dict or value.get('scope')!=scope.key()
                            or value.get('request_id')!=event_id):raise StorageError('invalid_delivery_identity')
                    # Includes failed/unknown crash receipts: never issue a second
                    # external send just because no Telegram ACK was recorded.
                    if value.get('state')=='completed':continue
                event_raw=_read(ledger.fd,entry.name,private=True)
                if event_raw is None:continue
                event=json.loads(event_raw)
                if (type(event) is not dict or event.get('scope')!=scope.key()
                        or event.get('event_id')!=event_id or event.get('kind')!='jev_result_published'):
                    raise StorageError('invalid_completion_identity')
                identifier=_identifier(event.get('request_id'))
                record_raw=_read(ledger.fd,'ledger-'+scope.key()+'-'+identifier+'.json',private=True)
                if record_raw is None:raise StorageError('completion_receipt_missing')
                record=json.loads(record_raw);fingerprint=record.get('fingerprint') if type(record) is dict else None
                if (type(fingerprint) is not str or not re.fullmatch('[a-f0-9]{64}',fingerprint)
                        or record.get('state')!='completed'):
                    raise StorageError('completion_receipt_not_committed')
                expected=hashlib.sha256(_json({'scope':scope.key(),'request_id':identifier,'fingerprint':fingerprint})).hexdigest()
                if expected!=event_id:raise StorageError('completion_fingerprint_conflict')
                # deliver_completion revalidates the exact event/result/receipt
                # under the real ledger locks before reserving an external send.
                handles.append((event_id,identifier,fingerprint))
                if len(handles)>=limit:break
    return handles


def run_host_pass(settings,secret,*,gateway_gid,invoke=None,verify_runtime=None,deliver=None,
                  should_stop=lambda:False):
    """Trusted host entrypoint. Injection callbacks exist for offline acceptance.

    Production bootstrap must load settings v2 and the host-only key as root;
    caller/config/user identity never comes from a model JSON parameter.
    """
    if type(settings) is not BridgeSettings or type(secret) is not AdmissionSecret:
        raise ValueError('protected_host_worker_required')
    worker=WorkerRuntime(settings,secret,invoke=invoke,verify_runtime=verify_runtime)
    summary={'processed':0,'authorization_pending':0,'acknowledged':0,'unknown':0,'errors':0,
             'legacy_untouched':0,'human_read_verified':False}
    def handled(action):
        try:
            outcome=action()
            if outcome.get('status')=='processed':summary['processed']+=1
            elif outcome.get('status')=='authorization_pending':summary['authorization_pending']+=1
            elif outcome.get('status')=='legacy_v1':summary['legacy_untouched']+=1
            else:summary['errors']+=1
        except Exception:summary['errors']+=1
    for handle in worker.pending():
        if should_stop():return summary
        handled(lambda handle=handle:worker.resume(handle))
    if should_stop():return summary
    inbox=_inbox(settings.queue)
    try:
        names=[]
        with os.scandir(inbox) as entries:
            for entry in entries:
                if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.json',entry.name):
                    names.append(entry.name)
                    if len(names)>=32:break
    finally:os.close(inbox)
    for name in names:
        if should_stop():return summary
        handled(lambda name=name:worker.consume(name))
    if should_stop():return summary
    for event,identifier,fingerprint in pending_completions(settings):
        if should_stop():return summary
        try:
            result=(deliver if deliver is not None else deliver_via_hermes)(
                settings,event,identifier,fingerprint,gateway_gid=gateway_gid)
            status=result.get('delivery_status')
            if status in ('acknowledged','unknown'):summary[status]+=1
            else:summary['errors']+=1
        except Exception:summary['errors']+=1
    return summary
