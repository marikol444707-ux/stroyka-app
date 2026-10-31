"""Reviewed public JSON discovery; no accounts, inferred facts or submissions.

Federation POST is exclusively the fixed public search operation. Each captured
request body is retained beside its response. Primary facts still require fresh
cards/documents. Redirects, non-JSON and malformed pages are never empty success.
"""
import json
import re
import time
from dataclasses import dataclass
from urllib.request import Request, build_opener
from urllib.error import HTTPError

from jev_agent.server_runtime.scripts.jev_commercial_search import (
    fedtorgi_payload, fedtorgi_page, rtender_page_data, rtender_row)
from .access import Decision, NoRedirect, USER_AGENT
from .b2b import Observation
from ..cli_result import _pairs, _nonfinite

FEDERATION_API = 'https://lk.fedtorgi.ru/api/v1/procedures/search?page=1&limit=10'
MAX_BODY = 256 * 1024
MAX_CAPTURE = 480 * 1024


@dataclass(frozen=True)
class Reply:
    status: int
    content_type: str
    body: bytes


def public_search(url, body):
    """Protected caller supplies generated endpoints, never arbitrary model URLs."""
    request = Request(url, data=body, headers={
        'User-Agent': USER_AGENT, 'Accept': 'application/json',
        **({'Content-Type': 'application/json'} if body is not None else {})})
    try:
        response = build_opener(NoRedirect).open(request, timeout=12)
    except HTTPError as error:
        response = error
    with response:
        return Reply(response.code, response.headers.get('Content-Type', ''), response.read(MAX_BODY + 1))


def observe(spec, profile, url, *, clock, access_check, fetch=public_search, monotonic=time.monotonic):
    if spec.approve(url) != 'listing' or spec.source.id not in ('federation', 'rtender'):
        raise ValueError('reviewed_native_api_listing_required')
    federation = spec.source.id == 'federation'
    if federation and url != FEDERATION_API:
        raise ValueError('exact_federation_search_required')
    profile.validate()
    terms = tuple(dict.fromkeys((*profile.queries, *profile.regions))) if federation else (None,)
    if not 1 <= len(terms) <= 20:
        raise ValueError('bounded_native_search_terms_required')
    links, captures, limitations = [], [], []
    attempts = 0
    deadline = monotonic() + 150

    def result(status, text=''):
        return Observation(url, status, clock(), text, {'url': url, 'notice_urls': links,
            'request_count': attempts, 'limitations': limitations})

    for term in terms:
        if monotonic() >= deadline:
            if not captures:
                return result('unavailable')
            limitations.append('read_budget_exhausted')
            break
        decision = access_check(url)
        if type(decision) is not Decision:
            raise ValueError('typed_native_access_decision_required')
        if not decision.allowed:
            return result(decision.status)
        payload = fedtorgi_payload(term) if federation else None
        body = json.dumps(payload, ensure_ascii=False).encode() if federation else None
        try:
            attempts += 1
            reply = fetch(url, body)
        except Exception:
            return result('unavailable')
        if type(reply) is not Reply or type(reply.body) is not bytes or len(reply.body) > MAX_BODY:
            return result('unavailable')
        if reply.status == 401:
            return result('login_required')
        # Live R-TENDER returns plain JSON with this legacy MIME type. It is
        # decoded strictly as JSON below, never evaluated as JavaScript/JSONP.
        allowed_types = ('application/json',) if federation else ('application/json','application/javascript')
        if (reply.status != 200 or type(reply.content_type) is not str
                or reply.content_type.split(';')[0].strip().lower() not in allowed_types):
            return result('unavailable')
        try:
            raw = reply.body.decode('utf-8-sig')
            data = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
            if federation:
                page = fedtorgi_page(data, 1)
                if (any(type(page.get(key)) is not int for key in ('page','limit','total_count'))
                        or len(page['data']) != min(page['total_count'],10)):
                    raise ValueError('complete_federation_first_page_required')
                found = []
                for row in page['data']:
                    if (type(row) is not dict or row.get('platform_type') != 'SECTION_COMMERCIAL_PROCEDURES'
                            or row.get('status') not in ('STATUS_ACTIVE', 'STATUS_ACCEPTING_APPLICATIONS')
                            or not isinstance(row.get('id'), str)
                            or not re.fullmatch(r'[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}', row['id'])):
                        raise ValueError('commercial_active_federation_row_required')
                    found.append('https://etpp.ru/tenders/' + row['id'])
            else:
                page = rtender_page_data(url, data, spec.terms[spec.listings.index(url)])
                if any(type(page.get(key)) is not int for key in ('count','totalCount')):
                    raise ValueError('integer_rtender_counts_required')
                found = [rtender_row(row)['url'] for row in page['list']]
        except (ValueError, TypeError, KeyError, RuntimeError, RecursionError):
            return result('unavailable')
        capture = {'url': url, 'request': payload, 'response_text': raw}
        if len(json.dumps([*captures, capture], ensure_ascii=False).encode()) > MAX_CAPTURE:
            if not captures:
                return result('unavailable')
            limitations.append('read_budget_exhausted')
            break
        captures.append(capture)
        links.extend(link for link in found if link not in links)
        if len(links) >= 40:
            links = links[:40]
            limitations.append('read_budget_exhausted')
            break
    return result('ok', json.dumps(captures, ensure_ascii=False))
