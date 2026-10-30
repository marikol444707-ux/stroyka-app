"""Strict model-facing v3 request: filters only, never ownership or endpoints."""
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

from .model import Profile, QUERIES, REGIONS
from .sources import source_registry


@dataclass(frozen=True)
class CommercialRequest:
    request_id: str
    regions: tuple[str, ...]
    source_ids: tuple[str, ...]
    minimum_rub: Decimal
    queries: tuple[str, ...]
    exclude_keywords: tuple[str, ...]

    def canonical_payload(self):
        return {'version':3,'mode':'direct_commercial','request_id':self.request_id,
                'regions':list(self.regions),'source_ids':list(self.source_ids),
                'minimum_rub':str(self.minimum_rub),'queries':list(self.queries),
                'exclude_keywords':list(self.exclude_keywords)}

    def fingerprint(self,company_id):
        if type(company_id) is not int or company_id<=0:raise ValueError('protected_company_required')
        raw=json.dumps({'company_id':company_id,'request':self.canonical_payload()},
                       sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        return hashlib.sha256(raw).hexdigest()

    def profile(self,base):
        if type(base) is not Profile:raise ValueError('protected_executor_profile_required')
        result=replace(base,regions=self.regions,minimum_rub=self.minimum_rub,
                       queries=self.queries,exclude_keywords=self.exclude_keywords)
        result.validate()
        return result


def _strings(payload,key,default,allowed=None,*,empty=False,limit=32):
    values=payload.get(key,list(default))
    if (type(values) is not list or len(values)>limit or not empty and not values
            or any(type(value) is not str or not 2<=len(value)<=80
                   or any(ord(char)<32 for char in value) for value in values)):
        raise ValueError('bounded_commercial_filter_required')
    if len(set(values))!=len(values) or allowed is not None and set(values)-set(allowed):
        raise ValueError('unsupported_commercial_filter')
    return tuple(sorted(values))


def validate_request(payload,*,sources=None):
    allowed={'version','mode','request_id','regions','source_ids','minimum_rub','queries','exclude_keywords'}
    if (type(payload) is not dict or set(payload)-allowed
            or type(payload.get('version')) is not int or payload['version']!=3
            or payload.get('mode')!='direct_commercial'
            or type(payload.get('request_id')) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',payload['request_id'])):
        raise ValueError('explicit_commercial_v3_request_required')
    sources=source_registry() if sources is None else sources
    minimum=payload.get('minimum_rub','3000000')
    if type(minimum) not in (str,int,Decimal) or len(str(minimum))>40:
        raise ValueError('exact_commercial_price_required')
    try: minimum=Decimal(minimum)
    except (InvalidOperation,ValueError):raise ValueError('exact_commercial_price_required') from None
    if not minimum.is_finite() or not 0<=minimum<=Decimal('1e12'):
        raise ValueError('bounded_commercial_price_required')
    if minimum.as_tuple().exponent < -2:raise ValueError('commercial_price_kopecks_required')
    # Bound exponent BEFORE formatting; no enormous strings or Decimal-context
    # rounding of authoritative amounts (normalize() can round at precision 28).
    text=format(minimum,'f')
    if '.' in text:text=text.rstrip('0').rstrip('.')
    minimum=Decimal(text) if minimum else Decimal(0)
    return CommercialRequest(payload['request_id'],
        _strings(payload,'regions',REGIONS,REGIONS),
        _strings(payload,'source_ids',sorted(sources),sources),minimum,
        _strings(payload,'queries',QUERIES,QUERIES),
        _strings(payload,'exclude_keywords',(),empty=True,limit=20))
