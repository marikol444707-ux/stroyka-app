"""Completion consumer for the observed Hermes send_message_tool contract.

No timers, models, tokens, home-channel fallback, generic send API or automatic
resends. Must run in a protected Hermes binding and only after owner approval to
send. An unknown outcome is not retried: Hermes/Telegram has no verified external
idempotency key. This does not promise exactly-once delivery or human readership.
"""
from dataclasses import dataclass
import hashlib
import html
import importlib
import importlib.util
import json
from pathlib import Path
import re

from .cli_result import _pairs, _nonfinite
from .discovery import RuntimeMismatch
from .presentation import render_report
from .state import RequestLedger, Scope, StorageError, _json, _read

HERMES_SEND_SHA256='65058bf22cf614c4e954131d81e5655b8016dfc8c87e74b9ed6582c733f02227'
HERMES_SEND_SOURCE_REVISION='bf0203a794a07aac3ff764972ab9087baa4e4f4e'


@dataclass(frozen=True)
class TelegramRoute:
    scope: Scope
    chat_id: str

    def target(self):
        if (type(self.scope) is not Scope or not isinstance(self.chat_id,str)
                or not re.fullmatch(r'-?[1-9][0-9]{0,18}',self.chat_id)):
            raise ValueError('protected_numeric_telegram_route_required')
        self.scope.key()
        return 'telegram:'+self.chat_id


def build_send_args(report, scope, route):
    if type(route) is not TelegramRoute or route.scope!=scope:
        raise ValueError('notification_scope_mismatch')
    target=route.target()
    for limit in (1800,1000):
        if report.get('schema_version')==3:
            from .commercial.preview import render_preview
            text=render_preview(report,scope,max_chars=limit)
        else:text=render_report(report,scope,max_chars=limit)
        # Hermes auto-extracts MEDIA:<path> and [[as_document]] directives before
        # dispatch. Encode colon/brackets *after* escaping untrusted page text,
        # so it cannot attach a local file. Telegram decodes the HTML entities.
        escaped=html.escape(text,quote=True).replace(':','&#58;').replace('[','&#91;').replace(']','&#93;')
        message='<b>JEV</b>\n'+escaped
        if len(message.encode('utf-16-le'))//2<=3800:
            return {'action':'send','target':target,'message':message}
    raise ValueError('notification_text_size_limit')


def load_hermes_sender():
    """Called inside the reviewed Hermes installation; never from a model tool.

    Import preserves Hermes' own authorization, configuration and sender policy.
    No credentials are copied into JEV. Dependencies and live delivery still
    require acceptance on the actual installation.
    """
    try:
        spec=importlib.util.find_spec('tools.send_message_tool')
        if spec is None or not spec.origin:raise RuntimeMismatch('hermes_sender_unavailable')
        source=Path(spec.origin)
        if source!=Path('/opt/hermes/tools/send_message_tool.py') or source.is_symlink():
            raise RuntimeMismatch('reviewed_hermes_sender_required')
        if source.stat().st_size>256*1024 or hashlib.sha256(source.read_bytes()).hexdigest()!=HERMES_SEND_SHA256:
            raise RuntimeMismatch('reviewed_hermes_sender_required')
        module=importlib.import_module('tools.send_message_tool')
        return module.send_message_tool
    except (ImportError,OSError,AttributeError):
        raise RuntimeMismatch('hermes_sender_unavailable') from None


def _acknowledgement(raw, route):
    if not isinstance(raw,str) or len(raw.encode('utf-8'))>32768:return None
    try:value=json.loads(raw,object_pairs_hook=_pairs,parse_constant=_nonfinite)
    except (ValueError,RecursionError):return None
    if (type(value) is not dict or value.get('success') is not True or value.get('partial_success')
            or value.get('error') or value.get('warnings') or value.get('platform')!='telegram'
            or str(value.get('chat_id'))!=route.chat_id):return None
    identifier=value.get('message_id')
    return str(identifier) if type(identifier) in (str,int) and re.fullmatch('[1-9][0-9]{0,29}',str(identifier)) else None


def deliver_completion(private_directory, scope, event_id, request_id, fingerprint, *, route, send):
    """Validate committed result/event, reserve attempt, call Hermes, save ack.

    send must be the protected Hermes binding; tests inject a synthetic sender.
    A crash/exception after reservation yields unknown and never another call.
    """
    if (type(scope) is not Scope or not isinstance(event_id,str)
            or not re.fullmatch('[a-f0-9]{64}',event_id) or not callable(send)):
        raise ValueError('protected_completion_binding_required')
    expected_id=hashlib.sha256(_json({'scope':scope.key(),'request_id':request_id,'fingerprint':fingerprint})).hexdigest()
    if event_id!=expected_id:raise StorageError('completion_identity_conflict')
    with RequestLedger(private_directory,scope) as jobs:
        with jobs.claim(request_id,fingerprint,existing_only=True) as job:
            result=job.result
            event_raw=_read(jobs.fd,'completion-'+event_id+'.json',private=True)
            expected={'format':1,'event_id':event_id,'kind':'jev_result_published','scope':scope.key(),
                      'request_id':request_id,'result_sha256':hashlib.sha256(_json(result)).hexdigest(),
                      'delivery_status':'pending','notification_sent':False}
            if event_raw!=_json(expected):raise StorageError('committed_completion_required')
            report=result
            if result.get('status')=='failed' and result.get('reason') in (
                    'execution_interrupted','execution_failed','execution_not_completed','runtime_changed'):
                # A minimal interrupted/error receipt is owned by this ledger;
                # project only public error fields, not arbitrary unscoped data.
                report={'schema_version':2,'company_id':scope.company_id,'protected_scope':scope.key(),
                        'request_id':request_id,'status':'failed','reason':result['reason']}
            args=build_send_args(report,scope,route)
            attempt_fingerprint=hashlib.sha256(_json(args)).hexdigest()
            with RequestLedger(private_directory,scope,namespace='delivery') as deliveries:
                with deliveries.claim(event_id,attempt_fingerprint) as attempt:
                    if attempt.action=='execute':
                        message_id=None
                        try:message_id=_acknowledgement(send(args),route)
                        except Exception:pass  # Never persist credential-bearing response/error text.
                        attempt.complete({'request_id':event_id,'job_request_id':request_id,
                            'delivery_status':'acknowledged' if message_id else 'unknown',
                            'notification_sent':True if message_id else None,'message_id':message_id,
                            'human_read_verified':False})
                    record=attempt.result
                    if record.get('delivery_status') not in ('acknowledged','unknown'):
                        return {'request_id':event_id,'job_request_id':request_id,'delivery_status':'unknown',
                                'notification_sent':None,'message_id':None,'human_read_verified':False}
                    return record
