"""Gateway-owned admission receipts, separate from model-generated request JSON.

Call issue_admission only from a trusted gateway tool binding with the real
SessionSource and existing authorization method. Never expose signing to the
model. Keys must be provisioned outside model-readable files/env/tool arguments;
this module does not provision keys or assume that protection already exists.
No env/session fallback, default company, queue writes, or live notifications.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import secrets

from .contract import MAX_REQUEST_BYTES, _pairs, validate_v2_request
from .notification import TelegramRoute
from .queue import _decode, _filename
from .state import Scope, _json

DOMAIN=b'stroyka-jev-admission-v1\0'
TTL=3600
FIELDS={'version','request_id','request_sha256','company_id','principal_subject',
        'telegram_user_id','reply_chat_id','profile','issued_at','expires_at','nonce'}


@dataclass(frozen=True)
class OwnerBinding:
    scope: Scope
    telegram_user_id: str
    reply_chat_id: str
    profile: str | None

    def validate(self):
        if (type(self.scope) is not Scope or not isinstance(self.telegram_user_id,str)
                or not re.fullmatch('[1-9][0-9]{0,18}',self.telegram_user_id)
                or self.reply_chat_id!=self.telegram_user_id
                or self.profile is not None and (not isinstance(self.profile,str)
                    or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',self.profile))):
            raise ValueError('protected_private_chat_owner_binding_required')
        self.scope.key()


def _policies(bindings):
    if type(bindings) is not tuple or not bindings or len(bindings)>32:
        raise ValueError('protected_owner_bindings_required')
    for binding in bindings:
        if type(binding) is not OwnerBinding:raise ValueError('invalid_owner_binding')
        binding.validate()
    return bindings


def _key(key):
    if type(key) is not bytes or not 32<=len(key)<=64:
        raise ValueError('protected_admission_key_required')


def _now(clock):
    value=clock()
    if type(value) is not int or value<0:raise ValueError('integer_utc_epoch_required')
    return value


def authorized_owner(raw,source,*,authorize_source,bindings,request_validator=validate_v2_request):
    """Validate real gateway origin without requiring a signing key there."""
    policies=_policies(bindings)
    if type(raw) is not bytes or len(raw)>MAX_REQUEST_BYTES:raise ValueError('bounded_request_wire_required')
    if not callable(request_validator):raise ValueError('protected_request_validator_required')
    request=request_validator(_decode(raw))
    if isinstance(source,dict) or not callable(authorize_source) or authorize_source(source) is not True:
        raise ValueError('gateway_authorization_required')
    platform=getattr(source,'platform',None)
    platform=getattr(platform,'value',platform)
    if (platform!='telegram' or getattr(source,'chat_type',None)!='dm'
            or getattr(source,'thread_id',None) not in (None,'') or getattr(source,'is_bot',False)
            or getattr(source,'profile_route_rejected',False)):
        raise ValueError('authorized_private_telegram_source_required')
    user=getattr(source,'user_id',None);chat=getattr(source,'chat_id',None);profile=getattr(source,'profile',None)
    matches=[binding for binding in policies if (binding.telegram_user_id,binding.reply_chat_id,binding.profile)==(user,chat,profile)]
    if len(matches)!=1:raise ValueError('owner_company_binding_missing_or_ambiguous')
    return matches[0],request


def issue_admission(raw,source,*,authorize_source,bindings,signing_key,clock,request_validator=validate_v2_request):
    """Only request raw is model-controlled; every other parameter is server-bound.

    Private Telegram DM only in this first binding: group/thread routing requires
    separate authorization and delivery semantics. Existing gateway authorization
    remains mandatory even if the configured owner matches.
    """
    _key(signing_key)
    binding,request=authorized_owner(raw,source,authorize_source=authorize_source,bindings=bindings,
                                     request_validator=request_validator)
    user=getattr(source,'user_id',None);chat=getattr(source,'chat_id',None);profile=getattr(source,'profile',None)
    issued=_now(clock)
    body={'version':1,'request_id':request.request_id,'request_sha256':hashlib.sha256(raw).hexdigest(),
          'company_id':binding.scope.company_id,'principal_subject':binding.scope.principal_subject,
          'telegram_user_id':user,'reply_chat_id':chat,'profile':profile,
          'issued_at':issued,'expires_at':issued+TTL,'nonce':secrets.token_hex(16)}
    signature=hmac.new(signing_key,DOMAIN+_json(body),hashlib.sha256).hexdigest()
    return {'body':body,'signature':signature}


def make_authenticator(*,receipt_loader,bindings,verification_key,clock):
    """Callback for QueueConfig. receipt_loader reads only the detached receipt.

    Receipts may be readable/writable by the queue producer: a valid MAC is still
    required. MACs authenticate admission, not exactly-once execution; the durable
    request ledger supplies replay/conflict handling. No permissive fallback.
    """
    _key(verification_key);policies=_policies(bindings)
    if not callable(receipt_loader):raise ValueError('bounded_receipt_loader_required')
    def authenticate(filename,digest,scope):
        try:
            identifier=_filename(filename)
            if type(scope) is not Scope or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):return False
            raw=receipt_loader(filename)
            if type(raw) is not bytes or len(raw)>4096:return False
            def nonfinite(_):raise ValueError('nonfinite')
            envelope=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_constant=nonfinite)
            if type(envelope) is not dict or set(envelope)!={'body','signature'}:return False
            body=envelope['body'];signature=envelope['signature']
            if (type(body) is not dict or set(body)!=FIELDS or type(signature) is not str
                    or not re.fullmatch('[a-f0-9]{64}',signature)):return False
            expected=hmac.new(verification_key,DOMAIN+_json(body),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature,expected):return False
            if (type(body['version']) is not int or body['version']!=1 or type(body['company_id']) is not int
                    or body['company_id']!=scope.company_id or body['principal_subject']!=scope.principal_subject
                    or body['request_id']!=identifier or body['request_sha256']!=digest):return False
            if (type(body['issued_at']) is not int or type(body['expires_at']) is not int
                    or body['expires_at']-body['issued_at']!=TTL
                    or not body['issued_at']<=_now(clock)<body['expires_at']):return False
            if not isinstance(body['nonce'],str) or not re.fullmatch('[a-f0-9]{32}',body['nonce']):return False
            matches=[binding for binding in policies if binding.scope==scope and
                     (binding.telegram_user_id,binding.reply_chat_id,binding.profile)==
                     (body['telegram_user_id'],body['reply_chat_id'],body['profile'])]
            return len(matches)==1
        except (ValueError,TypeError,KeyError,UnicodeError,OSError,RecursionError):
            return False
    return authenticate


def owner_route(bindings,scope):
    """Recipient from protected policy, never from request/receipt fields."""
    matches=[binding for binding in _policies(bindings) if binding.scope==scope]
    if len(matches)!=1:raise ValueError('owner_route_missing_or_ambiguous')
    return TelegramRoute(scope,matches[0].reply_chat_id)
