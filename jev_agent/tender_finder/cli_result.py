"""Decode bounded existing JEV CLI output without losing nonzero partial JSON.

No process launching, shell, model calls, import-to-CRM, or source fetching here.
The runtime adapter must still verify CLI identity and operation capabilities.
"""
from dataclasses import dataclass
import json
from urllib.parse import parse_qs, urlsplit

from .contract import REGION

MAX_RESULT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CLIResult:
    status: str
    report: dict | None
    code: str | None
    returncode: int


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate_field')
        result[key] = value
    return result


def _nonfinite(_):
    raise ValueError('nonfinite_number')


def _decode_json(stdout, returncode):
    if type(returncode) is not int:
        raise ValueError('integer_returncode_required')
    if not isinstance(stdout, bytes):
        raise ValueError('stdout_bytes_required')
    if len(stdout) > MAX_RESULT_BYTES:
        return None, CLIResult('failed', None, 'cli_result_too_large', returncode)
    try:
        data = json.loads(stdout.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        return None, CLIResult('failed', None, 'invalid_cli_json', returncode)
    if type(data) is not dict or type(data.get('ok')) is not bool:
        return None, CLIResult('failed', None, 'invalid_cli_report', returncode)
    return data, None


def decode_commercial_result(stdout, returncode):
    """The commercial report shape; EIS has a separate, narrower decoder."""
    data, error = _decode_json(stdout, returncode)
    if error:
        return error
    # Recognize only the source report shape already present in JEV source.
    if type(data.get('sources')) is not list or any(type(item) is not dict for item in data['sources']):
        return CLIResult('failed', None, 'invalid_cli_sources', returncode)
    for field in ('confirmed', 'review'):
        if type(data.get(field)) is not list or any(type(item) is not dict for item in data[field]):
            return CLIResult('failed', None, 'invalid_cli_candidates', returncode)
    candidates = bool(data['confirmed'] or data['review'])
    source_success = any(item.get('ok') is True for item in data['sources'])
    all_sources_success = bool(data['sources']) and all(item.get('ok') is True for item in data['sources'])
    if returncode == 0 and data['ok'] and all_sources_success:
        return CLIResult('completed', data, None, returncode)
    if candidates or source_success:
        # Retain evidence, but never upgrade a nonzero/contradictory run to success.
        return CLIResult('partial', data, 'cli_nonzero_exit' if returncode else 'source_coverage_partial', returncode)
    return CLIResult('failed', data, 'cli_failed_without_verified_coverage', returncode)


def _eis_url(value, *, registry=False):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        return False
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.netloc != 'zakupki.gov.ru' or url.fragment
                or url.username is not None or url.password is not None):
            return False
        if registry:
            return url.path == '/epz/order/extendedsearch/results.html'
        numbers = parse_qs(url.query).get('regNumber', [])
        return (url.path.endswith('/common-info.html') and len(numbers) == 1
                and numbers[0].isascii() and numbers[0].isdigit() and len(numbers[0]) <= 30)
    except ValueError:
        return False


def decode_eis_result(stdout, returncode, *, query):
    """Decode the pinned browser registry format; links are NOT verified cards.

    Unknown amounts, deadlines and actual works address stay unknown. Filters
    verified in the registry are discovery evidence, not individual card facts.
    """
    data, error = _decode_json(stdout, returncode)
    if error:
        return error
    links = data.get('notice_links')
    if data['ok'] is False and links is None:
        return CLIResult('failed', data, 'cli_busy' if data.get('status') == 'busy' else 'eis_source_failed', returncode)
    if (type(links) is not list or len(links) > 10 or any(not _eis_url(link) for link in links)
            or type(data.get('notice_links_observed')) is not int
            or data['notice_links_observed'] < len(links)):
        return CLIResult('failed', None, 'invalid_eis_links', returncode)
    if not _eis_url(data.get('url'), registry=True) or data.get('query') != query:
        return CLIResult('failed', None, 'eis_query_not_verified', returncode)
    params = parse_qs(urlsplit(data['url']).query)
    scoped = (data.get('search_execution_verified') is True
              and data.get('delivery_region_filter_verified') is True
              and data.get('active_only_filter_verified') is True
              and data.get('law') == '44-ФЗ' and data.get('delivery_region') == REGION
              and params.get('searchString') == [query] and params.get('deliveryPlaceGAR') == [REGION]
              and params.get('fz44') == ['on'] and params.get('af') == ['on']
              and not any(key in params for key in ('fz223','ppRf615','ca','pc','pa')))
    if (returncode == 0 and data['ok'] and scoped
            and ((links and data.get('status') == 'keyword_search_observed')
                 or (not links and data['notice_links_observed'] == 0 and data.get('status') == 'keyword_search_empty'))):
        if data['notice_links_observed'] > len(links):
            return CLIResult('partial', data, 'eis_listing_truncated', returncode)
        return CLIResult('completed', data, None, returncode)
    if links:
        return CLIResult('partial', data, 'cli_nonzero_exit' if returncode else 'eis_scope_not_verified', returncode)
    return CLIResult('failed', data, 'eis_discovery_not_verified', returncode)
